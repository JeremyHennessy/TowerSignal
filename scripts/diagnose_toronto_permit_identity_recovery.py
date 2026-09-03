from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from diagnose_toronto_permit_final_identity import resolve_row, targeted_rows
from diagnose_toronto_building_permit_targeted_v2 import SOURCES, row_address
from toronto_final_identity_cleanup import address_point_root, canonical_address, linked_range_parent, load_address_points
from toronto_market_common import clean_text

OFFICIAL_HISTORICAL_STREET_ALIASES = {
    # City of Toronto By-law 302-2020 renamed this portion of Russell Street
    # between St. George Street and Spadina Crescent to Ursula Franklin Street.
    # Diagnostic only: promotion requires exact current Address Point identity.
    "16 RUSSELL ST": "16 URSULA FRANKLIN ST",
}


def relaxed_canonical(value: Any) -> str:
    text = clean_text(value).upper().replace("’", "'")
    # Publisher formatting variants only: apostrophe omission, detached civic
    # suffix letters, and old Toronto permit spellings such as MC CAUL/MCCaul.
    text = text.replace("'", "")
    text = re.sub(r"^(\d+)\s+([A-Z])\s+", r"\1\2 ", text)
    text = re.sub(r"\bMC\s+([A-Z])", r"MC\1", text)
    return canonical_address(text)


def build_relaxed_index(by_id: dict[str, dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    index: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in by_id.values():
        address = relaxed_canonical(row.get("address"))
        if not address:
            continue
        root = address_point_root(row, by_id)
        root_id = clean_text(root.get("address_point_id"))
        if root_id:
            index[address][root_id] = root
    return index


def recover(row: dict[str, Any], by_id: dict[str, dict[str, Any]], by_address: dict[str, list[dict[str, Any]]], relaxed_index: dict[str, dict[str, dict[str, Any]]]) -> tuple[dict[str, Any] | None, str, dict[str, Any]]:
    permit_apid = clean_text(row.get("GEO_ID"))
    permit_address_raw = row_address(row)
    permit_address = canonical_address(permit_address_raw)
    relaxed_permit = relaxed_canonical(permit_address_raw)
    evidence: dict[str, Any] = {
        "permit_geo_id": permit_apid or None,
        "permit_address": permit_address_raw or None,
        "canonical_permit_address": permit_address or None,
        "relaxed_canonical_permit_address": relaxed_permit or None,
    }

    if permit_apid and permit_apid in by_id:
        municipal = by_id[permit_apid]
        root = address_point_root(municipal, by_id)
        relaxed_child = relaxed_canonical(municipal.get("address"))
        relaxed_root = relaxed_canonical(root.get("address"))
        evidence.update({
            "municipal_address_point_id": municipal.get("address_point_id"),
            "municipal_address": municipal.get("address"),
            "root_address_point_id": root.get("address_point_id"),
            "root_address": root.get("address"),
        })
        if relaxed_permit and relaxed_permit == relaxed_child:
            return root, "RELAXED_PUBLISHER_FORMAT_MATCH_TO_GEO_ID_CHILD", evidence
        if relaxed_permit and relaxed_permit == relaxed_root:
            return root, "RELAXED_PUBLISHER_FORMAT_MATCH_TO_GEO_ID_ROOT", evidence
        historical_target = OFFICIAL_HISTORICAL_STREET_ALIASES.get(permit_address)
        if historical_target and historical_target == canonical_address(root.get("address")):
            evidence["official_alias_basis"] = "CITY_OF_TORONTO_BYLAW_302_2020"
            return root, "OFFICIAL_STREET_RENAME_ALIAS_SAME_ADDRESS_POINT_ID", evidence

    if relaxed_permit:
        roots = relaxed_index.get(relaxed_permit, {})
        if len(roots) == 1:
            root = next(iter(roots.values()))
            evidence.update({"root_address_point_id": root.get("address_point_id"), "root_address": root.get("address")})
            return root, "RELAXED_UNIQUE_CIVIC_ADDRESS_TO_CURRENT_ROOT", evidence
        if len(roots) > 1:
            evidence["candidate_root_address_point_ids"] = sorted(roots)
            return None, "RELAXED_CIVIC_ADDRESS_AMBIGUOUS_NOT_FORCED", evidence

    range_root, endpoint_ids = linked_range_parent(permit_address_raw, by_address, by_id)
    if range_root is not None:
        evidence["range_endpoint_address_point_ids"] = endpoint_ids
        evidence["root_address_point_id"] = range_root.get("address_point_id")
        evidence["root_address"] = range_root.get("address")
        return range_root, "EXPLICIT_RANGE_ENDPOINTS_CONVERGE_ON_CURRENT_ROOT", evidence

    return None, "NO_ADDITIONAL_DETERMINISTIC_RECOVERY", evidence


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only recovery audit for Toronto targeted permit rows quarantined by the strict identity contract")
    parser.add_argument("--output", type=Path, default=Path("toronto-permit-identity-recovery.json"))
    args = parser.parse_args()

    by_id, by_address, scanned = load_address_points()
    relaxed_index = build_relaxed_index(by_id)
    baseline_unresolved = []
    recovered = []
    remaining = []
    baseline_counts = Counter()
    recovery_counts = Counter()

    for source, resource_id in SOURCES.items():
        rows = targeted_rows(resource_id)
        for identity, row in rows.items():
            root, basis, baseline_evidence = resolve_row(row, by_id, by_address)
            if root is not None:
                continue
            baseline_counts[source] += 1
            baseline = {
                "source": source,
                "permit_identity": identity,
                "baseline_basis": basis,
                "permit_geo_id": baseline_evidence.get("permit_geo_id"),
                "permit_address": baseline_evidence.get("permit_address"),
                "description": clean_text(row.get("DESCRIPTION")) or None,
                "status": clean_text(row.get("STATUS")) or None,
            }
            baseline_unresolved.append(baseline)
            recovery_root, recovery_basis, evidence = recover(row, by_id, by_address, relaxed_index)
            recovery_counts[recovery_basis] += 1
            result = {
                **baseline,
                "recovery_basis": recovery_basis,
                "resolved_property_id": f"toronto-address-point:{clean_text(recovery_root.get('address_point_id'))}" if recovery_root else None,
                "resolved_address": recovery_root.get("address") if recovery_root else None,
                "recovery_evidence": evidence,
            }
            if recovery_root is not None:
                recovered.append(result)
            else:
                remaining.append(result)

    report = {
        "schema_version": "toronto-permit-identity-recovery-diagnostic-1.0",
        "status": "PASSED_DIAGNOSTIC",
        "scope": "Read-only. Tests only bounded publisher-format normalization, exact current Address Point root convergence, and one official historical street rename. No fuzzy matching and no production writes.",
        "address_point_rows_scanned": scanned,
        "baseline_unresolved_rows": len(baseline_unresolved),
        "baseline_unresolved_by_source": dict(sorted(baseline_counts.items())),
        "deterministically_recoverable_rows": len(recovered),
        "remaining_unresolved_rows": len(remaining),
        "recovery_basis_counts": dict(sorted(recovery_counts.items())),
        "recovered": recovered,
        "remaining": remaining,
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "baseline_unresolved_rows": report["baseline_unresolved_rows"],
        "baseline_unresolved_by_source": report["baseline_unresolved_by_source"],
        "deterministically_recoverable_rows": report["deterministically_recoverable_rows"],
        "remaining_unresolved_rows": report["remaining_unresolved_rows"],
        "recovery_basis_counts": report["recovery_basis_counts"],
        "recovered_sample": recovered[:20],
        "remaining": remaining,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
