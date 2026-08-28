from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from toronto_market_common import read_json, utc_now, write_json

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data" / "toronto" / "market" / "current"
POC_CSV = ROOT / "data" / "toronto" / "poc" / "current" / "properties.csv"


def safe_fraction(num: Any, den: Any) -> float | None:
    if isinstance(num, int) and isinstance(den, int) and den:
        return num / den
    return None


def main() -> None:
    with POC_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        poc = list(csv.DictReader(handle))
    spine = read_json(MARKET / "property_spine.json") or {}
    recon = read_json(MARKET / "reconciliation_details.json") or {}
    links = read_json(MARKET / "property_source_links.json") or {}
    aic = read_json(MARKET / "aic_corpus_summary.json") or {}
    aic_index = read_json(MARKET / "aic_document_index.json") or {}
    tower_candidates = read_json(MARKET / "aic_explicit_tower_candidates.json") or {}
    aerial = read_json(MARKET / "aerial_model_report.json") or {}
    aerial_candidates = read_json(MARKET / "aerial_candidates.json") or {}
    graph = read_json(MARKET / "entity_graph.json") or {}
    construction = read_json(MARKET / "construction_act_source_policy.json") or {}

    props = [p for p in spine.get("properties", []) if isinstance(p, dict)]
    canonical = len(props)
    original_resolved = int(recon.get("resolved_count") or 0)
    original_unresolved = int(recon.get("unresolved_count") or 0)
    if original_resolved + original_unresolved != len(poc):
        raise RuntimeError("Coverage cannot be emitted until every original POC record has a reconciliation status")

    source_coverage: dict[str, Any] = {}
    for source, data in (links.get("sources") or {}).items():
        if not isinstance(data, dict):
            continue
        d = dict(data)
        d["candidate_universe_property_link_fraction"] = safe_fraction(d.get("matched_canonical_properties"), canonical)
        if isinstance(d.get("source_records"), int) and isinstance(d.get("matched_records"), int):
            d["source_record_match_fraction"] = safe_fraction(d["matched_records"], d["source_records"])
            d["unmatched_source_records"] = d["source_records"] - d["matched_records"]
        source_coverage[source] = d

    tower_status_counts = Counter(str(r.get("tower_status") or "UNKNOWN") for r in poc)
    documentary_confirmed = tower_status_counts.get("CONFIRMED", 0)
    supporting_only = tower_status_counts.get("SUPPORTING_ONLY", 0)

    documents = [d for d in aic_index.get("documents", []) if isinstance(d, dict)]
    parse_counts = Counter(str(d.get("parse_status") or "UNKNOWN") for d in documents)
    zero_text = sum((d.get("parse_status") == "PARSED") and int(d.get("text_chars_extracted") or 0) == 0 for d in documents)
    category_counts = Counter(c for d in documents for c in (d.get("categories") or []))
    signal_doc_count = sum(any((d.get("signal_counts") or {}).values()) for d in documents)

    if isinstance(tower_candidates, dict):
        candidate_records = tower_candidates.get("documents") or tower_candidates.get("candidates") or tower_candidates.get("properties") or []
    elif isinstance(tower_candidates, list):
        candidate_records = tower_candidates
    else:
        candidate_records = []

    if isinstance(aerial_candidates, dict):
        aerial_records = aerial_candidates.get("candidates") or []
    elif isinstance(aerial_candidates, list):
        aerial_records = aerial_candidates
    else:
        aerial_records = []

    aerial_scoring = aerial.get("scoring") or {}
    graph_counts = graph.get("counts") or {}
    report = {
        "schema_version": "toronto-market-coverage-1.1",
        "generated_at": utc_now(),
        "coverage_contract": {
            "meaning": "Measured source, reconciliation, document, relationship and screening coverage only.",
            "true_market_denominator": "No validated total installed Toronto cooling-tower population has been established from public data.",
            "prohibition": "Canonical candidate properties, AIC applications, large buildings, and aerial-screened properties are not substituted for the unknown tower-population denominator.",
        },
        "poc_reconciliation": {
            "original_properties": len(poc),
            "resolved_to_current_address_point": original_resolved,
            "unresolved_with_explicit_status": original_unresolved,
            "reconciliation_fraction": safe_fraction(original_resolved, len(poc)),
            "resolution_status_counts": recon.get("resolution_status_counts") or {},
        },
        "expanded_property_universe": {
            "canonical_address_point_properties": canonical,
            "original_poc_properties_present_in_spine": sum(bool(p.get("is_original_poc_property")) for p in props),
            "expanded_properties_beyond_original_poc": sum(not bool(p.get("is_original_poc_property")) for p in props),
            "properties_with_usable_coordinates": sum(p.get("longitude") is not None and p.get("latitude") is not None for p in props),
            "unresolved_candidate_addresses": (spine.get("counts") or {}).get("unresolved_candidate_addresses"),
        },
        "documentary_tower_evidence": {
            "original_poc_confirmed_properties": documentary_confirmed,
            "original_poc_supporting_only_properties": supporting_only,
            "original_poc_status_counts": dict(tower_status_counts),
            "aic_explicit_tower_candidate_records": len(candidate_records),
            "contract": "AIC candidates remain evidence/review candidates unless separately promoted by the TowerSignal evidence contract.",
        },
        "source_coverage": source_coverage,
        "aic_coverage": {
            "applications_total_source": aic.get("applications_total_source"),
            "unique_applications_scanned": aic.get("unique_applications_scanned"),
            "applications_in_shards": aic.get("applications_in_shards"),
            "application_pages_fetched": aic.get("application_pages_fetched"),
            "application_page_fetch_errors": aic.get("application_page_fetch_errors"),
            "documents_discovered": aic.get("documents_discovered"),
            "documents_parsed": aic.get("documents_parsed"),
            "documents_fetch_errors": aic.get("documents_fetch_errors"),
            "target_document_count": aic.get("target_document_count"),
            "documents_with_mechanical_signals": aic.get("documents_with_mechanical_signals"),
            "document_index_records": len(documents),
            "parse_status_counts": dict(parse_counts),
            "parsed_documents_with_zero_text_ocr_gap": zero_text,
            "category_counts": dict(category_counts),
            "documents_with_any_target_signal": signal_doc_count,
            "explicit_tower_candidate_records": len(candidate_records),
        },
        "relationship_coverage": {
            "edge_count": graph_counts.get("edges"),
            "relationship_counts": graph_counts.get("relationships") or {},
            "properties_by_relationship": graph_counts.get("properties_by_relationship") or {},
            "chain_coverage": graph_counts.get("chain_coverage") or {},
            "construction_act_statuses": {str(s.get("publisher")): s.get("automation_status") for s in construction.get("sources", []) if isinstance(s, dict)},
        },
        "aerial_screening": {
            "status": aerial.get("status"),
            "canonical_properties_with_coordinates": sum(p.get("longitude") is not None and p.get("latitude") is not None for p in props),
            "requested_positive_properties": (aerial.get("training") or {}).get("requested_positive_properties"),
            "requested_weak_controls": (aerial.get("training") or {}).get("requested_weak_controls"),
            "usable_training_images": (aerial.get("training") or {}).get("usable_images"),
            "candidate_properties_requested": aerial_scoring.get("candidate_properties_requested"),
            "candidate_properties_scored": aerial_scoring.get("candidate_properties_scored"),
            "persisted_candidate_records": len(aerial_records),
            "weak_label_validation": aerial.get("weak_label_validation"),
            "interpretation": "Weak-label visual similarity only. The measured discrimination is not cooling-tower detection accuracy and no aerial score upgrades tower confirmation.",
        },
        "true_cooling_tower_market_coverage": {
            "coverage_percent": None,
            "status": "UNKNOWN_DENOMINATOR",
            "reason": "No defensible public total installed cooling-tower denominator for Toronto has been established.",
        },
    }
    write_json(MARKET / "coverage_report.json", report)
    print(json.dumps({
        "poc": report["poc_reconciliation"],
        "expanded": report["expanded_property_universe"],
        "tower_evidence": report["documentary_tower_evidence"],
        "aic": report["aic_coverage"],
        "relationships": report["relationship_coverage"],
        "aerial": report["aerial_screening"],
        "true_market": report["true_cooling_tower_market_coverage"],
    }, indent=2))

if __name__ == "__main__":
    main()
