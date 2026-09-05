from __future__ import annotations

import argparse
import gzip
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_ROOT = "https://data.cityofnewyork.us"
DATASET_ID = "jqfp-uff7"
USER_AGENT = "TowerSignal/1.0 (+https://github.com/JeremyHennessy/TowerSignal)"
SELECT = "objectid,tbbl,address,material,record_ty,city_owned"
REQUIRED_FIELDS = {"objectid", "tbbl", "address", "material", "record_ty", "city_owned"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _request_json(url: str, retries: int = 4, timeout: int = 120) -> Any:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(2**attempt)
    raise RuntimeError(f"Failed to retrieve lead-service-line source after {retries} attempts: {url}: {last_error}")


def _iso_from_epoch(value: Any) -> str | None:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError):
        return None


def source_metadata() -> dict[str, Any]:
    payload = _request_json(f"{API_ROOT}/api/views/{DATASET_ID}")
    if not isinstance(payload, dict):
        raise RuntimeError("Lead-service-line metadata was not an object")
    fields = {
        str(column.get("fieldName"))
        for column in payload.get("columns", [])
        if isinstance(column, dict) and column.get("fieldName")
    }
    missing = sorted(REQUIRED_FIELDS - fields)
    if missing:
        raise RuntimeError(f"Lead-service-line source missing required fields: {', '.join(missing)}")
    return {
        "name": str(payload.get("name") or DATASET_ID),
        "source_last_updated_at": _iso_from_epoch(payload.get("rowsUpdatedAt") or payload.get("dataUpdatedAt")),
    }


def source_count() -> int:
    query = urlencode({"$select": "count(*) as count"})
    payload = _request_json(f"{API_ROOT}/resource/{DATASET_ID}.json?{query}")
    if not isinstance(payload, list) or not payload or "count" not in payload[0]:
        raise RuntimeError("Lead-service-line count query returned an unexpected payload")
    return int(payload[0]["count"])


def normalize_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "record_id": str(row.get("objectid") or "").strip() or None,
        "bbl": str(row.get("tbbl") or "").strip() or None,
        "address": str(row.get("address") or "").strip() or None,
        "material": str(row.get("material") or "").strip() or None,
        "record_type": str(row.get("record_ty") or "").strip() or None,
        "city_owned": str(row.get("city_owned") or "").strip() or None,
        "source_dataset_id": DATASET_ID,
    }


def build(output: Path, summary_path: Path, *, page_size: int) -> dict[str, Any]:
    metadata = source_metadata()
    expected = source_count()
    output.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    material_counts: Counter[str] = Counter()
    record_type_counts: Counter[str] = Counter()
    city_owned_counts: Counter[str] = Counter()
    bbls: set[str] = set()
    written = 0
    offset = 0

    with gzip.open(output, "wt", encoding="utf-8", compresslevel=6) as handle:
        while offset < expected:
            params = {
                "$limit": page_size,
                "$offset": offset,
                "$order": "objectid",
                "$select": SELECT,
            }
            payload = _request_json(f"{API_ROOT}/resource/{DATASET_ID}.json?{urlencode(params)}")
            if not isinstance(payload, list):
                raise RuntimeError(f"Lead-service-line source returned a non-list page at offset {offset}")
            for raw in payload:
                if not isinstance(raw, dict):
                    raise RuntimeError(f"Lead-service-line source returned a non-object row at offset {offset}")
                row = normalize_row(raw)
                handle.write(json.dumps(row, separators=(",", ":")) + "\n")
                written += 1
                if row["bbl"]:
                    bbls.add(str(row["bbl"]))
                material_counts[str(row["material"] or "MISSING")] += 1
                record_type_counts[str(row["record_type"] or "MISSING")] += 1
                city_owned_counts[str(row["city_owned"] or "MISSING")] += 1
            if len(payload) < page_size:
                break
            offset += page_size

    if written != expected:
        output.unlink(missing_ok=True)
        raise RuntimeError(
            f"Lead-service-line pagination incomplete: expected {expected:,} rows, wrote {written:,}. Refusing partial cache."
        )

    summary = {
        "schema_version": "1.0",
        "generated_at": utc_now(),
        "source": {
            "dataset_id": DATASET_ID,
            "name": metadata["name"],
            "url": f"https://data.cityofnewyork.us/d/{DATASET_ID}",
            "source_last_updated_at": metadata["source_last_updated_at"],
            "source_record_count": expected,
            "fetched_record_count": written,
            "pagination_complete": True,
            "selected_fields": SELECT.split(","),
            "geometry_excluded": True,
        },
        "summary": {
            "record_count": written,
            "unique_bbl_count": len(bbls),
            "material_counts": dict(sorted(material_counts.items())),
            "record_type_counts": dict(sorted(record_type_counts.items())),
            "city_owned_counts": dict(sorted(city_owned_counts.items())),
        },
        "evidence_semantics": {
            "property_link": "BBL is source-reported by NYC DEP.",
            "material": "Last known material category recorded for the property; not a TowerSignal inference.",
        },
        "data_file": output.name,
    }
    summary_path.write_text(json.dumps(summary, separators=(",", ":")), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build exact-count NYC DEP lead-service-line cache")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--page-size", type=int, default=50000)
    args = parser.parse_args()
    summary = build(args.output, args.summary, page_size=args.page_size)
    print(json.dumps(summary["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
