from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ALLOWED_SOURCES = {"NYC_CHECKBOOK_CITYWIDE", "NYC_CHECKBOOK_EDC"}
MAX_CACHE_BYTES = 60 * 1024 * 1024


def _parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("cache generated_at is missing")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def validate_cache(
    path: Path,
    *,
    max_age_days: float,
    require_production_volume: bool,
) -> dict[str, Any]:
    size = path.stat().st_size
    if size <= 0:
        raise ValueError("Checkbook cache is empty")
    if size > MAX_CACHE_BYTES:
        raise ValueError(f"Checkbook cache exceeds hard size ceiling: {size} > {MAX_CACHE_BYTES}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0":
        raise ValueError("Unsupported Checkbook cache schema_version")
    generated = _parse_timestamp(payload.get("generated_at"))
    age_days = (datetime.now(timezone.utc) - generated).total_seconds() / 86400
    if age_days < -0.25:
        raise ValueError(f"Checkbook cache timestamp is implausibly in the future: {age_days:.2f} days")
    if age_days > max_age_days:
        raise ValueError(f"Checkbook cache is stale: {age_days:.2f} days > {max_age_days}")

    summary = payload.get("summary")
    source = payload.get("source")
    health = payload.get("source_health")
    contracts = payload.get("contracts")
    if not isinstance(summary, Mapping):
        raise ValueError("Checkbook cache summary is missing")
    if not isinstance(source, Mapping):
        raise ValueError("Checkbook cache source metadata is missing")
    if not isinstance(health, Mapping):
        raise ValueError("Checkbook cache source_health is missing")
    if not isinstance(contracts, list):
        raise ValueError("Checkbook cache contracts is not a list")

    deferred = source.get("deferred_scopes")
    if not isinstance(deferred, list) or not any(
        isinstance(item, Mapping)
        and item.get("name") == "NYCHA"
        and item.get("status") == "DEFERRED_SEPARATE_ADAPTER"
        for item in deferred
    ):
        raise ValueError("Checkbook cache must explicitly declare the deferred NYCHA scope")

    procurement_ids: set[str] = set()
    source_counts: dict[str, int] = {key: 0 for key in ALLOWED_SOURCES}
    for index, contract in enumerate(contracts):
        if not isinstance(contract, Mapping):
            raise ValueError(f"Checkbook contract {index} is not an object")
        procurement_id = str(contract.get("procurement_id") or "")
        if not procurement_id:
            raise ValueError(f"Checkbook contract {index} is missing procurement_id")
        if procurement_id in procurement_ids:
            raise ValueError(f"Duplicate Checkbook procurement_id: {procurement_id}")
        procurement_ids.add(procurement_id)

        contract_source = str(contract.get("source") or "")
        if contract_source not in ALLOWED_SOURCES:
            raise ValueError(f"Unsupported Checkbook contract source: {contract_source}")
        source_counts[contract_source] += 1

        if contract.get("service_category") in (None, "", "UNRELATED"):
            raise ValueError(f"Cache contains non-relevant contract {procurement_id}")
        if contract.get("service_confidence") not in {"CONFIRMED", "STRONG", "VERIFY"}:
            raise ValueError(f"Contract {procurement_id} has invalid service confidence")
        if not isinstance(contract.get("raw"), Mapping):
            raise ValueError(f"Contract {procurement_id} is missing raw source provenance")
        if contract.get("facility_match_confidence") != "UNLINKED":
            raise ValueError(f"Contract {procurement_id} invents facility linkage")
        if contract.get("tower_link_confidence") != "UNLINKED":
            raise ValueError(f"Contract {procurement_id} invents tower linkage")
        if contract.get("tower_account_system_ids") not in ([], ()):
            raise ValueError(f"Contract {procurement_id} invents tower account IDs")
        if contract.get("company_id") is not None:
            raise ValueError(f"Build 016C cache must not silently resolve company identity for {procurement_id}")
        if contract.get("vendor_raw") and contract.get("company_match_confidence") != "UNRESOLVED":
            raise ValueError(f"Unresolved vendor confidence is inconsistent for {procurement_id}")
        if contract.get("vendor_role") not in {"PRIME", "SUBCONTRACTOR"}:
            raise ValueError(f"Contract {procurement_id} is missing vendor_role")

    for source_name in ALLOWED_SOURCES:
        entry = health.get(source_name)
        if not isinstance(entry, Mapping):
            raise ValueError(f"Missing source health for {source_name}")
        if entry.get("status") == "FAILED":
            raise ValueError(f"Checkbook source health failed for {source_name}: {entry.get('status_reasons')}")
        if entry.get("pagination_complete") is not True:
            raise ValueError(f"Checkbook pagination incomplete for {source_name}")
        if entry.get("schema_valid") is not True:
            raise ValueError(f"Checkbook schema invalid for {source_name}")
        if int(entry.get("normalized_contract_count") or 0) != source_counts[source_name]:
            raise ValueError(f"Checkbook normalized count mismatch for {source_name}")

    citywide_health = health.get("NYC_CHECKBOOK_CITYWIDE")
    if not isinstance(citywide_health, Mapping):
        raise ValueError("Missing Citywide Checkbook source health")
    if citywide_health.get("subvendor_pagination_complete") is not True:
        raise ValueError("Checkbook Citywide subcontract pagination is incomplete")
    try:
        subvendor_source_count = int(citywide_health.get("subvendor_record_count") or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("Checkbook Citywide subvendor_record_count is invalid") from exc
    if subvendor_source_count < 0:
        raise ValueError("Checkbook Citywide subvendor_record_count is negative")
    if int(summary.get("citywide_subvendor_source_transaction_count") or 0) != subvendor_source_count:
        raise ValueError("Checkbook Citywide subcontract source count does not match source health")

    if int(summary.get("relevant_contract_count") or -1) != len(contracts):
        raise ValueError("Checkbook relevant_contract_count does not match contracts array")

    if require_production_volume:
        if int(summary.get("citywide_source_transaction_count") or 0) < 1000:
            raise ValueError("Checkbook citywide source volume is below conservative production threshold")
        if int(summary.get("edc_source_transaction_count") or 0) < 1:
            raise ValueError("Checkbook NYCEDC source volume is below conservative production threshold")
        if len(contracts) < 1:
            raise ValueError("Checkbook cache contains no relevant procurement contracts")

    return {
        "status": "PASS",
        "size_bytes": size,
        "age_days": round(age_days, 3),
        "generated_at": payload.get("generated_at"),
        "relevant_contracts": len(contracts),
        "citywide_source_transaction_count": int(summary.get("citywide_source_transaction_count") or 0),
        "citywide_subvendor_source_transaction_count": subvendor_source_count,
        "edc_source_transaction_count": int(summary.get("edc_source_transaction_count") or 0),
        "source_counts": source_counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a TowerSignal Checkbook NYC cache")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--max-age-days", type=float, default=2)
    parser.add_argument("--require-production-volume", action="store_true")
    args = parser.parse_args()
    result = validate_cache(
        args.cache,
        max_age_days=args.max_age_days,
        require_production_volume=args.require_production_volume,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
