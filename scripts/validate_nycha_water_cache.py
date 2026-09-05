from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _as_int(value: object, *, default: int = 0) -> int:
    return default if value is None else int(value)


def validate(path: Path, *, max_age_days: int, require_production_volume: bool) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0" or payload.get("domain") != "NYCHA_WATER_CONTRACT_RELEASE_LINES":
        raise RuntimeError("Unexpected NYCHA water cache schema/domain")
    generated = datetime.fromisoformat(str(payload.get("generated_at") or "").replace("Z", "+00:00"))
    age_days = (datetime.now(timezone.utc) - generated).total_seconds() / 86400
    if age_days < -0.05 or age_days > max_age_days:
        raise RuntimeError(f"NYCHA water cache age is {age_days:.2f} days")

    summary = payload.get("summary")
    health = payload.get("source_health")
    records = payload.get("records")
    if not isinstance(summary, dict) or not isinstance(health, list) or not isinstance(records, list):
        raise RuntimeError("NYCHA water cache missing summary/source health/records")
    expected_partition_count = _as_int(summary.get("fiscal_year_count")) * _as_int(summary.get("purpose_query_term_count"))
    if len(health) != expected_partition_count:
        raise RuntimeError("NYCHA fiscal-year/purpose-query/source-health count mismatch")
    seen_partitions: set[tuple[int, str]] = set()
    for source in health:
        if source.get("status") != "HEALTHY" or source.get("pagination_complete") is not True or source.get("schema_valid") is not True:
            raise RuntimeError(f"Unhealthy NYCHA source partition: {source.get('fiscal_year')}")
        if _as_int(source.get("source_record_count"), default=-1) != _as_int(source.get("fetched_record_count"), default=-2):
            raise RuntimeError(f"NYCHA source-count mismatch: {source.get('fiscal_year')}")
        partition_key = (_as_int(source.get("fiscal_year")), str(source.get("purpose_query") or ""))
        if partition_key in seen_partitions:
            raise RuntimeError(f"Duplicate NYCHA source partition: {partition_key}")
        seen_partitions.add(partition_key)

    if len(records) != _as_int(summary.get("relevant_release_line_count"), default=-1):
        raise RuntimeError("NYCHA relevant record count mismatch")
    if sum(_as_int(source.get("source_record_count")) for source in health) != _as_int(summary.get("source_record_count"), default=-1):
        raise RuntimeError("NYCHA total source count mismatch")

    ids: set[str] = set()
    contracts: set[str] = set()
    vendors: set[str] = set()
    locations: set[str] = set()
    for row in records:
        record_id = str(row.get("source_record_id") or "")
        if not record_id or record_id in ids:
            raise RuntimeError(f"Missing/duplicate NYCHA release-line identity: {record_id!r}")
        ids.add(record_id)
        if row.get("service_category") == "UNRELATED":
            raise RuntimeError(f"Published unrelated NYCHA row: {record_id}")
        if row.get("company_id") is not None or row.get("company_match_confidence") not in {"UNRESOLVED", None}:
            raise RuntimeError(f"NYCHA vendor was unexpectedly resolved: {record_id}")
        if row.get("location") and row.get("location_link_confidence") != "NYCHA_SOURCE_CONTEXT":
            raise RuntimeError(f"NYCHA location promoted beyond source context: {record_id}")
        if row.get("contract_id"):
            contracts.add(str(row["contract_id"]))
        if row.get("vendor_key"):
            vendors.add(str(row["vendor_key"]))
        if row.get("location"):
            locations.add(str(row["location"]))

    expected_sets = {
        "relevant_contract_count": len(contracts),
        "relevant_vendor_count": len(vendors),
        "relevant_location_count": len(locations),
    }
    for key, value in expected_sets.items():
        if _as_int(summary.get(key), default=-1) != value:
            raise RuntimeError(f"NYCHA summary mismatch for {key}")

    if require_production_volume:
        if _as_int(summary.get("fiscal_year_count")) != 5:
            raise RuntimeError("NYCHA production cache must cover five fiscal years")
        if _as_int(summary.get("purpose_query_term_count")) < 8:
            raise RuntimeError("NYCHA production cache must cover the bounded purpose query set")
        floors = {
            "source_record_count": 5000,
            "unique_scanned_release_line_count": 2500,
            "relevant_release_line_count": 10,
            "relevant_contract_count": 5,
            "relevant_vendor_count": 3,
        }
        for key, floor in floors.items():
            value = _as_int(summary.get(key))
            if value < floor:
                raise RuntimeError(f"Implausibly small NYCHA {key}: {value:,} < {floor:,}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate TowerSignal NYCHA water-contract cache")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--max-age-days", type=int, default=1)
    parser.add_argument("--require-production-volume", action="store_true")
    args = parser.parse_args()
    payload = validate(args.cache, max_age_days=args.max_age_days, require_production_volume=args.require_production_volume)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
