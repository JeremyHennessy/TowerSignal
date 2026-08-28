from __future__ import annotations
import argparse, csv, hashlib, io, json, re
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from toronto_market_common import (
    canonical_street_address, clean_text, get_value, iter_record_objects, read_json,
    record_property_addresses, request_bytes, request_json, utc_now, write_json
)

ROOT=Path(__file__).resolve().parents[1]
TOR_CKAN="https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action"
ADDRESS_POINTS_CSV="https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/abedd8bc-e3dd-4d45-8e69-79165a76e4fa/resource/64d4e54b-738f-4cd9-a9e7-8050fac8a52f/download/address-points-4326.csv"
AIC_LAYER="https://gis.toronto.ca/arcgis/rest/services/cot_geospatial11/FeatureServer/60"
RENTSAFE_RESOURCE="3ad76a8c-0518-4df2-b94e-8c747d62f8c1"

def action(name:str, params:dict[str,Any])->Any:
    p=request_json(f"{TOR_CKAN}/{name}?{urlencode(params)}",timeout=120)
    if p.get("success") is not True: raise RuntimeError(f"Toronto CKAN {name} failed")
    return p.get("result")

def pull_health(market:Path)->None:
    result=action("package_search",{"q":'"Highrise Residential Health Hazards"',"rows":20})
    packages=result.get("results") or []
    pkg=next((p for p in packages if p.get("name")=="residential-health-hazards" or "highrise residential health hazards" in str(p.get("title","")).lower()),None)
    pkg=action("package_show",{"id":pkg["id"] if pkg else "residential-health-hazards"})
    resources=[r for r in pkg.get("resources",[]) if isinstance(r,dict)]
    usable=sorted([r for r in resources if r.get("datastore_active") or str(r.get("format","")).upper()=="CSV"],key=lambda r:not bool(r.get("datastore_active")))
    if not usable: raise RuntimeError("No usable Highrise Residential Health Hazards resource")
    r=usable[0]; rows=[]
    if r.get("datastore_active"):
        off=0
        while True:
            rs=action("datastore_search",{"resource_id":r["id"],"limit":1000,"offset":off})
            batch=[x for x in rs.get("records",[]) if isinstance(x,dict)]; rows+=batch
            if not batch or off+len(batch)>=int(rs.get("total") or 0): break
            off+=len(batch)
    else:
        rows=list(csv.DictReader(io.StringIO(request_bytes(r["url"]).decode("utf-8-sig",errors="replace"))))
    write_json(market/"open_licensed/toronto_highrise_residential_health_hazards.json",{
        "metadata":{"key":"toronto_highrise_residential_health_hazards","title":pkg.get("title"),"package_id":pkg.get("id"),
        "portal_url":"https://open.toronto.ca/dataset/residential-health-hazards/","license":"Open Government Licence - Toronto",
        "retrieved_at":utc_now(),"row_count":len(rows),"resource":{"id":r.get("id"),"name":r.get("name"),"url":r.get("url")},
        "semantic_contract":"Health records are property context only and never establish cooling-tower presence."},"records":rows})

def pull_aic(market:Path)->None:
    fields="OBJECTID,PROPERTYRSN,MAINPROPERTYRSN,FOLDERRSN,REFERENCEFILE,FOLDERTYPE,FOLDERNAME,FOLDERDESCRIPTION,ASSIGNEDPLANNER,ASSIGNEDPLANNER2,LONGITUDE,LATITUDE,LAST_MODIFIED_DATE,RECORD_STATUS,AIC_URL,FULL_ADDRESS,APPLICATION_NUMBER,APPLICATION_TYPE,LATEST_MILESTONE,LATEST_MILESTONE_DATE,HEARING_DATE,SUBMIT_DATE,COMPLETE_DATE,STATUS_DESC,FOLDERTYPE_DESC,STATUS_GROUP,AIC_ENCRYPTED_VALUE"
    rows=[]; off=0
    while True:
        q=urlencode({"where":"1=1","outFields":fields,"returnGeometry":"false","orderByFields":"OBJECTID ASC","resultOffset":off,"resultRecordCount":2000,"f":"json"})
        p=request_json(f"{AIC_LAYER}/query?{q}",timeout=120)
        if p.get("error"): raise RuntimeError(f"AIC query failed: {p['error']}")
        batch=[f["attributes"] for f in p.get("features",[]) if isinstance(f,dict) and isinstance(f.get("attributes"),dict)]
        rows+=batch
        if len(batch)<2000: break
        off+=len(batch)
    write_json(market/"open_licensed/toronto_aic_applications.json",{
        "metadata":{"key":"toronto_aic_applications","source_layer":AIC_LAYER,"retrieved_at":utc_now(),"row_count":len(rows),
        "coverage_caveat":"Some closed applications may not appear in AIC.","tower_semantics":"Application metadata does not upgrade tower status."},"applications":rows})

