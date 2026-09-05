from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

EXACT_BBL_CONFIDENCES = {"CONFIRMED_SOURCE_BBL", "EXACT_SINGLE_BBL"}
EXACT_BIN_CONFIDENCES = {"CONFIRMED_SOURCE_BIN", "EXACT_SINGLE_BIN"}

COLLECTION_KEYS = (
    "water_311_requests",
    "hpd_open_water_violations",
    "dob_water_job_filings",
    "dob_water_permits",
    "ll84_water_benchmarks",
)

DATE_KEYS = {
    "water_311_requests": ("created_date", "closed_date"),
    "hpd_open_water_violations": ("inspection_date", "current_status_date"),
    "dob_water_job_filings": ("filing_date", "approved_date", "signoff_date"),
    "dob_water_permits": ("issued_date", "approved_date", "expired_date"),
    "ll84_water_benchmarks": ("year_ending", "last_modified_date_water", "report_year"),
}


def _normalize_bbl(value: Any) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits if len(digits) == 10 and digits[0] in "12345" else None


def _normalize_bin(value: Any) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits if len(digits) == 7 else None


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


def _records(payload: Mapping[str, Any], key: str) -> Iterable[dict[str, Any]]:
    rows = payload.get(key)
    if rows is None:
        return []
    if not isinstance(rows, list):
        raise RuntimeError(f"NYC water-signal collection is malformed: {key}")
    return [row for row in rows if isinstance(row, dict)]


def _compact(row: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key != "raw"}


def _empty_collections() -> dict[str, list[dict[str, Any]]]:
    return {key: [] for key in COLLECTION_KEYS}


def _row_date(row: Mapping[str, Any], key: str) -> str:
    for field in DATE_KEYS[key]:
        value = row.get(field)
        if value not in (None, ""):
            return str(value)
    return ""


def _sort_rows(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (_row_date(row, key), str(row.get("source_record_id") or row.get("request_id") or row.get("violation_id") or row.get("activity_id") or row.get("benchmark_id") or "")), reverse=True)


def _add(
    contexts: dict[str, dict[str, list[dict[str, Any]]]],
    systems: Iterable[Mapping[str, Any]],
    key: str,
    row: Mapping[str, Any],
) -> int:
    added = 0
    compact = _compact(row)
    for system in systems:
        system_id = str(system.get("system_id") or "")
        if not system_id:
            continue
        contexts.setdefault(system_id, _empty_collections())[key].append(compact)
        added += 1
    return added


def _systems_for_source_property(
    row: Mapping[str, Any],
    bbl_to_systems: Mapping[str, list[Mapping[str, Any]]],
    bin_to_systems: Mapping[str, list[Mapping[str, Any]]],
) -> list[Mapping[str, Any]]:
    confidence = str(row.get("property_link_confidence") or "")
    bbl = _normalize_bbl(row.get("bbl"))
    bin_value = _normalize_bin(row.get("bin"))
    if confidence in EXACT_BBL_CONFIDENCES and bbl:
        return bbl_to_systems.get(bbl, [])
    if confidence in EXACT_BIN_CONFIDENCES and bin_value:
        return bin_to_systems.get(bin_value, [])
    return []


def _systems_for_ll84(
    row: Mapping[str, Any],
    bbl_to_systems: Mapping[str, list[Mapping[str, Any]]],
    bin_to_systems: Mapping[str, list[Mapping[str, Any]]],
) -> list[Mapping[str, Any]]:
    confidence = str(row.get("property_link_confidence") or "")
    bbls = row.get("bbls")
    bins = row.get("bins")
    if confidence == "EXACT_SINGLE_BBL" and isinstance(bbls, list) and len(bbls) == 1:
        return bbl_to_systems.get(_normalize_bbl(bbls[0]) or "", [])
    if confidence == "EXACT_SINGLE_BIN" and isinstance(bins, list) and len(bins) == 1:
        return bin_to_systems.get(_normalize_bin(bins[0]) or "", [])
    return []


