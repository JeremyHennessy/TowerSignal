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
WAREHOUSE = ROOT / "data/toronto/warehouse/current/open_licensed"
MANIFEST = MARKET / "building_permit_recovery_manifest.json"

SOURCE_FILES = {
    "toronto_building_permits_active_targeted": WAREHOUSE / "toronto_building_permits_active_targeted.json",
    "toronto_building_permits_cleared_targeted_since_2017": WAREHOUSE / "toronto_building_permits_cleared_targeted_since_2017.json",
}

STRICT_BASELINE_SHA = "101c6808b22bb5ce69a16697f97df95424ad0e2c"
EXPECTED_BASE_PROPERTIES = 13371
EXPECTED_BASE_LINKS = 40012
EXPECTED_BASE_PERMIT_LINKS = 1244
EXPECTED_RECOVERED_ROWS = 47
EXPECTED_NEW_PROPERTIES = 9
EXPECTED_REMAINING_UNRESOLVED = 3
EXPECTED_FINAL_PROPERTIES = 13380
EXPECTED_FINAL_LINKS = 40059
EXPECTED_FINAL_PERMIT_LINKS = 1291
EXPECTED_FINAL_PERMIT_PROPERTIES = 700
EXPECTED_RELATIONSHIP_EDGES = 6343
EXPECTED_LINKED_SOURCE_FAMILIES = 16


def permit_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in payload.get("rows", []) if isinstance(row, dict)]