def construction_policy(market:Path)->None:
    write_json(market/"construction_act_source_policy.json",{
        "schema_version":"toronto-construction-act-source-policy-0.1","generated_at":utc_now(),
        "legal_context":{"effective_2026":"Ontario regulation names Daily Commercial News, Link2Build and Ontario Construction News as construction trade news websites.",
        "decision":"No automated bulk ingestion without a written licence/API agreement compatible with TowerSignal commercial use.",
        "distinction":"Statutory public publication does not override publisher website terms."},
        "sources":[
            {"publisher":"Daily Commercial News / ConstructConnect","automation_status":"PERMISSION_REQUIRED","url":"https://canada.constructconnect.com/dcn/certificates-and-notices"},
            {"publisher":"Link2Build","automation_status":"PERMISSION_REQUIRED","url":"https://www.link2build.ca/certificates/"},
            {"publisher":"Ontario Construction News","automation_status":"PERMISSION_REQUIRED","url":"https://ontarioconstructionnews.com/forms"}],
        "relationship_adapter":{"status":"READY_FOR_LICENSED_INPUT","roles":["OWNER","CONTRACTOR","PAYMENT_CERTIFIER","SUBCONTRACTOR"]}})

def point_address(row:dict[str,Any])->str:
    d=clean_text(get_value(row,"ADDRESS","FULL_ADDRESS","SITE_ADDRESS"))
    if d:return d
    n=clean_text(get_value(row,"LO_NUM","LOW_NUM","HOUSE_NUMBER","STREET_NUM","STREET_NUMBER")); s=clean_text(get_value(row,"LO_NUM_SUF","HOUSE_SUFFIX")); st=clean_text(get_value(row,"STREET_NAME","LF_NAME","LFNAME")); typ=clean_text(get_value(row,"STREET_TYPE")); dr=clean_text(get_value(row,"STREET_DIRECTION","STREET_DIR"))
    return " ".join(x for x in (n+s,st,typ,dr) if x)

def point_coordinates(row:dict[str,Any])->tuple[float|None,float|None]:
    try:return float(get_value(row,"LONGITUDE","LON","X")),float(get_value(row,"LATITUDE","LAT","Y"))
    except (TypeError,ValueError):pass
    try:
        coordinates=json.loads(str(row.get("geometry") or "{}")).get("coordinates")
        while isinstance(coordinates,list) and len(coordinates)==1:coordinates=coordinates[0]
        return float(coordinates[0]),float(coordinates[1])
    except (TypeError,ValueError,IndexError,json.JSONDecodeError):return None,None

