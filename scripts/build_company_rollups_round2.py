#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path

BATCH_ID = "company-rollups-round2-20260924"

ROLLUPS = [
  {
    "master_id":"observed-company-173726c34e2635b73352","rollup_name":"EMSL Analytical",
    "source_name":"EMSL official identity + source typo review","source_url":"https://www.emsl.com/ContactUs.aspx",
    "ids":["known-firm-9099c3bdf5ceac30424b","known-firm-732c1805e6190492512a","known-firm-6d9b286dd1492e1f9e56"],
  },
  {
    "master_id":"known-firm-a7f10c34b147fea6227e","rollup_name":"Atlantank",
    "source_name":"Atlantank trademark + Atlantic Cooling official AtlanTANK service page",
    "source_url":"https://www.atlanticcooling.com/our-services/water-tanks",
    "ids":[
      "known-firm-a7f10c34b147fea6227e","known-firm-0fe26b7999d72040b794","known-firm-3a1607edcf144795851a",
      "known-firm-370796543e206c4970d1","known-firm-1e17165e7f7078af9f7a","known-firm-d79321a44ee7385ec46c",
      "known-firm-1dc5f8e77db7a0c70078","known-firm-3a6b2948b159cd4492cc","known-firm-e10aeb7128430721fe40",
    ],
  },
  {
    "master_id":"known-firm-b065bfa0e94c40d3383d","rollup_name":"International Wood Tanks",
    "source_name":"International Wood Tanks official website","source_url":"https://www.internationalwoodtanks.com/",
    "ids":[
      "known-firm-b065bfa0e94c40d3383d","known-firm-8b8fc571f237a4f52c1f","known-firm-5b4b86a6c4a776c0aaf0",
      "known-firm-9ad0257472e274e84696","known-firm-444242819fe857c367b3","known-firm-09dd8752f7916720e727",
      "known-firm-0415a26186ddbf693e2d",
    ],
  },
  {
    "master_id":"observed-company-4ad4d3f8dcf283e00a52","rollup_name":"Dewberry Engineers",
    "source_name":"Dewberry official website","source_url":"https://www.dewberry.com/contact",
    "ids":["observed-company-4ad4d3f8dcf283e00a52","known-firm-4902abe99a0df562e967"],
  },
  {
    "master_id":"observed-company-c069b30df19a3580f279","rollup_name":"WSP USA Buildings",
    "source_name":"WSP 2025 Annual Information Form","source_url":"https://www.wsp.com/-/media/investors/reports/aif/en/2025/2025-annual-information-form-en-for-filing.pdf",
    "ids":["observed-company-c069b30df19a3580f279","known-firm-2991a4138c41e029c7dd"],
  },
  {
    "master_id":"known-firm-8bce1b52bfb4d2b17c37","rollup_name":"Culligan of Manhattan",
    "source_name":"Fred Smith Plumbing official Culligan affiliate history","source_url":"https://www.fredsmithplumbing.com/press-news-view/fred-smith-plumbing-heating-affiliate-culligan-of-manhattan-wins-customer-service-award/",
    "ids":[
      "known-firm-8bce1b52bfb4d2b17c37","known-firm-96b9fc2ffd1fdb2940ca","known-firm-16d69eadff4dea0de713",
      "known-firm-0c9d72bb8a0cf2ab27d2","known-firm-1dcc33878b09097b079b",
    ],
  },
  {
    "master_id":"known-firm-0d605706e6abe584a1b8","rollup_name":"Environmental Building Solutions",
    "source_name":"Environmental Building Solutions official website + source typo review","source_url":"https://www.ebsllcnyc.com/",
    "ids":[
      "known-firm-2f90d731d7bc7894212a","known-firm-0ccde7152aa30e8777f1","known-firm-fa1ec94540a5331fd4bc",
      "known-firm-96ab1b26d09cd932c1ed","known-firm-87cfff45cb9c12376304","known-firm-75622fccbe018a316bdc",
      "known-firm-992239214d341eb0d0e0","known-firm-ef3d2cc98f8f9370dfea","known-firm-969db3da8845b989c308",
      "known-firm-0c6e60e17e986e929cda","known-firm-a814c77cf67f1d00cf72","known-firm-162ee446e8908d42e8ea",
      "known-firm-33b671b10ceaf9db93c8","known-firm-04a7317c4b98f9f179c1","known-firm-ebf9b8f89568fbb6da2d",
      "known-firm-4355f4121e51812248ec","known-firm-e0dbb9fe091d6449c0d5","known-firm-01f44be9553cc517666f",
      "known-firm-4247e936303f5c90845c","known-firm-761b8eb6bdf902d01e5f","known-firm-fa58326ec72b5824ce1b",
      "known-firm-a492af862c2a907525dc","known-firm-c0ed980f22ffb9f94bb2","known-firm-14aa511b28edbffb4a70",
      "known-firm-35b5f50dd7e2215b867d","known-firm-ece9c5036b5d3d5eb496","known-firm-8d59abc4702d5f92c4f0",
      "known-firm-ac9b3924f583bbf905b9","known-firm-5bbc1f2eb00a8cdad72c","known-firm-961d7d1ce97e5edcbe8a",
      "known-firm-5769baa30152cc089b56","known-firm-54980da6fe2d92220e6d","known-firm-dbc00fc2b28e0c4a7ece",
    ],
  },
]

