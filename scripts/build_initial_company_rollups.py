#!/usr/bin/env python3
import argparse
import json
import math
import re
from pathlib import Path

BATCH_ID = "initial-company-rollups-20260924"
KNOWN_FIRMS_URL = "https://jeremyhennessy.github.io/TowerSignal/data/known-firms.json"

FAMILIES = [
    {"key":"Tower Water","master":"known-firm-a76ae2375cff31677267","rollup":"Tower Water","expected":5,"source_name":"Tower Water official website","source_url":"https://towerwater.com/"},
    {"key":"EMSL","master":"observed-company-173726c34e2635b73352","rollup":"EMSL Analytical","expected":31,"source_name":"EMSL official contact page","source_url":"https://www.emsl.com/ContactUs.aspx"},
    {"key":"Isseks","master":"known-firm-809b6b7911aa65e98654","rollup":"Isseks Bros.","expected":29,"source_name":"Isseks Bros. official website","source_url":"https://www.isseks.com/"},
    {"key":"Barclay","master":"observed-company-65f2b666fe7b7b6e3dc3","rollup":"Barclay Water Management","expected":8,"source_name":"Ecolab acquisition announcement","source_url":"https://investor.ecolab.com/news/news-details/2024/Ecolab-Acquires-Barclay-Water-Management/default.aspx"},
    {"key":"Rosenwach","master":"observed-company-fa031414cf0b56a27aa6","rollup":"Rosenwach Tank","expected":14,"source_name":"Rosenwach Group official history","source_url":"https://www.rosenwachgroup.com/about.php"},
    {"key":"Metro","master":"observed-company-9a049993a3ba62961d8f","rollup":"The Metro Group","expected":7,"source_name":"The Metro Group official website","source_url":"https://www.metrogroupinc.com/"},
    {"key":"Nalco","master":"observed-company-f914504c7de8f74d88ad","rollup":"Nalco Water","expected":15,"source_name":"Ecolab Nalco Water business page","source_url":"https://www.ecolab.com/en-us/about/our-businesses/nalco-water-and-process-services"},
    {"key":"Atlas","master":"known-firm-d83ead023885a2b589ff","rollup":"Atlas Environmental Lab","expected":30,"source_name":"Atlas Environmental Lab official website","source_url":"https://www.atlasenvironmentallab.com/"},
    {"key":"JMZ","master":"known-firm-090bba53807e820fcbf5","rollup":"JMZ Maintenance","expected":14,"source_name":"TowerSignal exact-name source normalization","source_url":KNOWN_FIRMS_URL},
    {"key":"Pace","master":"observed-company-9c424024fa9e6da2e03b","rollup":"Pace Analytical","expected":3,"source_name":"Pace Analytical official website","source_url":"https://www.pacelabs.com/"},
    {"key":"Special Pathogens","master":"observed-company-4d4ccb2349b7714cbfe5","rollup":"Special Pathogens Laboratory","expected":4,"source_name":"Special Pathogens Laboratory official website","source_url":"https://specialpathogenslab.com/"},
    {"key":"Clarity","master":"observed-company-d2e3c6ea5d94cd5c541a","rollup":"Clarity Water Technologies","expected":2,"source_name":"Clarity Water Technologies official website","source_url":"https://claritywatertech.com/"},
    {"key":"Phoenix","master":"known-firm-fae0951d34dbc3979741","rollup":"Phoenix Environmental Laboratories","expected":2,"source_name":"Phoenix Environmental Laboratories official website","source_url":"https://phoenixlabs.com/"},
    {"key":"Cascade","master":"observed-company-40a2c59b810a30c84370","rollup":"Cascade Water Services","expected":5,"source_name":"Town of North Hempstead procurement record","source_url":"https://www.northhempsteadny.gov/filestorage/16253/17996/25226/2017-07-18.pdf"},
    {"key":"American Pipe","master":"observed-company-39105f0bf6c208878fc4","rollup":"American Pipe & Tank","expected":22,"source_name":"American Pipe & Tank official website","source_url":"https://www.americanpipeandtank.com/"},
    {"key":"EBS","master":"known-firm-0d605706e6abe584a1b8","rollup":"Environmental Building Solutions","expected":37,"source_name":"Environmental Building Solutions official website","source_url":"https://www.ebsllcnyc.com/"},
    {"key":"Certified Laboratories","master":"known-firm-fbc0cd4c7f1cd22b516c","rollup":"Certified Laboratories","expected":10,"source_name":"Certified Laboratories official website","source_url":"https://certified-laboratories.com/"},
    {"key":"Ambient","master":"known-firm-6b56cafe734ffee630a0","rollup":"Ambient Group","expected":7,"source_name":"Ambient Group official website","source_url":"https://www.ambientgroup.com/"},
    {"key":"Loring","master":"observed-company-f55a9f6f9ff8ef956101","rollup":"Loring Consulting Engineers","expected":2,"source_name":"Loring Consulting Engineers official website","source_url":"https://www.loringengineers.com/"},
    {"key":"York","master":"known-firm-c78a735b2c646c06e3f3","rollup":"York Analytical / ALS","expected":3,"source_name":"Rockland County 2026 contract amendment","source_url":"https://legislature.rocklandcountyny.gov/home/showpublisheddocument/8274/639083980186570000"},
]

