from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from diagnose_toronto_building_permit_targeted_v2 import SOURCES, row_address, signal_keys
from diagnose_toronto_permit_final_identity import resolve_row, targeted_rows
from diagnose_toronto_permit_identity_recovery import build_relaxed_index, recover
from toronto_final_identity_cleanup import address_point_root, canonical_address, load_address_points
from toronto_market_common import clean_text


def street_and_number(value: Any) -> tuple[str, str, str] | None:
    canonical = canonical_address(value)
    match = re.match(r"^(\d+)([A-Z]?)\s+(.+)$", canonical)
    if not match:
        return None
    return match.group(1), match.group(2), match.group(3)


def build_base_root_index(by_id: dict[str, dict[str, Any]]) -> dict[tuple[str, str], set[str]]:
    output: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in by_id.values():
        parsed = street_and_number(row.get("address"))
        if not parsed:
            continue
        base, _suffix, street = parsed
        root = address_point_root(row, by_id)
        root_id = clean_text(root.get("address_point_id"))
        if root_id:
            output[(base, street)].add(root_id)
    return output


def recover_omitted_suffix(row: dict[str, Any], by_id: dict[str, dict[str, Any]], base_roots: dict[tuple[str, str], set[str]]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    permit_geo_id = clean_text(row.get("GEO_ID"))
    municipal = by_id.get(permit_geo_id)
    if not municipal:
        return None, {"reason": "PERMIT_GEO_ID_NOT_CURRENT"}
    permit_parts = street_and_number(row_address(row))
    municipal_parts = street_and_number(municipal.get("address"))
    if not permit_parts or not municipal_parts:
        return None, {"reason": "UNPARSABLE_CIVIC_ADDRESS"}
    permit_base, permit_suffix, permit_street = permit_parts
    municipal_base, municipal_suffix, municipal_street = municipal_parts
    evidence = {
        "permit_geo_id": permit_geo_id,
        "permit_address": row_address(row),
        "municipal_address": municipal.get("address"),
        "permit_base": permit_base,
        "permit_suffix": permit_suffix,
        "municipal_base": municipal_base,
        "municipal_suffix": municipal_suffix,
        "permit_street": permit_street,
        "municipal_street": municipal_street,
    }
    if permit_suffix:
        evidence["reason"] = "PERMIT_ALREADY_HAS_SUFFIX"
        return None, evidence
    if not municipal_suffix:
        evidence["reason"] = "CURRENT_ADDRESS_HAS_NO_SUFFIX_TO_RECOVER"
        return None, evidence
    if permit_base != municipal_base or permit_street != municipal_street:
        evidence["reason"] = "BASE_NUMBER_OR_STREET_MISMATCH"
        return None, evidence
    roots = base_roots.get((permit_base, permit_street), set())
    root = address_point_root(municipal, by_id)
    root_id = clean_text(root.get("address_point_id"))
    evidence["current_variant_root_ids"] = sorted(roots)
    evidence["municipal_root_address_point_id"] = root_id
    evidence["municipal_root_address"] = root.get("address")
    if roots != {root_id}:
        evidence["reason"] = "BASE_NUMBER_HAS_MULTIPLE_CURRENT_ROOTS"
        return None, evidence
    evidence["reason"] = "CURRENT_GEO_ID_BASE_NUMBER_STREET_UNIQUE_ROOT_SUFFIX_OMISSION"
    return root, evidence


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only omitted-civic-suffix recovery audit for remaining Toronto permit rows")
    parser.add_argument("--output", type=Path, default=Path("toronto-permit-suffix-recovery.json"))
    args = parser.parse_args()

    by_id, by_address, scanned = load_address_points()
    relaxed_index = build_relaxed_index(by_id)
    base_roots = build_base_root_index(by_id)
    baseline_remaining = []
    recovered = []
    still_remaining = []

    for source, resource_id in SOURCES.items():
        for identity, row in targeted_rows(resource_id).items():
            strict_root, strict_basis, _ = resolve_row(row, by_id, by_address)
            if strict_root is not None:
                continue
            first_recovery_root, first_recovery_basis, _ = recover(row, by_id, by_address, relaxed_index)
            if first_recovery_root is not None:
                continue
            record = {
                "source": source,
                "permit_identity": identity,
                "permit_geo_id": clean_text(row.get("GEO_ID")) or None,
                "permit_address": row_address(row),
                "strict_basis": strict_basis,
                "prior_recovery_basis": first_recovery_basis,
                "signals": signal_keys(row),
                "status": clean_text(row.get("STATUS")) or None,
                "description": clean_text(row.get("DESCRIPTION")) or None,
            }
            baseline_remaining.append(record)
            root, evidence = recover_omitted_suffix(row, by_id, base_roots)
            result = {
                **record,
                "suffix_recovery_basis": evidence.get("reason"),
                "resolved_property_id": f"toronto-address-point:{clean_text(root.get('address_point_id'))}" if root else None,
                "resolved_address": root.get("address") if root else None,
                "evidence": evidence,
            }
            if root is not None:
                recovered.append(result)
            else:
                still_remaining.append(result)

    report = {
        "schema_version": "toronto-permit-suffix-recovery-diagnostic-1.0",
        "status": "PASSED_DIAGNOSTIC",
        "scope": "Read-only. A row is recovered only when its permit GEO_ID is a current Address Point, permit street/base number exactly match that point, the permit omits a current suffix, and all current suffix variants for the base address converge to the same current root.",
        "address_point_rows_scanned": scanned,
        "rows_remaining_after_prior_recovery": len(baseline_remaining),
        "suffix_recoverable_rows": len(recovered),
        "remaining_unresolved_rows": len(still_remaining),
        "recovered": recovered,
        "remaining": still_remaining,
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
