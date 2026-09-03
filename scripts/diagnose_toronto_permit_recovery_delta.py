from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from diagnose_toronto_building_permit_targeted_v2 import SOURCES, signal_keys
from diagnose_toronto_permit_final_identity import resolve_row, targeted_rows
from diagnose_toronto_permit_identity_recovery import recover, build_relaxed_index
from toronto_final_identity_cleanup import load_address_points
from toronto_market_common import clean_text, read_json

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data/toronto/market/current"


def apid(root: dict[str, Any] | None) -> str:
    return clean_text(root.get("address_point_id")) if root else ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only net-delta audit for deterministic permit identity recoveries")
    parser.add_argument("--output", type=Path, default=Path("toronto-permit-recovery-delta.json"))
    args = parser.parse_args()

    spine = read_json(MARKET / "property_spine.json") or {}
    current_properties = [item for item in spine.get("properties", []) if isinstance(item, dict)]
    current_apids = {clean_text(item.get("address_point_id")) for item in current_properties if clean_text(item.get("address_point_id"))}
    by_id, by_address, scanned = load_address_points()
    relaxed_index = build_relaxed_index(by_id)

    strict_resolved_rows = 0
    strict_unresolved_rows = 0
    strict_roots: set[str] = set()
    strict_new_roots: set[str] = set()
    recovery_rows: list[dict[str, Any]] = []
    recovery_roots: set[str] = set()
    recovery_new_vs_current: set[str] = set()
    recovery_incremental_vs_strict: set[str] = set()
    remaining_rows: list[dict[str, Any]] = []
    source_counts: dict[str, Counter[str]] = defaultdict(Counter)
    signal_counts = Counter()

    for source, resource_id in SOURCES.items():
        rows = targeted_rows(resource_id)
        for identity, row in rows.items():
            strict_root, strict_basis, _ = resolve_row(row, by_id, by_address)
            if strict_root is not None:
                strict_resolved_rows += 1
                root_id = apid(strict_root)
                strict_roots.add(root_id)
                if root_id not in current_apids:
                    strict_new_roots.add(root_id)
                continue

            strict_unresolved_rows += 1
            recovery_root, recovery_basis, evidence = recover(row, by_id, by_address, relaxed_index)
            source_counts[source][recovery_basis] += 1
            if recovery_root is None:
                remaining_rows.append({
                    "source": source,
                    "permit_identity": identity,
                    "strict_basis": strict_basis,
                    "recovery_basis": recovery_basis,
                    "permit_geo_id": clean_text(row.get("GEO_ID")) or None,
                    "permit_address": evidence.get("permit_address"),
                    "signals": signal_keys(row),
                    "status": clean_text(row.get("STATUS")) or None,
                    "description": clean_text(row.get("DESCRIPTION")) or None,
                })
                continue

            root_id = apid(recovery_root)
            recovery_roots.add(root_id)
            if root_id not in current_apids:
                recovery_new_vs_current.add(root_id)
            if root_id not in strict_roots:
                recovery_incremental_vs_strict.add(root_id)
            signals = signal_keys(row)
            signal_counts.update(signals)
            recovery_rows.append({
                "source": source,
                "permit_identity": identity,
                "strict_basis": strict_basis,
                "recovery_basis": recovery_basis,
                "resolved_property_id": f"toronto-address-point:{root_id}",
                "resolved_address": recovery_root.get("address"),
                "already_in_current_spine": root_id in current_apids,
                "already_in_strict_permit_property_union": root_id in strict_roots,
                "signals": signals,
                "status": clean_text(row.get("STATUS")) or None,
                "description": clean_text(row.get("DESCRIPTION")) or None,
            })

    # Strict roots were accumulated as we traversed rows. A recovery root can be
    # encountered before a later strict row resolves to the same property. Recompute
    # the true incremental set against the complete strict union after traversal.
    recovery_incremental_vs_strict = recovery_roots - strict_roots
    final_projected_roots = strict_roots | recovery_roots
    final_new_roots = final_projected_roots - current_apids

    strict_expected_properties = len(current_apids | strict_new_roots)
    final_projected_properties = len(current_apids | final_new_roots)

    report = {
        "schema_version": "toronto-permit-recovery-delta-diagnostic-1.0",
        "status": "PASSED_DIAGNOSTIC",
        "scope": "Read-only delta calculation. No fuzzy matching or writes. Compares the strict 1,244-row permit identity contract to the bounded deterministic recovery rules.",
        "address_point_rows_scanned": scanned,
        "current_spine_properties": len(current_apids),
        "strict": {
            "resolved_rows": strict_resolved_rows,
            "unresolved_rows": strict_unresolved_rows,
            "resolved_property_union": len(strict_roots),
            "new_properties_vs_current_spine": len(strict_new_roots),
            "projected_spine_properties": strict_expected_properties,
        },
        "recovery": {
            "recovered_rows": len(recovery_rows),
            "remaining_unresolved_rows": len(remaining_rows),
            "recovered_property_union": len(recovery_roots),
            "recovered_roots_already_in_current_spine": len(recovery_roots & current_apids),
            "recovered_roots_already_in_strict_permit_union": len(recovery_roots & strict_roots),
            "incremental_property_roots_beyond_strict_union": len(recovery_incremental_vs_strict),
            "incremental_new_properties_beyond_strict_spine": len(final_new_roots - strict_new_roots),
            "final_projected_spine_properties": final_projected_properties,
            "signal_row_counts": dict(sorted(signal_counts.items())),
            "source_recovery_basis_counts": {source: dict(sorted(counts.items())) for source, counts in sorted(source_counts.items())},
        },
        "incremental_property_roots": sorted(recovery_incremental_vs_strict),
        "incremental_new_property_roots": sorted(final_new_roots - strict_new_roots),
        "recovered_rows": recovery_rows,
        "remaining_unresolved_rows": remaining_rows,
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "current_spine_properties": report["current_spine_properties"],
        "strict": report["strict"],
        "recovery": report["recovery"],
        "incremental_property_roots": report["incremental_property_roots"],
        "incremental_new_property_roots": report["incremental_new_property_roots"],
        "remaining_unresolved_rows": report["remaining_unresolved_rows"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