DETAILS = {
    "known-firm-a76ae2375cff31677267": {
        "legal_name":"Tower Cleaning Plus, Inc.","website":"https://towerwater.com/",
        "headquarters_address":"5 Shirley Avenue","headquarters_city":"Somerset","headquarters_region":"NJ","headquarters_postal_code":"08873","headquarters_country":"US",
        "parent_company_name":"Sylmar Group","company_type":"Commercial and industrial water treatment, cooling-tower cleaning and Legionella management",
        "identity_source_name":"Tower Water official website","identity_source_url":"https://towerwater.com/blog/",
        "website_source_name":"Tower Water official website","website_source_url":"https://towerwater.com/",
        "headquarters_source_name":"Tower Water official website","headquarters_source_url":"https://towerwater.com/blog/",
        "parent_source_name":"Sylmar Group acquisition announcement","parent_source_url":"https://sylmargrp.com/sylmar-group-acquires-tower-water-building-the-leading-water-treatment-platform-in-the-northeast/"
    },
    "observed-company-9c424024fa9e6da2e03b": {
        "legal_name":"Pace Analytical Services, LLC","website":"https://www.pacelabs.com/",
        "headquarters_address":"2665 Long Lake Road, Suite 300","headquarters_city":"Roseville","headquarters_region":"MN","headquarters_postal_code":"55113","headquarters_country":"US",
        "company_type":"Environmental and analytical laboratory testing",
        "identity_source_name":"Pace Analytical official website","identity_source_url":"https://www.pacelabs.com/company/news-and-insights/pace-corporate/40th-anniversary/",
        "website_source_name":"Pace Analytical official website","website_source_url":"https://www.pacelabs.com/",
        "headquarters_source_name":"Pace Analytical official website","headquarters_source_url":"https://www.pacelabs.com/cookie-policy-eu/"
    },
    "observed-company-4d4ccb2349b7714cbfe5": {
        "legal_name":"Special Pathogens Laboratory, LLC","website":"https://specialpathogenslab.com/",
        "headquarters_address":"1401 Forbes Avenue, Suite 401","headquarters_city":"Pittsburgh","headquarters_region":"PA","headquarters_postal_code":"15219","headquarters_country":"US",
        "company_type":"Legionella and waterborne-pathogen laboratory testing and consulting",
        "identity_source_name":"Special Pathogens Laboratory official sampling guide","identity_source_url":"https://specialpathogenslab.com/wp-content/uploads/2022/10/LegionellaSamplingShipping_10-26-21.pdf",
        "website_source_name":"Special Pathogens Laboratory official website","website_source_url":"https://specialpathogenslab.com/",
        "headquarters_source_name":"Special Pathogens Laboratory official sampling guide","headquarters_source_url":"https://specialpathogenslab.com/wp-content/uploads/2022/10/LegionellaSamplingShipping_10-26-21.pdf"
    },
    "observed-company-d2e3c6ea5d94cd5c541a": {
        "legal_name":"Clarity Water Technologies, LLC","website":"https://claritywatertech.com/",
        "headquarters_address":"87 Hunt Road","headquarters_city":"Orangeburg","headquarters_region":"NY","headquarters_postal_code":"10962","headquarters_country":"US",
        "company_type":"Industrial and commercial water treatment",
        "identity_source_name":"Clarity Water Technologies official About page","identity_source_url":"https://claritywatertech.com/about-us/",
        "website_source_name":"Clarity Water Technologies official website","website_source_url":"https://claritywatertech.com/",
        "headquarters_source_name":"Clarity Water Technologies official About page","headquarters_source_url":"https://claritywatertech.com/about-us/"
    },
    "known-firm-fae0951d34dbc3979741": {
        "legal_name":"Phoenix Environmental Laboratories, Inc.","website":"https://phoenixlabs.com/",
        "headquarters_address":"587 Middle Turnpike East","headquarters_city":"Manchester","headquarters_region":"CT","headquarters_postal_code":"06040","headquarters_country":"US",
        "company_type":"Environmental laboratory testing",
        "identity_source_name":"Connecticut laboratory certification","identity_source_url":"https://www.phoenixlabs.com/WebDocs/CT-CERT.pdf",
        "website_source_name":"Phoenix Environmental Laboratories official website","website_source_url":"https://phoenixlabs.com/",
        "headquarters_source_name":"Phoenix Environmental Laboratories official Contact page","headquarters_source_url":"https://phoenixlabs.com/ContactUs.aspx"
    },
    "observed-company-40a2c59b810a30c84370": {
        "legal_name":"Cascade Water Services, Inc.","website":"http://www.cascadewater.com/",
        "headquarters_address":"113 Bloomingdale Road","headquarters_city":"Hicksville","headquarters_region":"NY","headquarters_postal_code":"11801","headquarters_country":"US",
        "company_type":"Water treatment, cooling-tower treatment and cleaning services",
        "identity_source_name":"Town of North Hempstead procurement record","identity_source_url":"https://www.northhempsteadny.gov/filestorage/16253/17996/25226/2017-07-18.pdf",
        "website_source_name":"NY OGS previously-approved subcontractor record","website_source_url":"https://online.ogs.ny.gov/dnc/contractorConsultant/esb/OGS%20Previously-Approved%20Subcontractors%2C%2007-02-13.pdf",
        "headquarters_source_name":"Town of North Hempstead procurement record","headquarters_source_url":"https://www.northhempsteadny.gov/filestorage/16253/17996/25226/2017-07-18.pdf"
    },
    "known-firm-c78a735b2c646c06e3f3": {
        "legal_name":"York Analytical Laboratories, Inc.",
        "headquarters_address":"120 Research Boulevard","headquarters_city":"Stratford","headquarters_region":"CT","headquarters_postal_code":"06615","headquarters_country":"US",
        "parent_company_name":"ALS Group USA, Corp.","company_type":"Diagnostic and analytical laboratory testing",
        "identity_source_name":"Rockland County contract record","identity_source_url":"https://legislature.rocklandcountyny.gov/home/showpublisheddocument/8274/639083980186570000",
        "headquarters_source_name":"Rockland County contract record","headquarters_source_url":"https://legislature.rocklandcountyny.gov/home/showpublisheddocument/8274/639083980186570000",
        "parent_source_name":"Rockland County 2026 contract amendment","parent_source_url":"https://legislature.rocklandcountyny.gov/home/showpublisheddocument/8274/639083980186570000"
    },
    "observed-company-fa031414cf0b56a27aa6": {
        "parent_company_name":"Rosenwach Group","parent_source_name":"Rosenwach Group official history","parent_source_url":"https://www.rosenwachgroup.com/about.php"
    },
    "known-firm-fbc0cd4c7f1cd22b516c": {
        "parent_company_name":"Certified Group","parent_source_name":"Certified Group official website","parent_source_url":"https://www.certifiedgroup.com/"
    },
    "observed-company-f914504c7de8f74d88ad": {
        "parent_company_name":"Ecolab","parent_source_name":"Ecolab Nalco Water business page","parent_source_url":"https://www.ecolab.com/en-us/about/our-businesses/nalco-water-and-process-services"
    },
    "observed-company-65f2b666fe7b7b6e3dc3": {
        "parent_company_name":"Ecolab","parent_source_name":"Ecolab acquisition announcement","parent_source_url":"https://investor.ecolab.com/news/news-details/2024/Ecolab-Acquires-Barclay-Water-Management/default.aspx",
        "revenue_amount":50000000,"revenue_year":2023,"revenue_type":"reported","revenue_confidence":"confirmed",
        "revenue_source_name":"Ecolab acquisition announcement","revenue_source_url":"https://investor.ecolab.com/news/news-details/2024/Ecolab-Acquires-Barclay-Water-Management/default.aspx"
    }
}