DETAILS = {
  "known-firm-a7f10c34b147fea6227e": {
    "legal_name":"Atlantank, LLC",
    "website":"https://www.atlanticcooling.com/our-services/water-tanks",
    "company_type":"Water storage tank installation, maintenance, repair and cleaning",
    "identity_source_name":"USPTO ATLANTANK registration",
    "identity_source_url":"https://tmng-al.uspto.gov/resting2/api/casedoc/cms/case/79410265/office-action/OfficeAction7275026.pdf",
    "website_source_name":"Atlantic Cooling official AtlanTANK service page",
    "website_source_url":"https://www.atlanticcooling.com/our-services/water-tanks",
  },
  "known-firm-b065bfa0e94c40d3383d": {
    "website":"https://www.internationalwoodtanks.com/",
    "company_type":"Wooden water tank construction, maintenance, repair, restoration and water testing",
    "identity_source_name":"International Wood Tanks official website",
    "identity_source_url":"https://www.internationalwoodtanks.com/",
    "website_source_name":"International Wood Tanks official website",
    "website_source_url":"https://www.internationalwoodtanks.com/",
  },
  "observed-company-4ad4d3f8dcf283e00a52": {
    "legal_name":"Dewberry Engineers Inc.",
    "website":"https://www.dewberry.com/",
    "headquarters_address":"8401 Arlington Boulevard","headquarters_city":"Fairfax","headquarters_region":"VA",
    "headquarters_postal_code":"22031-4666","headquarters_country":"US",
    "company_type":"Planning, design, engineering and construction professional services",
    "revenue_amount":763000000,"revenue_year":2025,"revenue_type":"reported","revenue_confidence":"confirmed",
    "revenue_source_name":"Dewberry 2026 CEO announcement","revenue_source_url":"https://www.dewberry.com/insights-news/article/2026/02/18/dewberry-announces-new-ceo-david-j-mahoney-pe",
    "identity_source_name":"Dewberry official contact page","identity_source_url":"https://www.dewberry.com/contact",
    "website_source_name":"Dewberry official website","website_source_url":"https://www.dewberry.com/",
    "headquarters_source_name":"Dewberry official legal disclaimer","headquarters_source_url":"https://www.dewberry.com/legal-disclaimer",
  },
  "observed-company-c069b30df19a3580f279": {
    "legal_name":"WSP USA Buildings Inc.",
    "website":"https://www.wsp.com/en-us",
    "parent_company_name":"WSP Global Inc.",
    "company_type":"Engineering and professional services",
    "identity_source_name":"WSP 2025 Annual Information Form",
    "identity_source_url":"https://www.wsp.com/-/media/investors/reports/aif/en/2025/2025-annual-information-form-en-for-filing.pdf",
    "website_source_name":"WSP official website","website_source_url":"https://www.wsp.com/en-us",
    "parent_source_name":"WSP 2025 Annual Information Form",
    "parent_source_url":"https://www.wsp.com/-/media/investors/reports/aif/en/2025/2025-annual-information-form-en-for-filing.pdf",
  },
  "known-firm-8bce1b52bfb4d2b17c37": {
    "website":"https://fredsmithplumbing.com/our-services/water-purification/",
    "company_type":"Water purification and filtration services",
    "identity_source_name":"Fred Smith Plumbing official Culligan affiliate history",
    "identity_source_url":"https://www.fredsmithplumbing.com/press-news-view/fred-smith-plumbing-heating-affiliate-culligan-of-manhattan-wins-customer-service-award/",
    "website_source_name":"Fred Smith Plumbing official water purification page",
    "website_source_url":"https://fredsmithplumbing.com/our-services/water-purification/",
  },
  "observed-company-a3bc0790172dfd16ed5a": {
    "legal_name":"Rochester Midland Corporation",
    "website":"https://www.rochestermidland.com/",
    "headquarters_address":"155 Paragon Drive","headquarters_city":"Rochester","headquarters_region":"NY",
    "headquarters_postal_code":"14624","headquarters_country":"US",
    "company_type":"Water treatment, food safety and specialty chemical products and technical services",
    "revenue_low":150000000,"revenue_type":"range","revenue_confidence":"strong",
    "revenue_source_name":"Rochester Midland CEO profile","revenue_source_url":"https://www.rochestermidland.com/team/jim-white/",
    "identity_source_name":"Rochester Midland official website","identity_source_url":"https://www.rochestermidland.com/",
    "website_source_name":"Rochester Midland official website","website_source_url":"https://www.rochestermidland.com/",
    "headquarters_source_name":"Rochester Midland official website","headquarters_source_url":"https://www.rochestermidland.com/",
  },
}