def build_spine(poc_csv:Path,warehouse:Path,market:Path)->dict[str,Any]:
    poc=list(csv.DictReader(poc_csv.open("r",encoding="utf-8-sig",newline=""))); candidates={}
    def add(addr,source,pkey=None,status=None,gid=None):
        raw=clean_text(addr); canon=canonical_street_address(raw)
        if not canon:return
        e=candidates.setdefault(canon,{"canonical_address":canon,"aliases":[],"sources":[],"poc_keys":[],"statuses":[],"geoids":[]})
        if raw and raw not in e["aliases"]:e["aliases"].append(raw)
        if source not in e["sources"]:e["sources"].append(source)
        if pkey and pkey not in e["poc_keys"]:e["poc_keys"].append(pkey)
        if status and status not in e["statuses"]:e["statuses"].append(status)
        if gid and gid not in e["geoids"]:e["geoids"].append(gid)
    for r in poc:add(r.get("address"),"toronto_poc",r.get("property_key"),r.get("tower_status"),r.get("geo_id"))
    for root in (warehouse/"open_licensed",market/"open_licensed"):
        if not root.exists():continue
        for path in root.glob("*.json"):
            if path.name.endswith("_metadata.json"):continue
            try:p=read_json(path)
            except Exception:continue
            for rec in iter_record_objects(p):
                for a in record_property_addresses(rec):add(a,path.stem)
    targets=set(candidates); legacy_targets={g for e in candidates.values() for g in e["geoids"]}
    data=request_bytes(ADDRESS_POINTS_CSV,timeout=180,max_bytes=300_000_000); reader=csv.DictReader(io.StringIO(data.decode("utf-8-sig",errors="replace"))); matches=defaultdict(dict); by_point_id={}; scanned=0
    for row in reader:
        scanned+=1; point_id=clean_text(row.get("ADDRESS_POINT_ID")); addr=point_address(row); canon=canonical_street_address(addr); lon,lat=point_coordinates(row)
        point={"address_point_id":point_id,"address_point_id_link":clean_text(row.get("ADDRESS_POINT_ID_LINK")) or None,"address_id":clean_text(row.get("ADDRESS_ID")) or None,"address_id_link":clean_text(row.get("ADDRESS_ID_LINK")) or None,"address_string_id":clean_text(row.get("ADDRESS_STRING_ID")) or None,"centreline_id":clean_text(row.get("CENTRELINE_ID")) or None,"address":addr,"canonical_address":canon,"longitude":lon,"latitude":lat,"municipality":clean_text(row.get("MUNICIPALITY_NAME") or row.get("MUNICIPALITY")) or None,"address_class":clean_text(row.get("ADDRESS_CLASS")) or None,"address_class_description":clean_text(row.get("ADDRESS_CLASS_DESC")) or None,"maintenance_stage":clean_text(row.get("MAINT_STAGE")) or None}
        by_point_id[point_id]=point
        if canon in targets:matches[canon][point_id]=point
        if point_id in legacy_targets:
            for c,e in candidates.items():
                if point_id in e["geoids"]:matches[c][point_id]=point
    props=[]; unresolved=[]; resolution_by_poc={}; property_by_identifier={}
    for canon,e in sorted(candidates.items()):
        opts=list(matches.get(canon,{}).values())
        direct=[o for o in opts if o["address_point_id"] in e["geoids"]]; roots={o.get("address_point_id_link") or o["address_point_id"] for o in opts}; chosen=None; basis=None
        if direct:chosen=direct[0];basis="EXACT_LEGACY_GEO_ID_VALUE_AS_CURRENT_ADDRESS_POINT_ID"
        elif len(roots)==1 and opts:chosen=by_point_id.get(next(iter(roots))) or opts[0];basis="EXACT_UNIQUE_CIVIC_ADDRESS"
        elif len(opts)==1:chosen=opts[0];basis="EXACT_UNIQUE_CIVIC_ADDRESS"
        if not chosen:
            reason="AMBIGUOUS_MUNICIPAL_ADDRESS" if opts else "NO_CURRENT_MUNICIPAL_MATCH"; unresolved.append({**e,"resolution_status":reason,"match_count":len(opts),"candidate_address_point_ids":sorted(o["address_point_id"] for o in opts)})
            for key in e["poc_keys"]:resolution_by_poc[key]={"property_key":key,"resolution_status":reason,"canonical_address":canon,"legacy_geo_ids":e["geoids"],"candidate_address_point_ids":sorted(o["address_point_id"] for o in opts)}
            continue
        canonical_id=chosen.get("address_point_id_link") or chosen["address_point_id"]; canonical_point=by_point_id.get(canonical_id) or chosen; pid=f"toronto-address-point:{canonical_id}"; prop=property_by_identifier.get(pid)
        if prop is None:
            prop={"property_id":pid,"canonical_identifier_type":"TORONTO_ADDRESS_POINT_ID","canonical_identifier":canonical_id,"legacy_geo_ids":[],"address_point_id":canonical_id,"address_id":canonical_point.get("address_id"),"canonical_address":canonical_street_address(canonical_point.get("address") or canon),"display_address":canonical_point.get("address") or chosen.get("address") or e["aliases"][0],"longitude":canonical_point.get("longitude"),"latitude":canonical_point.get("latitude"),"municipality":canonical_point.get("municipality"),"address_aliases":[],"source_keys":[],"is_original_poc_property":False,"poc_property_keys":[],"poc_tower_statuses":[],"identity_basis":basis,"identity_confidence":"DETERMINISTIC","source_address_point_ids":[]}; property_by_identifier[pid]=prop;props.append(prop)
        for field,values in (("legacy_geo_ids",e["geoids"]),("address_aliases",e["aliases"]),("source_keys",e["sources"]),("poc_property_keys",e["poc_keys"]),("poc_tower_statuses",e["statuses"]),("source_address_point_ids",[chosen["address_point_id"]])):prop[field]=sorted(set(prop[field])|set(values))
        prop["is_original_poc_property"]|=bool(e["poc_keys"])
        for key in e["poc_keys"]:resolution_by_poc[key]={"property_key":key,"resolution_status":basis,"property_id":pid,"canonical_identifier":canonical_id,"matched_address_point_id":chosen["address_point_id"],"legacy_geo_ids":e["geoids"],"canonical_address":canon}
    allp={r.get("property_key") for r in poc if r.get("property_key")}
    missing=allp-set(resolution_by_poc)
    if missing:raise RuntimeError(f"POC reconciliation lost records: {sorted(missing)}")
    categories={}
    for r in resolution_by_poc.values():categories[r["resolution_status"]]=categories.get(r["resolution_status"],0)+1
    resolved=sum(bool(r.get("property_id")) for r in resolution_by_poc.values())
    out={"schema_version":"toronto-property-spine-0.2","generated_at":utc_now(),"identity_contract":{"canonical_id":"toronto-address-point:<ADDRESS_POINT_ID>; linked child points resolve to ADDRESS_POINT_ID_LINK parent","identifier_semantics":{"ADDRESS_POINT_ID":"unique municipal spatial address-point identifier and TowerSignal canonical key","ADDRESS_ID":"unique repository address-record identifier retained as an alias, not used as the spatial spine","ADDRESS_POINT_ID_LINK":"explicit municipal parent/related address-point link; used for canonical-parent resolution","ADDRESS_ID_LINK":"corresponding address-record link; retained as provenance","legacy_GEO_ID":"building-permit GEO_ID values empirically reconcile to current ADDRESS_POINT_ID values; retained as legacy aliases"},"fuzzy_matching":False,"tower_semantics":"Identity never upgrades tower status."},"counts":{"original_poc_properties":len(allp),"original_poc_resolved":resolved,"original_poc_unresolved":len(allp)-resolved,"poc_resolution_categories":dict(sorted(categories.items())),"candidate_addresses_total":len(candidates),"canonical_properties_resolved":len(props),"expanded_properties_beyond_original_poc":sum(not p["is_original_poc_property"] for p in props),"unresolved_candidate_addresses":len(unresolved),"address_point_rows_scanned":scanned},"properties":sorted(props,key=lambda p:p["property_id"]),"poc_reconciliation":[resolution_by_poc[k] for k in sorted(resolution_by_poc)],"unresolved":unresolved}
    write_json(market/"property_spine.json",out);write_json(market/"reconciliation_summary.json",{k:out[k] for k in ("schema_version","generated_at","identity_contract","counts","poc_reconciliation","unresolved")});return out