DETAIL_COLUMNS = [
    "legal_name","website","headquarters_address","headquarters_city","headquarters_region","headquarters_postal_code","headquarters_country",
    "parent_company_name","company_type","revenue_amount","revenue_year","revenue_type","revenue_source_name","revenue_source_url","revenue_confidence",
    "identity_source_name","identity_source_url","website_source_name","website_source_url",
    "headquarters_source_name","headquarters_source_url","parent_source_name","parent_source_url"
]

def family_match(key, name):
    n = name.lower()
    if key == "Tower Water":
        return "tower water" in n or "tower cleaning plus" in n
    if key == "EMSL":
        return re.search(r"\bemsl\b|emslanalytic|emslanalytical", name, re.I) is not None
    if key == "Isseks":
        return "issek" in n
    if key == "Barclay":
        return "barclay water" in n
    if key == "Rosenwach":
        return "rosenwach" in n
    if key == "Metro":
        return re.search(r"\bmetro group\b|the metro group", name, re.I) is not None
    if key == "Nalco":
        return re.search(r"\bnalco\b", name, re.I) is not None
    if key == "Atlas":
        return "atlas env" in n
    if key == "JMZ":
        return re.search(r"\bjmz\b", name, re.I) is not None and "/" not in name
    if key == "Pace":
        return "pace analytical" in n
    if key == "Special Pathogens":
        return "special pathogens" in n
    if key == "Clarity":
        return "clarity water" in n
    if key == "Phoenix":
        return "phoenix environmental" in n or "phoenix env" in n
    if key == "Cascade":
        return "cascade water" in n and "solution" not in n
    if key == "American Pipe":
        return (
            "american pipe" in n
            and any(token in n for token in ["tank","tnak","tanjk","andtank","7 tank","% tank"])
            and "testing" not in n and "& pipe" not in n
        )
    if key == "EBS":
        root = n in {"ebs","e b s","ebs, llc"} or (
            ("environmental" in n or "enviromental" in n)
            and "building" in n
            and any(token in n for token in ["solution","solu","soulution","soution"])
        )
        return root and "consulting" not in n and "services" not in n and "structures" not in n
    if key == "Certified Laboratories":
        return re.search(r"certified laborator|certified labs?", name, re.I) is not None
    if key == "Ambient":
        return re.search(r"\bambient (group|environmental)", name, re.I) is not None
    if key == "Loring":
        return re.search(r"\bloring\b", name, re.I) is not None
    if key == "York":
        return "york analytical" in n
    raise KeyError(key)

