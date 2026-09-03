from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from toronto_final_identity_cleanup import canonical_address
from toronto_market_common import clean_text, read_json, utc_now, write_json
from toronto_source_identity import find_source_record, stable_source_record_id

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data/toronto/market/current"
WAREHOUSE = ROOT / "data/toronto/warehouse/current"
SOURCE_LINK_KEY = "tobids_awarded_contracts_exact_document_address_prior_poc"
GRAPH_SOURCE_KEY = "tobids_awarded_contracts"
RELATIONSHIP = "SUCCESSFUL_BIDDER_AT_PROPERTY"
EXPECTED_SOURCE_ROWS = 7670
EXPECTED_ROWS_WITH_DESCRIPTION = 1521
EXPECTED_EXACT_ROWS = 15
EXPECTED_AMBIGUOUS_ROWS = 5
EXPECTED_EXISTING_EXACT_ROWS = 3
EXPECTED_NEW_LINKS = 12
EXPECTED_FINAL_SOURCE_LINKS = 17
EXPECTED_FINAL_PROPERTIES = 13
EXPECTED_NEW_EDGES = 12
EXPECTED_FINAL_BIDDER_EDGES = 17
EXPECTED_FINAL_BIDDER_PROPERTIES = 13

SUFFIX_MAP = {
    "ST": "STREET", "STREET": "STREET",
    "RD": "ROAD", "ROAD": "ROAD",
    "AVE": "AVENUE", "AV": "AVENUE", "AVENUE": "AVENUE",
    "BLVD": "BOULEVARD", "BOULEVARD": "BOULEVARD",
    "DR": "DRIVE", "DRIVE": "DRIVE",
    "CT": "COURT", "CRT": "COURT", "COURT": "COURT",
    "CRES": "CRESCENT", "CR": "CRESCENT", "CRESCENT": "CRESCENT",
    "HWY": "HIGHWAY", "HIGHWAY": "HIGHWAY",
    "PKWY": "PARKWAY", "PARKWAY": "PARKWAY",
    "PL": "PLACE", "PLACE": "PLACE",
    "LN": "LANE", "LANE": "LANE",
    "TRL": "TRAIL", "TRAIL": "TRAIL",
    "TER": "TERRACE", "TERR": "TERRACE", "TERRACE": "TERRACE",
    "SQ": "SQUARE", "SQUARE": "SQUARE",
    "CIR": "CIRCLE", "CIRCLE": "CIRCLE",
    "GRV": "GROVE", "GROVE": "GROVE",
}


def normalize_free_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).upper()
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return " ".join(SUFFIX_MAP.get(token, token) for token in text.split())


def normalized_property_address(value: Any) -> str:
    return normalize_free_text(canonical_address(value))


def address_number(address: str) -> str | None:
    if not address:
        return None
    token = address.split()[0]
    return token if re.fullmatch(r"\d{1,5}[A-Z]?", token) else None


def exact_address_matches(normalized_text: str, candidates: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    padded = f" {normalized_text} "
    return [candidate for candidate in candidates if f" {candidate[0]} " in padded]


def organization_id(name: str) -> str:
    normalized = " ".join(clean_text(name).upper().split())
    return "org:" + hashlib.sha1(normalized.encode()).hexdigest()[:20]


def normalized_org(value: Any) -> str:
    return " ".join(clean_text(value).upper().split())


def candidate_rows(properties: list[dict[str, Any]], rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    by_address: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for prop in properties:
        address = normalized_property_address(prop.get("display_address") or prop.get("canonical_address"))
        if address:
            by_address[address].append(prop)

    candidates_by_number: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    ambiguous_property_addresses = 0
    for address, matches in by_address.items():
        number = address_number(address)
        if not number or len(address.split()) < 3:
            continue
        if len(matches) != 1:
            ambiguous_property_addresses += 1
            continue
        prop = matches[0]
        pid = clean_text(prop.get("property_id"))
        display = clean_text(prop.get("display_address") or prop.get("canonical_address"))
        if pid and display:
            candidates_by_number[number].append((address, pid, display))

    exact: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        description = clean_text(row.get("Solicitation Document Description"))
        supplier = clean_text(row.get("Successful Supplier"))
        if not description or not supplier:
            continue
        normalized = normalize_free_text(description)
        numbers = set(re.findall(r"\b\d{1,5}[A-Z]?\b", normalized))
        matched: dict[str, tuple[str, str, str]] = {}
        for number in numbers:
            for candidate in exact_address_matches(normalized, candidates_by_number.get(number, [])):
                matched[candidate[1]] = candidate
        if not matched:
            continue
        if len(matched) > 1:
            ambiguous.append({
                "source_row_index": idx,
                "document_number": row.get("Document Number"),
                "successful_supplier": supplier,
                "matched_properties": sorted(matched),
            })
            continue
        candidate = next(iter(matched.values()))
        exact.append({
            "source_row_index": idx,
            "row": row,
            "property_id": candidate[1],
            "display_address": candidate[2],
            "successful_supplier": supplier,
        })
    return exact, ambiguous, ambiguous_property_addresses


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
            "properties_with_facility_operator_or_reporter": len(property_sets.get("FACILITY_OPERATOR_OR_REPORTER_AT", set())),
            "properties_with_chemtrac_reporting_facility": len(property_sets.get("CHEMTRAC_REPORTING_FACILITY_AT", set())),
            "properties_with_licence_holder": len(property_sets.get("LICENCE_HOLDER_AT_PROPERTY", set())),
        },
    }