SOURCE_FILES=[("chemtrac_history","warehouse","open_licensed/chemtrac_history.json"),("ontario_ewrb_large_buildings","warehouse","open_licensed/ontario_ewrb_large_buildings.json"),("ontario_environmental_compliance_reports","warehouse","open_licensed/ontario_environmental_compliance_reports.json"),("toronto_highrise_residential_health_hazards","market","open_licensed/toronto_highrise_residential_health_hazards.json"),("toronto_aic_applications","market","open_licensed/toronto_aic_applications.json")]

def join_sources(warehouse:Path,market:Path)->dict[str,Any]:
    spine=read_json(market/"property_spine.json"); props=spine["properties"]; byaddr={}
    for p in props:
        for address in [p.get("canonical_address"),*p.get("address_aliases",[])]:byaddr[canonical_street_address(address)]=p
    links=[]; summaries={}
    for source,loc,rel in SOURCE_FILES:
        path=(warehouse if loc=="warehouse" else market)/rel; payload=read_json(path)
        if payload is None:summaries[source]={"status":"SOURCE_FILE_MISSING"};continue
        records=list(iter_record_objects(payload)); rwa=mr=0; mp=set();years=set();organizations=set()
        for resource in (payload.get("metadata",{}).get("resources",[]) if isinstance(payload,dict) else []):
            try:
                year=int(resource.get("year"));
                if 1990<=year<=datetime.now(timezone.utc).year+1:years.add(year)
            except (TypeError,ValueError):pass
        for i,r in enumerate(records):
            for key,value in r.items():
                normalized=re.sub(r"[^a-z]","",str(key).lower())
                if "organization" in normalized or "reporter" in normalized:
                    name=clean_text(value)
                    if name and name.upper() not in {"N/A","NA","NONE","UNKNOWN","NOT AVAILABLE"}:organizations.add(name)
                if "date" in normalized or "year" in normalized:
                    found={int(x) for x in re.findall(r"\b(?:19|20)\d{2}\b",str(value))}
                    try:
                        number=float(value)
                        if number>100_000_000_000:found.add(datetime.fromtimestamp(number/1000,timezone.utc).year)
                    except (TypeError,ValueError,OverflowError,OSError):pass
                    years|={year for year in found if 1990<=year<=datetime.now(timezone.utc).year+1}
            addrs=record_property_addresses(r); rwa+=bool(addrs); matched=False
            for a in addrs:
                p=byaddr.get(canonical_street_address(a))
                if not p:continue
                rid=next((r.get(k) for k in ("_id","OBJECTID","id","APPLICATION_NUMBER","FOLDERRSN") if r.get(k) not in (None,"")),None)
                links.append({"property_id":p["property_id"],"source_key":source,"source_record_id":f"{source}:{rid if rid is not None else 'row'}:{i}","source_row_index":i,"match_basis":"EXACT_CANONICAL_PROPERTY_ADDRESS_TO_ADDRESS_POINT_SPINE","source_address":a});mp.add(p["property_id"]);matched=True;break
            mr+=matched
        summaries[source]={"status":"JOINED","source_records":len(records),"records_with_property_address":rwa,"matched_records":mr,"unmatched_records":len(records)-mr,"matched_canonical_properties":len(mp),"earliest_year":min(years) if years else None,"latest_year":max(years) if years else None,"available_years":sorted(years),"distinct_organizations_or_reporters":len(organizations),"identity_limitation":None if rwa else "PUBLIC_SOURCE_HAS_NO_DETERMINISTIC_PROPERTY_ADDRESS_FIELD"}
    out={"schema_version":"toronto-market-property-links-0.2","generated_at":utc_now(),"join_contract":{"basis":"Exact canonical property-address equality to municipal Address Point spine","fuzzy_matching":False},"counts":{"canonical_properties":len(props),"total_source_links":len(links),"properties_with_any_new_link":len({l["property_id"] for l in links})},"sources":summaries,"links":links}; write_json(market/"property_source_links.json",out);return out