def sql_lit(value):
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"

def slog(value, cap):
    return min(1.0, math.log1p(max(0.0, float(value or 0))) / math.log1p(cap))

def score(firm):
    role_weights = {
        "DWT_INSPECTION_PROVIDER":15,
        "DWT_LABORATORY":15,
        "DEC_7G_REGISTERED_BUSINESS":12,
        "PROCUREMENT_VENDOR":10,
        "DOB_NOW_APPLICANT_BUSINESS":4,
        "DOB_NOW_OWNER_BUSINESS":0,
        "LEGACY_DOB_OWNER_BUSINESS":0,
    }
    role = max([0] + [role_weights.get(v,2) for v in firm.get("roles",[])])
    result = (
        25*slog(firm.get("serviced_site_count",0),500)
        +20*slog(firm.get("tower_account_count",0),250)
        +10*slog(firm.get("observed_site_count",0),500)
        +10*slog(firm.get("observed_contract_count",0),50)
        +5*slog(max(0,firm.get("observed_contract_value",0) or 0),10_000_000)
        +5*min(1,(firm.get("observed_customer_count",0) or 0)/5)
        +5*min(1,(firm.get("active_qualification_count",0) or 0))
        +(5 if firm.get("active_last_12m") else 0)
        +role
    )
    return max(0,min(100,round(result)))

def reason(firm):
    parts=[]
    if firm.get("serviced_site_count"): parts.append(f"{firm['serviced_site_count']:,} serviced sites")
    if firm.get("tower_account_count"): parts.append(f"{firm['tower_account_count']:,} tower accounts")
    if firm.get("observed_contract_count"): parts.append(f"{firm['observed_contract_count']:,} public contracts")
    if firm.get("observed_customer_count"): parts.append(f"{firm['observed_customer_count']:,} public buyers")
    if firm.get("active_qualification_count"):
        n=firm["active_qualification_count"]
        parts.append(f"{n:,} active 7G registration{'s' if n != 1 else ''}")
    if firm.get("active_last_12m"): parts.append("observed in last 12 months")
    return " · ".join(parts[:4]) or "TowerSignal public-record company evidence"

