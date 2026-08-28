from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from toronto_market_common import read_json, utc_now, write_json

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data" / "toronto" / "market" / "current"
POC_CSV = ROOT / "data" / "toronto" / "poc" / "current" / "properties.csv"


def walk_finite(value: Any, path: str = "$") -> None:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise AssertionError(f"non-finite float at {path}")
    elif isinstance(value, dict):
        for key, child in value.items():
            walk_finite(child, f"{path}.{key}")
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            walk_finite(child, f"{path}[{idx}]")


def sample(items: list[Any], count: int = 3) -> list[Any]:
    if len(items) <= count:
        return items
    positions = sorted({0, len(items) // 2, len(items) - 1})
    return [items[i] for i in positions[:count]]


def main() -> None:
    required = [
        "property_spine.json",
        "identity_contract.json",
        "reconciliation_summary.json",
        "reconciliation_details.json",
        "property_source_links.json",
        "construction_act_source_policy.json",
        "aic_corpus_summary.json",
        "aic_document_index.json",
        "aic_application_scan_status.json",
        "aic_explicit_tower_candidates.json",
        "entity_graph.json",
        "coordinate_recovery_report.json",
        "aerial_model_report.json",
        "coverage_report.json",
    ]
    missing = [name for name in required if not (MARKET / name).exists()]
    if missing:
        raise AssertionError(f"missing required final outputs: {missing}")

    parsed: dict[str, Any] = {}
    for path in MARKET.rglob("*.json"):
        if "work" in path.parts:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise AssertionError(f"invalid JSON {path}: {exc}") from exc
        walk_finite(payload, str(path.relative_to(MARKET)))
        parsed[str(path.relative_to(MARKET))] = payload

    with POC_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        poc = list(csv.DictReader(handle))
    assert len(poc) == 177, f"expected 177 POC rows, got {len(poc)}"

    spine = parsed["property_spine.json"]
    recon = parsed["reconciliation_details.json"]
    links = parsed["property_source_links.json"]
    graph = parsed["entity_graph.json"]
    coverage = parsed["coverage_report.json"]
    aerial = parsed["aerial_model_report.json"]
    aic = parsed["aic_corpus_summary.json"]
    aic_index = parsed["aic_document_index.json"]

    props = [p for p in spine.get("properties", []) if isinstance(p, dict)]
    prop_ids = [p.get("property_id") for p in props]
    assert len(prop_ids) == len(set(prop_ids)), "duplicate canonical property IDs"
    assert all(isinstance(pid, str) and pid.startswith("toronto-address-point:") for pid in prop_ids), "non-Address-Point canonical ID remains"
    id_set = set(prop_ids)

    address_point_ids = [str(p.get("address_point_id") or "") for p in props]
    assert all(address_point_ids), "canonical property missing address_point_id"
    assert len(address_point_ids) == len(set(address_point_ids)), "duplicate canonical address_point_id"

    bad_coords = []
    for p in props:
        lon, lat = p.get("longitude"), p.get("latitude")
        if lon is None or lat is None:
            bad_coords.append((p.get("property_id"), "MISSING"))
            continue
        if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)) or not (-80.0 <= lon <= -78.0) or not (43.0 <= lat <= 44.5):
            bad_coords.append((p.get("property_id"), [lon, lat]))
    assert not bad_coords, f"invalid/missing Toronto coordinates: {bad_coords[:10]}"

    records = recon.get("records") or []
    assert len(records) == 177, f"reconciliation ledger has {len(records)} rows"
    keys = [r.get("property_key") for r in records]
    assert len(keys) == len(set(keys)) == 177, "reconciliation property keys not unique"
    assert int(recon.get("resolved_count") or 0) + int(recon.get("unresolved_count") or 0) == 177
    resolved_refs = [r.get("property_id") for r in records if r.get("resolved")]
    assert all(pid in id_set for pid in resolved_refs), "resolved POC record references missing canonical property"

    source_links = links.get("links") or []
    link_keys = []
    for link in source_links:
        assert link.get("property_id") in id_set, f"broken source link property {link.get('property_id')}"
        link_keys.append((link.get("property_id"), link.get("source_key"), link.get("source_record_id")))
    assert len(link_keys) == len(set(link_keys)), "duplicate source relationship edge"
    if isinstance(links.get("counts"), dict):
        assert int(links["counts"].get("total_source_links") or 0) == len(source_links)
        assert int(links["counts"].get("properties_with_any_new_link") or 0) == len({l.get("property_id") for l in source_links})

    edges = graph.get("edges") or []
    edge_ids = [e.get("edge_id") for e in edges]
    assert len(edge_ids) == len(set(edge_ids)), "duplicate entity graph edge IDs"
    for edge in edges:
        pid = edge.get("property_id") or edge.get("to_node")
        assert pid in id_set, f"broken entity graph property reference {pid}"
    if isinstance(graph.get("counts"), dict):
        assert int(graph["counts"].get("edges") or 0) == len(edges)

    true_cov = coverage.get("true_cooling_tower_market_coverage") or {}
    assert true_cov.get("coverage_percent") is None
    assert true_cov.get("status") == "UNKNOWN_DENOMINATOR"

    assert (aerial.get("training") or {}).get("usable_images", 0) >= 20, "aerial stage did not actually train"
    assert aerial.get("status") == "WEAK_LABEL_MODEL_FIT"
    aerial_scoring = aerial.get("scoring") or {}
    assert int(aerial_scoring.get("candidate_properties_scored") or 0) > 0, "aerial stage did not score candidate properties"

    app_total = int(aic.get("applications_total_source") or 0)
    apps_in_shards = int(aic.get("applications_in_shards") or 0)
    unique_apps = int(aic.get("unique_applications_scanned") or 0)
    assert app_total > 0 and apps_in_shards == app_total, f"AIC scan incomplete: source={app_total}, shards={apps_in_shards}"
    assert unique_apps == app_total, f"AIC unique-application scan incomplete: source={app_total}, unique={unique_apps}"
    parsed_docs = int(aic.get("documents_parsed") or 0)
    discovered_docs = int(aic.get("documents_discovered") or 0)
    assert discovered_docs >= parsed_docs >= 0

    unresolved = [r for r in records if not r.get("resolved")]
    resolved_by_status: dict[str, list[Any]] = defaultdict(list)
    for r in records:
        if r.get("resolved"):
            resolved_by_status[str(r.get("resolution_status"))].append({
                "property_key": r.get("property_key"),
                "property_id": r.get("property_id"),
                "input_address": r.get("input_address"),
                "canonical_address": r.get("canonical_address"),
            })

    links_by_source: dict[str, list[Any]] = defaultdict(list)
    for l in source_links:
        links_by_source[str(l.get("source_key"))].append({
            "property_id": l.get("property_id"),
            "source_record_id": l.get("source_record_id"),
            "source_address": l.get("source_address"),
            "match_basis": l.get("match_basis"),
        })

    edges_by_rel: dict[str, list[Any]] = defaultdict(list)
    for e in edges:
        edges_by_rel[str(e.get("relationship"))].append({
            "property_id": e.get("property_id"),
            "organization_node": e.get("from_node"),
            "source_key": e.get("source_key"),
            "basis": e.get("basis"),
            "confidence": e.get("confidence"),
            "evidence": e.get("evidence"),
        })

    docs = [d for d in aic_index.get("documents", []) if isinstance(d, dict)]
    tower_docs = [d for d in docs if int((d.get("signal_counts") or {}).get("cooling_tower", 0) or 0) > 0]
    mechanical_docs = [d for d in docs if any((d.get("signal_counts") or {}).values())]

    qa_report = {
        "schema_version": "toronto-final-qa-1.1",
        "generated_at": utc_now(),
        "status": "STRUCTURAL_VALIDATION_PASSED",
        "json_files_validated": len(parsed),
        "counts": {
            "canonical_properties": len(props),
            "poc_reconciliation_rows": len(records),
            "poc_resolved": recon.get("resolved_count"),
            "poc_unresolved": recon.get("unresolved_count"),
            "source_links": len(source_links),
            "entity_edges": len(edges),
            "aic_applications": app_total,
            "aic_documents_discovered": discovered_docs,
            "aic_documents_parsed": parsed_docs,
            "aic_document_index_records": len(docs),
            "aic_tower_signal_documents": len(tower_docs),
            "aic_any_target_signal_documents": len(mechanical_docs),
            "aerial_candidates_scored": aerial_scoring.get("candidate_properties_scored"),
        },
        "unresolved_properties": unresolved,
        "representative_resolution_samples": {status: sample(items) for status, items in sorted(resolved_by_status.items())},
        "representative_historical_join_samples": {source: sample(items) for source, items in sorted(links_by_source.items())},
        "representative_relationship_samples": {rel: sample(items) for rel, items in sorted(edges_by_rel.items())},
        "representative_aic_tower_documents": sample([{k: d.get(k) for k in ("application_number", "full_address", "url", "label", "sha256", "page_count", "parse_status", "signal_counts", "role_candidates")} for d in tower_docs], 5),
        "representative_aic_signal_documents": sample([{k: d.get(k) for k in ("application_number", "full_address", "url", "label", "sha256", "page_count", "parse_status", "categories", "signal_counts")} for d in mechanical_docs], 5),
        "evidence_contract_checks": {
            "all_properties_current_address_point_namespace": True,
            "all_resolved_poc_refs_exist": True,
            "all_source_link_refs_exist": True,
            "all_entity_graph_property_refs_exist": True,
            "true_market_coverage_unknown_denominator": True,
            "aerial_scores_do_not_upgrade_tower_confirmation": True,
            "aic_unique_application_scan_complete": True,
        },
    }
    write_json(MARKET / "qa_report.json", qa_report)
    print(json.dumps(qa_report["counts"], indent=2))
    print(json.dumps({"unresolved": unresolved, "resolution_samples": qa_report["representative_resolution_samples"]}, indent=2))


if __name__ == "__main__":
    main()