def merge_aic(market:Path)->dict[str,Any]:
    paths=sorted((market/"work").glob("aic_corpus_shard_*.json"))
    if not paths:raise RuntimeError("No AIC shard outputs")
    shards=[read_json(p) for p in paths]; apps=[]; totals={k:0 for k in ("application_pages_attempted","application_pages_fetched","application_page_fetch_errors","application_attachment_api_gated","application_legacy_redirects_without_attachment_catalogue","documents_discovered","documents_parsed","documents_scanned_or_image_only","documents_encrypted","documents_corrupt_or_unreadable","documents_oversized_skipped","documents_not_pdf","documents_fetch_errors","target_document_count","documents_with_mechanical_signals")}
    for s in shards:
        apps+=s.get("applications",[])
        for k in totals:totals[k]+=int(s.get(k,0) or 0)
    apps.sort(key=lambda a:int(a.get("objectid") or 0)); index=[]; scan=[]; cats={}; sigs={}; tower=[]
    for a in apps:
        scan.append({"objectid":a.get("objectid"),"application_number":a.get("application_number"),"full_address":a.get("full_address"),"page_status":a.get("page_status"),"document_count":a.get("document_count",0)})
        for d in a.get("documents",[]):
            e={"objectid":a.get("objectid"),"application_number":a.get("application_number"),"full_address":a.get("full_address"),"application_type":a.get("application_type"),"url":d.get("url"),"label":d.get("label"),"sha256":d.get("sha256"),"bytes":d.get("bytes"),"page_count":d.get("page_count"),"text_chars_extracted":d.get("text_chars_extracted"),"parse_status":d.get("parse_status"),"extraction_confidence":d.get("extraction_confidence"),"categories":d.get("categories",[]),"signal_counts":d.get("signal_counts",{}),"evidence_excerpts":d.get("evidence_excerpts",[]),"role_candidates":d.get("role_candidates",[])}; index.append(e)
            for c in e["categories"]:cats[c]=cats.get(c,0)+1
            for k,v in e["signal_counts"].items():sigs[k]=sigs.get(k,0)+int(v or 0)
            if int(e["signal_counts"].get("cooling_tower",0) or 0)>0:tower.append(e)
    total=max((int(s.get("applications_total_source",0) or 0) for s in shards),default=0); unique=len({a.get("objectid") for a in apps if a.get("objectid") is not None})
    summary={"schema_version":"toronto-aic-corpus-0.2","generated_at":utc_now(),"shard_count":len(shards),"applications_total_source":total,"applications_in_shards":sum(int(s.get("applications_in_shard",0) or 0) for s in shards),"unique_applications_scanned":unique,**totals,"category_counts":cats,"signal_mention_counts":sigs,"explicit_cooling_tower_document_candidates":len(tower),"coverage":{"application_scan_fraction":unique/total if total else None},"evidence_contract":{"candidate_only":"AIC extraction does not mutate confirmed tower status.","ocr":"No OCR; scanned PDFs may have zero extracted text."}}
    write_json(market/"aic_corpus_summary.json",summary);write_json(market/"aic_document_index.json",{"metadata":summary,"documents":index});write_json(market/"aic_application_scan_status.json",{"metadata":summary,"applications":scan});write_json(market/"aic_explicit_tower_candidates.json",{"metadata":summary,"documents":tower});write_json(market/"work/aic_full_corpus.json",{"metadata":summary,"applications":apps});return summary

