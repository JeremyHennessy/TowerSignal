from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

DATASET_ID = "jqfp-uff7"
SOURCE_URL = "https://data.cityofnewyork.us/d/jqfp-uff7"


def _normalize_bbl(value: Any) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits if len(digits) == 10 and digits[0] in "12345" else None


def _safe_detail_path(base: Path, system_id: str) -> Path:
    safe = "".join(ch for ch in system_id if ch.isalnum() or ch in ("-", "_"))
    return base / "details" / (safe[:2] or "xx").lower() / f"{safe}.json"


def _load_systems(output_dir: Path) -> dict[str, Any]:
    path = output_dir / "systems.json"
    if not path.exists():
        raise RuntimeError(f"Base NYC systems payload is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload.get("systems"), list) or not isinstance(payload.get("metadata"), dict):
        raise RuntimeError("Base NYC systems payload is malformed")
    return payload


def _iter_rows(path: Path) -> Iterable[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise RuntimeError(f"Service-line cache row {line_number} is not an object")
            yield row


def _counts(rows: list[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts = Counter(str(row.get(key) or "MISSING") for row in rows)
    return dict(sorted(counts.items()))


def _context(rows: list[dict[str, Any]], summary: Mapping[str, Any]) -> dict[str, Any]:
    source = summary.get("source") if isinstance(summary.get("source"), dict) else {}
    return {
        "summary": {
            "record_count": len(rows),
            "material_counts": _counts(rows, "material"),
            "record_type_counts": _counts(rows, "record_type"),
            "city_owned_counts": _counts(rows, "city_owned"),
        },
        "records": sorted(
            rows,
            key=lambda row: (
                str(row.get("record_type") or ""),
                str(row.get("material") or ""),
                str(row.get("record_id") or ""),
            ),
        ),
        "evidence_boundaries": {
            "property_link": "Exact source-reported NYC DEP BBL only; address text is not used for matching.",
            "material": "Last-known service-line material category as published by NYC DEP; not a TowerSignal inference.",
        },
        "source": {
            "dataset_id": DATASET_ID,
            "name": str(source.get("name") or "NYC DEP Lead Service Line Location Coordinates"),
            "url": str(source.get("url") or SOURCE_URL),
            "source_record_count": int(source.get("source_record_count") or 0),
            "source_last_updated_at": source.get("source_last_updated_at"),
            "generated_at": str(summary.get("generated_at") or ""),
        },
    }


def attach(output_dir: Path, data_path: Path, summary_path: Path) -> dict[str, Any]:
    payload = _load_systems(output_dir)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("schema_version") != "1.0":
        raise RuntimeError("Unexpected service-line summary schema version")

    systems = payload["systems"]
    bbl_to_systems: dict[str, list[dict[str, Any]]] = {}
    for row in systems:
        bbl = _normalize_bbl(row.get("bbl"))
        if bbl:
            bbl_to_systems.setdefault(bbl, []).append(row)

    matched_by_bbl: dict[str, list[dict[str, Any]]] = {bbl: [] for bbl in bbl_to_systems}
    for row in _iter_rows(data_path):
        bbl = _normalize_bbl(row.get("bbl"))
        if bbl in matched_by_bbl:
            matched_by_bbl[bbl].append(row)

    systems_with_records = 0
    matched_record_total = 0
    matched_bbl_count = 0
    for bbl, records in matched_by_bbl.items():
        if records:
            matched_bbl_count += 1
            matched_record_total += len(records)
        context = _context(records, summary) if records else None
        for system in bbl_to_systems[bbl]:
            system["nyc_lead_service_line_record_count"] = len(records)
            system["nyc_lead_service_line_materials"] = sorted(
                {str(row.get("material")) for row in records if row.get("material")}
            )
            if records:
                systems_with_records += 1
            detail_path = _safe_detail_path(output_dir, str(system.get("system_id") or ""))
            if not detail_path.exists():
                raise RuntimeError(f"Missing account detail while attaching service-line records: {system.get('system_id')}")
            detail = json.loads(detail_path.read_text(encoding="utf-8"))
            detail["nyc_lead_service_lines"] = context
            detail_path.write_text(json.dumps(detail, separators=(",", ":")), encoding="utf-8")

    metadata = payload["metadata"]
    metadata.update({
        "nyc_lead_service_line_cache_available": True,
        "nyc_lead_service_line_dataset_id": DATASET_ID,
        "nyc_lead_service_line_source_record_count": int((summary.get("source") or {}).get("source_record_count") or 0),
        "nyc_lead_service_line_requested_bbl_count": len(bbl_to_systems),
        "nyc_lead_service_line_matched_bbl_count": matched_bbl_count,
        "nyc_lead_service_line_matched_record_count": matched_record_total,
        "nyc_lead_service_line_match_basis": "BBL_EXACT",
    })
    payload["summary"]["systems_with_nyc_lead_service_line_records"] = systems_with_records
    (output_dir / "systems.json").write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    report = {
        "dataset_id": DATASET_ID,
        "match_basis": "BBL_EXACT",
        "requested_bbl_count": len(bbl_to_systems),
        "matched_bbl_count": matched_bbl_count,
        "matched_record_count": matched_record_total,
        "systems_attached": systems_with_records,
    }
    (output_dir / "nyc-service-line-coverage.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Attach exact-BBL NYC DEP service-line records to TowerSignal account details")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(attach(args.output, args.data, args.summary), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
