from __future__ import annotations

import argparse
import json
from pathlib import Path

EXPECTED_DATASETS = {"ehig-g5x3", "8w5p-k45m", "d84c-dk28", "p3p6-xqr5"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate TowerSignal NYS authority procurement payload")
    parser.add_argument("--input", type=Path, default=Path("public/data/procurement-nys-authorities.json"))
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("NYS authority procurement payload must be an object")
    contracts = payload.get("contracts")
    health = payload.get("source_health")
    summary = payload.get("summary") or {}
    if not isinstance(contracts, list) or not isinstance(health, list):
        raise SystemExit("NYS authority procurement payload is missing contracts[] or source_health[]")

    dataset_ids = {str(row.get("dataset_id")) for row in health if isinstance(row, dict)}
    if dataset_ids != EXPECTED_DATASETS:
        raise SystemExit(f"NYS authority procurement dataset coverage mismatch: {sorted(dataset_ids)}")
    if any(row.get("status") != "HEALTHY" or row.get("pagination_complete") is not True or row.get("schema_valid") is not True for row in health if isinstance(row, dict)):
        raise SystemExit("NYS authority procurement source health is not fully green")

    ids: set[str] = set()
    vendor_rows = 0
    for row in contracts:
        if not isinstance(row, dict):
            raise SystemExit("NYS authority procurement contract must be an object")
        procurement_id = str(row.get("procurement_id") or "")
        if not procurement_id or procurement_id in ids:
            raise SystemExit(f"Missing or duplicate NYS authority procurement_id: {procurement_id!r}")
        ids.add(procurement_id)
        if row.get("service_category") == "UNRELATED":
            raise SystemExit(f"Unrelated procurement row was published: {procurement_id}")
        if not str(row.get("source") or "").startswith("NYS_ABO_"):
            raise SystemExit(f"Unexpected NYS authority source: {row.get('source')}")
        if not str(row.get("source_url") or "").startswith("https://data.ny.gov/d/"):
            raise SystemExit(f"Missing authoritative source URL: {procurement_id}")
        semantics = str(row.get("observed_value_evidence") or "").lower()
        if "not vendor revenue" not in semantics:
            raise SystemExit(f"NYS authority value semantics missing: {procurement_id}")
        if row.get("vendor_raw"):
            vendor_rows += 1

    if int(summary.get("relevant_contract_count") or -1) != len(contracts):
        raise SystemExit("NYS authority relevant_contract_count does not reconcile")
    if int(summary.get("vendor_record_count") or -1) != vendor_rows:
        raise SystemExit("NYS authority vendor_record_count does not reconcile")
    if int(summary.get("source_dataset_count") or -1) != len(EXPECTED_DATASETS):
        raise SystemExit("NYS authority source_dataset_count does not reconcile")
    if len(contracts) == 0:
        raise SystemExit("NYS authority procurement returned zero relevant records")

    print(json.dumps({
        "source_dataset_count": len(health),
        "source_record_count": summary.get("source_record_count"),
        "relevant_contract_count": len(contracts),
        "vendor_record_count": vendor_rows,
        "exact_unique_procurement_ids": True,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
