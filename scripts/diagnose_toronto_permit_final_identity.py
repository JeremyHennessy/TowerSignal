from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from diagnose_toronto_building_permit_targeted_v2 import (
    DISCOVERY_QUERIES,
    SOURCES,
    fetch_query_rows,
    permit_identity,
    row_address,
    signal_keys,
)
from toronto_final_identity_cleanup import address_point_root, canonical_address, load_address_points
from toronto_market_common import clean_text, read_json

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data/toronto/market/current"


def targeted_rows(resource_id: str) -> dict[str, dict[str, Any]]:
    discovered: dict[str, dict[str, Any]] = {}
    for query in DISCOVERY_QUERIES:
        _, rows = fetch_query_rows(resource_id, query)
        for row in rows:
            discovered.setdefault(permit_identity(row), row)
    return {identity: row for identity, row in discovered.items() if signal_keys(row)}


def resolve_row(row: dict[str, Any], by_id: dict[str, dict[str, Any]], by_address: dict[str, list[dict[str, Any]]]) -> tuple[dict[str, Any] | None, str, dict[str, Any]]:
    permit_apid = clean_text(row.get("GEO_ID"))
    permit_address_raw = row_address(row)
    permit_address = canonical_address(permit_address_raw)
    evidence: dict[str, Any] = {
        "permit_geo_id": permit_apid or None,
        "permit_address": permit_address_raw or None,
        "canonical_permit_address": permit_address or None,
    }

    if permit_apid and permit_apid in by_id:
        municipal = by_id[permit_apid]
        root = address_point_root(municipal, by_id)
        municipal_address = canonical_address(municipal.get("address"))
        root_address = canonical_address(root.get("address"))
        evidence.update({
            "municipal_address_point_id": municipal.get("address_point_id"),
            "municipal_address": municipal.get("address"),
            "root_address_point_id": root.get("address_point_id"),
            "root_address": root.get("address"),
        })
        if permit_address and permit_address == root_address:
            return root, "PERMIT_GEO_ID_TO_CURRENT_ADDRESS_POINT_ROOT_WITH_EXACT_CIVIC_ADDRESS", evidence
        if permit_address and permit_address == municipal_address and municipal.get("address_point_id") != root.get("address_point_id"):
            return root, "PERMIT_GEO_ID_LINKED_TO_ROOT_SOURCE_ADDRESS_MATCHES_CHILD", evidence
        # Do not trust a GEO_ID with a conflicting civic address. Fall through to
        # exact address resolution so the source can still resolve safely.
        evidence["geo_id_address_conflict"] = True

    if permit_address:
        candidates = by_address.get(permit_address, [])
        roots: dict[str, dict[str, Any]] = {}
        for candidate in candidates:
            root = address_point_root(candidate, by_id)
            root_id = clean_text(root.get("address_point_id"))
            if root_id:
                roots[root_id] = root
        if len(roots) == 1:
            root = next(iter(roots.values()))
            evidence.update({
                "root_address_point_id": root.get("address_point_id"),
                "root_address": root.get("address"),
            })
            return root, "EXACT_UNIQUE_CIVIC_ADDRESS_TO_CURRENT_ADDRESS_POINT_ROOT", evidence
        if len(roots) > 1:
            evidence["candidate_root_address_point_ids"] = sorted(roots)
            return None, "AMBIGUOUS_CURRENT_ADDRESS_POINT_ROOTS_NOT_FORCED", evidence

    return None, "NO_CURRENT_ADDRESS_POINT_IDENTITY", evidence


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only final identity proof for targeted Toronto building permits")
    parser.add_argument("--output", type=Path, default=Path("toronto-permit-final-identity.json"))
    args = parser.parse_args()

    spine = read_json(MARKET / "property_spine.json") or {}
    properties = [item for item in spine.get("properties", []) if isinstance(item, dict)]
    current_property_ids = {clean_text(item.get("property_id")) for item in properties}
    current_apids = {clean_text(item.get("address_point_id")) for item in properties if clean_text(item.get("address_point_id"))}
    by_id, by_address, scanned = load_address_points()

    source_results: dict[str, Any] = {}
    all_resolved_apids: set[str] = set()
    all_new_apids: set[str] = set()
    all_existing_apids: set[str] = set()
    unresolved_records: list[dict[str, Any]] = []
    conflict_records: list[dict[str, Any]] = []

    for source, resource_id in SOURCES.items():
        rows = targeted_rows(resource_id)
        basis_counts = Counter()
        resolved_apids: set[str] = set()
        new_apids: set[str] = set()
        existing_apids: set[str] = set()
        resolved_rows = 0
        source_unresolved = 0
        source_conflicts = 0
        signal_resolved_properties: dict[str, set[str]] = defaultdict(set)
        for identity, row in rows.items():
            root, basis, evidence = resolve_row(row, by_id, by_address)
            basis_counts[basis] += 1
            if evidence.get("geo_id_address_conflict"):
                source_conflicts += 1
                if len(conflict_records) < 200:
                    conflict_records.append({"source": source, "permit_identity": identity, "basis": basis, **evidence, "description": clean_text(row.get("DESCRIPTION"))})
            if root is None:
                source_unresolved += 1
                if len(unresolved_records) < 300:
                    unresolved_records.append({"source": source, "permit_identity": identity, "basis": basis, **evidence, "description": clean_text(row.get("DESCRIPTION"))})
                continue
            apid = clean_text(root.get("address_point_id"))
            if not apid:
                raise RuntimeError(f"Resolved permit root missing ADDRESS_POINT_ID: {identity}")
            resolved_rows += 1
            resolved_apids.add(apid)
            all_resolved_apids.add(apid)
            if apid in current_apids:
                existing_apids.add(apid)
                all_existing_apids.add(apid)
            else:
                new_apids.add(apid)
                all_new_apids.add(apid)
            for signal in signal_keys(row):
                signal_resolved_properties[signal].add(apid)

        source_results[source] = {
            "targeted_rows": len(rows),
            "resolved_rows": resolved_rows,
            "unresolved_rows": source_unresolved,
            "rows_with_geo_id_address_conflict": source_conflicts,
            "resolution_basis_counts": dict(sorted(basis_counts.items())),
            "resolved_properties": len(resolved_apids),
            "existing_spine_properties": len(existing_apids),
            "new_spine_properties": len(new_apids),
            "signal_resolved_property_counts": {key: len(value) for key, value in sorted(signal_resolved_properties.items())},
        }

    overlap = all_existing_apids & all_new_apids
    if overlap:
        raise RuntimeError(f"Permit final identity partition overlap: {sorted(overlap)[:20]}")
    expected_property_ids = {f"toronto-address-point:{apid}" for apid in all_existing_apids}
    if not expected_property_ids.issubset(current_property_ids):
        raise RuntimeError("Existing permit Address Point identities do not map to current property IDs")

    report = {
        "schema_version": "toronto-permit-final-identity-diagnostic-1.0",
        "status": "PASSED_DIAGNOSTIC",
        "contract": "Resolve each targeted permit to current Toronto Address Point root. Permit GEO_ID is accepted only when its civic address agrees with the root/linked child; otherwise exact unique civic-address-to-root fallback is required. Ambiguities and missing identities are never forced.",
        "address_point_rows_scanned": scanned,
        "current_property_spine_count": len(properties),
        "sources": source_results,
        "union_resolved_properties": len(all_resolved_apids),
        "union_existing_spine_properties": len(all_existing_apids),
        "union_new_spine_properties": len(all_new_apids),
        "projected_property_spine_count": len(properties) + len(all_new_apids),
        "unresolved_record_sample": unresolved_records,
        "geo_id_address_conflict_sample": conflict_records,
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "address_point_rows_scanned": report["address_point_rows_scanned"],
        "current_property_spine_count": report["current_property_spine_count"],
        "sources": source_results,
        "union_resolved_properties": report["union_resolved_properties"],
        "union_existing_spine_properties": report["union_existing_spine_properties"],
        "union_new_spine_properties": report["union_new_spine_properties"],
        "projected_property_spine_count": report["projected_property_spine_count"],
        "unresolved_record_sample_count": len(unresolved_records),
        "geo_id_address_conflict_sample_count": len(conflict_records),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
