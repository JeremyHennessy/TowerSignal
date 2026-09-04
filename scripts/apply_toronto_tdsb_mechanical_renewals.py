from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from apply_toronto_targeted_building_permits import property_node, recompute_graph_counts
from toronto_final_identity_cleanup import canonical_address
from toronto_market_common import clean_text, read_json, utc_now, write_json
from toronto_source_identity import stable_source_record_id

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data/toronto/market/current"
SNAPSHOT = ROOT / "data/toronto/warehouse/current/open_licensed/tdsb_facility_condition_renewal.json"
SOURCE_KEY = "tdsb_facility_condition_renewal"

EXPECTED_BASE_PROPERTIES = 13380
EXPECTED_BASE_LINKS = 40059
EXPECTED_BASE_GRAPH_EDGES = 6343
EXPECTED_SOURCE_ROWS = 826
EXPECTED_MATCHED_ROWS = 782
EXPECTED_UNMATCHED_ROWS = 44
EXPECTED_MATCHED_SCHOOLS = 334
EXPECTED_MATCHED_ROOTS = 330
EXPECTED_NEW_PROPERTIES = 289
EXPECTED_FINAL_PROPERTIES = 13669
EXPECTED_FINAL_LINKS = 40841
EXPECTED_LINKED_SOURCE_FAMILIES = 17
EXPECTED_SOURCE_SUMMARY_ENTRIES = 20
EXPECTED_EXPLICIT_TOWER_SCHOOLS = 13


def source_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in payload.get("rows", []) if isinstance(row, dict)]