DETAIL_COLS = [
  "legal_name","website","headquarters_address","headquarters_city","headquarters_region","headquarters_postal_code",
  "headquarters_country","parent_company_name","company_type","revenue_amount","revenue_low","revenue_high","revenue_currency",
  "revenue_year","revenue_type","revenue_source_name","revenue_source_url","revenue_confidence",
  "identity_source_name","identity_source_url","website_source_name","website_source_url",
  "headquarters_source_name","headquarters_source_url","parent_source_name","parent_source_url",
]

def lit(v):
    if v is None: return "NULL"
    if isinstance(v,bool): return "true" if v else "false"
    if isinstance(v,(int,float)): return str(v)
    return "'" + str(v).replace("'","''") + "'"

def slog(v,cap):
    return min(1.0, math.log1p(max(0.0,float(v or 0))) / math.log1p(cap))

def score(f):
    weights={"DWT_INSPECTION_PROVIDER":15,"DWT_LABORATORY":15,"DEC_7G_REGISTERED_BUSINESS":12,"PROCUREMENT_VENDOR":10,"DOB_NOW_APPLICANT_BUSINESS":4,"DOB_NOW_OWNER_BUSINESS":0,"LEGACY_DOB_OWNER_BUSINESS":0}
    role=max([0]+[weights.get(v,2) for v in f.get("roles",[])])
    return max(0,min(100,round(
      25*slog(f.get("serviced_site_count",0),500)+20*slog(f.get("tower_account_count",0),250)
      +10*slog(f.get("observed_site_count",0),500)+10*slog(f.get("observed_contract_count",0),50)
      +5*slog(max(0,f.get("observed_contract_value",0) or 0),10_000_000)
      +5*min(1,(f.get("observed_customer_count",0) or 0)/5)+5*min(1,(f.get("active_qualification_count",0) or 0))
      +(5 if f.get("active_last_12m") else 0)+role
    )))

