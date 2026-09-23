from __future__ import annotations
import concurrent.futures as cf
import datetime as dt
from decimal import Decimal, InvalidOperation
import gzip, hashlib, json, os, re, threading, time
from collections import Counter, defaultdict
from pathlib import Path
import urllib.parse as up
import urllib.request as ur

OUT = Path(os.getenv("AUDIT_OUTPUT", ".audit-stage4"))
OUT.mkdir(parents=True, exist_ok=True)
LIVE = "https://jeremyhennessy.github.io/TowerSignal/"
REQS = []
LOCK = threading.Lock()

def save(name, obj):
    p = OUT / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

def gzsave(name, obj):
    with gzip.open(OUT / name, "wt", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)

def get(url, *, raw=False, timeout=75):
    headers = {"User-Agent": "TowerSignal-independent-stage4-audit/20260923"}
    for attempt in range(3):
        rec = {"url": url, "requested_at": dt.datetime.now(dt.timezone.utc).isoformat(), "attempt": attempt + 1}
        try:
            with ur.urlopen(ur.Request(url, headers=headers), timeout=timeout) as r:
                b = r.read()
                rec.update(status=r.status, bytes=len(b), sha256=hashlib.sha256(b).hexdigest(),
                           headers={k:v for k,v in r.headers.items() if k.lower() in ("date","etag","last-modified","content-type","cache-control")})
            with LOCK: REQS.append(rec)
            return b if raw else json.loads(b)
        except Exception as ex:
            rec.update(error=str(ex), status=getattr(ex, "code", None))
            with LOCK: REQS.append(rec)
            if getattr(ex, "code", None) not in (429,500,502,503,504) or attempt == 2:
                return {"_audit_error": str(ex), "url": url}
            time.sleep(2 * (attempt + 1))

def clean(v):
    if v is None: return None
    s = str(v).strip()
    return s or None

def pos_int(v):
    s = clean(v)
    if not s: return None
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    if not d.is_finite() or d <= 0 or d != d.to_integral_value():
        return None
    return str(int(d))

def assigned_bin(v):
    s = pos_int(v)
    if not s or len(s) != 7 or s[0] not in "12345" or s[1:] == "000000":
        return None
    return s

def norm_bbl(v):
    s = pos_int(v)
    if not s or len(s) != 10 or s[0] not in "12345":
        return None
    if int(s[1:6]) <= 0 or int(s[6:]) <= 0:
        return None
    return s

def registration_bbl(row):
    try:
        borough = int(Decimal(str(row.get("boroid"))))
        block = int(Decimal(str(row.get("block"))))
        lot = int(Decimal(str(row.get("lot"))))
    except Exception:
        return None
    if borough not in range(1,6) or block <= 0 or lot <= 0:
        return None
    return f"{borough}{block:05d}{lot:04d}"

def stable_full_socrata(host, ident, order):
    meta_before = get(f"https://{host}/api/views/{ident}.json")
    qroot = f"https://{host}/resource/{ident}.json"
    count_before = get(qroot + "?" + up.urlencode({"$select":"count(*) as n"}))
    expected = int(count_before[0]["n"]) if isinstance(count_before, list) and count_before else None
    rows = []
    offset = 0
    complete = True
    while True:
        params = {"$select":"*,:id as audit_row_id", "$order":order, "$limit":50000, "$offset":offset}
        page = get(qroot + "?" + up.urlencode(params), timeout=100)
        if not isinstance(page, list):
            complete = False
            break
        rows.extend(page)
        if len(page) < 50000: break
        offset += 50000
    count_after = get(qroot + "?" + up.urlencode({"$select":"count(*) as n"}))
    meta_after = get(f"https://{host}/api/views/{ident}.json")
    expected_after = int(count_after[0]["n"]) if isinstance(count_after, list) and count_after else None
    ids = [r.get("audit_row_id") for r in rows]
    stable = complete and expected is not None and expected == expected_after == len(rows) == len(set(ids))
    stable = stable and meta_before.get("rowsUpdatedAt") == meta_after.get("rowsUpdatedAt")
    return rows, {
        "dataset_id": ident, "host": host, "expected_before": expected, "expected_after": expected_after,
        "retrieved": len(rows), "unique_row_ids": len(set(ids)), "pagination_completed": complete,
        "rows_updated_before": meta_before.get("rowsUpdatedAt"), "rows_updated_after": meta_after.get("rowsUpdatedAt"),
        "stable_complete_snapshot": stable, "metadata_before": meta_before, "metadata_after": meta_after,
    }

