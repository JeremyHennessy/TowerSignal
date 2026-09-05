from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _timestamp(value: Any) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise RuntimeError("Missing generated_at timestamp")
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _int_field(record: dict[str, Any], key: str, *, context: str) -> int:
    if key not in record or record[key] is None:
        raise RuntimeError(f"Missing integer field {key} for {context}")
    try:
        return int(record[key])
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Invalid integer field {key} for {context}: {record[key]!r}") from exc


def validate(path: Path, *, max_age_days: int, require_production_volume: bool) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0":
        raise RuntimeError(f"Unexpected NYC water signal schema version: {payload.get('schema_version')!r}")
    age = (datetime.now(timezone.utc) - _timestamp(payload.get("generated_at"))).total_seconds() / 86400
    if age < -0.05 or age > max_age_days:
        raise RuntimeError(f"NYC water signal cache generated_at age is {age:.2f} days")

    summary = payload.get("summary")
    source_health = payload.get("source_health")
    if not isinstance(summary, dict) or not isinstance(source_health, list) or len(source_health) < 5:
        raise RuntimeError("NYC water signal cache must contain summary and source-health records")
    for source in source_health:
        if not isinstance(source, dict):
            raise RuntimeError("Source-health record is not an object")
        if source.get("status") != "HEALTHY" or source.get("pagination_complete") is not True or source.get("schema_valid") is not True:
            raise RuntimeError(f"Unhealthy source {source.get('dataset_id')}")
        context = str(source.get("dataset_id") or "unknown source")
        if _int_field(source, "source_record_count", context=context) != _int_field(source, "fetched_record_count", context=context):
            raise RuntimeError(f"Source count mismatch for {source.get('dataset_id')}")
    hpd_sources = [
        source for source in source_health if source.get("dataset_id") == "wvxf-dwi5"
    ]
    hpd_partition_count = int(summary.get("hpd_source_partition_count") or 0)
    hpd_fetch_strategy = str(summary.get("hpd_source_fetch_strategy") or "KEYWORD_PARTITIONS")
    if len(hpd_sources) != hpd_partition_count:
        raise RuntimeError("HPD source partition count mismatch")
    hpd_partition_records = sum(
        int(source.get("source_record_count") or 0) for source in hpd_sources
    )
    if int(summary.get("hpd_source_partition_record_count") or -1) != hpd_partition_records:
        raise RuntimeError("HPD source partition record count mismatch")
    hpd_unique = int(summary.get("hpd_open_water_violation_count") or 0)
    hpd_duplicate_raw = summary.get("hpd_duplicate_partition_violation_count")
    hpd_duplicates = -1 if hpd_duplicate_raw is None else int(hpd_duplicate_raw)
    if hpd_fetch_strategy == "OPEN_VIOLATIONS_LOCAL_TERM_FILTER":
        raise RuntimeError("HPD local-filter strategy is too broad for production cache verification")
    if hpd_fetch_strategy in {"KEYWORD_PARTITIONS", "UPPERCASE_KEYWORD_PARTITIONS"}:
        if hpd_partition_count < 8:
            raise RuntimeError("HPD source partition count mismatch")
        if hpd_duplicates < 0 or hpd_partition_records - hpd_duplicates != hpd_unique:
            raise RuntimeError("HPD partition de-duplication counts do not reconcile")
    else:
        raise RuntimeError(f"Unknown HPD source fetch strategy: {hpd_fetch_strategy}")

    collections = {
        "water_311_request_count": "water_311_requests",
        "hpd_open_water_violation_count": "hpd_open_water_violations",
        "dob_water_job_filing_count": "dob_water_job_filings",
        "dob_water_permit_count": "dob_water_permits",
        "dob_observed_business_count": "dob_observed_businesses",
        "ll84_water_benchmark_count": "ll84_water_benchmarks",
    }
    for summary_key, collection_key in collections.items():
        collection = payload.get(collection_key)
        if not isinstance(collection, list):
            raise RuntimeError(f"Missing collection {collection_key}")
        if len(collection) != int(summary.get(summary_key) or 0):
            raise RuntimeError(f"Summary mismatch for {summary_key}")

    building_311 = sum(1 for row in payload["water_311_requests"] if row.get("is_building_water_signal") is True)
    if building_311 != int(summary.get("water_311_building_signal_count") or 0):
        raise RuntimeError("311 building-water summary mismatch")
    for row in payload["water_311_requests"]:
        category = str(row.get("category") or "")
        confidence = row.get("property_link_confidence")
        if not category.startswith("BUILDING_") and confidence in {"CONFIRMED_SOURCE_BBL", "ADDRESS_CONTEXT"}:
            raise RuntimeError(f"Non-building 311 context was promoted to property evidence: {category}")

    for row in payload["hpd_open_water_violations"]:
        if str(row.get("violation_status") or "").lower() != "open":
            raise RuntimeError("HPD cache contains a non-open violation")

    for collection_key in ("dob_water_job_filings", "dob_water_permits"):
        for row in payload[collection_key]:
            if row.get("applicant_business_raw"):
                if row.get("relationship_evidence") != "RECORDED_DOB_ROLE":
                    raise RuntimeError("DOB business role missing recorded-role evidence")
                if row.get("service_assignment_confidence") != "NOT_PROOF_OF_SERVICE_CONTRACT":
                    raise RuntimeError("DOB applicant was misrepresented as service assignment")

    exact_ll84 = 0
    multi_ll84 = 0
    potable_ll84 = 0
    for row in payload["ll84_water_benchmarks"]:
        bbls = row.get("bbls")
        bins = row.get("bins")
        if not isinstance(bbls, list) or not isinstance(bins, list):
            raise RuntimeError("LL84 row missing identifier lists")
        confidence = row.get("property_link_confidence")
        if confidence == "EXACT_SINGLE_BBL":
            if len(bbls) != 1 or row.get("property_key") != f"NYC-BBL-{bbls[0]}":
                raise RuntimeError("Invalid LL84 single-BBL linkage")
            exact_ll84 += 1
        elif confidence == "EXACT_SINGLE_BIN":
            if bbls or len(bins) != 1 or row.get("property_key") != f"NYC-BIN-{bins[0]}":
                raise RuntimeError("Invalid LL84 single-BIN linkage")
            exact_ll84 += 1
        elif confidence == "MULTI_IDENTIFIER_CONTEXT":
            if row.get("property_key") is not None:
                raise RuntimeError("Multi-identifier LL84 row was force-linked")
            multi_ll84 += 1
        if row.get("municipal_potable_total_kgal") is not None:
            potable_ll84 += 1
    if exact_ll84 != int(summary.get("ll84_exact_single_property_count") or 0):
        raise RuntimeError("LL84 exact-link summary mismatch")
    if multi_ll84 != int(summary.get("ll84_multi_identifier_count") or 0):
        raise RuntimeError("LL84 multi-identifier summary mismatch")
    if potable_ll84 != int(summary.get("ll84_rows_with_municipal_potable_total") or 0):
        raise RuntimeError("LL84 potable-water summary mismatch")

    if require_production_volume:
        minimums = {
            "water_311_request_count": 5000,
            "hpd_open_water_violation_count": 5000,
            "dob_water_job_filing_count": 1000,
            "dob_water_permit_count": 1000,
            "ll84_water_benchmark_count": 80000,
        }
        for key, minimum in minimums.items():
            value = int(summary.get(key) or 0)
            if value < minimum:
                raise RuntimeError(f"Implausibly small production {key}: {value:,} < {minimum:,}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate TowerSignal NYC building-water signal cache")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--max-age-days", type=int, default=1)
    parser.add_argument("--require-production-volume", action="store_true")
    args = parser.parse_args()
    payload = validate(args.cache, max_age_days=args.max_age_days, require_production_volume=args.require_production_volume)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