def reason(f):
    p=[]
    if f.get("serviced_site_count"): p.append(f"{f['serviced_site_count']:,} serviced sites")
    if f.get("tower_account_count"): p.append(f"{f['tower_account_count']:,} tower accounts")
    if f.get("observed_contract_count"): p.append(f"{f['observed_contract_count']:,} public contracts")
    if f.get("observed_customer_count"): p.append(f"{f['observed_customer_count']:,} public buyers")
    if f.get("active_qualification_count"): p.append(f"{f['active_qualification_count']:,} active 7G registrations")
    if f.get("active_last_12m"): p.append("observed in last 12 months")
    return " · ".join(p[:4]) or "TowerSignal public-record company evidence"

def plan(payload):
    byid={f["firm_id"]:f for f in payload["firms"]}
    targets=[]
    seen={}
    for group in ROLLUPS:
        for fid in group["ids"]:
            if fid not in byid:
                raise RuntimeError(f"Missing accepted firm ID {fid} for {group['rollup_name']}")
            prior=seen.get(fid)
            if prior and prior!=group["master_id"]:
                raise RuntimeError(f"Duplicate target {fid}: {prior} vs {group['master_id']}")
            seen[fid]=group["master_id"]
            targets.append({
              "company_id":fid,"canonical_name":byid[fid]["canonical_name"],"master_id":group["master_id"],
              "rollup_name":group["rollup_name"],"source_name":group["source_name"],"source_url":group["source_url"]
            })
    if len(targets)!=61 or len(seen)!=61:
        raise RuntimeError(f"Expected 61 unique round-2 targets, got {len(targets)}/{len(seen)}")
    for master in DETAILS:
        if master not in byid:
            raise RuntimeError(f"Detail master missing from accepted firms: {master}")
    candidates=[]
    for f in payload["firms"]:
        name=(f.get("canonical_name") or "").strip()
        if not name or name.upper() in {"N/A","NA","NONE","UNKNOWN"}: continue
        candidates.append({"firm_id":f["firm_id"],"canonical_name":name,"priority_score":score(f),"priority_reason":reason(f)})
    candidates.sort(key=lambda r:(-r["priority_score"],r["canonical_name"]))
    return targets,candidates[:180],byid