def scoped_socrata(host, ident, where_clauses, order):
    qroot = f"https://{host}/resource/{ident}.json"
    meta_before = get(f"https://{host}/api/views/{ident}.json")
    rows = []
    scopes = []
    for where in where_clauses:
        params = {"$select":"*,:id as audit_row_id", "$where":where, "$order":order, "$limit":50000}
        page = get(qroot + "?" + up.urlencode(params), timeout=100)
        ok = isinstance(page, list) and len(page) < 50000
        if isinstance(page, list): rows.extend(page)
        scopes.append({"where":where, "retrieved":len(page) if isinstance(page,list) else None, "below_cap":ok})
    meta_after = get(f"https://{host}/api/views/{ident}.json")
    uniq = {}
    for r in rows: uniq[r.get("audit_row_id") or json.dumps(r,sort_keys=True)] = r
    stable = all(s["below_cap"] for s in scopes) and meta_before.get("rowsUpdatedAt") == meta_after.get("rowsUpdatedAt")
    return list(uniq.values()), {"dataset_id":ident,"host":host,"scopes":scopes,"unique_rows":len(uniq),
                                "rows_updated_before":meta_before.get("rowsUpdatedAt"),
                                "rows_updated_after":meta_after.get("rowsUpdatedAt"),
                                "stable_scoped_snapshot":stable}

def fetch_hosted_detail(system):
    sid = str(system["system_id"])
    rel = f"data/details/{sid[:2].lower()}/{sid}.json"
    b = get(LIVE + rel, raw=True)
    if not isinstance(b, bytes):
        return sid, None, b
    try:
        return sid, json.loads(b), {"sha256":hashlib.sha256(b).hexdigest(),"bytes":len(b),"path":rel}
    except Exception as ex:
        return sid, None, {"error":str(ex),"path":rel}

start = dt.datetime.now(dt.timezone.utc).isoformat()
systems_before_b = get(LIVE + "data/systems.json", raw=True)
if not isinstance(systems_before_b, bytes):
    raise SystemExit("Hosted systems universe unavailable; audit cannot classify zero as absence")
systems_payload = json.loads(systems_before_b)
systems = systems_payload.get("systems") or []
nys_hosted = get(LIVE + "data/nys-systems.json")
nys_metadata_hosted = get(LIVE + "data/nys-metadata.json")
save("hosted-systems-metadata.json", {"sha256":hashlib.sha256(systems_before_b).hexdigest(),"system_count":len(systems),
                                      "generated_at":systems_payload.get("generated_at"),"metadata":systems_payload.get("metadata")})
save("hosted-nys-metadata.json", nys_metadata_hosted)

details = {}
detail_manifest = []
with cf.ThreadPoolExecutor(max_workers=10) as pool:
    for sid, detail, meta in pool.map(fetch_hosted_detail, systems):
        detail_manifest.append({"system_id":sid, **(meta if isinstance(meta,dict) else {"error":meta})})
        if detail is not None: details[sid] = detail
save("hosted-detail-manifest.json", detail_manifest)
if len(details) != len(systems):
    raise SystemExit(f"Hosted detail retrieval incomplete: {len(details)}/{len(systems)}")

