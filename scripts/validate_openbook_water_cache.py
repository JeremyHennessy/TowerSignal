from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _generated(value: Any) -> datetime:
    text = str(value or "")
    if not text:
        raise RuntimeError("Open Book cache missing generated_at")
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def validate(path: Path, *, max_age_days: int, require_production_volume: bool) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0":
        raise RuntimeError("Unexpected Open Book water cache schema version")
    age_days = (datetime.now(timezone.utc) - _generated(payload.get("generated_at"))).total_seconds() / 86400
    if age_days < -0.05 or age_days > max_age_days:
        raise RuntimeError(f"Open Book cache generated_at age is {age_days:.2f} days")

    source = payload.get("source")
    summary = payload.get("summary")
    contracts = payload.get("contracts")
    if not isinstance(source, dict) or not isinstance(summary, dict) or not isinstance(contracts, list):
        raise RuntimeError("Open Book water cache missing source, summary, or contracts")
    if source.get("transport_complete") is not True or source.get("schema_valid") is not True:
        raise RuntimeError("Open Book source transport/schema proof failed")
    if not source.get("sha256") or len(str(source["sha256"])) != 64:
        raise RuntimeError("Open Book source hash missing or invalid")
    if int(summary.get("relevant_contract_count") or -1) != len(contracts):
        raise RuntimeError("Open Book relevant contract count mismatch")

    transaction_total = 0
    contract_ids: set[str] = set()
    for contract in contracts:
        if not isinstance(contract, dict):
            raise RuntimeError("Open Book contract record is not an object")
        contract_id = str(contract.get("contract_id") or "")
        if not contract_id or contract_id in contract_ids:
            raise RuntimeError(f"Missing/duplicate Open Book contract ID: {contract_id!r}")
        contract_ids.add(contract_id)
        if contract.get("service_category") == "UNRELATED":
            raise RuntimeError(f"Published unrelated Open Book contract: {contract_id}")
        if contract.get("company_match_confidence") != "UNRESOLVED":
            raise RuntimeError("Open Book adapter unexpectedly resolved a vendor identity")
        transactions = contract.get("transactions")
        if not isinstance(transactions, list) or not transactions:
            raise RuntimeError(f"Open Book contract missing transactions: {contract_id}")
        if int(contract.get("transaction_count") or 0) != len(transactions):
            raise RuntimeError(f"Open Book transaction count mismatch: {contract_id}")
        transaction_ids = [str(row.get("transaction_id") or "") for row in transactions if isinstance(row, dict)]
        if len(transaction_ids) != len(transactions) or len(transaction_ids) != len(set(transaction_ids)):
            raise RuntimeError(f"Open Book transaction identities invalid: {contract_id}")
        transaction_total += len(transactions)
        amounts = [float(row["transaction_amount"]) for row in transactions if isinstance(row, dict) and row.get("transaction_amount") is not None]
        expected_net = round(sum(amounts), 2) if amounts else None
        actual_net = contract.get("net_transaction_amount")
        if expected_net is None:
            if actual_net is not None:
                raise RuntimeError(f"Open Book net transaction amount should be null: {contract_id}")
        elif abs(float(actual_net) - expected_net) > 0.01:
            raise RuntimeError(f"Open Book net transaction amount mismatch: {contract_id}")

    if transaction_total != int(summary.get("relevant_transaction_count") or -1):
        raise RuntimeError("Open Book relevant transaction total mismatch")

    if require_production_volume:
        floors = {
            "source_transaction_count": 200000,
            "source_contract_count": 80000,
            "relevant_contract_count": 100,
            "relevant_transaction_count": 100,
            "relevant_vendor_count": 25,
        }
        for key, floor in floors.items():
            value = int(summary.get(key) or 0)
            if value < floor:
                raise RuntimeError(f"Implausibly small Open Book {key}: {value:,} < {floor:,}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate TowerSignal Open Book NY water-contract cache")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--max-age-days", type=int, default=1)
    parser.add_argument("--require-production-volume", action="store_true")
    args = parser.parse_args()
    payload = validate(args.cache, max_age_days=args.max_age_days, require_production_volume=args.require_production_volume)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