def manifest_recoveries(payload: dict[str, Any]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for raw in payload.get("recoveries") or []:
        if not isinstance(raw, list) or len(raw) != 5:
            raise RuntimeError(f"Invalid recovery manifest entry: {raw!r}")
        source_key, permit_identity, apid, basis, address = [clean_text(value) for value in raw]
        if not all((source_key, permit_identity, apid, basis, address)):
            raise RuntimeError(f"Incomplete recovery manifest entry: {raw!r}")
        output.append({
            "source_key": source_key,
            "permit_identity": permit_identity,
            "address_point_id": apid,
            "property_id": f"toronto-address-point:{apid}",
            "recovery_basis": basis,
            "resolved_address": address,
        })
    return output


def remaining_unresolved(payload: dict[str, Any]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for raw in payload.get("remaining_unresolved") or []:
        if not isinstance(raw, list) or len(raw) != 3:
            raise RuntimeError(f"Invalid unresolved manifest entry: {raw!r}")
        source_key, permit_identity, reason = [clean_text(value) for value in raw]
        output.append({"source_key": source_key, "permit_identity": permit_identity, "reason": reason})
    return output


def main() -> None:
    manifest = read_json(MANIFEST) or {}
    if clean_text(manifest.get("strict_baseline_sha")) != STRICT_BASELINE_SHA:
        raise RuntimeError("Recovery manifest baseline SHA mismatch")
    recoveries = manifest_recoveries(manifest)
    unresolved_manifest = remaining_unresolved(manifest)
    if len(recoveries) != EXPECTED_RECOVERED_ROWS:
        raise RuntimeError(f"Expected {EXPECTED_RECOVERED_ROWS} recovery rows, found {len(recoveries)}")
    if len(unresolved_manifest) != EXPECTED_REMAINING_UNRESOLVED:
        raise RuntimeError(f"Expected {EXPECTED_REMAINING_UNRESOLVED} remaining unresolved rows")
    recovery_keys = {(item["source_key"], item["permit_identity"]) for item in recoveries}
    if len(recovery_keys) != len(recoveries):
        raise RuntimeError("Recovery manifest contains duplicate source/permit identities")
    unresolved_keys = {(item["source_key"], item["permit_identity"]) for item in unresolved_manifest}
    if recovery_keys & unresolved_keys:
        raise RuntimeError("A permit cannot be both recovered and unresolved")

    snapshots: dict[str, dict[str, Any]] = {}
    rows_by_source: dict[str, list[dict[str, Any]]] = {}
    row_lookup: dict[tuple[str, str], tuple[int, dict[str, Any]]] = {}
    for source_key, path in SOURCE_FILES.items():
        payload = read_json(path) or {}
        snapshots[source_key] = payload
        rows = permit_rows(payload)
        rows_by_source[source_key] = rows
        for index, row in enumerate(rows):
            identity = clean_text(row.get("_towersignal_permit_identity"))
            if not identity:
                raise RuntimeError(f"Persisted permit snapshot row missing identity: {source_key}:{index}")
            key = (source_key, identity)
            if key in row_lookup:
                raise RuntimeError(f"Duplicate persisted permit identity: {key}")
            row_lookup[key] = (index, row)

    strict_unresolved_keys = {
        (source_key, clean_text(row.get("_towersignal_permit_identity")))
        for source_key, rows in rows_by_source.items()
        for row in rows
        if not clean_text(row.get("_towersignal_root_address_point_id"))
    }
    if len(strict_unresolved_keys) != 50:
        raise RuntimeError(f"Strict snapshots no longer contain 50 unresolved permit rows: {len(strict_unresolved_keys)}")
    if recovery_keys | unresolved_keys != strict_unresolved_keys:
        missing = sorted(strict_unresolved_keys - (recovery_keys | unresolved_keys))
        extra = sorted((recovery_keys | unresolved_keys) - strict_unresolved_keys)
        raise RuntimeError(f"Recovery manifest does not partition strict unresolved rows; missing={missing}, extra={extra}")

    spine = read_json(MARKET / "property_spine.json") or {}
    properties = [item for item in spine.get("properties", []) if isinstance(item, dict)]
    if len(properties) != EXPECTED_BASE_PROPERTIES:
        raise RuntimeError(f"Recovery requires {EXPECTED_BASE_PROPERTIES} strict-baseline properties, found {len(properties)}")
    property_by_id = {clean_text(prop.get("property_id")): prop for prop in properties}
    if len(property_by_id) != EXPECTED_BASE_PROPERTIES:
        raise RuntimeError("Strict-baseline property IDs are not unique")
    baseline_property_json = {
        pid: json.dumps(prop, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
        for pid, prop in property_by_id.items()
    }

    roots = manifest.get("new_property_roots") or {}
    if not isinstance(roots, dict) or len(roots) != EXPECTED_NEW_PROPERTIES:
        raise RuntimeError(f"Recovery manifest must contain exactly {EXPECTED_NEW_PROPERTIES} new root records")
    recovery_apids = {item["address_point_id"] for item in recoveries}
    new_apids = set(roots)
    if not new_apids.issubset(recovery_apids):
        raise RuntimeError("Manifest contains a new root that is not referenced by a recovery")
    for apid in new_apids:
        if f"toronto-address-point:{apid}" in property_by_id:
            raise RuntimeError(f"Recovery root unexpectedly already exists in strict baseline: {apid}")

    links_payload = read_json(MARKET / "property_source_links.json") or {}
    existing_links = [item for item in links_payload.get("links", []) if isinstance(item, dict)]
    if len(existing_links) != EXPECTED_BASE_LINKS:
        raise RuntimeError(f"Recovery requires {EXPECTED_BASE_LINKS} strict-baseline source links, found {len(existing_links)}")
    permit_sources = set(SOURCE_FILES)
    existing_permit_links = [item for item in existing_links if clean_text(item.get("source_key")) in permit_sources]
    if len(existing_permit_links) != EXPECTED_BASE_PERMIT_LINKS:
        raise RuntimeError(f"Recovery requires {EXPECTED_BASE_PERMIT_LINKS} strict permit links, found {len(existing_permit_links)}")
    existing_link_ids = {
        (clean_text(item.get("source_key")), clean_text(item.get("source_record_id")))
        for item in existing_links
    }

    recovery_rows: list[dict[str, Any]] = []
    aliases_by_new_apid: dict[str, set[str]] = defaultdict(set)
    sources_by_new_apid: dict[str, set[str]] = defaultdict(set)
    legacy_ids_by_new_apid: dict[str, set[str]] = defaultdict(set)
    bases_by_new_apid: dict[str, set[str]] = defaultdict(set)
    new_links: list[dict[str, Any]] = []

    for item in recoveries:
        key = (item["source_key"], item["permit_identity"])
        match = row_lookup.get(key)
        if not match:
            raise RuntimeError(f"Recovery row not found in persisted snapshots: {key}")
        row_index, row = match
        if clean_text(row.get("_towersignal_root_address_point_id")):
            raise RuntimeError(f"Recovery row is no longer strict-unresolved: {key}")
        source_record_id = stable_source_record_id(item["source_key"], row)
        if (item["source_key"], source_record_id) in existing_link_ids:
            raise RuntimeError(f"Recovery would duplicate an existing source record: {key}")
        property_id = item["property_id"]
        if property_id not in property_by_id and item["address_point_id"] not in roots:
            raise RuntimeError(f"Recovered property is neither strict-existing nor a declared new root: {property_id}")
        if property_id in property_by_id:
            existing_address = clean_text(property_by_id[property_id].get("display_address"))
            if existing_address != item["resolved_address"]:
                raise RuntimeError(f"Recovered address disagrees with strict property {property_id}: {existing_address!r} != {item['resolved_address']!r}")
        else:
            apid = item["address_point_id"]
            aliases_by_new_apid[apid].add(clean_text(row.get("_towersignal_source_address")))
            sources_by_new_apid[apid].add(item["source_key"])
            bases_by_new_apid[apid].add(item["recovery_basis"])
            permit_geo_id = clean_text(row.get("GEO_ID"))
            if permit_geo_id and permit_geo_id != apid:
                legacy_ids_by_new_apid[apid].add(permit_geo_id)
        new_links.append({
            "property_id": property_id,
            "source_key": item["source_key"],
            "source_record_id": source_record_id,
            "source_row_index": row_index,
            "match_basis": item["recovery_basis"],
            "source_address": clean_text(row.get("_towersignal_source_address")) or None,
        })
        recovery_rows.append({
            **item,
            "source_record_id": source_record_id,
            "source_row_index": row_index,
            "source_address": clean_text(row.get("_towersignal_source_address")) or None,
            "signals": row.get("_towersignal_signals") or [],
            "status": row.get("STATUS"),
            "description": row.get("DESCRIPTION"),
        })

    if len(new_links) != EXPECTED_RECOVERED_ROWS:
        raise RuntimeError("Recovery link count changed unexpectedly")

    new_properties: list[dict[str, Any]] = []
    for apid in sorted(new_apids, key=lambda value: int(value)):
        root = roots[apid]
        if clean_text(root.get("address")) == "":
            raise RuntimeError(f"New root missing address: {apid}")
        lon, lat = root.get("longitude"), root.get("latitude")
        if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)) or not (-80 <= lon <= -78) or not (43 <= lat <= 44.5):
            raise RuntimeError(f"New recovery root has invalid coordinates: {apid}: {lon}, {lat}")
        property_id = f"toronto-address-point:{apid}"
        prop = {
            "property_id": property_id,
            "canonical_identifier_type": "CITY_OF_TORONTO_ADDRESS_POINT_ID",
            "canonical_identifier": apid,
            "address_point_id": apid,
            "address_id": root.get("address_id"),
            "address_string_id": root.get("address_string_id"),
            "centreline_id": root.get("centreline_id"),
            "address_point_id_link": root.get("address_point_id_link"),
            "address_id_link": root.get("address_id_link"),
            "address_link": None,
            "canonical_address": canonical_address(root.get("address")),
            "display_address": root.get("address"),
            "longitude": lon,
            "latitude": lat,
            "municipality": root.get("municipality"),
            "municipality_name": root.get("municipality_name"),
            "place_name": root.get("place_name"),
            "address_aliases": sorted(value for value in aliases_by_new_apid.get(apid, set()) if value),
            "source_keys": sorted(sources_by_new_apid.get(apid, set())),
            "is_original_poc_property": False,
            "poc_property_keys": [],
            "poc_tower_statuses": [],
            "legacy_geo_ids": [],
            "linked_address_point_ids": sorted(legacy_ids_by_new_apid.get(apid, set())),
            "identity_basis": "TARGETED_BUILDING_PERMIT_DETERMINISTIC_RECOVERY_TO_CURRENT_ADDRESS_POINT_ROOT",
            "identity_confidence": "DETERMINISTIC",
            "identity_contract_version": "toronto-address-point-1.1",
            "coordinate_basis": "CITY_ADDRESS_POINTS_4326_GEOMETRY_MULTIPOINT",
            "poc_identity_resolutions": [],
            "permit_recovery_bases": sorted(bases_by_new_apid.get(apid, set())),
        }
        new_properties.append(prop)
        property_by_id[property_id] = prop

    if len(new_properties) != EXPECTED_NEW_PROPERTIES:
        raise RuntimeError(f"Expected {EXPECTED_NEW_PROPERTIES} new recovery properties, found {len(new_properties)}")
    properties.extend(new_properties)
    properties.sort(key=lambda item: clean_text(item.get("property_id")))
    if len(properties) != EXPECTED_FINAL_PROPERTIES:
        raise RuntimeError(f"Final recovery property count mismatch: {len(properties)}")
    if len({clean_text(item.get("address_point_id")) for item in properties}) != EXPECTED_FINAL_PROPERTIES:
        raise RuntimeError("Recovery created duplicate Address Point IDs")
    for prop in properties:
        pid = clean_text(prop.get("property_id"))
        if pid in baseline_property_json:
            after = json.dumps(prop, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
            if after != baseline_property_json[pid]:
                raise RuntimeError(f"Recovery mutated strict-baseline property object: {pid}")

    all_links = existing_links + new_links
    link_identities = [
        (clean_text(item.get("property_id")), clean_text(item.get("source_key")), clean_text(item.get("source_record_id")))
        for item in all_links
    ]
    if len(link_identities) != len(set(link_identities)):
        raise RuntimeError("Recovery created duplicate property/source/record link identities")
    if len(all_links) != EXPECTED_FINAL_LINKS:
        raise RuntimeError(f"Final recovery link count mismatch: {len(all_links)}")
    all_links.sort(key=lambda item: (clean_text(item.get("property_id")), clean_text(item.get("source_key")), clean_text(item.get("source_record_id"))))

    permit_links = [item for item in all_links if clean_text(item.get("source_key")) in permit_sources]
    permit_properties = {clean_text(item.get("property_id")) for item in permit_links}
    if len(permit_links) != EXPECTED_FINAL_PERMIT_LINKS:
        raise RuntimeError(f"Expected {EXPECTED_FINAL_PERMIT_LINKS} permit links after recovery, found {len(permit_links)}")
    if len(permit_properties) != EXPECTED_FINAL_PERMIT_PROPERTIES:
        raise RuntimeError(f"Expected {EXPECTED_FINAL_PERMIT_PROPERTIES} permit-linked properties after recovery, found {len(permit_properties)}")

    source_summaries = dict(links_payload.get("sources") or {})
    recovery_counts_by_source: dict[str, Counter[str]] = defaultdict(Counter)
    for row in recovery_rows:
        recovery_counts_by_source[row["source_key"]][row["recovery_basis"]] += 1
    unresolved_by_source = Counter(item["source_key"] for item in unresolved_manifest)
    for source_key in SOURCE_FILES:
        rows = rows_by_source[source_key]
        source_links = [item for item in all_links if clean_text(item.get("source_key")) == source_key]
        basis_counts = Counter(clean_text(item.get("match_basis")) for item in source_links)
        if unresolved_by_source[source_key]:
            basis_counts["NO_CURRENT_ADDRESS_POINT_IDENTITY"] += unresolved_by_source[source_key]
        if sum(basis_counts.values()) != len(rows):
            raise RuntimeError(f"Recovery resolution-basis accounting does not cover all {source_key} rows")
        source_summaries[source_key] = {
            **dict(source_summaries.get(source_key) or {}),
            "status": "JOINED_WITH_DETERMINISTIC_RECOVERY",
            "source_records": len(rows),
            "records_with_property_address": len(rows),
            "matched_records": len(source_links),
            "matched_canonical_properties": len({clean_text(item.get("property_id")) for item in source_links}),
            "unresolved_rows_not_forced": unresolved_by_source[source_key],
            "geo_id_address_conflict_rows": sum(bool(row.get("_towersignal_permit_geo_id_address_conflict")) for row in rows),
            "resolution_basis_counts": dict(sorted(basis_counts.items())),
            "recovered_rows": sum(recovery_counts_by_source[source_key].values()),
            "recovery_basis_counts": dict(sorted(recovery_counts_by_source[source_key].items())),
        }

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
    if len(graph_edges) != EXPECTED_RELATIONSHIP_EDGES:
        raise RuntimeError(f"Recovery must preserve {EXPECTED_RELATIONSHIP_EDGES} relationship edges")
    if any(clean_text(item.get("source_key")) in permit_sources for item in graph_edges):
        raise RuntimeError("Permit recovery must not create organization relationship edges")
    graph_nodes = [item for item in graph.get("nodes", []) if isinstance(item, dict)]
    graph_nodes_by_id = {clean_text(item.get("node_id")): item for item in graph_nodes if clean_text(item.get("node_id"))}
    for prop in new_properties:
        if prop["property_id"] in graph_nodes_by_id:
            raise RuntimeError(f"Recovery graph node already exists: {prop['property_id']}")
        graph_nodes_by_id[prop["property_id"]] = property_node(prop)
    graph["generated_at"] = utc_now()
    graph["nodes"] = list(graph_nodes_by_id.values())
    graph["edges"] = graph_edges
    diagnostics = dict(graph.get("diagnostics") or {})
    diagnostics["building_permit_deterministic_recovery"] = {
        "recovered_rows": EXPECTED_RECOVERED_ROWS,
        "new_properties": EXPECTED_NEW_PROPERTIES,
        "remaining_unresolved_rows": EXPECTED_REMAINING_UNRESOLVED,
        "relationship_edges_added": 0,
        "tower_status_promotions": 0,
    }
    graph["diagnostics"] = diagnostics
    recompute_graph_counts(graph)
    if int((graph.get("counts") or {}).get("edges") or 0) != EXPECTED_RELATIONSHIP_EDGES:
        raise RuntimeError("Recovery changed relationship edge count")
    if int((graph.get("counts") or {}).get("property_nodes") or 0) != EXPECTED_FINAL_PROPERTIES:
        raise RuntimeError("Recovery graph property-node count does not match expanded spine")
    write_json(MARKET / "entity_graph.json", graph)

    linked_source_families = len({clean_text(item.get("source_key")) for item in all_links if clean_text(item.get("source_key"))})
    if linked_source_families != EXPECTED_LINKED_SOURCE_FAMILIES:
        raise RuntimeError(f"Recovery changed linked source-family count: {linked_source_families}")

    report = {
        "schema_version": "toronto-building-permit-recovery-1.0",
        "generated_at": utc_now(),
        "status": "PASSED",
        "strict_baseline_sha": STRICT_BASELINE_SHA,
        "contract": "Adds only the 47 permit rows in the static deterministic recovery manifest to their proven current Address Point roots. Existing strict-baseline properties are immutable; nine new City root properties are appended. The three remaining permit identities stay unresolved. No permit organization relationship or tower-evidence promotion occurs.",
        "baseline": {
            "properties": EXPECTED_BASE_PROPERTIES,
            "source_links": EXPECTED_BASE_LINKS,
            "permit_links": EXPECTED_BASE_PERMIT_LINKS,
            "relationship_edges": EXPECTED_RELATIONSHIP_EDGES,
        },
        "metrics": {
            "recovered_rows": len(recovery_rows),
            "new_properties": len(new_properties),
            "remaining_unresolved_rows": len(unresolved_manifest),
            "final_properties": len(properties),
            "final_source_links": len(all_links),
            "final_permit_links": len(permit_links),
            "final_permit_linked_properties": len(permit_properties),
            "relationship_edges_before_and_after": EXPECTED_RELATIONSHIP_EDGES,
            "linked_source_families": linked_source_families,
            "source_summary_entries": len(source_summaries),
        },
        "recovery_basis_counts": dict(sorted(Counter(item["recovery_basis"] for item in recovery_rows).items())),
        "source_recovery_counts": {source: dict(sorted(counter.items())) for source, counter in sorted(recovery_counts_by_source.items())},
        "recovered_records": recovery_rows,
        "new_property_ids": sorted(item["property_id"] for item in new_properties),
        "remaining_unresolved": unresolved_manifest,
        "evidence_runs": manifest.get("evidence_runs") or {},
    }
    write_json(MARKET / "building_permit_recovery_report.json", report)
    print(json.dumps({key: value for key, value in report.items() if key not in {"recovered_records", "new_property_ids"}}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
