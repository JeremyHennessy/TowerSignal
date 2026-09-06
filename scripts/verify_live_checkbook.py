from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.checkbook import (
    CITYWIDE_SCOPE,
    CITYWIDE_SOURCE,
    EDC_SCOPE,
    EDC_SOURCE,
    RequestXml,
    _default_request_xml,
    fetch_scope,
)
from towersignal.procurement import normalize_space


COMPARE_FIELDS: dict[str, tuple[str, ...]] = {
    CITYWIDE_SOURCE: (
        "prime_contract_id",
        "prime_vendor",
        "prime_contract_purpose",
        "prime_contract_original_amount",
        "prime_contract_current_amount",
        "prime_vendor_spent_to_date",
        "prime_contract_start_date",
        "prime_contract_end_date",
        "prime_contracting_agency",
    ),
    EDC_SOURCE: (
        "contract_id",
        "prime_vendor",
        "purpose",
        "original_amount",
        "current_amount",
        "spent_to_date",
        "start_date",
        "end_date",
        "other_government_entities",
    ),
}


def _normalized(value: Any) -> str:
    return normalize_space(str(value or ""))


def _deterministic_sample(rows: Sequence[Mapping[str, Any]], *, seed: str, sample_size: int) -> list[Mapping[str, Any]]:
    ranked = sorted(
        rows,
        key=lambda row: hashlib.sha256(
            f"{seed}|{row.get('procurement_id')}".encode("utf-8")
        ).hexdigest(),
    )
    return ranked[:sample_size]


def _live_contract_rows(
    source: str,
    contract_id: str,
    cached_contract: Mapping[str, Any],
    *,
    request_xml: RequestXml,
) -> tuple[dict[str, str], ...]:
    extra_criteria: list[tuple[str, str, str]] = []
    if source == CITYWIDE_SOURCE:
        fiscal_year = normalize_space(str(cached_contract.get("source_fiscal_year") or ""))
        if fiscal_year:
            extra_criteria.append(("fiscal_year", "value", fiscal_year))
        spec = CITYWIDE_SCOPE
    elif source == EDC_SOURCE:
        spec = EDC_SCOPE
    else:
        raise ValueError(f"Unsupported Checkbook source: {source}")

    extra_criteria.append(("contract_id", "value", contract_id))
    return fetch_scope(
        spec,
        request_xml=request_xml,
        page_size=100,
        extra_criteria=tuple(extra_criteria),
    ).rows


def verify_cache(
    path: Path,
    *,
    sample_size: int,
    request_xml: RequestXml = _default_request_xml,
) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    generated_at = str(payload.get("generated_at") or "")
    contracts = payload.get("contracts")
    if not isinstance(contracts, list):
        raise ValueError("Checkbook cache contracts is not a list")
    if sample_size <= 0:
        raise ValueError("sample_size must be positive")

    prime_rows = [
        row
        for row in contracts
        if isinstance(row, Mapping)
        and row.get("vendor_role") == "PRIME"
        and row.get("source") in COMPARE_FIELDS
        and row.get("source_contract_id")
    ]

    selected: list[Mapping[str, Any]] = []
    for source in (CITYWIDE_SOURCE, EDC_SOURCE):
        candidates = [row for row in prime_rows if row.get("source") == source]
        selected.extend(_deterministic_sample(candidates, seed=f"{generated_at}|{source}", sample_size=sample_size))

    if not selected:
        raise ValueError("Checkbook cache has no prime contracts available for live verification")

    results: list[dict[str, Any]] = []
    for contract in selected:
        source = str(contract["source"])
        contract_id = str(contract["source_contract_id"])
        live_rows = _live_contract_rows(source, contract_id, contract, request_xml=request_xml)
        if not live_rows:
            raise RuntimeError(f"Live Checkbook query returned no rows for {source} {contract_id}")

        matching = [
            row
            for row in live_rows
            if _normalized(row.get("prime_contract_id" if source == CITYWIDE_SOURCE else "contract_id")) == contract_id
        ]
        if not matching:
            raise RuntimeError(f"Live Checkbook query did not return exact contract {source} {contract_id}")

        cached_raw = contract.get("raw")
        if not isinstance(cached_raw, Mapping):
            raise ValueError(f"Cached contract {contract_id} is missing raw source evidence")

        expected_signature = tuple(_normalized(cached_raw.get(field)) for field in COMPARE_FIELDS[source])
        live_signatures = {
            tuple(_normalized(row.get(field)) for field in COMPARE_FIELDS[source])
            for row in matching
        }
        passed = expected_signature in live_signatures
        results.append(
            {
                "source": source,
                "contract_id": contract_id,
                "source_fiscal_year": contract.get("source_fiscal_year"),
                "fields": list(COMPARE_FIELDS[source]),
                "result": "PASS" if passed else "FAIL",
            }
        )
        if not passed:
            raise RuntimeError(
                f"Cached Checkbook evidence no longer matches exact live contract {source} {contract_id}"
            )

    return {
        "generated_at": generated_at,
        "sample_size_per_available_source": sample_size,
        "verified_contract_count": len(results),
        "result": "PASS",
        "contracts": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Independently verify TowerSignal Checkbook cache rows against live Checkbook NYC")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=2)
    args = parser.parse_args()
    print(json.dumps(verify_cache(args.cache, sample_size=args.sample_size), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