def fetch_rentsafe()->list[dict[str,Any]]:
    rows=[];off=0
    while True:
        r=action("datastore_search",{"resource_id":RENTSAFE_RESOURCE,"limit":1000,"offset":off});b=[x for x in r.get("records",[]) if isinstance(x,dict)];rows+=b
        if not b or off+len(b)>=int(r.get("total") or 0):break
        off+=len(b)
    return rows

def build_graph(warehouse:Path,market:Path)->dict[str,Any]:
    spine=read_json(market/"property_spine.json");props=spine["properties"];byaddr={}
    for p in props:
        for address in [p.get("canonical_address"),*p.get("address_aliases",[])]:byaddr[canonical_street_address(address)]=p
    byid={p["property_id"]:p for p in props};by_poc={key:p for p in props for key in p.get("poc_property_keys",[])}
    nodes={p["property_id"]:{"node_id":p["property_id"],"node_type":"PROPERTY","name":p.get("display_address"),"address_point_id":p.get("address_point_id")} for p in props};edges={}
    def oid(name):return "org:"+hashlib.sha1(clean_text(name).upper().encode()).hexdigest()[:16]
    def add(name,pid,rel,src,basis,conf,evidence=None):
        n=clean_text(name)
        if not n or n.upper() in {"N/A","NA","NONE","UNKNOWN","NOT AVAILABLE"} or pid not in byid:return
        o=oid(n);nodes.setdefault(o,{"node_id":o,"node_type":"ORGANIZATION","name":n});key=hashlib.sha1(json.dumps([o,pid,rel,src,evidence],sort_keys=True,default=str).encode()).hexdigest()[:20]
        edges.setdefault(key,{"edge_id":"edge:"+key,"from_node":o,"to_node":pid,"relationship":rel,"source_key":src,"basis":basis,"confidence":conf,"evidence":evidence or {}})
    for r in fetch_rentsafe():
        p=byaddr.get(canonical_street_address(r.get("SITE_ADDRESS")))
        if p:add(r.get("PROP_MANAGEMENT_COMPANY_NAME"),p["property_id"],"PROPERTY_MANAGER_OF","rentsafe_registration","EXPLICIT_PROP_MANAGEMENT_COMPANY_NAME_AT_EXACT_ADDRESS","CONFIRMED_SOURCE_FIELD",{"rsn":r.get("RSN")})
    old=read_json(warehouse/"property_joins.json",{}) or {}
    for item in old.get("properties",[]):
        legacy_key=item.get("property_key");mapped=by_poc.get(legacy_key);pid=mapped.get("property_id") if mapped else None
        if pid not in byid:continue
        m=item.get("matches",{})
        for r in m.get("tobids_awarded_contracts",[]) or []:add(r.get("successful_supplier"),pid,"CONTRACTOR_AT_PROPERTY","tobids_awarded_contracts","SUCCESSFUL_SUPPLIER_IN_EXACT_PROPERTY-AWARD_MATCH","CONFIRMED_SOURCE_FIELD",{"document_number":r.get("document_number"),"award_date":r.get("award_date")})
        for r in m.get("ontario_bps_energy_2024",[]) or []:add(r.get("organization"),pid,"FACILITY_OPERATOR_OR_REPORTER_AT","ontario_bps_energy_2024","ORGANIZATION_FIELD_AT_EXACT_PROPERTY_ADDRESS","SOURCE_ROLE_NOT_OWNERSHIP",{"property_name":r.get("property_name")})
    roles={"OWNER":"OWNER_OF","PROPERTY_MANAGER":"PROPERTY_MANAGER_OF","PROPERTY_MANAGEMENT":"PROPERTY_MANAGER_OF","MECHANICAL_CONTRACTOR":"MECHANICAL_CONTRACTOR_FOR","CONTRACTOR":"CONTRACTOR_FOR","MECHANICAL_ENGINEER":"MECHANICAL_ENGINEER_FOR","MECHANICAL_CONSULTANT":"MECHANICAL_CONSULTANT_FOR","ENGINEER":"ENGINEER_FOR","ARCHITECT":"ARCHITECT_FOR","CONSULTANT":"CONSULTANT_FOR","APPLICANT":"APPLICANT_FOR"}
    for d in (read_json(market/"aic_document_index.json",{}) or {}).get("documents",[]):
        p=byaddr.get(canonical_street_address(d.get("full_address")))
        if not p:continue
        for c in d.get("role_candidates",[]) or []:
            rel=roles.get(str(c.get("role","")).upper())
            if rel:add(c.get("name"),p["property_id"],rel,"toronto_aic_supporting_documents","ROLE_LABEL_AND_NAME_EXTRACTED_FROM_AIC_DOCUMENT","TEXT_PATTERN_CANDIDATE_REQUIRES_REVIEW",{"application_number":d.get("application_number"),"document_url":d.get("url")})
    el=list(edges.values());counts={}
    for e in el:counts[e["relationship"]]=counts.get(e["relationship"],0)+1
    sets={r:{e["to_node"] for e in el if e["relationship"]==r} for r in counts};chain={"properties_with_owner":len(sets.get("OWNER_OF",set())),"properties_with_property_manager":len(sets.get("PROPERTY_MANAGER_OF",set())),"properties_with_engineer_or_mechanical_consultant":len(sets.get("ENGINEER_FOR",set())|sets.get("MECHANICAL_ENGINEER_FOR",set())|sets.get("MECHANICAL_CONSULTANT_FOR",set())),"properties_with_contractor_or_mechanical_contractor":len(sets.get("CONTRACTOR_AT_PROPERTY",set())|sets.get("CONTRACTOR_FOR",set())|sets.get("MECHANICAL_CONTRACTOR_FOR",set()))}
    out={"schema_version":"toronto-market-entity-graph-0.1","generated_at":utc_now(),"relationship_contract":{"ownership":"Operator/reporter/manager/supplier are not relabelled owner.","aic":"Text-pattern edges require review.","construction_act":"No publisher data until licensed."},"counts":{"nodes":len(nodes),"organization_nodes":sum(n["node_type"]=="ORGANIZATION" for n in nodes.values()),"property_nodes":len(props),"edges":len(el),"relationships":counts,"chain_coverage":chain},"nodes":list(nodes.values()),"edges":el};write_json(market/"entity_graph.json",out);return out