def main() -> None:
    spine = read_json(MARKET / "property_spine.json") or {}
    properties = [item for item in spine.get("properties", []) if isinstance(item, dict)]
    if len(properties) != 13065:
        raise RuntimeError(f"Toronto property spine drift: expected 13065, found {len(properties)}")

    tobids = read_json(WAREHOUSE / "open_licensed/tobids_awarded_contracts.json") or {}
    rows = [item for item in tobids.get("rows", []) if isinstance(item, dict)]
    if len(rows) != EXPECTED_SOURCE_ROWS:
        raise RuntimeError(f"TOBids source snapshot drift: expected {EXPECTED_SOURCE_ROWS}, found {len(rows)}")
    rows_with_description = sum(bool(clean_text(row.get("Solicitation Document Description"))) for row in rows)
    if rows_with_description != EXPECTED_ROWS_WITH_DESCRIPTION:
        raise RuntimeError(f"TOBids description count drift: expected {EXPECTED_ROWS_WITH_DESCRIPTION}, found {rows_with_description}")

    exact, ambiguous, ambiguous_property_addresses = candidate_rows(properties, rows)
    if len(exact) != EXPECTED_EXACT_ROWS:
        raise RuntimeError(f"TOBids exact-match drift: expected {EXPECTED_EXACT_ROWS}, found {len(exact)}")
    if len(ambiguous) != EXPECTED_AMBIGUOUS_ROWS:
        raise RuntimeError(f"TOBids ambiguous-row drift: expected {EXPECTED_AMBIGUOUS_ROWS}, found {len(ambiguous)}")

    links_payload = read_json(MARKET / "property_source_links.json") or {}
    links = [item for item in links_payload.get("links", []) if isinstance(item, dict)]
    existing_source_links = [item for item in links if clean_text(item.get("source_key")) == SOURCE_LINK_KEY]
    existing_publisher_identities: set[tuple[str, str]] = set()
    unresolved_legacy_links: list[dict[str, Any]] = []
    for link in existing_source_links:
        pid = clean_text(link.get("property_id"))
        resolved = find_source_record(SOURCE_LINK_KEY, clean_text(link.get("source_record_id")), rows)
        if not resolved:
            unresolved_legacy_links.append(link)
            continue
        existing_publisher_identities.add((pid, stable_source_record_id(SOURCE_LINK_KEY, resolved)))
    if unresolved_legacy_links:
        raise RuntimeError(f"TOBids legacy source links failed publisher-row resolution: {unresolved_legacy_links[:5]}")


    new_links: list[dict[str, Any]] = []
    existing_exact_rows = 0
    for item in exact:
        row = item["row"]
        pid = item["property_id"]
        idx = item["source_row_index"]
        source_record_id = stable_source_record_id(SOURCE_LINK_KEY, row)
        publisher_key = (pid, source_record_id)
        if publisher_key in existing_publisher_identities:
            existing_exact_rows += 1
            continue
        new_links.append({
            "property_id": pid,
            "source_key": SOURCE_LINK_KEY,
            "source_record_id": source_record_id,
            "source_row_index": idx,
            "match_basis": "EXACT_NORMALIZED_CIVIC_ADDRESS_PHRASE_IN_SOLICITATION_DESCRIPTION_TO_UNIQUE_CURRENT_ADDRESS_POINT_PROPERTY",
            "source_address": item["display_address"],
        })

    if existing_exact_rows != EXPECTED_EXISTING_EXACT_ROWS:
        raise RuntimeError(f"TOBids expected {EXPECTED_EXISTING_EXACT_ROWS} already-linked exact rows, found {existing_exact_rows}")
    if len(new_links) != EXPECTED_NEW_LINKS:
        raise RuntimeError(f"TOBids expected {EXPECTED_NEW_LINKS} new source links, found {len(new_links)}")

    updated_links = links + new_links
    identities = [
        (clean_text(item.get("property_id")), clean_text(item.get("source_key")), clean_text(item.get("source_record_id")))
        for item in updated_links
    ]
    if len(identities) != len(set(identities)):
        raise RuntimeError("TOBids apply would create duplicate property/source/record identities")
    updated_links.sort(key=lambda item: (clean_text(item.get("property_id")), clean_text(item.get("source_key")), clean_text(item.get("source_record_id"))))

    final_source_links = [item for item in updated_links if clean_text(item.get("source_key")) == SOURCE_LINK_KEY]
    final_source_properties = {clean_text(item.get("property_id")) for item in final_source_links if clean_text(item.get("property_id"))}
    if len(final_source_links) != EXPECTED_FINAL_SOURCE_LINKS:
        raise RuntimeError(f"TOBids final source-link count drift: expected {EXPECTED_FINAL_SOURCE_LINKS}, found {len(final_source_links)}")
    if len(final_source_properties) != EXPECTED_FINAL_PROPERTIES:
        raise RuntimeError(f"TOBids final property coverage drift: expected {EXPECTED_FINAL_PROPERTIES}, found {len(final_source_properties)}")

    sources = dict(links_payload.get("sources") or {})
    source_meta = dict(sources.get(SOURCE_LINK_KEY) or {})
    source_meta.update({
        "status": "JOINED",
        "source_records": len(rows),
        "records_with_solicitation_description": rows_with_description,
        "matched_records": len(final_source_links),
        "matched_canonical_properties": len(final_source_properties),
        "ambiguous_multi_property_rows_not_forced": len(ambiguous),
        "ambiguous_property_addresses_not_used": ambiguous_property_addresses,
        "links_added_in_citywide_exact_description_pass": len(new_links),
        "role_semantics": "Successful Supplier supports SUCCESSFUL_BIDDER_AT_PROPERTY only. Mechanical, contractor-specialty, engineering, ownership, and consulting roles are not inferred from category or keywords.",
    })
    sources[SOURCE_LINK_KEY] = source_meta
    links_payload["generated_at"] = utc_now()
    links_payload["sources"] = sources
    links_payload["links"] = updated_links
    links_payload["counts"] = {
        "canonical_properties": len(properties),
        "total_source_links": len(updated_links),
        "properties_with_any_new_link": len({clean_text(item.get("property_id")) for item in updated_links if clean_text(item.get("property_id"))}),
        "source_family_count": len(sources),
    }
    write_json(MARKET / "property_source_links.json", links_payload)

    graph = read_json(MARKET / "entity_graph.json") or {}
    nodes_by_id = {
        clean_text(item.get("node_id")): item
        for item in (graph.get("nodes") or [])
        if isinstance(item, dict) and clean_text(item.get("node_id"))
    }
    edges = [item for item in (graph.get("edges") or []) if isinstance(item, dict)]
    existing_pairs: set[tuple[str, str]] = set()
    for edge in edges:
        if clean_text(edge.get("source_key")) != GRAPH_SOURCE_KEY or clean_text(edge.get("relationship")) != RELATIONSHIP:
            continue
        node = nodes_by_id.get(clean_text(edge.get("from_node"))) or {}
        name = normalized_org(node.get("name"))
        pid = clean_text(edge.get("property_id") or edge.get("to_node"))
        if name and pid:
            existing_pairs.add((pid, name))

    exact_by_row = {item["source_row_index"]: item for item in exact}
    new_edges: list[dict[str, Any]] = []
    for link in new_links:
        idx = link["source_row_index"]
        item = exact_by_row[idx]
        row = item["row"]
        supplier = item["successful_supplier"]
        pid = item["property_id"]
        pair = (pid, normalized_org(supplier))
        if pair in existing_pairs:
            raise RuntimeError(f"TOBids new source link at row {idx} already has a bidder edge")
        oid = organization_id(supplier)
        nodes_by_id.setdefault(oid, {"node_id": oid, "node_type": "ORGANIZATION", "name": supplier})
        evidence = {
            "document_number": row.get("Document Number"),
            "award_date": row.get("Award Authority Obtained Date"),
            "award": row.get("Award"),
            "source_row_index": idx,
            "source_address": item["display_address"],
        }
        key_payload = [oid, pid, RELATIONSHIP, GRAPH_SOURCE_KEY, evidence]
        eid = "edge:" + hashlib.sha1(json.dumps(key_payload, sort_keys=True, default=str).encode()).hexdigest()[:20]
        if any(clean_text(edge.get("edge_id")) == eid for edge in edges) or any(clean_text(edge.get("edge_id")) == eid for edge in new_edges):
            raise RuntimeError(f"TOBids duplicate edge identity at row {idx}")
        new_edges.append({
            "edge_id": eid,
            "from_node": oid,
            "to_node": pid,
            "property_id": pid,
            "relationship": RELATIONSHIP,
            "source_key": GRAPH_SOURCE_KEY,
            "basis": "EXPLICIT_SUCCESSFUL_SUPPLIER_AND_EXACT_CIVIC_ADDRESS_PHRASE_IN_SOLICITATION_DESCRIPTION",
            "confidence": "CONFIRMED_SOURCE_FIELD_AND_EXACT_ADDRESS_TEXT",
            "evidence": evidence,
        })
        existing_pairs.add(pair)

    if len(new_edges) != EXPECTED_NEW_EDGES:
        raise RuntimeError(f"TOBids expected {EXPECTED_NEW_EDGES} new bidder edges, found {len(new_edges)}")

    graph["generated_at"] = utc_now()
    graph["nodes"] = list(nodes_by_id.values())
    graph["edges"] = edges + new_edges
    diagnostics = dict(graph.get("diagnostics") or {})
    diagnostics[GRAPH_SOURCE_KEY] = {
        "source_rows": len(rows),
        "rows_with_solicitation_description": rows_with_description,
        "exact_single_current_property_rows": len(exact),
        "ambiguous_multi_property_rows_not_forced": len(ambiguous),
        "new_citywide_exact_property_supplier_pairs": len(new_edges),
        "role_limitation": "Successful Supplier is retained only as SUCCESSFUL_BIDDER_AT_PROPERTY. No contractor specialty, engineer, consultant, operator, or ownership role is inferred.",
    }
    graph["diagnostics"] = diagnostics
    recompute_graph_counts(graph)

    counts = graph.get("counts") or {}
    relationship_counts = counts.get("relationships") or {}
    properties_by_relationship = counts.get("properties_by_relationship") or {}
    if int(relationship_counts.get(RELATIONSHIP) or 0) != EXPECTED_FINAL_BIDDER_EDGES:
        raise RuntimeError(f"TOBids bidder edge count drift: expected {EXPECTED_FINAL_BIDDER_EDGES}, found {relationship_counts.get(RELATIONSHIP)}")
    if int(properties_by_relationship.get(RELATIONSHIP) or 0) != EXPECTED_FINAL_BIDDER_PROPERTIES:
        raise RuntimeError(f"TOBids bidder property count drift: expected {EXPECTED_FINAL_BIDDER_PROPERTIES}, found {properties_by_relationship.get(RELATIONSHIP)}")
    if any(
        clean_text(edge.get("source_key")) == GRAPH_SOURCE_KEY and clean_text(edge.get("relationship")) != RELATIONSHIP
        for edge in graph.get("edges", []) if isinstance(edge, dict)
    ):
        raise RuntimeError("TOBids source produced a relationship outside SUCCESSFUL_BIDDER_AT_PROPERTY")
    write_json(MARKET / "entity_graph.json", graph)

    report = {
        "schema_version": "toronto-tobids-relationship-apply-1.0",
        "generated_at": utc_now(),
        "status": "PASSED",
        "source_link_key": SOURCE_LINK_KEY,
        "graph_source_key": GRAPH_SOURCE_KEY,
        "match_contract": "A solicitation row is promotable only when one exact normalized full civic-address phrase maps to one current Toronto Address Point property. Rows matching multiple current properties are withheld.",
        "relationship_contract": "Successful Supplier creates SUCCESSFUL_BIDDER_AT_PROPERTY only. Mechanical, contractor-specialty, engineering, consulting, operator, and ownership roles are not inferred.",
        "metrics": {
            "source_rows": len(rows),
            "rows_with_description": rows_with_description,
            "exact_rows": len(exact),
            "ambiguous_rows_not_forced": len(ambiguous),
            "existing_exact_rows": existing_exact_rows,
            "new_links": len(new_links),
            "final_source_links": len(final_source_links),
            "final_source_properties": len(final_source_properties),
            "new_relationship_edges": len(new_edges),
            "final_successful_bidder_edges": int(relationship_counts.get(RELATIONSHIP) or 0),
            "final_successful_bidder_properties": int(properties_by_relationship.get(RELATIONSHIP) or 0),
        },
        "ambiguous_rows": ambiguous,
        "new_relationships": [
            {
                "source_row_index": link["source_row_index"],
                "property_id": link["property_id"],
                "display_address": exact_by_row[link["source_row_index"]]["display_address"],
                "successful_supplier": exact_by_row[link["source_row_index"]]["successful_supplier"],
                "document_number": exact_by_row[link["source_row_index"]]["row"].get("Document Number"),
            }
            for link in new_links
        ],
        "graph_chain_coverage": counts.get("chain_coverage") or {},
    }
    write_json(MARKET / "tobids_relationship_apply_report.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
