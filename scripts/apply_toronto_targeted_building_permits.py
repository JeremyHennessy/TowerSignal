from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from toronto_final_identity_cleanup import canonical_address
from toronto_market_common import clean_text, read_json, utc_now, write_json
from toronto_source_identity import stable_source_record_id

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data/toronto/market/current"
WAREHOUSE = ROOT / "data/toronto/warehouse/current/open_licensed"

SOURCE_CONFIG = {
    "toronto_building_permits_active_targeted": {
        "snapshot": WAREHOUSE / "toronto_building_permits_active_targeted.json",
        "expected_rows": 573,
        "expected_links": 540,
        "expected_properties": 327,
        "lifecycle": "ACTIVE",
    },
    "toronto_building_permits_cleared_targeted_since_2017": {
        "snapshot": WAREHOUSE / "toronto_building_permits_cleared_targeted_since_2017.json",
        "expected_rows": 721,
        "expected_links": 704,
        "expected_properties": 429,
        "lifecycle": "CLEARED_SINCE_2017",
    },
}

EXPECTED_CURRENT_PROPERTIES = 13065
EXPECTED_NEW_PROPERTIES = 306
EXPECTED_FINAL_PROPERTIES = 13371
EXPECTED_NEW_LINKS = 1244
EXPECTED_UNRESOLVED_ROWS = 50
EXPECTED_EXISTING_LINKS = 38768
EXPECTED_FINAL_LINKS = 40012
EXPECTED_GRAPH_EDGES = 6343


def recompute_graph_counts(graph: dict[str, Any]) -> None:
    nodes = [node for node in graph.get("nodes", []) if isinstance(node, dict)]
    edges = [edge for edge in graph.get("edges", []) if isinstance(edge, dict)]
    rel_counts: Counter[str] = Counter()
    property_sets: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        relationship = clean_text(edge.get("relationship"))
        pid = clean_text(edge.get("property_id") or edge.get("to_node"))
        if relationship and pid:
            rel_counts[relationship] += 1
            property_sets[relationship].add(pid)
    graph["counts"] = {
        "nodes": len(nodes),
        "property_nodes": sum(node.get("node_type") == "PROPERTY" for node in nodes),
        "organization_nodes": sum(node.get("node_type") == "ORGANIZATION" for node in nodes),
        "edges": len(edges),
        "relationships": dict(sorted(rel_counts.items())),
        "properties_by_relationship": {key: len(value) for key, value in sorted(property_sets.items())},
        "chain_coverage": {
            "properties_with_owner": len(property_sets.get("OWNER_OF", set())),
            "properties_with_property_manager": len(property_sets.get("PROPERTY_MANAGER_OF", set())),
            "properties_with_engineer_or_consultant": len(
                property_sets.get("ENGINEER_FOR", set())
                | property_sets.get("MECHANICAL_ENGINEER_FOR", set())
                | property_sets.get("CONSULTANT_FOR", set())
            ),
            "properties_with_contractor_or_successful_bidder": len(
                property_sets.get("CONTRACTOR_AT_PROPERTY", set())
                | property_sets.get("MECHANICAL_CONTRACTOR_AT_PROPERTY", set())
                | property_sets.get("SUCCESSFUL_BIDDER_AT_PROPERTY", set())
            ),
            "properties_with_facility_operator_or_reporter": len(property_sets.get("FACILITY_OPERATOR_OR_REPORTER_AT", set())),
            "properties_with_chemtrac_reporting_facility": len(property_sets.get("CHEMTRAC_REPORTING_FACILITY_AT", set())),
            "properties_with_licence_holder": len(property_sets.get("LICENCE_HOLDER_AT_PROPERTY", set())),
        },
    }


def permit_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in payload.get("rows", []) if isinstance(row, dict)]


def source_record_id(source_key: str, row: dict[str, Any]) -> str:
    return stable_source_record_id(source_key, row)


