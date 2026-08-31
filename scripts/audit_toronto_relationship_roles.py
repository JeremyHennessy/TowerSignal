from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / "data/toronto/market/current/entity_graph.json"
REPORT = ROOT / "data/toronto/market/current/relationship_role_audit.json"

ALLOWED: dict[str, dict[str, set[str]]] = {
    "rentsafe_registration": {
        "PROPERTY_MANAGER_OF": {"CONFIRMED_SOURCE_FIELD"},
    },
    "ontario_bps_energy_2024": {
        "FACILITY_OPERATOR_OR_REPORTER_AT": {"SOURCE_ROLE_NOT_OWNERSHIP"},
    },
    "chemtrac_history": {
        "CHEMTRAC_REPORTING_FACILITY_AT": {"CONFIRMED_SOURCE_FIELD_NOT_OWNERSHIP_OR_OPERATOR"},
    },
    "business_licence_matches_prior_poc": {
        "LICENCE_HOLDER_AT_PROPERTY": {"CONFIRMED_SOURCE_FIELD_NOT_OWNERSHIP"},
    },
    "ontario_environmental_compliance_reports": {
        "OWNER_OF": {"CONFIRMED_SOURCE_FIELD"},
    },
    "tobids_awarded_contracts": {
        "SUCCESSFUL_BIDDER_AT_PROPERTY": {"CONFIRMED_SOURCE_FIELD"},
    },
    "toronto_aic_supporting_documents": {
        "OWNER_OF": {"TEXT_PATTERN_CANDIDATE_REQUIRES_REVIEW"},
        "PROPERTY_MANAGER_OF": {"TEXT_PATTERN_CANDIDATE_REQUIRES_REVIEW"},
        "MECHANICAL_CONTRACTOR_AT_PROPERTY": {"TEXT_PATTERN_CANDIDATE_REQUIRES_REVIEW"},
        "CONTRACTOR_AT_PROPERTY": {"TEXT_PATTERN_CANDIDATE_REQUIRES_REVIEW"},
        "MECHANICAL_ENGINEER_FOR": {"TEXT_PATTERN_CANDIDATE_REQUIRES_REVIEW"},
        "CONSULTANT_FOR": {"TEXT_PATTERN_CANDIDATE_REQUIRES_REVIEW"},
        "ENGINEER_FOR": {"TEXT_PATTERN_CANDIDATE_REQUIRES_REVIEW"},
        "ARCHITECT_FOR": {"TEXT_PATTERN_CANDIDATE_REQUIRES_REVIEW"},
        "APPLICANT_FOR": {"TEXT_PATTERN_CANDIDATE_REQUIRES_REVIEW"},
    },
}