# Current artifact-level contact/owner census before independent source comparison.
status_counts = Counter()
contact_cases = []
owner_blank = []
for sid, d in details.items():
    reg = d.get("hpd_registration") if isinstance(d.get("hpd_registration"),dict) else None
    status = d.get("hpd_lookup_status")
    status_counts[status] += 1
    contacts = (reg or {}).get("contacts") or []
    bc = d.get("building_context") if isinstance(d.get("building_context"),dict) else {}
    ident = d.get("identity") or {}
    row = {"system_id":sid,"address":ident.get("address"),"bin":ident.get("bin"),"bbl":ident.get("bbl"),
           "bbl_aliases":ident.get("bbl_aliases"),"hpd_status":status,"contact_count":len(contacts),
           "registration_id":(reg or {}).get("registration_id"),"source_registration_id_raw":(reg or {}).get("source_registration_id_raw"),
           "match_basis":(reg or {}).get("match_basis"),"source_bin":(reg or {}).get("source_bin"),"source_bbl":(reg or {}).get("source_bbl"),
           "property_identity_agrees":(reg or {}).get("property_identity_agrees"),"owner_name":bc.get("owner_name"),
           "source_owner_name_raw":bc.get("source_owner_name_raw")}
    if len(contacts)==0 or status!="MATCHED": contact_cases.append(row)
    if not bc.get("owner_name"): owner_blank.append(row)
save("hosted-contact-owner-census-before-source-check.json",
     {"system_count":len(details),"hpd_status_counts":dict(status_counts),"zero_or_nonmatched_count":len(contact_cases),
      "blank_owner_count":len(owner_blank),"cases":contact_cases,"blank_owner_cases":owner_blank})

# Independent complete HPD registration snapshot.
hpd_regs, hpd_reg_meta = stable_full_socrata("data.cityofnewyork.us","tesw-yqqr","registrationid,buildingid,:id")
save("hpd-registration-retrieval.json", hpd_reg_meta)
gzsave("hpd-registration-raw.json.gz", hpd_regs)
by_bin, by_bbl, rid_identities = defaultdict(list), defaultdict(list), defaultdict(set)
for r in hpd_regs:
    b = assigned_bin(r.get("bin"))
    rb = registration_bbl(r)
    rid = pos_int(r.get("registrationid"))
    if b: by_bin[b].append(r)
    if rb: by_bbl[rb].append(r)
    if rid: rid_identities[rid].add((clean(r.get("buildingid")), b, rb))
conflicting_rids = {rid for rid,keys in rid_identities.items() if len(keys)>1}

def rank_reg(r):
    return (str(r.get("lastregistrationdate") or "")[:10], int(pos_int(r.get("registrationid")) or 0), str(r.get("buildingid") or ""))

selected = {}
preclass = {}
for sid,d in details.items():
    ident = d.get("identity") or {}
    b = assigned_bin(ident.get("bin"))
    aliases = [norm_bbl(x) for x in (ident.get("bbl_aliases") or [])]
    canonical = norm_bbl(ident.get("bbl"))
    if canonical and canonical not in aliases: aliases.append(canonical)
    aliases = [x for x in aliases if x]
    exact = by_bin.get(b,[]) if b else []
    basis = None
    candidate = None
    if exact:
        props = {registration_bbl(r) for r in exact if registration_bbl(r)}
        if len(props)!=1:
            preclass[sid] = "AMBIGUOUS_HPD_BUILDING_PROPERTY"
            continue
        candidate=max(exact,key=rank_reg); basis="BIN_EXACT"
    else:
        parcel_rows=[]
        for a in aliases: parcel_rows.extend(by_bbl.get(a,[]))
        # Deduplicate source rows if an alias list repeats.
        unique={r.get("audit_row_id"):r for r in parcel_rows}
        parcel_rows=list(unique.values())
        if parcel_rows:
            candidate=max(parcel_rows,key=rank_reg); basis="BBL_PARCEL_EXACT"
    if candidate is None:
        preclass[sid] = "NO_REGISTRATION_ON_CHECKED_KEYS" if b or aliases else "IDENTITY_UNRESOLVED"
        continue
    rid=pos_int(candidate.get("registrationid"))
    if not rid:
        preclass[sid]="UNUSABLE_SOURCE_REGISTRATION_ID"
    elif rid in conflicting_rids:
        preclass[sid]="COLLIDING_SOURCE_REGISTRATION_ID"
    else:
        selected[sid]=(candidate,basis,rid)