def build_plan(payload):
    firms = payload["firms"]
    by_id = {f["firm_id"]:f for f in firms}
    aliases=[]
    seen={}
    report={}
    for spec in FAMILIES:
        matches=[f for f in firms if family_match(spec["key"], f.get("canonical_name",""))]
        if len(matches) != spec["expected"]:
            raise RuntimeError(f"{spec['key']} expected {spec['expected']} variants, found {len(matches)}")
        if spec["master"] not in {f["firm_id"] for f in matches}:
            raise RuntimeError(f"{spec['key']} master {spec['master']} missing from selected variants")
        report[spec["key"]]=len(matches)
        for firm in matches:
            fid=firm["firm_id"]
            prior=seen.get(fid)
            if prior and prior != spec["master"]:
                raise RuntimeError(f"cross-family alias conflict for {fid}: {prior} vs {spec['master']}")
            seen[fid]=spec["master"]
            aliases.append({
                "company_id":fid,
                "canonical_name":firm["canonical_name"],
                "master_id":spec["master"],
                "rollup_name":spec["rollup"],
                "source_name":spec["source_name"],
                "source_url":spec["source_url"],
            })
    if len(aliases) != 250 or len(seen) != 250:
        raise RuntimeError(f"expected 250 unique reviewed variants, found aliases={len(aliases)} unique={len(seen)}")
    candidates=[]
    for firm in firms:
        name=(firm.get("canonical_name") or "").strip()
        if not name or name.upper() in {"N/A","NA","NONE","UNKNOWN"}:
            continue
        candidates.append({
            "firm_id":firm["firm_id"],
            "canonical_name":name,
            "priority_score":score(firm),
            "priority_reason":reason(firm),
        })
    candidates.sort(key=lambda row:(-row["priority_score"], row["canonical_name"]))
    candidates=candidates[:180]
    if len(candidates) != 180:
        raise RuntimeError(f"expected 180 research candidates, got {len(candidates)}")
    detail_rows=[]
    for master_id, detail in DETAILS.items():
        if master_id not in by_id:
            raise RuntimeError(f"detail master missing from known firms: {master_id}")
        row={"master_id":master_id,"canonical_name":by_id[master_id]["canonical_name"]}
        row.update({col:detail.get(col) for col in DETAIL_COLUMNS})
        detail_rows.append(row)
    return aliases, detail_rows, candidates, report