def load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected object: {path}")
    return payload


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def main() -> None:
    graph = load(GRAPH)
    nodes = {clean(node.get("node_id")): node for node in graph.get("nodes", []) if isinstance(node, dict) and clean(node.get("node_id"))}
    edges = [edge for edge in graph.get("edges", []) if isinstance(edge, dict)]
    property_nodes = {key for key, node in nodes.items() if node.get("node_type") == "PROPERTY"}
    organization_nodes = {key for key, node in nodes.items() if node.get("node_type") == "ORGANIZATION"}

    invalid_contract: list[dict[str, Any]] = []
    invalid_endpoints: list[dict[str, Any]] = []
    empty_organizations: list[dict[str, Any]] = []
    semantic_keys: Counter[tuple[str, str, str, str]] = Counter()
    relationship_sources: dict[str, Counter[str]] = defaultdict(Counter)
    confidence_counts: Counter[str] = Counter()

    for edge in edges:
        source = clean(edge.get("source_key"))
        relationship = clean(edge.get("relationship"))
        confidence = clean(edge.get("confidence"))
        from_node = clean(edge.get("from_node"))
        to_node = clean(edge.get("to_node"))
        allowed_confidence = (ALLOWED.get(source) or {}).get(relationship)
        if not allowed_confidence or confidence not in allowed_confidence:
            invalid_contract.append({
                "edge_id": edge.get("edge_id"),
                "source_key": source,
                "relationship": relationship,
                "confidence": confidence,
                "basis": edge.get("basis"),
            })
        if from_node not in organization_nodes or to_node not in property_nodes or clean(edge.get("property_id")) != to_node:
            invalid_endpoints.append({
                "edge_id": edge.get("edge_id"),
                "from_node": from_node,
                "to_node": to_node,
                "property_id": edge.get("property_id"),
            })
        org_name = clean((nodes.get(from_node) or {}).get("name"))
        if not org_name:
            empty_organizations.append({"edge_id": edge.get("edge_id"), "from_node": from_node})
        semantic_keys[(from_node, to_node, relationship, source)] += 1
        relationship_sources[relationship][source] += 1
        confidence_counts[confidence] += 1

    semantic_duplicates = [
        {
            "from_node": key[0], "to_node": key[1], "relationship": key[2], "source_key": key[3], "count": count,
            "organization": clean((nodes.get(key[0]) or {}).get("name")),
        }
        for key, count in semantic_keys.items() if count > 1
    ]

    ownership_edges = [edge for edge in edges if edge.get("relationship") == "OWNER_OF"]
    ownership_by_source = Counter(clean(edge.get("source_key")) for edge in ownership_edges)
    invalid_confirmed_ownership = [
        {"edge_id": edge.get("edge_id"), "source_key": edge.get("source_key"), "confidence": edge.get("confidence")}
        for edge in ownership_edges
        if not (
            (edge.get("source_key") == "ontario_environmental_compliance_reports" and edge.get("confidence") == "CONFIRMED_SOURCE_FIELD")
            or (edge.get("source_key") == "toronto_aic_supporting_documents" and edge.get("confidence") == "TEXT_PATTERN_CANDIDATE_REQUIRES_REVIEW")
        )
    ]

    forbidden_role_inflation = [
        {"edge_id": edge.get("edge_id"), "source_key": edge.get("source_key"), "relationship": edge.get("relationship")}
        for edge in edges
        if (
            edge.get("source_key") == "chemtrac_history" and edge.get("relationship") != "CHEMTRAC_REPORTING_FACILITY_AT"
        ) or (
            edge.get("source_key") == "business_licence_matches_prior_poc" and edge.get("relationship") != "LICENCE_HOLDER_AT_PROPERTY"
        ) or (
            edge.get("source_key") == "ontario_bps_energy_2024" and edge.get("relationship") != "FACILITY_OPERATOR_OR_REPORTER_AT"
        )
    ]

    declared = (graph.get("counts") or {}).get("edges")
    hard_failures = {
        "declared_edge_count_mismatch": 0 if declared == len(edges) else 1,
        "invalid_role_source_confidence_contracts": len(invalid_contract),
        "invalid_graph_endpoints": len(invalid_endpoints),
        "empty_organization_nodes": len(empty_organizations),
        "invalid_confirmed_ownership_edges": len(invalid_confirmed_ownership),
        "forbidden_role_inflation_edges": len(forbidden_role_inflation),
    }
    # Semantic duplicates are reported separately: repeated supporting evidence
    # can currently create multiple AIC evidence edges. They are not silently
    # treated as additional independent relationships in this audit.
    status = "FAILED" if any(hard_failures.values()) else "PASSED_WITH_DUPLICATE_EVIDENCE_REVIEW" if semantic_duplicates else "PASSED"
    report = {
        "schema_version": "toronto-relationship-role-audit-1.0",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": status,
        "counts": {
            "nodes": len(nodes),
            "property_nodes": len(property_nodes),
            "organization_nodes": len(organization_nodes),
            "edges": len(edges),
            "semantic_relationship_keys": len(semantic_keys),
            "semantic_duplicate_relationships": len(semantic_duplicates),
            "ownership_edges": len(ownership_edges),
        },
        "hard_failures": hard_failures,
        "ownership_by_source": dict(sorted(ownership_by_source.items())),
        "relationship_sources": {key: dict(sorted(value.items())) for key, value in sorted(relationship_sources.items())},
        "confidence_counts": dict(sorted(confidence_counts.items())),
        "semantic_duplicates": semantic_duplicates[:500],
        "invalid_contracts": invalid_contract[:500],
        "invalid_endpoints": invalid_endpoints[:500],
        "invalid_ownership": invalid_confirmed_ownership[:500],
        "forbidden_role_inflation": forbidden_role_inflation[:500],
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "counts": report["counts"], "hard_failures": hard_failures, "ownership_by_source": report["ownership_by_source"]}, indent=2))
    if status == "FAILED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