def build_sql(targets,candidates,byid):
    target_values=",".join("(" + ",".join(lit(r[k]) for k in ["company_id","canonical_name","master_id","rollup_name","source_name","source_url"]) + ")" for r in targets)
    detail_rows=[]
    for master,detail in DETAILS.items():
        row={"company_id":master,"canonical_name":byid[master]["canonical_name"],**detail}
        if not row.get("revenue_currency"): row["revenue_currency"]="USD"
        if not row.get("revenue_type"): row["revenue_type"]="unknown"
        if not row.get("revenue_confidence"): row["revenue_confidence"]="unknown"
        detail_rows.append(row)
    detail_values=",".join("(" + ",".join(lit(r.get(k)) for k in ["company_id","canonical_name"]+DETAIL_COLS) + ")" for r in detail_rows)
    candidate_values=",".join("(" + ",".join([lit(r["firm_id"]),lit(r["canonical_name"]),str(r["priority_score"]),lit(r["priority_reason"])]) + ")" for r in candidates)
    cols=", ".join(DETAIL_COLS)
    updates=",\n    ".join(f"{c}=COALESCE(public.company_private_profiles.{c},EXCLUDED.{c})" for c in DETAIL_COLS)
    return f"""
BEGIN;

DO $$
DECLARE v_users integer; v_admins integer; v_rollups integer;
BEGIN
  SELECT count(*) INTO v_users FROM neon_auth."user";
  SELECT count(*) INTO v_admins FROM neon_auth."user" WHERE lower(coalesce(role,''))='admin';
  SELECT count(*) INTO v_rollups FROM public.company_private_profiles WHERE rollup_company_id IS NOT NULL;
  IF v_users<>2 OR v_admins<>2 OR v_rollups<239 THEN
    RAISE EXCEPTION 'Round2 guard failed: users=% admins=% rollups=%',v_users,v_admins,v_rollups;
  END IF;
END $$;

CREATE TEMP TABLE ts_r2_target(
 company_id text PRIMARY KEY,canonical_name text NOT NULL,master_id text NOT NULL,rollup_name text NOT NULL,source_name text NOT NULL,source_url text NOT NULL
) ON COMMIT DROP;
INSERT INTO ts_r2_target VALUES {target_values};

CREATE TEMP TABLE ts_r2_details(
 company_id text PRIMARY KEY,canonical_name text NOT NULL,
 legal_name text,website text,headquarters_address text,headquarters_city text,headquarters_region text,headquarters_postal_code text,
 headquarters_country text,parent_company_name text,company_type text,revenue_amount numeric,revenue_low numeric,revenue_high numeric,
 revenue_currency text,revenue_year integer,revenue_type text,revenue_source_name text,revenue_source_url text,revenue_confidence text,
 identity_source_name text,identity_source_url text,website_source_name text,website_source_url text,
 headquarters_source_name text,headquarters_source_url text,parent_source_name text,parent_source_url text
) ON COMMIT DROP;
INSERT INTO ts_r2_details VALUES {detail_values};

CREATE TEMP TABLE ts_r2_candidates(firm_id text PRIMARY KEY,canonical_name text NOT NULL,priority_score integer NOT NULL,priority_reason text NOT NULL) ON COMMIT DROP;
INSERT INTO ts_r2_candidates VALUES {candidate_values};

DO $$
BEGIN
 IF (SELECT count(*) FROM ts_r2_target)<>61 THEN RAISE EXCEPTION 'Expected 61 round2 targets'; END IF;
 IF EXISTS(
   SELECT 1 FROM ts_r2_target t JOIN public.company_private_profiles p ON p.company_id=t.company_id
   WHERE (t.company_id=t.master_id AND p.rollup_company_id IS NOT NULL)
      OR (t.company_id<>t.master_id AND p.rollup_company_id IS NOT NULL AND p.rollup_company_id<>t.master_id)
 ) THEN RAISE EXCEPTION 'Existing reviewed rollup conflicts with round2 plan'; END IF;
END $$;

CREATE TEMP TABLE ts_r2_stats ON COMMIT DROP AS
SELECT
 (SELECT count(*) FROM public.company_private_profiles) before_profiles,
 (SELECT count(*) FROM public.company_private_profiles WHERE rollup_company_id IS NOT NULL) before_rollups,
 (SELECT count(*) FROM ts_r2_target t LEFT JOIN public.company_private_profiles p ON p.company_id=t.company_id WHERE p.company_id IS NULL) new_profiles,
 (SELECT count(*) FROM ts_r2_target t LEFT JOIN public.company_private_profiles p ON p.company_id=t.company_id WHERE t.company_id<>t.master_id AND p.rollup_company_id IS NULL) new_rollups;

CREATE TEMP TABLE ts_r2_queue_state ON COMMIT DROP AS
WITH normalized AS(
 SELECT COALESCE(CASE WHEN t.company_id<>t.master_id THEN t.master_id END,p.rollup_company_id,q.company_id) resolved_company_id,q.*
 FROM public.company_private_research_queue q
 LEFT JOIN ts_r2_target t ON t.company_id=q.company_id
 LEFT JOIN public.company_private_profiles p ON p.company_id=q.company_id
), ranked AS(
 SELECT *,row_number() OVER(PARTITION BY resolved_company_id ORDER BY
  CASE status WHEN 'complete' THEN 5 WHEN 'verified' THEN 4 WHEN 'needs-review' THEN 3 WHEN 'researching' THEN 2 ELSE 1 END DESC,
  last_researched_at DESC NULLS LAST,updated_at DESC) rn
 FROM normalized
)
SELECT resolved_company_id company_id,status,research_owner,last_researched_at FROM ranked WHERE rn=1;

INSERT INTO public.company_private_profiles(
 company_id,canonical_name,rollup_name,rollup_company_id,rollup_source_name,rollup_source_url,enrichment_checked_at,
 updated_at,last_change_source,last_change_batch_id
)
SELECT company_id,canonical_name,rollup_name,CASE WHEN company_id=master_id THEN NULL ELSE master_id END,source_name,source_url,now(),now(),'import','{BATCH_ID}'
FROM ts_r2_target
ON CONFLICT(company_id) DO UPDATE SET
 canonical_name=EXCLUDED.canonical_name,rollup_name=EXCLUDED.rollup_name,rollup_company_id=EXCLUDED.rollup_company_id,
 rollup_source_name=EXCLUDED.rollup_source_name,rollup_source_url=EXCLUDED.rollup_source_url,enrichment_checked_at=EXCLUDED.enrichment_checked_at,
 updated_at=now(),last_change_source='import',last_change_batch_id='{BATCH_ID}';

INSERT INTO public.company_private_profiles(company_id,canonical_name,{cols},enrichment_checked_at,updated_at,last_change_source,last_change_batch_id)
SELECT company_id,canonical_name,{cols},now(),now(),'import','{BATCH_ID}' FROM ts_r2_details
ON CONFLICT(company_id) DO UPDATE SET
    {updates},
    enrichment_checked_at=now(),updated_at=now(),last_change_source='import',last_change_batch_id='{BATCH_ID}';

CREATE TEMP TABLE ts_r2_selected ON COMMIT DROP AS
WITH mapped AS(
 SELECT r.*,COALESCE(p.rollup_company_id,r.firm_id) master_id
 FROM ts_r2_candidates r LEFT JOIN public.company_private_profiles p ON p.company_id=r.firm_id
), best AS(
 SELECT DISTINCT ON(master_id) master_id,canonical_name candidate_name,priority_score base_priority_score,priority_reason
 FROM mapped ORDER BY master_id,priority_score DESC,canonical_name
), family AS(
 SELECT b.*,COALESCE(m.canonical_name,b.candidate_name) master_name,
  GREATEST(1,(SELECT count(*) FROM public.company_private_profiles fp WHERE fp.company_id=b.master_id OR fp.rollup_company_id=b.master_id)) family_size
 FROM best b LEFT JOIN public.company_private_profiles m ON m.company_id=b.master_id
)
SELECT master_id company_id,master_name canonical_name,
 LEAST(100,base_priority_score+LEAST(5,GREATEST(0,family_size-1)))::integer priority_score,
 priority_reason||CASE WHEN family_size>1 THEN ' · '||family_size::text||' reviewed source identities in private family' ELSE '' END priority_reason
FROM family ORDER BY priority_score DESC,canonical_name LIMIT 100;

INSERT INTO public.company_private_profiles(company_id,canonical_name,last_change_source,last_change_batch_id)
SELECT company_id,canonical_name,'system','research-queue-sync-20260924' FROM ts_r2_selected
ON CONFLICT(company_id) DO NOTHING;

INSERT INTO public.company_private_research_queue(company_id,priority_score,priority_reason,missing_fields,status,research_owner,last_researched_at,updated_at,last_change_source,last_change_batch_id)
SELECT s.company_id,s.priority_score,s.priority_reason,
 to_jsonb(array_remove(ARRAY[
   CASE WHEN p.website IS NULL THEN 'website' END,
   CASE WHEN p.headquarters_address IS NULL AND p.headquarters_city IS NULL THEN 'headquarters' END,
   CASE WHEN p.company_type IS NULL THEN 'company type' END,
   CASE WHEN p.parent_company_id IS NULL AND p.parent_company_name IS NULL AND position('independently owned' in lower(coalesce(p.internal_summary,'')))=0 THEN 'parent / ownership' END,
   CASE WHEN p.revenue_amount IS NULL AND p.revenue_low IS NULL AND p.revenue_high IS NULL THEN 'revenue' END,
   CASE WHEN NOT EXISTS(SELECT 1 FROM public.company_private_contacts c WHERE c.company_id=s.company_id AND c.active) THEN 'contact' END
 ]::text[],NULL)),
 COALESCE(qs.status,'unreviewed'),qs.research_owner,qs.last_researched_at,now(),'system','research-queue-sync-20260924'
FROM ts_r2_selected s JOIN public.company_private_profiles p ON p.company_id=s.company_id
LEFT JOIN ts_r2_queue_state qs ON qs.company_id=s.company_id
ON CONFLICT(company_id) DO UPDATE SET
 priority_score=EXCLUDED.priority_score,priority_reason=EXCLUDED.priority_reason,missing_fields=EXCLUDED.missing_fields,
 status=EXCLUDED.status,research_owner=EXCLUDED.research_owner,last_researched_at=EXCLUDED.last_researched_at,
 updated_at=now(),last_change_source='system',last_change_batch_id='research-queue-sync-20260924';

DELETE FROM public.company_private_research_queue q WHERE NOT EXISTS(SELECT 1 FROM ts_r2_selected s WHERE s.company_id=q.company_id);

DO $$
DECLARE s record; v_profiles integer;v_rollups integer;v_queue integer;v_alias_queue integer;v_target_ok integer;
BEGIN
 SELECT * INTO s FROM ts_r2_stats;
 SELECT count(*) INTO v_profiles FROM public.company_private_profiles;
 SELECT count(*) INTO v_rollups FROM public.company_private_profiles WHERE rollup_company_id IS NOT NULL;
 SELECT count(*) INTO v_queue FROM public.company_private_research_queue;
 SELECT count(*) INTO v_alias_queue FROM public.company_private_research_queue q JOIN public.company_private_profiles p ON p.company_id=q.company_id WHERE p.rollup_company_id IS NOT NULL;
 SELECT count(*) INTO v_target_ok FROM ts_r2_target t JOIN public.company_private_profiles p ON p.company_id=t.company_id
 WHERE (t.company_id=t.master_id AND p.rollup_company_id IS NULL AND p.rollup_name=t.rollup_name)
    OR (t.company_id<>t.master_id AND p.rollup_company_id=t.master_id AND p.rollup_name=t.rollup_name);
 IF v_profiles<s.before_profiles+s.new_profiles THEN RAISE EXCEPTION 'Round2 profile count failed'; END IF;
 IF v_rollups<>s.before_rollups+s.new_rollups THEN RAISE EXCEPTION 'Round2 rollup count failed: before=% new=% after=%',s.before_rollups,s.new_rollups,v_rollups; END IF;
 IF v_queue<>100 OR v_alias_queue<>0 OR v_target_ok<>61 THEN RAISE EXCEPTION 'Round2 acceptance failed: queue=% alias_queue=% targets=%',v_queue,v_alias_queue,v_target_ok; END IF;
END $$;

SELECT 'COMPANY_ROUND2=PASS' result,
 (SELECT count(*) FROM public.company_private_profiles) profiles,
 (SELECT count(*) FROM public.company_private_profiles WHERE rollup_company_id IS NOT NULL) rollups,
 (SELECT count(*) FROM public.company_private_research_queue) research_queue,
 (SELECT count(*) FROM public.company_private_contacts) contacts,
 (SELECT count(*) FROM public.company_private_change_log) audit_rows,
 (SELECT new_profiles FROM ts_r2_stats) added_profiles,
 (SELECT new_rollups FROM ts_r2_stats) added_rollups;

COMMIT;
"""

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--known-firms",required=True)
    p.add_argument("--sql-out",required=True)
    p.add_argument("--plan-out")
    a=p.parse_args()
    payload=json.loads(Path(a.known_firms).read_text(encoding="utf-8"))
    if payload.get("domain")!="TOWERSIGNAL_KNOWN_FIRMS": raise RuntimeError("Unexpected known-firms domain")
    targets,candidates,byid=plan(payload)
    Path(a.sql_out).write_text(build_sql(targets,candidates,byid),encoding="utf-8")
    if a.plan_out:
        Path(a.plan_out).write_text(json.dumps({"schema":"TOWERSIGNAL_COMPANY_ROLLUP_ROUND2_V1","targets":targets,"details":DETAILS},indent=2),encoding="utf-8")
    print(f"COMPANY_ROUND2_PLAN=PASS targets={len(targets)} details={len(DETAILS)}")

if __name__=="__main__":
    main()
