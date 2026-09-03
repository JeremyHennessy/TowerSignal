from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from toronto_final_identity_cleanup import canonical_address
from toronto_market_common import clean_text, read_json, utc_now, write_json
from toronto_source_identity import stable_source_record_id

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data/toronto/market/current"
WAREHOUSE = ROOT / "data/toronto/warehouse/current"
SOURCE_KEY = "ontario_bps_energy_2024"
RELATIONSHIP = "FACILITY_OPERATOR_OR_REPORTER_AT"
EXPECTED_SOURCE_ROWS = 1863
EXPECTED_MATCHED_ROWS = 362
EXPECTED_MATCHED_PROPERTIES = 275
EXPECTED_AMBIGUOUS_ROWS = 0


def organization_id(name: str) -> str:
    normalized = " ".join(clean_text(name).upper().split())
    return "org:" + hashlib.sha1(normalized.encode()).hexdigest()[:20]


def property_index(properties: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_address: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for prop in properties:
        seen: set[str] = set()
        for raw in [prop.get("display_address"), prop.get("canonical_address"), *(prop.get("address_aliases") or [])]:
            address = canonical_address(raw)
            if not address or address in seen:
                continue
            seen.add(address)
            by_address[address].append(prop)
    return by_address


def recompute_graph_counts(graph: dict[str, Any]) -> None:
    edges = [edge for edge in graph.get("edges", []) if isinstance(edge, dict)]
    nodes = [node for node in graph.get("nodes", []) if isinstance(node, dict)]
    rel_counts: Counter[str] = Counter()
    property_sets: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        relationship = clean_text(edge.get("relationship"))
        pid = clean_text(edge.get("property_id") or edge.get("to_node"))
        if not relationship or not pid:
            continue
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
            "properties_with_facility_operator_or_reporter": len(property_sets.get(RELATIONSHIP, set())),
            "properties_with_chemtrac_reporting_facility": len(property_sets.get("CHEMTRAC_REPORTING_FACILITY_AT", set())),
            "properties_with_licence_holder": len(property_sets.get("LICENCE_HOLDER_AT_PROPERTY", set())),
        },
    }