rids = sorted({v[2] for v in selected.values()}, key=int)
clauses=[f"registrationid in ({','.join(rids[i:i+250])})" for i in range(0,len(rids),250)]
hpd_contacts, hpd_contact_meta = scoped_socrata("data.cityofnewyork.us","feu5-w2e2",clauses,"registrationid,type,registrationcontactid,:id")
save("hpd-contact-retrieval.json", hpd_contact_meta)
gzsave("hpd-contact-scoped-raw.json.gz", hpd_contacts)
contacts_by_rid=defaultdict(list)
for r in hpd_contacts:
    rid=pos_int(r.get("registrationid"))
    if rid: contacts_by_rid[rid].append(r)

contact_reconciliation=[]
product_status_discrepancies=[]
verified_negative=0
for sid,d in details.items():
    product=d.get("hpd_lookup_status")
    if sid in preclass:
        independent=preclass[sid]; rid=None; basis=None; source_contact_count=0
    else:
        candidate,basis,rid=selected[sid]
        source_contact_count=len(contacts_by_rid.get(rid,[]))
        independent="MATCHED" if source_contact_count else "VERIFIED_EMPTY_CONTACTS"
    rec={"system_id":sid,"product_status":product,"independent_status":independent,
         "registration_id":rid,"match_basis":basis,"source_contact_count":source_contact_count}
    contact_reconciliation.append(rec)
    if product != independent: product_status_discrepancies.append(rec)
    if independent in ("NO_REGISTRATION_ON_CHECKED_KEYS","VERIFIED_EMPTY_CONTACTS"): verified_negative += 1
save("hpd-current-full-account-reconciliation.json",
     {"registration_snapshot_stable":hpd_reg_meta["stable_complete_snapshot"],
      "contact_snapshot_stable":hpd_contact_meta["stable_scoped_snapshot"],
      "accounts":len(details),"independent_status_counts":dict(Counter(r["independent_status"] for r in contact_reconciliation)),
      "product_status_discrepancy_count":len(product_status_discrepancies),
      "verified_negative_case_count_if_sources_stable":verified_negative if hpd_reg_meta["stable_complete_snapshot"] and hpd_contact_meta["stable_scoped_snapshot"] else None,
      "discrepancies":product_status_discrepancies,"records":contact_reconciliation})

# Fresh scoped PLUTO owner comparison for every canonical BBL.
bbls=sorted({norm_bbl((d.get("identity") or {}).get("bbl")) for d in details.values() if norm_bbl((d.get("identity") or {}).get("bbl"))}, key=int)
pluto_clauses=[f"bbl in ({','.join(bbls[i:i+150])})" for i in range(0,len(bbls),150)]
pluto_rows, pluto_meta = scoped_socrata("data.cityofnewyork.us","64uk-42ks",pluto_clauses,"bbl,:id")
save("pluto-owner-retrieval.json",pluto_meta)
gzsave("pluto-owner-scoped-raw.json.gz",pluto_rows)
pluto_by_bbl={}
for r in pluto_rows:
    b=norm_bbl(r.get("bbl"))
    if b: pluto_by_bbl[b]=r
owner_records=[]; owner_discrepancies=[]; source_owner_blank=0; no_pluto_row=0
for sid,d in details.items():
    ident=d.get("identity") or {}; b=norm_bbl(ident.get("bbl")); bc=d.get("building_context") or {}
    r=pluto_by_bbl.get(b)
    if not r:
        no_pluto_row+=1
        owner_records.append({"system_id":sid,"bbl":b,"source_status":"NO_MATCHING_SOURCE_ROW","product_owner":bc.get("owner_name")})
        continue
    raw=clean(r.get("ownername")); src_owner=None if (raw or "").upper()=="UNAVAILABLE OWNER" else raw
    if src_owner is None: source_owner_blank+=1
    rec={"system_id":sid,"bbl":b,"source_owner_raw":raw,"independent_owner":src_owner,
         "product_owner":bc.get("owner_name"),"product_source_owner_raw":bc.get("source_owner_name_raw")}
    owner_records.append(rec)
    if src_owner != bc.get("owner_name") or raw != bc.get("source_owner_name_raw"): owner_discrepancies.append(rec)