def coverage(poc_csv:Path,market:Path)->dict[str,Any]:
    poc=list(csv.DictReader(poc_csv.open("r",encoding="utf-8-sig",newline="")));confirmed=sum(r.get("tower_status")=="CONFIRMED" for r in poc);sp=read_json(market/"property_spine.json");links=read_json(market/"property_source_links.json");aic=read_json(market/"aic_corpus_summary.json",{}) or {};aerial=read_json(market/"aerial_model_report.json",{}) or {};graph=read_json(market/"entity_graph.json",{}) or {};c=sp["counts"];exp=int(c.get("canonical_properties_resolved",0) or 0);sm={}
    for s,d in links.get("sources",{}).items():sm[s]={**d,"candidate_universe_property_link_fraction":d.get("matched_canonical_properties")/exp if exp and isinstance(d.get("matched_canonical_properties"),int) else None}
    out={"schema_version":"toronto-market-coverage-0.2","generated_at":utc_now(),"true_cooling_tower_market_coverage":{"status":"UNKNOWN_DENOMINATOR","coverage_percent":None,"reason":"No validated authoritative denominator for all Toronto cooling towers has been established.","known_documentary_confirmed_properties":confirmed},"identity_coverage":{"original_poc_properties":c.get("original_poc_properties"),"original_poc_resolved":c.get("original_poc_resolved"),"original_poc_unresolved":c.get("original_poc_unresolved"),"poc_resolution_categories":c.get("poc_resolution_categories"),"original_poc_reconciliation_fraction":c.get("original_poc_resolved")/c.get("original_poc_properties") if c.get("original_poc_properties") else None,"expanded_canonical_candidate_property_universe":exp,"properties_beyond_original_poc":c.get("expanded_properties_beyond_original_poc"),"unresolved_candidate_addresses":c.get("unresolved_candidate_addresses")},"source_identity_coverage":sm,"aic_corpus_coverage":{"applications_total_source":aic.get("applications_total_source"),"unique_applications_scanned":aic.get("unique_applications_scanned"),"application_scan_fraction":(aic.get("coverage") or {}).get("application_scan_fraction"),"documents_discovered":aic.get("documents_discovered"),"documents_parsed":aic.get("documents_parsed"),"explicit_cooling_tower_document_candidates":aic.get("explicit_cooling_tower_document_candidates"),"ocr_gap":"Image-only documents not covered."},"aerial_coverage":{"status":aerial.get("status"),"candidate_properties_scored":(aerial.get("scoring") or {}).get("candidate_properties_scored"),"interpretation":"Weak visual similarity only."},"relationship_coverage":(graph.get("counts") or {}).get("chain_coverage",{}),"market_measurement_contract":{"true_market_pct":"Blocked until defensible denominator exists.","current_metric":"candidate-universe evidence penetration"}};write_json(market/"coverage_report.json",out);return out

def core(poc:Path,warehouse:Path,market:Path)->None:
    pull_health(market);pull_aic(market);construction_policy(market);build_spine(poc,warehouse,market);join_sources(warehouse,market);print(json.dumps({"core":"ok","spine":read_json(market/"property_spine.json")["counts"],"links":read_json(market/"property_source_links.json")["counts"]},indent=2))

def finalize(poc:Path,warehouse:Path,market:Path)->None:
    a=merge_aic(market);g=build_graph(warehouse,market);c=coverage(poc,market);print(json.dumps({"aic":a,"graph":g["counts"],"coverage":c["identity_coverage"]},indent=2))

def main():
    p=argparse.ArgumentParser();p.add_argument("stage",choices=["core","finalize"]);p.add_argument("--poc",type=Path,default=ROOT/"data/toronto/poc/current/properties.csv");p.add_argument("--warehouse",type=Path,default=ROOT/"data/toronto/warehouse/current");p.add_argument("--market",type=Path,default=ROOT/"data/toronto/market/current");a=p.parse_args();(core if a.stage=="core" else finalize)(a.poc,a.warehouse,a.market)
if __name__=="__main__":main()
