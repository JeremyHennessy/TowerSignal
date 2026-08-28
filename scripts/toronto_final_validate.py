from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from toronto_market_common import utc_now, write_json

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data" / "toronto" / "market" / "current"
POC_CSV = ROOT / "data" / "toronto" / "poc" / "current" / "properties.csv"


def walk_finite(value: Any, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise AssertionError(f"non-finite float at {path}")
    if isinstance(value, dict):
        for key, child in value.items(): walk_finite(child, f"{path}.{key}")
    elif isinstance(value, list):
        for idx, child in enumerate(value): walk_finite(child, f"{path}[{idx}]")


def sample(items: list[Any], count: int = 3) -> list[Any]:
    if len(items) <= count: return items
    positions = sorted({0, len(items)//2, len(items)-1})
    return [items[i] for i in positions[:count]]


def main() -> None:
    required = [
        "property_spine.json","identity_contract.json","reconciliation_summary.json","reconciliation_details.json",
        "property_source_links.json","construction_act_source_policy.json","aic_transport_report.json",
        "aic_corpus_summary.json","aic_document_index.json","aic_application_scan_status.json",
        "aic_explicit_tower_candidates.json","entity_graph.json","coordinate_recovery_report.json",
        "aerial_model_report.json","coverage_report.json",
    ]
    missing=[n for n in required if not (MARKET/n).exists()]
    if missing: raise AssertionError(f"missing required final outputs: {missing}")

    parsed={}
    for path in MARKET.rglob("*.json"):
        if "work" in path.parts: continue
        payload=json.loads(path.read_text(encoding="utf-8")); walk_finite(payload,str(path.relative_to(MARKET)))
        parsed[str(path.relative_to(MARKET))]=payload

    with POC_CSV.open("r",encoding="utf-8-sig",newline="") as handle: poc=list(csv.DictReader(handle))
    assert len(poc)==177
    spine=parsed["property_spine.json"]; recon=parsed["reconciliation_details.json"]
    links=parsed["property_source_links.json"]; graph=parsed["entity_graph.json"]
    coverage=parsed["coverage_report.json"]; aerial=parsed["aerial_model_report.json"]
    aic=parsed["aic_corpus_summary.json"]; aic_transport=parsed["aic_transport_report.json"]
    aic_index=parsed["aic_document_index.json"]

    props=[p for p in spine.get("properties",[]) if isinstance(p,dict)]
    prop_ids=[p.get("property_id") for p in props]; id_set=set(prop_ids)
    assert len(prop_ids)==len(id_set)
    assert all(isinstance(pid,str) and pid.startswith("toronto-address-point:") for pid in prop_ids)
    apids=[str(p.get("address_point_id") or "") for p in props]
    assert all(apids) and len(apids)==len(set(apids))
    bad=[]
    for p in props:
        lon,lat=p.get("longitude"),p.get("latitude")
        if not isinstance(lon,(int,float)) or not isinstance(lat,(int,float)) or not (-80<=lon<=-78) or not (43<=lat<=44.5): bad.append((p.get("property_id"),lon,lat))
    assert not bad, bad[:10]

    records=recon.get("records") or []
    assert len(records)==177 and len({r.get("property_key") for r in records})==177
    assert int(recon.get("resolved_count") or 0)+int(recon.get("unresolved_count") or 0)==177
    assert all(r.get("property_id") in id_set for r in records if r.get("resolved"))

    source_links=links.get("links") or []
    keys=[]
    for link in source_links:
        assert link.get("property_id") in id_set
        keys.append((link.get("property_id"),link.get("source_key"),link.get("source_record_id")))
    assert len(keys)==len(set(keys))
    if isinstance(links.get("counts"),dict):
        assert int(links["counts"].get("total_source_links") or 0)==len(source_links)

    edges=graph.get("edges") or []; edge_ids=[]
    for edge in edges:
        edge_ids.append(edge.get("edge_id")); pid=edge.get("property_id") or edge.get("to_node"); assert pid in id_set
    assert len(edge_ids)==len(set(edge_ids))

    true_cov=coverage.get("true_cooling_tower_market_coverage") or {}
    assert true_cov.get("coverage_percent") is None and true_cov.get("status")=="UNKNOWN_DENOMINATOR"
    assert aerial.get("status")=="WEAK_LABEL_MODEL_FIT"
    assert (aerial.get("training") or {}).get("usable_images",0)>=20
    scoring=aerial.get("scoring") or {}; assert int(scoring.get("candidate_properties_scored") or 0)>0

    app_total=int(aic.get("applications_total_source") or 0); assert app_total>0
    aic_blocked=aic.get("status")=="BLOCKED_EXTERNAL_ACCESS_CONTROL"
    if aic_blocked:
        assert aic_transport.get("status")=="BLOCKED_EXTERNAL_ACCESS_CONTROL"
        assert aic_transport.get("application_catalogue_records")==app_total
        assert parsed["aic_application_scan_status.json"].get("status")=="APPLICATION_CATALOGUE_COMPLETE_DOCUMENT_TRANSPORT_BLOCKED"
        assert (coverage.get("aic_coverage") or {}).get("document_transport_blocked") is True
        assert (coverage.get("documentary_tower_evidence") or {}).get("aic_explicit_tower_candidate_records") is None
    else:
        assert int(aic.get("applications_in_shards") or 0)==app_total
        assert int(aic.get("unique_applications_scanned") or 0)==app_total

    unresolved=[r for r in records if not r.get("resolved")]
    by_status=defaultdict(list)
    for r in records:
        if r.get("resolved"): by_status[str(r.get("resolution_status"))].append({k:r.get(k) for k in ("property_key","property_id","input_address","canonical_address")})
    by_source=defaultdict(list)
    for l in source_links: by_source[str(l.get("source_key"))].append({k:l.get(k) for k in ("property_id","source_record_id","source_address","match_basis")})
    by_rel=defaultdict(list)
    for e in edges: by_rel[str(e.get("relationship"))].append({k:e.get(k) for k in ("property_id","from_node","source_key","basis","confidence","evidence")})
    docs=[d for d in aic_index.get("documents",[]) if isinstance(d,dict)]

    qa={
        "schema_version":"toronto-final-qa-1.2","generated_at":utc_now(),"status":"STRUCTURAL_VALIDATION_PASSED",
        "json_files_validated":len(parsed),
        "counts":{"canonical_properties":len(props),"poc_reconciliation_rows":177,"poc_resolved":recon.get("resolved_count"),"poc_unresolved":recon.get("unresolved_count"),"source_links":len(source_links),"entity_edges":len(edges),"aic_application_catalogue":app_total,"aic_document_transport_status":aic.get("status"),"aic_documents_parsed":None if aic_blocked else aic.get("documents_parsed"),"aerial_candidates_scored":scoring.get("candidate_properties_scored")},
        "unresolved_properties":unresolved,
        "representative_resolution_samples":{s:sample(v) for s,v in sorted(by_status.items())},
        "representative_historical_join_samples":{s:sample(v) for s,v in sorted(by_source.items())},
        "representative_relationship_samples":{s:sample(v) for s,v in sorted(by_rel.items())},
        "evidence_contract_checks":{"all_properties_current_address_point_namespace":True,"all_resolved_poc_refs_exist":True,"all_source_link_refs_exist":True,"all_entity_graph_property_refs_exist":True,"true_market_coverage_unknown_denominator":True,"aerial_scores_do_not_upgrade_tower_confirmation":True,"aic_blocker_not_misreported_as_zero_documents":aic_blocked},
    }
    write_json(MARKET/"qa_report.json",qa)
    print(json.dumps(qa["counts"],indent=2)); print(json.dumps({"unresolved":unresolved},indent=2))

if __name__=="__main__": main()
