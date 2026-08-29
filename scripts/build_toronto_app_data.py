from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def organization_names(graph: dict[str, Any]) -> dict[str, str]:
    names: dict[str, str] = {}
    for node in graph.get("nodes") or []:
        if isinstance(node, dict) and node.get("node_type") == "ORGANIZATION":
            names[str(node.get("node_id"))] = str(node.get("name") or "Unknown organization")
    return names


def candidate_property_ids(payload: dict[str, Any]) -> set[str]:
    records = payload.get("documents") or payload.get("candidates") or payload.get("properties") or []
    return {
        str(record.get("property_id"))
        for record in records
        if isinstance(record, dict) and record.get("property_id")
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", type=Path, default=ROOT / "data/toronto/market/current")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data/toronto-market.json")
    args = parser.parse_args()

    market = args.market
    spine = load(market / "property_spine.json")
    reconciliation = load(market / "reconciliation_details.json")
    links_payload = load(market / "property_source_links.json")
    graph = load(market / "entity_graph.json")
    coverage = load(market / "coverage_report.json")
    aerial_payload = load(market / "aerial_candidates.json")
    aic_candidates = load(market / "aic_explicit_tower_candidates.json")

    links_by_property: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for link in links_payload.get("links") or []:
        if not isinstance(link, dict) or not link.get("property_id"):
            continue
        links_by_property[str(link["property_id"])].append({
            "source_key": str(link.get("source_key") or "unknown"),
            "source_record_id": str(link.get("source_record_id") or ""),
            "match_basis": str(link.get("match_basis") or ""),
            "source_address": link.get("source_address"),
        })

    names = organization_names(graph)
    relationships_by_property: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in graph.get("edges") or []:
        if not isinstance(edge, dict) or not edge.get("property_id"):
            continue
        relationships_by_property[str(edge["property_id"])].append({
            "relationship": str(edge.get("relationship") or "OTHER_RELATIONSHIP"),
            "organization": names.get(str(edge.get("from_node")), "Unknown organization"),
            "source_key": str(edge.get("source_key") or "unknown"),
            "confidence": str(edge.get("confidence") or "UNKNOWN"),
            "basis": str(edge.get("basis") or ""),
        })

    aerial_by_property: dict[str, dict[str, Any]] = {}
    for rank, candidate in enumerate(aerial_payload.get("candidates") or [], start=1):
        if isinstance(candidate, dict) and candidate.get("property_id"):
            aerial_by_property[str(candidate["property_id"])] = {**candidate, "review_rank": rank}

    aic_property_ids = candidate_property_ids(aic_candidates)
    properties: list[dict[str, Any]] = []
    evidence_counts: defaultdict[str, int] = defaultdict(int)
    for prop in spine.get("properties") or []:
        if not isinstance(prop, dict):
            continue
        property_id = str(prop.get("property_id") or "")
        statuses = {str(status) for status in (prop.get("poc_tower_statuses") or [])}
        aerial = aerial_by_property.get(property_id)
        if "CONFIRMED" in statuses:
            evidence_status = "CONFIRMED_DOCUMENTARY_TOWER"
        elif property_id in aic_property_ids:
            evidence_status = "AIC_DOCUMENT_CANDIDATE"
        elif aerial and int(aerial["review_rank"]) <= 50:
            evidence_status = "AERIAL_REVIEW_CANDIDATE"
        else:
            evidence_status = "NO_TOWER_ASSERTION"
        evidence_counts[evidence_status] += 1
        property_links = sorted(links_by_property.get(property_id, []), key=lambda item: (item["source_key"], item["source_record_id"]))
        source_keys = sorted(set(prop.get("source_keys") or []) | {item["source_key"] for item in property_links})
        properties.append({
            "property_id": property_id,
            "address_point_id": str(prop.get("address_point_id") or ""),
            "display_address": str(prop.get("display_address") or prop.get("canonical_address") or property_id),
            "municipality": str(prop.get("municipality") or "Toronto"),
            "longitude": prop.get("longitude"),
            "latitude": prop.get("latitude"),
            "identity_basis": str(prop.get("identity_basis") or ""),
            "identity_confidence": str(prop.get("identity_confidence") or ""),
            "is_original_poc_property": bool(prop.get("is_original_poc_property")),
            "tower_evidence_status": evidence_status,
            "source_keys": source_keys,
            "source_links": property_links,
            "relationships": sorted(relationships_by_property.get(property_id, []), key=lambda item: (item["relationship"], item["organization"])),
            "aerial_review_rank": int(aerial["review_rank"]) if aerial and int(aerial["review_rank"]) <= 50 else None,
            "aerial_visual_similarity_score": aerial.get("aerial_visual_similarity_score") if aerial and int(aerial["review_rank"]) <= 50 else None,
        })

    unresolved = []
    for record in reconciliation.get("records") or []:
        if not isinstance(record, dict) or record.get("resolved"):
            continue
        unresolved.append({
            "property_key": str(record.get("property_key") or ""),
            "input_address": record.get("input_address"),
            "resolution_status": str(record.get("resolution_status") or "UNRESOLVED"),
            "candidate_address_point_ids": [str(value) for value in (record.get("candidate_address_point_ids") or [])],
        })

    true_coverage = coverage.get("true_cooling_tower_market_coverage") or {}
    if true_coverage.get("status") != "UNKNOWN_DENOMINATOR" or true_coverage.get("coverage_percent") is not None:
        raise RuntimeError("Toronto app data cannot publish a manufactured market coverage percentage")
    if len(unresolved) != int(reconciliation.get("unresolved_count") or 0):
        raise RuntimeError("Unresolved POC queue does not match reconciliation count")

    payload = {
        "schema_version": "toronto-market-app-1.0",
        "generated_at": coverage.get("generated_at") or spine.get("generated_at"),
        "feature_status": "ISOLATED_BETA",
        "counts": {
            "canonical_properties": len(properties),
            "original_poc_properties": int(reconciliation.get("original_poc_count") or 177),
            "original_poc_resolved": int(reconciliation.get("resolved_count") or 0),
            "original_poc_unresolved": int(reconciliation.get("unresolved_count") or 0),
            "documentary_confirmed_properties": evidence_counts["CONFIRMED_DOCUMENTARY_TOWER"],
            "strong_documentary_candidates": evidence_counts["STRONG_DOCUMENTARY_CANDIDATE"],
            "aic_document_candidates": None if (coverage.get("aic_coverage") or {}).get("document_transport_blocked") else evidence_counts["AIC_DOCUMENT_CANDIDATE"],
            "aerial_review_candidates": evidence_counts["AERIAL_REVIEW_CANDIDATE"],
            "source_links": sum(len(value) for value in links_by_property.values()),
            "relationship_edges": sum(len(value) for value in relationships_by_property.values()),
        },
        "true_market_coverage": {"status": "UNKNOWN_DENOMINATOR", "coverage_percent": None},
        "source_coverage": coverage.get("source_coverage") or coverage.get("source_identity_coverage") or {},
        "limitations": [
            "The total installed Toronto cooling-tower population is unknown; no market coverage percentage is claimed.",
            "AIC supporting-document access is blocked by the current reCAPTCHA-protected attachment transport.",
            "Construction Act publisher content is excluded pending permission or a compatible licence.",
            "Ontario EWRB rows without usable civic addresses are not joined to properties.",
            "Aerial scores are weak-label review prioritization and never cooling-tower confirmation.",
        ],
        "unresolved_poc": unresolved,
        "properties": sorted(properties, key=lambda item: (item["display_address"], item["property_id"])),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(payload["counts"], indent=2))


if __name__ == "__main__":
    main()