def property_node(prop: dict[str, Any]) -> dict[str, Any]:
    return {
        "node_id": prop["property_id"],
        "node_type": "PROPERTY",
        "address": prop.get("display_address"),
        "address_point_id": prop.get("address_point_id"),
    }


def main() -> None:
    spine = read_json(MARKET / "property_spine.json") or {}
    properties = [item for item in spine.get("properties", []) if isinstance(item, dict)]
    if len(properties) != EXPECTED_CURRENT_PROPERTIES:
        raise RuntimeError(f"Permit apply requires {EXPECTED_CURRENT_PROPERTIES} baseline properties, found {len(properties)}")

    baseline_properties_json = {
        clean_text(prop.get("property_id")): json.dumps(prop, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
        for prop in properties
    }
    by_apid = {
        clean_text(prop.get("address_point_id")): prop
        for prop in properties
        if clean_text(prop.get("address_point_id"))
    }
    property_ids = {clean_text(prop.get("property_id")) for prop in properties}
    if len(by_apid) != EXPECTED_CURRENT_PROPERTIES or len(property_ids) != EXPECTED_CURRENT_PROPERTIES:
        raise RuntimeError("Baseline Toronto property identity is not one-to-one")

    source_payloads: dict[str, dict[str, Any]] = {}
    new_property_seed: dict[str, dict[str, Any]] = {}
    new_links: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    per_source_metrics: dict[str, Any] = {}

    for source_key, config in SOURCE_CONFIG.items():
        payload = read_json(config["snapshot"]) or {}
        source_payloads[source_key] = payload
        rows = permit_rows(payload)
        metadata = payload.get("metadata") or {}
        if len(rows) != config["expected_rows"]:
            raise RuntimeError(f"Permit snapshot drift for {source_key}: expected {config['expected_rows']}, found {len(rows)}")
        if int(metadata.get("targeted_row_count") or 0) != len(rows):
            raise RuntimeError(f"Permit snapshot metadata row count mismatch for {source_key}")

        source_links = 0
        source_properties: set[str] = set()
        source_unresolved = 0
        source_new_apids: set[str] = set()
        conflict_rows = 0
        resolution_counts: Counter[str] = Counter()

        for idx, row in enumerate(rows):
            apid = clean_text(row.get("_towersignal_root_address_point_id"))
            basis = clean_text(row.get("_towersignal_resolution_status")) or "NO_CURRENT_ADDRESS_POINT_IDENTITY"
            resolution_counts[basis] += 1
            conflict_rows += int(bool(row.get("_towersignal_permit_geo_id_address_conflict")))
            if not apid:
                source_unresolved += 1
                unresolved.append({
                    "source_key": source_key,
                    "source_row_index": idx,
                    "permit_identity": row.get("_towersignal_permit_identity"),
                    "permit_num": row.get("PERMIT_NUM"),
                    "revision_num": row.get("REVISION_NUM"),
                    "source_address": row.get("_towersignal_source_address"),
                    "permit_geo_id": row.get("GEO_ID"),
                    "resolution_status": basis,
                    "signals": row.get("_towersignal_signals") or [],
                    "status": row.get("STATUS"),
                    "description": row.get("DESCRIPTION"),
                })
                continue

            pid = f"toronto-address-point:{apid}"
            if apid not in by_apid and apid not in new_property_seed:
                lon = row.get("_towersignal_root_longitude")
                lat = row.get("_towersignal_root_latitude")
                if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
                    raise RuntimeError(f"New permit property {apid} missing validated Address Point coordinates")
                root_address = clean_text(row.get("_towersignal_root_address"))
                if not root_address:
                    raise RuntimeError(f"New permit property {apid} missing current root address")
                new_property_seed[apid] = {
                    "property_id": pid,
                    "canonical_identifier_type": "CITY_OF_TORONTO_ADDRESS_POINT_ID",
                    "canonical_identifier": apid,
                    "address_point_id": apid,
                    "address_id": row.get("_towersignal_root_address_id"),
                    "address_string_id": None,
                    "centreline_id": None,
                    "address_point_id_link": None,
                    "address_id_link": None,
                    "address_link": None,
                    "canonical_address": canonical_address(root_address),
                    "display_address": root_address,
                    "longitude": lon,
                    "latitude": lat,
                    "municipality": "Toronto",
                    "municipality_name": "Toronto",
                    "place_name": None,
                    "address_aliases": [],
                    "source_keys": [],
                    "is_original_poc_property": False,
                    "poc_property_keys": [],
                    "poc_tower_statuses": [],
                    "legacy_geo_ids": [],
                    "linked_address_point_ids": [],
                    "identity_basis": "TARGETED_BUILDING_PERMIT_TO_CURRENT_ADDRESS_POINT_ROOT",
                    "identity_confidence": "DETERMINISTIC",
                    "identity_contract_version": "toronto-address-point-1.1",
                    "coordinate_basis": "CITY_ADDRESS_POINTS_4326_GEOMETRY_MULTIPOINT",
                    "poc_identity_resolutions": [],
                }
            if apid not in by_apid:
                seed = new_property_seed[apid]
                seed["source_keys"] = list(dict.fromkeys([*seed.get("source_keys", []), source_key]))
                alias = clean_text(row.get("_towersignal_source_address"))
                if alias:
                    seed["address_aliases"] = list(dict.fromkeys([*seed.get("address_aliases", []), alias]))
                permit_geo_id = clean_text(row.get("GEO_ID"))
                if permit_geo_id and permit_geo_id != apid:
                    seed["linked_address_point_ids"] = list(dict.fromkeys([*seed.get("linked_address_point_ids", []), permit_geo_id]))
                source_new_apids.add(apid)

            source_links += 1
            source_properties.add(pid)
            new_links.append({
                "property_id": pid,
                "source_key": source_key,
                "source_record_id": source_record_id(source_key, row),
                "source_row_index": idx,
                "match_basis": basis,
                "source_address": clean_text(row.get("_towersignal_source_address")) or None,
            })

        if source_links != config["expected_links"]:
            raise RuntimeError(f"Permit resolved-link drift for {source_key}: expected {config['expected_links']}, found {source_links}")
        if len(source_properties) != config["expected_properties"]:
            raise RuntimeError(f"Permit property coverage drift for {source_key}: expected {config['expected_properties']}, found {len(source_properties)}")
        if source_unresolved != config["expected_rows"] - config["expected_links"]:
            raise RuntimeError(f"Permit unresolved-row drift for {source_key}")
        per_source_metrics[source_key] = {
            "source_rows": len(rows),
            "resolved_rows": source_links,
            "unresolved_rows": source_unresolved,
            "resolved_properties": len(source_properties),
            "new_properties": len(source_new_apids),
            "geo_id_address_conflict_rows": conflict_rows,
            "resolution_basis_counts": dict(sorted(resolution_counts.items())),
        }

    if len(new_links) != EXPECTED_NEW_LINKS:
        raise RuntimeError(f"Permit apply expected {EXPECTED_NEW_LINKS} source links, found {len(new_links)}")
    if len(unresolved) != EXPECTED_UNRESOLVED_ROWS:
        raise RuntimeError(f"Permit apply expected {EXPECTED_UNRESOLVED_ROWS} unresolved rows, found {len(unresolved)}")
    if len(new_property_seed) != EXPECTED_NEW_PROPERTIES:
        raise RuntimeError(f"Permit apply expected {EXPECTED_NEW_PROPERTIES} new properties, found {len(new_property_seed)}")

    new_properties = list(new_property_seed.values())
    for prop in new_properties:
        prop["source_keys"] = sorted(set(prop.get("source_keys") or []))
        prop["address_aliases"] = sorted(set(prop.get("address_aliases") or []))
        prop["linked_address_point_ids"] = sorted(set(prop.get("linked_address_point_ids") or []))
    properties.extend(new_properties)
    properties.sort(key=lambda item: clean_text(item.get("property_id")))

    if len(properties) != EXPECTED_FINAL_PROPERTIES:
        raise RuntimeError(f"Final property count drift: expected {EXPECTED_FINAL_PROPERTIES}, found {len(properties)}")
    if len({clean_text(item.get("property_id")) for item in properties}) != EXPECTED_FINAL_PROPERTIES:
        raise RuntimeError("Permit apply created duplicate property IDs")
    if len({clean_text(item.get("address_point_id")) for item in properties}) != EXPECTED_FINAL_PROPERTIES:
        raise RuntimeError("Permit apply created duplicate Address Point IDs")
    for prop in properties:
        lon, lat = prop.get("longitude"), prop.get("latitude")
        if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)) or not (-80 <= lon <= -78) or not (43 <= lat <= 44.5):
            raise RuntimeError(f"Permit property has invalid coordinates: {prop.get('property_id')}: {lon}, {lat}")
    for prop in properties:
        pid = clean_text(prop.get("property_id"))
        if pid in baseline_properties_json:
            current = json.dumps(prop, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
            if current != baseline_properties_json[pid]:
                raise RuntimeError(f"Permit apply mutated existing property object: {pid}")

    spine["generated_at"] = utc_now()
    spine["properties"] = properties
    counts = dict(spine.get("counts") or {})
    counts["canonical_properties_resolved"] = len(properties)
    counts["expanded_properties_beyond_original_poc"] = sum(not bool(item.get("is_original_poc_property")) for item in properties)
    counts["properties_with_usable_coordinates"] = sum(item.get("longitude") is not None and item.get("latitude") is not None for item in properties)
    spine["counts"] = counts
    write_json(MARKET / "property_spine.json", spine)

    links_payload = read_json(MARKET / "property_source_links.json") or {}
    existing_links = [item for item in links_payload.get("links", []) if isinstance(item, dict)]
    if len(existing_links) != EXPECTED_EXISTING_LINKS:
        raise RuntimeError(f"Permit apply requires {EXPECTED_EXISTING_LINKS} baseline links, found {len(existing_links)}")
    all_links = existing_links + new_links
    identity_tuples = [
        (clean_text(item.get("property_id")), clean_text(item.get("source_key")), clean_text(item.get("source_record_id")))
        for item in all_links
    ]
    if len(identity_tuples) != len(set(identity_tuples)):
        raise RuntimeError("Permit apply would create duplicate property/source/record link identities")
    if len(all_links) != EXPECTED_FINAL_LINKS:
        raise RuntimeError(f"Permit final link count drift: expected {EXPECTED_FINAL_LINKS}, found {len(all_links)}")
    all_links.sort(key=lambda item: (clean_text(item.get("property_id")), clean_text(item.get("source_key")), clean_text(item.get("source_record_id"))))

    sources = dict(links_payload.get("sources") or {})
    for source_key, metrics in per_source_metrics.items():
        snapshot_meta = (source_payloads[source_key].get("metadata") or {})
        sources[source_key] = {
            "status": "JOINED",
            "source_records": metrics["source_rows"],
            "records_with_property_address": metrics["source_rows"],
            "matched_records": metrics["resolved_rows"],
            "matched_canonical_properties": metrics["resolved_properties"],
            "unresolved_rows_not_forced": metrics["unresolved_rows"],
            "geo_id_address_conflict_rows": metrics["geo_id_address_conflict_rows"],
            "resolution_basis_counts": metrics["resolution_basis_counts"],
            "identity_contract": snapshot_meta.get("identity_contract"),
            "source_lifecycle": snapshot_meta.get("source_lifecycle"),
            "tower_status_policy": snapshot_meta.get("tower_status_policy"),
            "builder_role_policy": snapshot_meta.get("builder_role_policy"),
            "identity_limitation": None,
        }
    links_payload["generated_at"] = utc_now()
    links_payload["sources"] = sources
    links_payload["links"] = all_links
    links_payload["counts"] = {
        "canonical_properties": len(properties),
        "total_source_links": len(all_links),
        "properties_with_any_new_link": len({clean_text(item.get("property_id")) for item in all_links if clean_text(item.get("property_id"))}),
        "source_family_count": len(sources),
    }
    write_json(MARKET / "property_source_links.json", links_payload)

    graph = read_json(MARKET / "entity_graph.json") or {}
    graph_edges = [item for item in graph.get("edges", []) if isinstance(item, dict)]
    if len(graph_edges) != EXPECTED_GRAPH_EDGES:
        raise RuntimeError(f"Permit apply must not change baseline relationship edges; expected {EXPECTED_GRAPH_EDGES}, found {len(graph_edges)}")
    nodes_by_id = {
        clean_text(item.get("node_id")): item
        for item in (graph.get("nodes") or [])
        if isinstance(item, dict) and clean_text(item.get("node_id"))
    }
    for prop in new_properties:
        if prop["property_id"] in nodes_by_id:
            raise RuntimeError(f"New permit property already existed as graph node: {prop['property_id']}")
        nodes_by_id[prop["property_id"]] = property_node(prop)
    graph["generated_at"] = utc_now()
    graph["nodes"] = list(nodes_by_id.values())
    graph["edges"] = graph_edges
    diagnostics = dict(graph.get("diagnostics") or {})
    for source_key, metrics in per_source_metrics.items():
        diagnostics[source_key] = {
            "source_rows": metrics["source_rows"],
            "linked_rows": metrics["resolved_rows"],
            "linked_properties": metrics["resolved_properties"],
            "new_properties": metrics["new_properties"],
            "unresolved_rows_not_forced": metrics["unresolved_rows"],
            "role_limitation": "Permit source adds property/source evidence only. BUILDER_NAME is not promoted to an organization relationship.",
            "tower_status_limitation": "Permit source does not automatically change tower_evidence_status in this apply.",
        }
    graph["diagnostics"] = diagnostics
    recompute_graph_counts(graph)
    if int((graph.get("counts") or {}).get("edges") or 0) != EXPECTED_GRAPH_EDGES:
        raise RuntimeError("Permit apply changed relationship edge count")
    if int((graph.get("counts") or {}).get("property_nodes") or 0) != EXPECTED_FINAL_PROPERTIES:
        raise RuntimeError("Permit graph property-node count does not match expanded spine")
    if any(clean_text(edge.get("source_key")) in SOURCE_CONFIG for edge in graph_edges):
        raise RuntimeError("Permit source unexpectedly created organization relationship edges")
    write_json(MARKET / "entity_graph.json", graph)

    report = {
        "schema_version": "toronto-targeted-building-permit-apply-1.0",
        "generated_at": utc_now(),
        "status": "PASSED",
        "contract": "Only targeted permit revisions resolved to a current Toronto Address Point root are linked. Existing 13,065 property objects are immutable; 306 new root properties are appended. Ambiguous/missing identities are withheld. No permit organization relationship or automatic tower-status promotion occurs.",
        "baseline": {
            "properties": EXPECTED_CURRENT_PROPERTIES,
            "source_links": EXPECTED_EXISTING_LINKS,
            "relationship_edges": EXPECTED_GRAPH_EDGES,
        },
        "metrics": {
            "new_properties": len(new_properties),
            "final_properties": len(properties),
            "new_source_links": len(new_links),
            "final_source_links": len(all_links),
            "unresolved_rows_not_forced": len(unresolved),
            "relationship_edges_before_and_after": EXPECTED_GRAPH_EDGES,
            "source_summary_entries": len(sources),
            "linked_source_families": len({clean_text(item.get("source_key")) for item in all_links if clean_text(item.get("source_key"))}),
        },
        "sources": per_source_metrics,
        "unresolved_records": unresolved,
        "new_property_ids": sorted(prop["property_id"] for prop in new_properties),
    }
    write_json(MARKET / "building_permit_apply_report.json", report)
    print(json.dumps({key: value for key, value in report.items() if key not in {"unresolved_records", "new_property_ids"}}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
