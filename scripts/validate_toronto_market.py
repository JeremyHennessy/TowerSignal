from __future__ import annotations

import argparse,json,math
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]

def load(path:Path)->Any:
    with path.open(encoding="utf-8") as handle:return json.load(handle,parse_constant=lambda value:(_ for _ in ()).throw(ValueError(f"non-finite JSON value {value}")))

def finite(value:Any,path:str="root")->None:
    if isinstance(value,float) and not math.isfinite(value):raise AssertionError(f"non-finite number at {path}")
    if isinstance(value,dict):
        for key,item in value.items():finite(item,f"{path}.{key}")
    elif isinstance(value,list):
        for index,item in enumerate(value):finite(item,f"{path}[{index}]")

def validate(market:Path)->dict[str,int]:
    required=["property_spine.json","reconciliation_summary.json","property_source_links.json","aic_corpus_summary.json","aic_document_index.json","aic_application_scan_status.json","aic_explicit_tower_candidates.json","entity_graph.json","coverage_report.json"]
    payloads={name:load(market/name) for name in required}
    for name,payload in payloads.items():finite(payload,name)
    spine=payloads["property_spine.json"];properties=spine["properties"];property_ids=[p["property_id"] for p in properties]
    assert len(property_ids)==len(set(property_ids)),"duplicate canonical property_id"
    assert len(spine["poc_reconciliation"])==spine["counts"]["original_poc_properties"]==177,"POC outcome count mismatch"
    assert all(p.get("canonical_identifier_type")=="TORONTO_ADDRESS_POINT_ID" for p in properties),"invalid canonical identifier type"
    assert all(-79.7<=float(p["longitude"])<=-79.0 and 43.5<=float(p["latitude"])<=44.0 for p in properties),"invalid Toronto coordinate"
    property_set=set(property_ids);links=payloads["property_source_links.json"]["links"]
    assert all(link["property_id"] in property_set for link in links),"broken property source link"
    link_keys=[(link["source_key"],link["source_record_id"],link["property_id"]) for link in links]
    assert len(link_keys)==len(set(link_keys)),"duplicate source/property edge"
    graph=payloads["entity_graph.json"];node_ids=[node["node_id"] for node in graph["nodes"]];node_set=set(node_ids)
    assert len(node_ids)==len(node_set),"duplicate graph node"
    edge_ids=[edge["edge_id"] for edge in graph["edges"]]
    assert len(edge_ids)==len(set(edge_ids)),"duplicate graph edge"
    assert all(edge["from_node"] in node_set and edge["to_node"] in node_set for edge in graph["edges"]),"broken graph edge"
    coverage=payloads["coverage_report.json"]
    assert coverage["true_cooling_tower_market_coverage"]["coverage_percent"] is None,"manufactured market percentage"
    assert coverage["true_cooling_tower_market_coverage"]["status"]=="UNKNOWN_DENOMINATOR","invalid denominator status"
    return {"properties":len(properties),"poc_outcomes":len(spine["poc_reconciliation"]),"source_links":len(links),"graph_nodes":len(node_ids),"graph_edges":len(edge_ids)}

def main()->None:
    parser=argparse.ArgumentParser();parser.add_argument("--market",type=Path,default=ROOT/"data/toronto/market/current");args=parser.parse_args()
    print(json.dumps({"status":"VALID","counts":validate(args.market)},indent=2))

if __name__=="__main__":main()