def build_sql(aliases, details, candidates):
    alias_values=",".join(
        "(" + ",".join(sql_lit(row[k]) for k in ["company_id","canonical_name","master_id","rollup_name","source_name","source_url"]) + ")"
        for row in aliases
    )
    detail_values=",".join(
        "(" + ",".join(sql_lit(row.get(k)) for k in ["master_id","canonical_name"] + DETAIL_COLUMNS) + ")"
        for row in details
    )
    candidate_values=",".join(
        "(" + ",".join([sql_lit(row["firm_id"]),sql_lit(row["canonical_name"]),str(row["priority_score"]),sql_lit(row["priority_reason"])]) + ")"
        for row in candidates
    )
    detail_cols=", ".join(DETAIL_COLUMNS)
    update_detail=",\n    ".join(
        f"{col}=COALESCE(public.company_private_profiles.{col}, EXCLUDED.{col})"
        for col in DETAIL_COLUMNS
    )
    return f"""
BEGIN;

DO $$
DECLARE v_users integer; v_admins integer;
BEGIN
  SELECT count(*) INTO v_users FROM neon_auth."user";
  SELECT count(*) INTO v_admins FROM neon_auth."user" WHERE lower(coalesce(role,''))='admin';
  IF v_users <> 2 OR v_admins <> 2 THEN
    RAISE EXCEPTION 'Company enrichment auth guard failed: users=% admins=%', v_users, v_admins;
  END IF;
END $$;

CREATE TEMP TABLE ts_rollup_target (
  company_id text PRIMARY KEY,
  canonical_name text NOT NULL,
  master_id text NOT NULL,
  rollup_name text NOT NULL,
  source_name text NOT NULL,
  source_url text
) ON COMMIT DROP;

INSERT INTO ts_rollup_target VALUES
{alias_values};

CREATE TEMP TABLE ts_master_detail (
  master_id text PRIMARY KEY,
  canonical_name text NOT NULL,
  legal_name text,
  website text,
  headquarters_address text,
  headquarters_city text,
  headquarters_region text,
  headquarters_postal_code text,
  headquarters_country text,
  parent_company_name text,
  company_type text,
  revenue_amount numeric,
  revenue_year integer,
  revenue_type text,
  revenue_source_name text,
  revenue_source_url text,
  revenue_confidence text,
  identity_source_name text,
  identity_source_url text,
  website_source_name text,
  website_source_url text,
  headquarters_source_name text,
  headquarters_source_url text,
  parent_source_name text,
  parent_source_url text
) ON COMMIT DROP;

INSERT INTO ts_master_detail VALUES
{detail_values};

CREATE TEMP TABLE ts_raw_company_research (
  firm_id text PRIMARY KEY,
  canonical_name text NOT NULL,
  priority_score integer NOT NULL,
  priority_reason text NOT NULL
) ON COMMIT DROP;

INSERT INTO ts_raw_company_research VALUES
{candidate_values};

DO $$
BEGIN
  IF (SELECT count(*) FROM ts_rollup_target) <> 250 THEN
    RAISE EXCEPTION 'Expected 250 reviewed company variants';
  END IF;
  IF EXISTS (
    SELECT 1
    FROM ts_rollup_target t
    JOIN public.company_private_profiles p ON p.company_id=t.company_id
    WHERE
      (t.company_id=t.master_id AND p.rollup_company_id IS NOT NULL)
      OR
      (t.company_id<>t.master_id AND p.rollup_company_id IS NOT NULL AND p.rollup_company_id<>t.master_id)
  ) THEN
    RAISE EXCEPTION 'Existing reviewed rollup conflicts with initial company enrichment plan';
  END IF;
END $$;

CREATE TEMP TABLE ts_apply_stats ON COMMIT DROP AS
SELECT
  (SELECT count(*) FROM public.company_private_profiles) AS before_profiles,
  (SELECT count(*) FROM public.company_private_profiles WHERE rollup_company_id IS NOT NULL) AS before_rollups,
  (SELECT count(*) FROM ts_rollup_target t LEFT JOIN public.company_private_profiles p ON p.company_id=t.company_id WHERE p.company_id IS NULL) AS new_profiles,
  (SELECT count(*) FROM ts_rollup_target t LEFT JOIN public.company_private_profiles p ON p.company_id=t.company_id
    WHERE t.company_id<>t.master_id AND p.rollup_company_id IS NULL) AS new_rollups;

CREATE TEMP TABLE ts_queue_state ON COMMIT DROP AS
WITH normalized AS (
  SELECT
    COALESCE(
      CASE WHEN t.company_id<>t.master_id THEN t.master_id END,
      p.rollup_company_id,
      q.company_id
    ) AS resolved_company_id,
    q.*
  FROM public.company_private_research_queue q
  LEFT JOIN ts_rollup_target t ON t.company_id=q.company_id
  LEFT JOIN public.company_private_profiles p ON p.company_id=q.company_id
),
ranked AS (
  SELECT *,
    row_number() OVER (
      PARTITION BY resolved_company_id
      ORDER BY
        CASE status
          WHEN 'complete' THEN 5
          WHEN 'verified' THEN 4
          WHEN 'needs-review' THEN 3
          WHEN 'researching' THEN 2
          ELSE 1
        END DESC,
        last_researched_at DESC NULLS LAST,
        updated_at DESC
    ) AS rn
  FROM normalized
)
SELECT resolved_company_id AS company_id, status, research_owner, last_researched_at
FROM ranked
WHERE rn=1;

INSERT INTO public.company_private_profiles (
  company_id, canonical_name, rollup_name, rollup_company_id,
  rollup_source_name, rollup_source_url, enrichment_checked_at,
  updated_at, last_change_source, last_change_batch_id
)
SELECT
  company_id,
  canonical_name,
  rollup_name,
  CASE WHEN company_id=master_id THEN NULL ELSE master_id END,
  source_name,
  source_url,
  now(),
  now(),
  'import',
  '{BATCH_ID}'
FROM ts_rollup_target
ON CONFLICT (company_id) DO UPDATE SET
  canonical_name=EXCLUDED.canonical_name,
  rollup_name=EXCLUDED.rollup_name,
  rollup_company_id=EXCLUDED.rollup_company_id,
  rollup_source_name=EXCLUDED.rollup_source_name,
  rollup_source_url=EXCLUDED.rollup_source_url,
  enrichment_checked_at=EXCLUDED.enrichment_checked_at,
  updated_at=now(),
  last_change_source='import',
  last_change_batch_id='{BATCH_ID}';

INSERT INTO public.company_private_profiles (
  company_id, canonical_name, {detail_cols},
  enrichment_checked_at, updated_at, last_change_source, last_change_batch_id
)
SELECT
  master_id, canonical_name,
  legal_name, website, headquarters_address, headquarters_city, headquarters_region, headquarters_postal_code, headquarters_country,
  parent_company_name, company_type, revenue_amount, revenue_year,
  COALESCE(revenue_type,'unknown'), revenue_source_name, revenue_source_url, COALESCE(revenue_confidence,'unknown'),
  identity_source_name, identity_source_url, website_source_name, website_source_url,
  headquarters_source_name, headquarters_source_url, parent_source_name, parent_source_url,
  now(), now(), 'import', '{BATCH_ID}'
FROM ts_master_detail
ON CONFLICT (company_id) DO UPDATE SET
    {update_detail},
    enrichment_checked_at=now(),
    updated_at=now(),
    last_change_source='import',
    last_change_batch_id='{BATCH_ID}';

CREATE TEMP TABLE ts_company_research_selected ON COMMIT DROP AS
WITH mapped AS (
  SELECT r.*, COALESCE(p.rollup_company_id, r.firm_id) AS master_id
  FROM ts_raw_company_research r
  LEFT JOIN public.company_private_profiles p ON p.company_id=r.firm_id
),
best AS (
  SELECT DISTINCT ON (master_id)
    master_id,
    canonical_name AS candidate_name,
    priority_score AS base_priority_score,
    priority_reason
  FROM mapped
  ORDER BY master_id, priority_score DESC, canonical_name
),
family AS (
  SELECT
    b.*,
    COALESCE(master.canonical_name, b.candidate_name) AS master_name,
    GREATEST(
      1,
      (SELECT count(*)
       FROM public.company_private_profiles fp
       WHERE fp.company_id=b.master_id OR fp.rollup_company_id=b.master_id)
    ) AS family_size
  FROM best b
  LEFT JOIN public.company_private_profiles master ON master.company_id=b.master_id
)
SELECT
  master_id AS company_id,
  master_name AS canonical_name,
  LEAST(100, base_priority_score + LEAST(5, GREATEST(0, family_size-1)))::integer AS priority_score,
  priority_reason ||
    CASE WHEN family_size > 1
      THEN ' · ' || family_size::text || ' reviewed source identities in private family'
      ELSE ''
    END AS priority_reason
FROM family
ORDER BY priority_score DESC, canonical_name
LIMIT 100;

INSERT INTO public.company_private_profiles (
  company_id, canonical_name, last_change_source, last_change_batch_id
)
SELECT company_id, canonical_name, 'system', 'research-queue-sync-20260924'
FROM ts_company_research_selected
ON CONFLICT (company_id) DO NOTHING;

INSERT INTO public.company_private_research_queue (
  company_id, priority_score, priority_reason, missing_fields,
  status, research_owner, last_researched_at, updated_at,
  last_change_source, last_change_batch_id
)
SELECT
  s.company_id,
  s.priority_score,
  s.priority_reason,
  to_jsonb(array_remove(ARRAY[
    CASE WHEN p.website IS NULL THEN 'website' END,
    CASE WHEN p.headquarters_address IS NULL AND p.headquarters_city IS NULL THEN 'headquarters' END,
    CASE WHEN p.company_type IS NULL THEN 'company type' END,
    CASE WHEN p.parent_company_id IS NULL AND p.parent_company_name IS NULL
         AND position('independently owned' in lower(coalesce(p.internal_summary,''))) = 0
         THEN 'parent / ownership' END,
    CASE WHEN p.revenue_amount IS NULL AND p.revenue_low IS NULL AND p.revenue_high IS NULL THEN 'revenue' END,
    CASE WHEN NOT EXISTS (
      SELECT 1 FROM public.company_private_contacts c
      WHERE c.company_id=s.company_id AND c.active
    ) THEN 'contact' END
  ]::text[], NULL)),
  COALESCE(qs.status,'unreviewed'),
  qs.research_owner,
  qs.last_researched_at,
  now(),
  'system',
  'research-queue-sync-20260924'
FROM ts_company_research_selected s
JOIN public.company_private_profiles p ON p.company_id=s.company_id
LEFT JOIN ts_queue_state qs ON qs.company_id=s.company_id
ON CONFLICT (company_id) DO UPDATE SET
  priority_score=EXCLUDED.priority_score,
  priority_reason=EXCLUDED.priority_reason,
  missing_fields=EXCLUDED.missing_fields,
  status=EXCLUDED.status,
  research_owner=EXCLUDED.research_owner,
  last_researched_at=EXCLUDED.last_researched_at,
  updated_at=now(),
  last_change_source='system',
  last_change_batch_id='research-queue-sync-20260924';

DELETE FROM public.company_private_research_queue q
WHERE NOT EXISTS (
  SELECT 1 FROM ts_company_research_selected s WHERE s.company_id=q.company_id
);

DO $$
DECLARE
  s record;
  v_profiles integer;
  v_rollups integer;
  v_queue integer;
  v_alias_queue integer;
  v_target_ok integer;
BEGIN
  SELECT * INTO s FROM ts_apply_stats;
  SELECT count(*) INTO v_profiles FROM public.company_private_profiles;
  SELECT count(*) INTO v_rollups FROM public.company_private_profiles WHERE rollup_company_id IS NOT NULL;
  SELECT count(*) INTO v_queue FROM public.company_private_research_queue;
  SELECT count(*) INTO v_alias_queue
  FROM public.company_private_research_queue q
  JOIN public.company_private_profiles p ON p.company_id=q.company_id
  WHERE p.rollup_company_id IS NOT NULL;
  SELECT count(*) INTO v_target_ok
  FROM ts_rollup_target t
  JOIN public.company_private_profiles p ON p.company_id=t.company_id
  WHERE
    (t.company_id=t.master_id AND p.rollup_company_id IS NULL AND p.rollup_name=t.rollup_name)
    OR
    (t.company_id<>t.master_id AND p.rollup_company_id=t.master_id AND p.rollup_name=t.rollup_name);

  IF v_profiles < s.before_profiles + s.new_profiles THEN
    RAISE EXCEPTION 'Profile postcondition failed: before=% planned_new=% after=%', s.before_profiles, s.new_profiles, v_profiles;
  END IF;
  IF v_rollups <> s.before_rollups + s.new_rollups THEN
    RAISE EXCEPTION 'Rollup postcondition failed: before=% new=% after=%', s.before_rollups, s.new_rollups, v_rollups;
  END IF;
  IF v_queue <> 100 OR v_alias_queue <> 0 OR v_target_ok <> 250 THEN
    RAISE EXCEPTION 'Company postcondition failed: queue=% alias_queue=% target_ok=%', v_queue, v_alias_queue, v_target_ok;
  END IF;
END $$;

SELECT
  'INITIAL_COMPANY_ENRICHMENT=PASS' AS result,
  (SELECT count(*) FROM public.company_private_profiles) AS profiles,
  (SELECT count(*) FROM public.company_private_profiles WHERE rollup_company_id IS NOT NULL) AS rollups,
  (SELECT count(*) FROM public.company_private_research_queue) AS research_queue,
  (SELECT count(*) FROM public.company_private_contacts) AS contacts,
  (SELECT count(*) FROM public.company_private_change_log) AS audit_rows,
  (SELECT new_profiles FROM ts_apply_stats) AS added_profiles,
  (SELECT new_rollups FROM ts_apply_stats) AS added_rollups;

COMMIT;
"""

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--known-firms", required=True)
    parser.add_argument("--sql-out", required=True)
    parser.add_argument("--plan-out")
    args=parser.parse_args()

    payload=json.loads(Path(args.known_firms).read_text(encoding="utf-8"))
    if payload.get("domain") != "TOWERSIGNAL_KNOWN_FIRMS":
        raise RuntimeError("Unexpected known-firms payload domain")
    aliases, details, candidates, report=build_plan(payload)
    Path(args.sql_out).write_text(build_sql(aliases, details, candidates),encoding="utf-8")
    if args.plan_out:
        Path(args.plan_out).write_text(json.dumps({
            "schema":"TOWERSIGNAL_INITIAL_COMPANY_ROLLUP_PLAN_V1",
            "batch_id":BATCH_ID,
            "family_counts":report,
            "alias_count":len(aliases),
            "detail_master_count":len(details),
            "aliases":aliases,
            "details":details,
        },indent=2),encoding="utf-8")
    print(f"INITIAL_COMPANY_PLAN=PASS families={len(FAMILIES)} aliases={len(aliases)} detail_masters={len(details)}")

if __name__ == "__main__":
    main()