def _context(collections: Mapping[str, list[dict[str, Any]]], payload: Mapping[str, Any]) -> dict[str, Any] | None:
    record_count = sum(len(collections[key]) for key in COLLECTION_KEYS)
    if record_count == 0:
        return None

    category_counts: Counter[str] = Counter()
    applicant_businesses: set[str] = set()
    latest_dates: list[str] = []
    for key in COLLECTION_KEYS:
        for row in collections[key]:
            if row.get("category"):
                category_counts[str(row["category"])] += 1
            if key in {"dob_water_job_filings", "dob_water_permits"} and row.get("applicant_business_key"):
                applicant_businesses.add(str(row["applicant_business_key"]))
            date = _row_date(row, key)
            if date:
                latest_dates.append(date)

    source_health = payload.get("source_health") if isinstance(payload.get("source_health"), list) else []
    dataset_ids = sorted({
        str(source.get("dataset_id"))
        for source in source_health
        if isinstance(source, dict) and source.get("dataset_id")
    })
    source_record_count = sum(
        int(source.get("source_record_count") or 0)
        for source in source_health
        if isinstance(source, dict)
    )
    sorted_collections = {key: _sort_rows(collections[key], key) for key in COLLECTION_KEYS}
    return {
        "summary": {
            "record_count": record_count,
            "water_311_building_signal_count": len(collections["water_311_requests"]),
            "hpd_open_water_violation_count": len(collections["hpd_open_water_violations"]),
            "dob_water_job_filing_count": len(collections["dob_water_job_filings"]),
            "dob_water_permit_count": len(collections["dob_water_permits"]),
            "ll84_water_benchmark_count": len(collections["ll84_water_benchmarks"]),
            "dob_applicant_business_count": len(applicant_businesses),
            "category_counts": dict(sorted(category_counts.items())),
            "latest_observation_date": max(latest_dates) if latest_dates else None,
        },
        **sorted_collections,
        "evidence_boundaries": {
            "property_link": "Exact source-reported BBL or BIN only; address text and LL84 multi-identifier rows are not used for matching.",
            "roles": "DOB applicant and permittee names are regulatory roles, not proof of service assignment or contract award.",
            "ll84": "Benchmarking water-use rows are self-reported building context and may not represent current operating conditions.",
        },
        "source": {
            "dataset_ids": dataset_ids,
            "source_record_count": source_record_count,
            "generated_at": str(payload.get("generated_at") or ""),
            "query_boundaries": payload.get("query_boundaries") if isinstance(payload.get("query_boundaries"), dict) else {},
        },
    }


def attach(output_dir: Path, cache_path: Path) -> dict[str, Any]:
    systems_payload = _load_systems(output_dir)
    signal_payload = json.loads(cache_path.read_text(encoding="utf-8"))
    if signal_payload.get("schema_version") != "1.0" or signal_payload.get("domain") != "NYC_BUILDING_WATER_SIGNALS":
        raise RuntimeError("Unexpected NYC building-water signal cache")

    systems = systems_payload["systems"]
    bbl_to_systems: dict[str, list[Mapping[str, Any]]] = {}
    bin_to_systems: dict[str, list[Mapping[str, Any]]] = {}
    for system in systems:
        bbl = _normalize_bbl(system.get("bbl"))
        bin_value = _normalize_bin(system.get("bin"))
        if bbl:
            bbl_to_systems.setdefault(bbl, []).append(system)
        if bin_value:
            bin_to_systems.setdefault(bin_value, []).append(system)

    contexts: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for row in _records(signal_payload, "water_311_requests"):
        if row.get("is_building_water_signal") is True:
            _add(contexts, _systems_for_source_property(row, bbl_to_systems, bin_to_systems), "water_311_requests", row)
    for key in ("hpd_open_water_violations", "dob_water_job_filings", "dob_water_permits"):
        for row in _records(signal_payload, key):
            _add(contexts, _systems_for_source_property(row, bbl_to_systems, bin_to_systems), key, row)
    for row in _records(signal_payload, "ll84_water_benchmarks"):
        _add(contexts, _systems_for_ll84(row, bbl_to_systems, bin_to_systems), "ll84_water_benchmarks", row)

    systems_attached = 0
    attached_record_total = 0
    for system in systems:
        system_id = str(system.get("system_id") or "")
        context = _context(contexts.get(system_id, _empty_collections()), signal_payload)
        record_count = int(context["summary"]["record_count"]) if context else 0
        system["nyc_building_water_signal_count"] = record_count
        system["nyc_building_water_signal_types"] = sorted(context["summary"]["category_counts"]) if context else []
        if context:
            systems_attached += 1
            attached_record_total += record_count
        detail_path = _safe_detail_path(output_dir, system_id)
        if not detail_path.exists():
            raise RuntimeError(f"Missing account detail while attaching NYC building-water signals: {system_id}")
        detail = json.loads(detail_path.read_text(encoding="utf-8"))
        detail["nyc_building_water_signals"] = context
        detail_path.write_text(json.dumps(detail, separators=(",", ":")), encoding="utf-8")

    metadata = systems_payload["metadata"]
    metadata.update({
        "nyc_water_signal_cache_available": True,
        "nyc_water_signal_match_basis": "EXACT_SOURCE_BBL_OR_BIN",
        "nyc_water_signal_source_record_count": sum(
            int(source.get("source_record_count") or 0)
            for source in signal_payload.get("source_health", [])
            if isinstance(source, dict)
        ),
        "nyc_water_signal_systems_attached": systems_attached,
        "nyc_water_signal_attached_record_count": attached_record_total,
    })
    systems_payload["summary"]["systems_with_nyc_building_water_signals"] = systems_attached
    (output_dir / "systems.json").write_text(json.dumps(systems_payload, separators=(",", ":")), encoding="utf-8")
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    report = {
        "match_basis": "EXACT_SOURCE_BBL_OR_BIN",
        "requested_bbl_count": len(bbl_to_systems),
        "requested_bin_count": len(bin_to_systems),
        "systems_attached": systems_attached,
        "attached_record_count": attached_record_total,
    }
    (output_dir / "nyc-building-water-signal-coverage.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Attach exact-BBL/BIN NYC building-water signals to TowerSignal account details")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data")
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(attach(args.output, args.cache), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