def main() -> None:
    spine = read_json(MARKET / "property_spine.json") or {}
    properties = [item for item in spine.get("properties", []) if isinstance(item, dict)]
    if not properties:
        raise RuntimeError("Toronto property spine is missing")
    by_address = property_index(properties)

    bps_payload = read_json(WAREHOUSE / "open_licensed/ontario_bps_energy_2024.json") or {}
    rows = [item for item in bps_payload.get("toronto_candidates", []) if isinstance(item, dict)]
    declared_rows = int((bps_payload.get("metadata") or {}).get("toronto_candidate_row_count") or 0)
    if declared_rows != len(rows):
        raise RuntimeError(f"BPS candidate count mismatch: metadata={declared_rows}, rows={len(rows)}")
    if len(rows) != EXPECTED_SOURCE_ROWS:
        raise RuntimeError(f"BPS source snapshot drift: expected {EXPECTED_SOURCE_ROWS}, found {len(rows)}")

    links_payload = read_json(MARKET / "property_source_links.json") or {}
    retained_links = [
        item for item in (links_payload.get("links") or [])
        if isinstance(item, dict) and clean_text(item.get("source_key")) != SOURCE_KEY
    ]
    new_links: list[dict[str, Any]] = []
    matched_properties: set[str] = set()
    ambiguous_rows = 0
    rows_with_address = 0
    rows_with_organization = 0
    matched_rows = 0
    matched_organizations: set[str] = set()

    for idx, row in enumerate(rows):
        raw_address = clean_text(row.get("Address"))
        organization = clean_text(row.get("Organization"))
        address = canonical_address(raw_address)
        rows_with_address += bool(address)
        rows_with_organization += bool(organization)
        matches = by_address.get(address, []) if address else []
        unique = {clean_text(item.get("property_id")): item for item in matches if clean_text(item.get("property_id"))}
        if len(unique) > 1:
            ambiguous_rows += 1
            continue
        if len(unique) != 1:
            continue
        prop = next(iter(unique.values()))
        pid = clean_text(prop.get("property_id"))
        source_record_id = stable_source_record_id(SOURCE_KEY, row)
        new_links.append({
            "property_id": pid,
            "source_key": SOURCE_KEY,
            "source_record_id": source_record_id,
            "source_row_index": idx,
            "match_basis": "EXACT_CORRECTED_CANONICAL_PROPERTY_ADDRESS_TO_ADDRESS_POINT_SPINE",
            "source_address": raw_address,
        })
        matched_rows += 1
        matched_properties.add(pid)
        if organization:
            matched_organizations.add(organization)

    metrics = {
        "source_rows": len(rows),
        "rows_with_address": rows_with_address,
        "rows_with_organization": rows_with_organization,
        "matched_rows": matched_rows,
        "matched_properties": len(matched_properties),
        "distinct_organizations": len(matched_organizations),
        "ambiguous_rows_not_forced": ambiguous_rows,
    }
    expected_metrics = {
        "source_rows": EXPECTED_SOURCE_ROWS,
        "rows_with_address": EXPECTED_SOURCE_ROWS,
        "rows_with_organization": EXPECTED_SOURCE_ROWS,
        "matched_rows": EXPECTED_MATCHED_ROWS,
        "matched_properties": EXPECTED_MATCHED_PROPERTIES,
        "ambiguous_rows_not_forced": EXPECTED_AMBIGUOUS_ROWS,
    }
    for key, expected in expected_metrics.items():
        if metrics[key] != expected:
            raise RuntimeError(f"BPS deterministic match drift for {key}: expected {expected}, found {metrics[key]}")

    links = retained_links + new_links
    identities = [
        (clean_text(item.get("property_id")), clean_text(item.get("source_key")), clean_text(item.get("source_record_id")))
        for item in links
    ]
    if len(identities) != len(set(identities)):
        raise RuntimeError("BPS apply would create duplicate property/source/record identities")
    links.sort(key=lambda item: (clean_text(item.get("property_id")), clean_text(item.get("source_key")), clean_text(item.get("source_record_id"))))

    sources = dict(links_payload.get("sources") or {})
    sources[SOURCE_KEY] = {
        "status": "JOINED",
        "source_records": len(rows),
        "records_with_property_address": rows_with_address,
        "matched_records": matched_rows,
        "matched_canonical_properties": len(matched_properties),
        "ambiguous_address_rows_not_forced": ambiguous_rows,
        "links_added": len(new_links),
        "identity_limitation": None,
        "role_semantics": "Organization is retained only as FACILITY_OPERATOR_OR_REPORTER_AT; this source does not establish ownership.",
    }
    links_payload["generated_at"] = utc_now()
    links_payload["sources"] = sources
    links_payload["links"] = links
    links_payload["counts"] = {
        "canonical_properties": len(properties),
        "total_source_links": len(links),
        "properties_with_any_new_link": len({clean_text(item.get("property_id")) for item in links if clean_text(item.get("property_id"))}),
        "source_family_count": len(sources),
    }
    write_json(MARKET / "property_source_links.json", links_payload)

    graph = read_json(MARKET / "entity_graph.json") or {}
    nodes_by_id = {
        clean_text(item.get("node_id")): item
        for item in (graph.get("nodes") or [])
        if isinstance(item, dict) and clean_text(item.get("node_id"))
    }
    retained_edges = [
        item for item in (graph.get("edges") or [])
        if isinstance(item, dict) and clean_text(item.get("source_key")) != SOURCE_KEY
    ]
    new_edges: dict[str, dict[str, Any]] = {}
    for link in new_links:
        idx = link["source_row_index"]
        row = rows[idx]
        organization = clean_text(row.get("Organization"))
        if not organization:
            raise RuntimeError(f"BPS matched row {idx} has no Organization")
        pid = clean_text(link.get("property_id"))
        oid = organization_id(organization)
        nodes_by_id.setdefault(oid, {"node_id": oid, "node_type": "ORGANIZATION", "name": organization})
        evidence = {
            "property_name": row.get("Property Name"),
            "source_address": row.get("Address"),
        }
        key_payload = [oid, pid, RELATIONSHIP, SOURCE_KEY, evidence]
        eid = "edge:" + hashlib.sha1(json.dumps(key_payload, sort_keys=True, default=str).encode()).hexdigest()[:20]
        new_edges[eid] = {
            "edge_id": eid,
            "from_node": oid,
            "to_node": pid,
            "property_id": pid,
            "relationship": RELATIONSHIP,
            "source_key": SOURCE_KEY,
            "basis": "ORGANIZATION_FIELD_AT_EXACT_CURRENT_ADDRESS",
            "confidence": "SOURCE_ROLE_NOT_OWNERSHIP",
            "evidence": evidence,
        }

    graph["generated_at"] = utc_now()
    diagnostics = dict(graph.get("diagnostics") or {})
    diagnostics[SOURCE_KEY] = {
        "source_rows": len(rows),
        "exact_property_rows": matched_rows,
        "exact_properties": len(matched_properties),
        "distinct_organizations": len(matched_organizations),
        "ambiguous_rows_not_forced": ambiguous_rows,
        "role_limitation": "Organization is a public-sector reporting/operator context field and is not relabelled owner.",
    }
    graph["diagnostics"] = diagnostics
    graph["nodes"] = list(nodes_by_id.values())
    graph["edges"] = retained_edges + list(new_edges.values())
    recompute_graph_counts(graph)
    operator_properties = int((graph.get("counts") or {}).get("chain_coverage", {}).get("properties_with_facility_operator_or_reporter") or 0)
    if operator_properties != EXPECTED_MATCHED_PROPERTIES:
        raise RuntimeError(f"BPS relationship coverage drift: expected {EXPECTED_MATCHED_PROPERTIES} properties, found {operator_properties}")
    if any(
        edge.get("source_key") == SOURCE_KEY and edge.get("relationship") != RELATIONSHIP
        for edge in graph.get("edges", []) if isinstance(edge, dict)
    ):
        raise RuntimeError("BPS source produced a relationship outside the operator/reporter role contract")
    write_json(MARKET / "entity_graph.json", graph)

    report = {
        "schema_version": "toronto-bps-relationship-apply-1.0",
        "generated_at": utc_now(),
        "status": "PASSED",
        "source_key": SOURCE_KEY,
        "match_contract": "Exact canonical civic address to one existing Toronto Address Point property; ambiguous rows are never forced.",
        "relationship_contract": "Organization creates FACILITY_OPERATOR_OR_REPORTER_AT only and never OWNER_OF.",
        "metrics": metrics,
        "links_written": len(new_links),
        "relationship_edges_written": len(new_edges),
        "graph_chain_coverage": (graph.get("counts") or {}).get("chain_coverage") or {},
    }
    write_json(MARKET / "bps_relationship_apply_report.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
