from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from toronto_final_identity_cleanup import canonical_address
from toronto_market_common import clean_text, read_json, request_json, utc_now, write_json

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data" / "toronto" / "market" / "current"
WAREHOUSE = ROOT / "data" / "toronto" / "warehouse" / "current"
TOR_CKAN = "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action"
RENTSAFE_RESOURCE = "3ad76a8c-0518-4df2-b94e-8c747d62f8c1"

ROLE_MAP = {
    "OWNER": "OWNER_OF",
    "PROPERTY_MANAGER": "PROPERTY_MANAGER_OF",
    "PROPERTY_MANAGEMENT": "PROPERTY_MANAGER_OF",
    "MECHANICAL_CONTRACTOR": "MECHANICAL_CONTRACTOR_AT_PROPERTY",
    "CONTRACTOR": "CONTRACTOR_AT_PROPERTY",
    "MECHANICAL_ENGINEER": "MECHANICAL_ENGINEER_FOR",
    "MECHANICAL_CONSULTANT": "CONSULTANT_FOR",
    "ENGINEER": "ENGINEER_FOR",
    "ARCHITECT": "ARCHITECT_FOR",
    "CONSULTANT": "CONSULTANT_FOR",
    "APPLICANT": "APPLICANT_FOR",
}


def ckan_action(name: str, params: dict[str, Any]) -> Any:
    payload = request_json(f"{TOR_CKAN}/{name}?{urlencode(params)}", timeout=120)
    if payload.get("success") is not True:
        raise RuntimeError(f"Toronto CKAN action failed: {name}")
    return payload.get("result")


def fetch_rentsafe() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        result = ckan_action("datastore_search", {"resource_id": RENTSAFE_RESOURCE, "limit": 1000, "offset": offset})
        batch = [r for r in result.get("records", []) if isinstance(r, dict)]
        rows.extend(batch)
        if not batch or offset + len(batch) >= int(result.get("total") or 0):
            break
        offset += len(batch)
    return rows


def organization_id(name: str) -> str:
    normalized = " ".join(clean_text(name).upper().split())
    return "org:" + hashlib.sha1(normalized.encode()).hexdigest()[:20]


def add_edge(nodes: dict[str, Any], edges: dict[str, Any], property_ids: set[str], name: Any, pid: str, relationship: str, source: str, basis: str, confidence: str, evidence: dict[str, Any] | None = None) -> None:
    org_name = clean_text(name)
    if not org_name or org_name.upper() in {"N/A", "NA", "NONE", "UNKNOWN", "NOT AVAILABLE"} or pid not in property_ids:
        return
    oid = organization_id(org_name)
    nodes.setdefault(oid, {"node_id": oid, "node_type": "ORGANIZATION", "name": org_name})
    key_payload = [oid, pid, relationship, source, evidence or {}]
    eid = "edge:" + hashlib.sha1(json.dumps(key_payload, sort_keys=True, default=str).encode()).hexdigest()[:20]
    edges.setdefault(eid, {
        "edge_id": eid,
        "from_node": oid,
        "to_node": pid,
        "property_id": pid,
        "relationship": relationship,
        "source_key": source,
        "basis": basis,
        "confidence": confidence,
        "evidence": evidence or {},
    })