def main() -> None:
    snapshot = read_json(SNAPSHOT) or {}
    rows = source_rows(snapshot)
    metadata = snapshot.get("metadata") or {}
    if clean_text(snapshot.get("source_key")) != SOURCE_KEY:
        raise RuntimeError("TDSB source snapshot key mismatch")
    if len(rows) != EXPECTED_SOURCE_ROWS or int(metadata.get("source_records") or 0) != EXPECTED_SOURCE_ROWS:
        raise RuntimeError(f"TDSB source snapshot row drift: expected {EXPECTED_SOURCE_ROWS}, found {len(rows)}")

    resolved_rows = [row for row in rows if clean_text(row.get("resolution_status")) == "EXACT_LITERAL_TDSB_CIVIC_ADDRESS_TO_UNIQUE_CURRENT_ROOT"]
    unresolved_rows = [row for row in rows if row not in resolved_rows]
    if len(resolved_rows) != EXPECTED_MATCHED_ROWS or len(unresolved_rows) != EXPECTED_UNMATCHED_ROWS:
        raise RuntimeError(f"TDSB resolution accounting drift: resolved={len(resolved_rows)}, unresolved={len(unresolved_rows)}")
    matched_school_ids = {clean_text(row.get("school_id")) for row in resolved_rows if clean_text(row.get("school_id"))}
    matched_apids = {clean_text(row.get("address_point_id")) for row in resolved_rows if clean_text(row.get("address_point_id"))}
    if len(matched_school_ids) != EXPECTED_MATCHED_SCHOOLS or len(matched_apids) != EXPECTED_MATCHED_ROOTS:
        raise RuntimeError(f"TDSB matched school/root drift: schools={len(matched_school_ids)}, roots={len(matched_apids)}")
    explicit_tower_school_ids = {clean_text(row.get("school_id")) for row in resolved_rows if "cooling_tower" in (row.get("signals") or [])}
    if len(explicit_tower_school_ids) != EXPECTED_EXPLICIT_TOWER_SCHOOLS:
        raise RuntimeError(f"TDSB explicit tower-school drift: {len(explicit_tower_school_ids)}")

    spine = read_json(MARKET / "property_spine.json") or {}
    properties = [item for item in spine.get("properties", []) if isinstance(item, dict)]
    if len(properties) != EXPECTED_BASE_PROPERTIES:
        raise RuntimeError(f"TDSB apply requires {EXPECTED_BASE_PROPERTIES} recovery-baseline properties, found {len(properties)}")
    property_by_id = {clean_text(item.get("property_id")): item for item in properties}
    if len(property_by_id) != EXPECTED_BASE_PROPERTIES:
        raise RuntimeError("TDSB apply baseline property IDs are not unique")
    baseline_property_json = {
        pid: json.dumps(prop, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
        for pid, prop in property_by_id.items()
    }

    property_roots = snapshot.get("property_roots") or {}
    if not isinstance(property_roots, dict) or set(property_roots) != matched_apids:
        raise RuntimeError("TDSB snapshot root manifest does not exactly cover resolved Address Point roots")
    new_apids = {apid for apid in matched_apids if f"toronto-address-point:{apid}" not in property_by_id}
    if len(new_apids) != EXPECTED_NEW_PROPERTIES:
        raise RuntimeError(f"Expected {EXPECTED_NEW_PROPERTIES} new TDSB property roots, found {len(new_apids)}")

    aliases_by_apid: dict[str, set[str]] = defaultdict(set)
    for row in resolved_rows:
        apid = clean_text(row.get("address_point_id"))
        published = clean_text(row.get("published_address"))
        if apid and published:
            aliases_by_apid[apid].add(published)

    new_properties: list[dict[str, Any]] = []
    for apid in sorted(new_apids, key=int):
        root = property_roots[apid]
        if not isinstance(root, dict):
            raise RuntimeError(f"Invalid TDSB root record: {apid}")
        address = clean_text(root.get("address"))
        lon, lat = root.get("longitude"), root.get("latitude")
        if not address or not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
            raise RuntimeError(f"TDSB root lacks current City identity/coordinates: {apid}")
        if not (-80 <= float(lon) <= -78 and 43 <= float(lat) <= 44.5):
            raise RuntimeError(f"TDSB root has invalid Toronto coordinates: {apid}: {lon}, {lat}")
        pid = f"toronto-address-point:{apid}"
        prop = {
            "property_id": pid,
            "canonical_identifier_type": "CITY_OF_TORONTO_ADDRESS_POINT_ID",
            "canonical_identifier": apid,
            "address_point_id": apid,
            "address_id": root.get("address_id"),
            "address_string_id": root.get("address_string_id"),
            "centreline_id": root.get("centreline_id"),
            "address_point_id_link": root.get("address_point_id_link"),
            "address_id_link": root.get("address_id_link"),
            "address_link": root.get("address_link"),
            "canonical_address": canonical_address(address),
            "display_address": address,
            "longitude": lon,
            "latitude": lat,
            "municipality": root.get("municipality"),
            "municipality_name": root.get("municipality_name"),
            "place_name": root.get("place_name"),
            "address_aliases": sorted(aliases_by_apid.get(apid, set())),
            "source_keys": [SOURCE_KEY],
            "is_original_poc_property": False,
            "poc_property_keys": [],
            "poc_tower_statuses": [],
            "legacy_geo_ids": [],
            "linked_address_point_ids": [],
            "identity_basis": "TDSB_LITERAL_OFFICIAL_ADDRESS_TO_CURRENT_ADDRESS_POINT_ROOT",
            "identity_confidence": "DETERMINISTIC",
            "identity_contract_version": "toronto-address-point-1.1",
            "coordinate_basis": "CITY_ADDRESS_POINTS_4326_GEOMETRY_MULTIPOINT",
            "poc_identity_resolutions": [],
        }
        new_properties.append(prop)
        property_by_id[pid] = prop

    if len(new_properties) != EXPECTED_NEW_PROPERTIES:
        raise RuntimeError("TDSB new-property count changed unexpectedly")
    properties.extend(new_properties)
    properties.sort(key=lambda item: clean_text(item.get("property_id")))
    if len(properties) != EXPECTED_FINAL_PROPERTIES:
        raise RuntimeError(f"TDSB final property count mismatch: {len(properties)}")
    if len({clean_text(item.get("address_point_id")) for item in properties}) != EXPECTED_FINAL_PROPERTIES:
        raise RuntimeError("TDSB apply created duplicate Address Point IDs")
    for prop in properties:
        pid = clean_text(prop.get("property_id"))
        if pid in baseline_property_json:
            after = json.dumps(prop, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
            if after != baseline_property_json[pid]:
                raise RuntimeError(f"TDSB apply mutated recovery-baseline property object: {pid}")

    links_payload = read_json(MARKET / "property_source_links.json") or {}
    existing_links = [item for item in links_payload.get("links", []) if isinstance(item, dict)]
    if len(existing_links) != EXPECTED_BASE_LINKS:
        raise RuntimeError(f"TDSB apply requires {EXPECTED_BASE_LINKS} recovery-baseline links, found {len(existing_links)}")
    if any(clean_text(item.get("source_key")) == SOURCE_KEY for item in existing_links):
        raise RuntimeError("TDSB property source links already exist; refusing to duplicate ingestion")

    new_links: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if clean_text(row.get("resolution_status")) != "EXACT_LITERAL_TDSB_CIVIC_ADDRESS_TO_UNIQUE_CURRENT_ROOT":
            continue
        apid = clean_text(row.get("address_point_id"))
        pid = f"toronto-address-point:{apid}"
        if pid not in property_by_id:
            raise RuntimeError(f"Resolved TDSB row references missing property: {pid}")
        current_address = clean_text(row.get("current_address"))
        if current_address != clean_text(property_by_id[pid].get("display_address")):
            raise RuntimeError(f"TDSB row current address disagrees with property spine: {pid}")
        new_links.append({
            "property_id": pid,
            "source_key": SOURCE_KEY,
            "source_record_id": stable_source_record_id(SOURCE_KEY, row),
            "source_row_index": index,
            "match_basis": "EXACT_LITERAL_TDSB_CIVIC_ADDRESS_TO_UNIQUE_CURRENT_ROOT",
            "source_address": current_address,
        })

    if len(new_links) != EXPECTED_MATCHED_ROWS:
        raise RuntimeError(f"Expected {EXPECTED_MATCHED_ROWS} TDSB source links, found {len(new_links)}")
    all_links = existing_links + new_links
    identities = [
        (clean_text(item.get("property_id")), clean_text(item.get("source_key")), clean_text(item.get("source_record_id")))
        for item in all_links
    ]
    if len(identities) != len(set(identities)):
        raise RuntimeError("TDSB apply created duplicate property/source/record identities")
    all_links.sort(key=lambda item: (clean_text(item.get("property_id")), clean_text(item.get("source_key")), clean_text(item.get("source_record_id"))))
    if len(all_links) != EXPECTED_FINAL_LINKS:
        raise RuntimeError(f"TDSB final source-link count mismatch: {len(all_links)}")

    source_summaries = dict(links_payload.get("sources") or {})
    if SOURCE_KEY in source_summaries:
        raise RuntimeError("TDSB source summary already exists")
    source_summaries[SOURCE_KEY] = {
        "status": "JOINED_EXACT_LITERAL_ADDRESS",
        "source_records": EXPECTED_SOURCE_ROWS,
        "records_with_property_address": EXPECTED_SOURCE_ROWS,
        "matched_records": EXPECTED_MATCHED_ROWS,
        "matched_canonical_properties": EXPECTED_MATCHED_ROOTS,
        "unmatched_source_records": EXPECTED_UNMATCHED_ROWS,
        "renewal_schools": int(metadata.get("renewal_schools") or 0),
        "resolved_schools": EXPECTED_MATCHED_SCHOOLS,
        "ambiguous_schools_not_forced": int(metadata.get("ambiguous_schools_not_forced") or 0),
        "unresolved_schools_not_forced": int(metadata.get("unresolved_schools_not_forced") or 0),
        "explicit_cooling_tower_schools": EXPECTED_EXPLICIT_TOWER_SCHOOLS,
        "resolution_basis_counts": {
            "EXACT_LITERAL_TDSB_CIVIC_ADDRESS_TO_UNIQUE_CURRENT_ROOT": EXPECTED_MATCHED_ROWS,
            "UNLINKED_AMBIGUOUS_OR_NO_EXACT_CURRENT_ROOT": EXPECTED_UNMATCHED_ROWS,
        },
        "identity_limitation": "Only exact literal official TDSB school addresses resolving to one current City Address Point root are joined. Four ambiguous and fourteen unmatched schools remain unlinked.",
        "scope_limitation": "Non-cooling-tower renewal rows are supporting mechanical renewal intelligence only and do not establish cooling-tower presence.",
        "role_semantics": "TDSB facility-condition renewal records create no organization relationship role.",
    }
    if len(source_summaries) != EXPECTED_SOURCE_SUMMARY_ENTRIES:
        raise RuntimeError(f"Expected {EXPECTED_SOURCE_SUMMARY_ENTRIES} source summary entries after TDSB apply, found {len(source_summaries)}")

    spine["generated_at"] = utc_now()
    spine["properties"] = properties
    spine_counts = dict(spine.get("counts") or {})
    spine_counts["canonical_properties_resolved"] = len(properties)
    spine_counts["expanded_properties_beyond_original_poc"] = sum(not bool(item.get("is_original_poc_property")) for item in properties)
    spine_counts["properties_with_usable_coordinates"] = sum(item.get("longitude") is not None and item.get("latitude") is not None for item in properties)
    spine["counts"] = spine_counts
    write_json(MARKET / "property_spine.json", spine)

    links_payload["generated_at"] = utc_now()
    links_payload["sources"] = source_summaries
    links_payload["links"] = all_links
    links_payload["counts"] = {
        "canonical_properties": len(properties),
        "total_source_links": len(all_links),
        "properties_with_any_new_link": len({clean_text(item.get("property_id")) for item in all_links if clean_text(item.get("property_id"))}),
        "source_family_count": len(source_summaries),
    }
    write_json(MARKET / "property_source_links.json", links_payload)

    graph = read_json(MARKET / "entity_graph.json") or {}
    graph_edges = [item for item in graph.get("edges", []) if isinstance(item, dict)]
    if len(graph_edges) != EXPECTED_BASE_GRAPH_EDGES:
        raise RuntimeError(f"TDSB apply must preserve {EXPECTED_BASE_GRAPH_EDGES} relationship edges")
    graph_nodes = [item for item in graph.get("nodes", []) if isinstance(item, dict)]
    graph_nodes_by_id = {clean_text(item.get("node_id")): item for item in graph_nodes if clean_text(item.get("node_id"))}
    for prop in new_properties:
        if prop["property_id"] in graph_nodes_by_id:
            raise RuntimeError(f"TDSB graph property node unexpectedly exists: {prop['property_id']}")
        graph_nodes_by_id[prop["property_id"]] = property_node(prop)
    graph["generated_at"] = utc_now()
    graph["nodes"] = list(graph_nodes_by_id.values())
    graph["edges"] = graph_edges
    diagnostics = dict(graph.get("diagnostics") or {})
    diagnostics[SOURCE_KEY] = {
        "source_records": EXPECTED_SOURCE_ROWS,
        "matched_source_records": EXPECTED_MATCHED_ROWS,
        "matched_schools": EXPECTED_MATCHED_SCHOOLS,
        "matched_property_roots": EXPECTED_MATCHED_ROOTS,
        "new_properties": EXPECTED_NEW_PROPERTIES,
        "unlinked_source_records": EXPECTED_UNMATCHED_ROWS,
        "explicit_cooling_tower_schools": EXPECTED_EXPLICIT_TOWER_SCHOOLS,
        "relationship_edges_added": 0,
        "tower_status_promotions": 0,
        "scope_limitation": "Mechanical renewal context does not establish cooling-tower presence unless the source row explicitly says cooling tower; explicit tower schools were already documentary-confirmed before this ingestion.",
    }
    graph["diagnostics"] = diagnostics
    recompute_graph_counts(graph)
    if int((graph.get("counts") or {}).get("edges") or 0) != EXPECTED_BASE_GRAPH_EDGES:
        raise RuntimeError("TDSB apply changed relationship edge count")
    if int((graph.get("counts") or {}).get("property_nodes") or 0) != EXPECTED_FINAL_PROPERTIES:
        raise RuntimeError("TDSB graph property-node count does not match expanded spine")
    write_json(MARKET / "entity_graph.json", graph)

    linked_source_families = len({clean_text(item.get("source_key")) for item in all_links if clean_text(item.get("source_key"))})
    if linked_source_families != EXPECTED_LINKED_SOURCE_FAMILIES:
        raise RuntimeError(f"Expected {EXPECTED_LINKED_SOURCE_FAMILIES} linked source families, found {linked_source_families}")

    signal_row_counts = Counter(signal for row in resolved_rows for signal in (row.get("signals") or []))
    report = {
        "schema_version": "toronto-tdsb-mechanical-renewal-apply-1.0",
        "generated_at": utc_now(),
        "status": "PASSED",
        "contract": "Adds source-backed TDSB mechanical renewal evidence using only the verified strict-SHA source snapshot. Existing recovery-baseline properties are immutable; 289 new current City Address Point properties are appended. All 826 source rows are preserved, 782 exact-resolved rows are linked, and 44 rows at ambiguous/unmatched schools remain unlinked. No relationship edges or tower-status promotions are created.",
        "baseline": {
            "properties": EXPECTED_BASE_PROPERTIES,
            "source_links": EXPECTED_BASE_LINKS,
            "relationship_edges": EXPECTED_BASE_GRAPH_EDGES,
        },
        "metrics": {
            "source_records": EXPECTED_SOURCE_ROWS,
            "linked_records": EXPECTED_MATCHED_ROWS,
            "unlinked_records": EXPECTED_UNMATCHED_ROWS,
            "matched_schools": EXPECTED_MATCHED_SCHOOLS,
            "matched_property_roots": EXPECTED_MATCHED_ROOTS,
            "new_properties": EXPECTED_NEW_PROPERTIES,
            "final_properties": EXPECTED_FINAL_PROPERTIES,
            "final_source_links": EXPECTED_FINAL_LINKS,
            "relationship_edges_before_and_after": EXPECTED_BASE_GRAPH_EDGES,
            "linked_source_families": linked_source_families,
            "source_summary_entries": len(source_summaries),
            "explicit_cooling_tower_schools": EXPECTED_EXPLICIT_TOWER_SCHOOLS,
            "tower_status_promotions": 0,
            "relationship_edges_added": 0,
        },
        "resolved_signal_row_counts": dict(sorted(signal_row_counts.items())),
        "new_property_ids": sorted(item["property_id"] for item in new_properties),
        "explicit_cooling_tower_school_ids": sorted(explicit_tower_school_ids, key=int),
        "unlinked_source_rows": [
            {
                "source_record_id": stable_source_record_id(SOURCE_KEY, row),
                "school_id": row.get("school_id"),
                "school_name": row.get("school_name"),
                "published_address": row.get("published_address"),
                "resolution_status": row.get("resolution_status"),
                "renewal_text": row.get("renewal_text"),
            }
            for row in unresolved_rows
        ],
    }
    write_json(MARKET / "tdsb_mechanical_renewal_apply_report.json", report)
    print(json.dumps({key: value for key, value in report.items() if key not in {"new_property_ids", "unlinked_source_rows"}}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