save("pluto-owner-full-account-reconciliation.json",
     {"scoped_snapshot_stable":pluto_meta["stable_scoped_snapshot"],"requested_bbls":len(bbls),
      "matched_source_bbls":len(pluto_by_bbl),"source_owner_blank_or_unavailable_accounts":source_owner_blank,
      "no_matching_source_row_accounts":no_pluto_row,"owner_value_discrepancy_count":len(owner_discrepancies),
      "discrepancies":owner_discrepancies,"records":owner_records})

# Fresh complete NYS registry and independent normalization.
nys_rows, nys_meta = stable_full_socrata("health.data.ny.gov","24a4-muw7","equipment_id,:id")
save("nys-current-retrieval.json",nys_meta)
gzsave("nys-current-raw.json.gz",nys_rows)

def int_or_none(v):
    try: return int(float(str(v).strip()))
    except Exception: return None
def float_or_none(v):
    try: return float(str(v).strip())
    except Exception: return None
def date10(v):
    s=clean(v)
    if not s:return None
    try:return dt.date.fromisoformat(s[:10]).isoformat()
    except Exception:return None
def coords(lat,lon):
    rl,ro=clean(lat),clean(lon); a,b=float_or_none(lat),float_or_none(lon)
    if rl is None and ro is None:return (None,None,"MISSING",rl,ro)
    if a is not None and b is not None and 40.3<=a<=45.2 and -80.0<=b<=-71.5:return (a,b,"VALID",rl,ro)
    return (None,None,"INVALID_SOURCE",rl,ro)

best={}; duplicate=0; missing_id=0
for r in nys_rows:
    eid=clean(r.get("equipment_id"))
    if not eid: missing_id+=1;continue
    if eid in best:
        duplicate+=1
        if str(sorted(r.items())) > str(sorted(best[eid].items())): best[eid]=r
    else: best[eid]=r
norm=[]
for eid,r in best.items():
    address=clean(r.get("equipment_street_address"));city=clean(r.get("equipment_location_city"));zipc=clean(r.get("equipment_location_zip"))
    pk="|".join((address.casefold() if address else "",city.casefold() if city else "",zipc.casefold() if zipc else "")) if any((address,city,zipc)) else None
    lat,lon,cstat,rl,ro=coords(r.get("latitude"),r.get("longitude"))
    norm.append({"system_id":f"NYS-{eid}","source_equipment_id":eid,"address":address,"city":city,"zip":zipc,
                 "source_county":clean(r.get("county")),"property_key":pk,"regulation_compliance":clean(r.get("reg_comp")),
                 "ct_status":clean(r.get("ct_status")),"last_update_days":int_or_none(r.get("lastupdate")),
                 "last_sampled_days":int_or_none(r.get("last_sampled_days")),
                 "latest_sample_date":date10(r.get("equipment_last_legionellla_sample_collection_date")),
                 "latest_sample_result":clean(r.get("equipment_last_legionella_test_result")),
                 "operation_duration":clean(r.get("equipment_tower_operation_duration")),
                 "latitude":lat,"longitude":lon,"coordinate_status":cstat,"source_latitude_raw":rl,"source_longitude_raw":ro,
                 "source_raw_sample_date":r.get("equipment_last_legionellla_sample_collection_date"),
                 "source_raw_sample_result":r.get("equipment_last_legionella_test_result")})