def main() -> None:
    spine = read_json(MARKET / "property_spine.json") or {}
    props = [p for p in spine.get("properties", []) if isinstance(p, dict)]
    if not props:
        raise RuntimeError("Final property spine missing")
    property_ids = {p["property_id"] for p in props}
    by_addr: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for prop in props:
        by_addr[canonical_address(prop.get("display_address") or prop.get("canonical_address"))].append(prop)

    nodes: dict[str, Any] = {p["property_id"]: {
        "node_id": p["property_id"], "node_type": "PROPERTY", "address": p.get("display_address"), "address_point_id": p.get("address_point_id")
    } for p in props}
    edges: dict[str, Any] = {}
    diagnostics: dict[str, Any] = {}

    # RentSafe explicit management-company source field.
    rentsafe = fetch_rentsafe()
    rs_matched = 0
    rs_ambiguous = 0
    for row in rentsafe:
        matches = by_addr.get(canonical_address(row.get("SITE_ADDRESS")), [])
        if len(matches) > 1:
            rs_ambiguous += 1
            continue
        if len(matches) != 1:
            continue
        rs_matched += 1
        add_edge(nodes, edges, property_ids, row.get("PROP_MANAGEMENT_COMPANY_NAME"), matches[0]["property_id"], "PROPERTY_MANAGER_OF", "rentsafe_registration", "EXPLICIT_PROP_MANAGEMENT_COMPANY_NAME_AT_EXACT_CURRENT_ADDRESS", "CONFIRMED_SOURCE_FIELD", {"rsn": row.get("RSN"), "site_address": row.get("SITE_ADDRESS")})
    diagnostics["rentsafe_registration"] = {"source_rows": len(rentsafe), "exact_property_rows": rs_matched, "ambiguous_rows_not_forced": rs_ambiguous}

    # Full BPS file: organization is operator/reporter, explicitly not ownership.
    bps_payload = read_json(WAREHOUSE / "open_licensed/ontario_bps_energy_2024.json") or {}
    bps_rows = bps_payload.get("records") or bps_payload.get("toronto_rows") or []
    bps_matched = 0
    for row in bps_rows:
        if not isinstance(row, dict):
            continue
        address = row.get("address") or row.get("Address")
        matches = by_addr.get(canonical_address(address), [])
        if len(matches) != 1:
            continue
        bps_matched += 1
        add_edge(nodes, edges, property_ids, row.get("organization") or row.get("Organization"), matches[0]["property_id"], "FACILITY_OPERATOR_OR_REPORTER_AT", "ontario_bps_energy_2024", "ORGANIZATION_FIELD_AT_EXACT_CURRENT_ADDRESS", "SOURCE_ROLE_NOT_OWNERSHIP", {"property_name": row.get("property_name") or row.get("Property Name"), "source_address": address})
    diagnostics["ontario_bps_energy_2024"] = {"source_rows": len(bps_rows), "exact_property_rows": bps_matched}

    # Preserve already-reviewed deterministic POC award relationships, remapped by address.
    old = read_json(WAREHOUSE / "property_joins.json") or {}
    awards = 0
    for item in old.get("properties", []):
        matches = by_addr.get(canonical_address(item.get("address")), [])
        if len(matches) != 1:
            continue
        pid = matches[0]["property_id"]
        for row in (item.get("matches", {}) or {}).get("tobids_awarded_contracts", []) or []:
            awards += 1
            add_edge(nodes, edges, property_ids, row.get("successful_supplier"), pid, "SUCCESSFUL_BIDDER_AT_PROPERTY", "tobids_awarded_contracts", "SUCCESSFUL_SUPPLIER_IN_EXACT_PROPERTY_AWARD_MATCH", "CONFIRMED_SOURCE_FIELD", {"document_number": row.get("document_number"), "award_date": row.get("award_date"), "award": row.get("award")})
    diagnostics["tobids_awarded_contracts"] = {"deterministic_property_award_rows": awards, "scope_note": "Uses previously persisted exact POC property/document matches; does not infer an address from arbitrary award text in this pass."}

    # AIC text-labelled roles: keep review-required confidence. Never collapse role names.
    aic = read_json(MARKET / "aic_document_index.json") or {}
    aic_role_candidates = 0
    aic_role_edges = 0
    for doc in aic.get("documents", []):
        matches = by_addr.get(canonical_address(doc.get("full_address")), [])
        if len(matches) != 1:
            continue
        pid = matches[0]["property_id"]
        for candidate in doc.get("role_candidates", []) or []:
            aic_role_candidates += 1
            relationship = ROLE_MAP.get(str(candidate.get("role") or "").upper())
            if not relationship:
                continue
            before = len(edges)
            add_edge(nodes, edges, property_ids, candidate.get("name"), pid, relationship, "toronto_aic_supporting_documents", "ROLE_LABEL_AND_NAME_EXTRACTED_FROM_AIC_DOCUMENT_TEXT", "TEXT_PATTERN_CANDIDATE_REQUIRES_REVIEW", {"application_number": doc.get("application_number"), "document_url": doc.get("url"), "document_sha256": doc.get("sha256")})
            aic_role_edges += len(edges) - before
    diagnostics["toronto_aic_supporting_documents"] = {"role_candidates_seen": aic_role_candidates, "deduplicated_role_edges_added": aic_role_edges}

    edge_list = list(edges.values())
    rel_counts: dict[str, int] = defaultdict(int)
    property_sets: dict[str, set[str]] = defaultdict(set)
    for edge in edge_list:
        rel_counts[edge["relationship"]] += 1
        property_sets[edge["relationship"]].add(edge["property_id"])

    graph = {
        "schema_version": "toronto-market-entity-graph-1.0",
        "generated_at": utc_now(),
        "relationship_contract": {
            "ownership": "Only explicit OWNER-labelled source text may create OWNER_OF; manager/operator/reporter/supplier are never relabelled owner.",
            "aic": "AIC text-pattern role edges are review-required and are not treated as verified legal relationships until reviewed.",
            "construction_act": "No third-party publisher records ingested without compatible permission/licence.",
            "property_identity": "All property edges target the corrected unique City ADDRESS_POINT_ID spine by deterministic exact address or existing reviewed POC match.",
        },
        "diagnostics": diagnostics,
        "counts": {
            "nodes": len(nodes),
            "property_nodes": len(props),
            "organization_nodes": sum(n.get("node_type") == "ORGANIZATION" for n in nodes.values()),
            "edges": len(edge_list),
            "relationships": dict(sorted(rel_counts.items())),
            "properties_by_relationship": {k: len(v) for k, v in sorted(property_sets.items())},
            "chain_coverage": {
                "properties_with_owner": len(property_sets.get("OWNER_OF", set())),
                "properties_with_property_manager": len(property_sets.get("PROPERTY_MANAGER_OF", set())),
                "properties_with_engineer_or_consultant": len(property_sets.get("ENGINEER_FOR", set()) | property_sets.get("MECHANICAL_ENGINEER_FOR", set()) | property_sets.get("CONSULTANT_FOR", set())),
                "properties_with_contractor_or_successful_bidder": len(property_sets.get("CONTRACTOR_AT_PROPERTY", set()) | property_sets.get("MECHANICAL_CONTRACTOR_AT_PROPERTY", set()) | property_sets.get("SUCCESSFUL_BIDDER_AT_PROPERTY", set())),
                "properties_with_facility_operator_or_reporter": len(property_sets.get("FACILITY_OPERATOR_OR_REPORTER_AT", set())),
            },
        },
        "nodes": list(nodes.values()),
        "edges": edge_list,
    }
    write_json(MARKET / "entity_graph.json", graph)
    print(json.dumps({"counts": graph["counts"], "diagnostics": diagnostics}, indent=2))

if __name__ == "__main__":
    main()