pc=Counter(x["property_key"] for x in norm if x["property_key"])
for x in norm:x["property_equipment_count"]=pc.get(x["property_key"],1) if x["property_key"] else 1
hosted_rows=(nys_hosted or {}).get("systems") or []
hosted_by={str(r.get("source_equipment_id")):r for r in hosted_rows}
fresh_by={r["source_equipment_id"]:r for r in norm}
fields=["address","city","zip","source_county","property_key","property_equipment_count","regulation_compliance","ct_status",
        "last_update_days","last_sampled_days","latest_sample_date","latest_sample_result","operation_duration","latitude","longitude",
        "coordinate_status","source_latitude_raw","source_longitude_raw"]
value_mismatches=[]
for eid in sorted(set(hosted_by)&set(fresh_by), key=lambda x:int(x) if x.isdigit() else x):
    for field in fields:
        if hosted_by[eid].get(field)!=fresh_by[eid].get(field):
            value_mismatches.append({"equipment_id":eid,"field":field,"hosted":hosted_by[eid].get(field),"fresh":fresh_by[eid].get(field)})
source_missing=[]
for r in norm:
    if r["latest_sample_date"] is None or r["latest_sample_result"] is None:
        source_missing.append({"equipment_id":r["source_equipment_id"],"address":r["address"],"city":r["city"],"county":r["source_county"],
                               "raw_sample_date":r["source_raw_sample_date"],"normalized_sample_date":r["latest_sample_date"],
                               "raw_sample_result":r["source_raw_sample_result"],"normalized_sample_result":r["latest_sample_result"],
                               "source_field_diagnosis_date":"BLANK_IN_SOURCE" if clean(r["source_raw_sample_date"]) is None else ("MALFORMED_SOURCE_VALUE" if r["latest_sample_date"] is None else "PRESENT"),
                               "source_field_diagnosis_result":"BLANK_IN_SOURCE" if clean(r["source_raw_sample_result"]) is None else "PRESENT"})
save("nys-current-full-reconciliation.json",
     {"source_snapshot_stable":nys_meta["stable_complete_snapshot"],"fresh_raw_rows":len(nys_rows),"fresh_equipment":len(norm),
      "hosted_equipment":len(hosted_rows),"source_duplicate_equipment_rows":duplicate,"source_missing_equipment_id_rows":missing_id,
      "fresh_only_ids":sorted(set(fresh_by)-set(hosted_by)),"hosted_only_ids":sorted(set(hosted_by)-set(fresh_by)),
      "field_value_mismatch_count":len(value_mismatches),"field_value_mismatches":value_mismatches,
      "source_missing_date_or_result_count":len(source_missing),
      "source_missing_date_count":sum(1 for r in source_missing if r["normalized_sample_date"] is None),
      "source_missing_result_count":sum(1 for r in source_missing if r["normalized_sample_result"] is None),
      "source_missing_both_count":sum(1 for r in source_missing if r["normalized_sample_date"] is None and r["normalized_sample_result"] is None),
      "missing_cases":source_missing})

systems_after_b=get(LIVE+"data/systems.json",raw=True)
stable_hosted=isinstance(systems_after_b,bytes) and systems_after_b==systems_before_b
summary={"started_at":start,"finished_at":dt.datetime.now(dt.timezone.utc).isoformat(),
         "hosted_system_count":len(systems),"hosted_details_retrieved":len(details),"hosted_summary_stable":stable_hosted,
         "hpd_registration_source_stable":hpd_reg_meta["stable_complete_snapshot"],
         "hpd_contact_scope_stable":hpd_contact_meta["stable_scoped_snapshot"],
         "hpd_product_status_discrepancies":len(product_status_discrepancies),
         "pluto_scope_stable":pluto_meta["stable_scoped_snapshot"],"pluto_owner_discrepancies":len(owner_discrepancies),
         "nys_source_stable":nys_meta["stable_complete_snapshot"],"nys_value_mismatches":len(value_mismatches),
         "nys_fresh_only_ids":len(set(fresh_by)-set(hosted_by)),"nys_hosted_only_ids":len(set(hosted_by)-set(fresh_by)),
         "requests_recorded":len(REQS)}
save("stage4-summary.json",summary)
save("requests.json",REQS)
print("STAGE4",json.dumps(summary),flush=True)
