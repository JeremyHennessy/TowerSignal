from __future__ import annotations

import re
from collections import Counter
from typing import Any, Mapping, Sequence

from towersignal.domestic_water_market import (
    NYC_API_ROOT,
    SourceSnapshot,
    fetch_snapshot,
    normalize_company_key,
    normalize_space,
    parse_source_date,
    source_health,
    stable_id,
    utc_now,
)

SCHEMA_VERSION = "1.0"
NYC_311_DATASET_ID = "erm2-nwe9"
HPD_VIOLATIONS_DATASET_ID = "wvxf-dwi5"
DOB_JOB_FILINGS_DATASET_ID = "w9ak-ipjd"
DOB_APPROVED_PERMITS_DATASET_ID = "rbx6-tga4"
LL84_DATASET_ID = "5zyy-y8am"
NYC_311_START = "2025-01-01T00:00:00.000"
DOB_START = "2024-01-01T00:00:00.000"
HPD_MAX_PAGE_SIZE = 10000
HPD_WATER_TERMS = (
    "hot water",
    "water supply",
    "potable",
    "plumbing",
    "faucet",
    "sink",
    "toilet",
    "shower",
    "bathtub",
    "water closet",
)

NYC_311_WHERE = (
    "agency='DEP' AND created_date >= '2025-01-01T00:00:00.000' AND ("
    "lower(complaint_type) like '%water%' OR lower(descriptor) like '%water%' OR "
    "lower(descriptor_2) like '%water%' OR lower(complaint_type) like '%lead%' OR "
    "lower(descriptor) like '%lead%' OR lower(descriptor_2) like '%lead%')"
)
DOB_WATER_TERMS = (
    "lower(job_description) like '%water%' OR lower(job_description) like '%plumb%' OR "
    "lower(job_description) like '%backflow%' OR lower(job_description) like '%rpz%' OR "
    "lower(job_description) like '%booster%' OR lower(job_description) like '%pump%' OR "
    "lower(job_description) like '%tank%'"
)
DOB_JOB_WHERE = (
    "filing_date >= '2024-01-01T00:00:00.000' AND "
    "(plumbing_work_type='YES' OR mechanical_systems_work_type_='YES' OR boiler_equipment_work_type_='YES') AND ("
    + DOB_WATER_TERMS + ")"
)
DOB_PERMIT_WHERE = (
    "issued_date >= '2024-01-01T00:00:00.000' AND "
    "work_type in ('Plumbing','Mechanical Systems','Boiler Equipment') AND (" + DOB_WATER_TERMS + ")"
)


def _lower_text(*values: Any) -> str:
    return normalize_space(" ".join(str(value or "") for value in values)).lower()


def _normalize_bbl(value: Any) -> str | None:
    digits = re.sub(r"\D", "", normalize_space(value))
    return digits if len(digits) == 10 and digits[0] in "12345" else None


def _normalize_bin(value: Any) -> str | None:
    digits = re.sub(r"\D", "", normalize_space(value))
    return digits if len(digits) == 7 else None


def _identifier_list(value: Any, digits: int) -> list[str]:
    text = normalize_space(value)
    return sorted(set(re.findall(rf"(?<!\d)\d{{{digits}}}(?!\d)", text))) if text else []


def _number(value: Any) -> float | None:
    text = normalize_space(value).replace(",", "")
    if not text or text.lower() in {"n/a", "na", "not available", "none", "null", "-"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def classify_311(row: Mapping[str, Any]) -> str:
    text = _lower_text(row.get("complaint_type"), row.get("descriptor"), row.get("descriptor_2"))
    if any(term in text for term in ("sewer", "catch basin", "stormwater", "storm water")):
        return "SEWER_STORMWATER_CONTEXT"
    if "hydrant" in text:
        return "HYDRANT_CONTEXT"
    if any(term in text for term in ("water main", "main break", "street leak", "street flooding")):
        return "STREET_WATER_MAIN_CONTEXT"
    if any(term in text for term in ("water quality", "dirty water", "discolored", "discolour", "taste", "odor", "odour", "cloudy", "lead")):
        return "BUILDING_WATER_QUALITY"
    if any(term in text for term in ("no water", "low water", "water pressure", "low pressure")):
        return "BUILDING_NO_WATER_OR_PRESSURE"
    if "leak" in text:
        return "BUILDING_WATER_LEAK"
    return "OTHER_DEP_WATER"


def normalize_311(row: Mapping[str, Any]) -> dict[str, Any]:
    category = classify_311(row)
    bbl = _normalize_bbl(row.get("bbl"))
    address = normalize_space(row.get("incident_address")) or None
    is_building = category.startswith("BUILDING_")
    link = "CONFIRMED_SOURCE_BBL" if is_building and bbl else ("ADDRESS_CONTEXT" if is_building and address else "CONTEXT_ONLY")
    return {
        "request_id": normalize_space(row.get("unique_key")) or stable_id("311-water", dict(row)),
        "created_date": parse_source_date(row.get("created_date")),
        "closed_date": parse_source_date(row.get("closed_date")),
        "agency": normalize_space(row.get("agency")) or None,
        "agency_name": normalize_space(row.get("agency_name")) or None,
        "complaint_type": normalize_space(row.get("complaint_type")) or None,
        "descriptor": normalize_space(row.get("descriptor")) or None,
        "descriptor_2": normalize_space(row.get("descriptor_2")) or None,
        "category": category,
        "status": normalize_space(row.get("status")) or None,
        "resolution_description": normalize_space(row.get("resolution_description")) or None,
        "bbl": bbl,
        "address": address,
        "street_name": normalize_space(row.get("street_name")) or None,
        "borough": normalize_space(row.get("borough")) or None,
        "zip": normalize_space(row.get("incident_zip")) or None,
        "property_link_confidence": link,
        "is_building_water_signal": is_building,
        "raw": dict(row),
    }


def classify_hpd(row: Mapping[str, Any]) -> str:
    text = _lower_text(row.get("novdescription"))
    if "hot water" in text:
        return "HOT_WATER"
    if any(term in text for term in ("potable", "water supply", "cold water", "water closet")):
        return "WATER_SUPPLY_OR_FIXTURE"
    if any(term in text for term in ("faucet", "sink", "toilet", "shower", "bathtub")):
        return "PLUMBING_FIXTURE"
    if "plumbing" in text:
        return "PLUMBING_GENERAL"
    return "OTHER_WATER_HOUSING_CODE"


def normalize_hpd(row: Mapping[str, Any]) -> dict[str, Any]:
    bbl = _normalize_bbl(row.get("bbl"))
    bin_value = _normalize_bin(row.get("bin"))
    address = normalize_space(f"{normalize_space(row.get('housenumber'))} {normalize_space(row.get('streetname'))}") or None
    return {
        "violation_id": normalize_space(row.get("violationid")) or stable_id("hpd-water", dict(row)),
        "building_id": normalize_space(row.get("buildingid")) or None,
        "registration_id": normalize_space(row.get("registrationid")) or None,
        "bbl": bbl,
        "bin": bin_value,
        "address": address,
        "borough": normalize_space(row.get("boro")) or None,
        "zip": normalize_space(row.get("zip")) or None,
        "class": normalize_space(row.get("class")) or None,
        "inspection_date": parse_source_date(row.get("inspectiondate")),
        "nov_description": normalize_space(row.get("novdescription")) or None,
        "current_status": normalize_space(row.get("currentstatus")) or None,
        "current_status_date": parse_source_date(row.get("currentstatusdate")),
        "violation_status": normalize_space(row.get("violationstatus")) or None,
        "rent_impairing": normalize_space(row.get("rentimpairing")) or None,
        "category": classify_hpd(row),
        "property_link_confidence": "CONFIRMED_SOURCE_BBL" if bbl else ("CONFIRMED_SOURCE_BIN" if bin_value else "ADDRESS_CONTEXT"),
        "raw": dict(row),
    }


def _hpd_term_where(term: str) -> str:
    return f"violationstatus='Open' AND novdescription like '%{term.upper()}%'"


def _fetch_hpd_snapshots(*, page_size: int) -> list[SourceSnapshot]:
    snapshots: list[SourceSnapshot] = []
    for term in HPD_WATER_TERMS:
        snapshots.append(
            fetch_snapshot(
                HPD_VIOLATIONS_DATASET_ID, api_root=NYC_API_ROOT, order_by="violationid",
                required_fields=("violationid", "buildingid", "registrationid", "boro", "housenumber", "streetname", "zip", "class", "inspectiondate", "novdescription", "currentstatus", "currentstatusdate", "violationstatus", "rentimpairing", "bin", "bbl"),
                where=_hpd_term_where(term),
                select="violationid,buildingid,registrationid,boro,housenumber,streetname,zip,class,inspectiondate,novdescription,currentstatus,currentstatusdate,violationstatus,rentimpairing,bin,bbl",
                page_size=min(page_size, HPD_MAX_PAGE_SIZE),
                allow_count_fallback=True,
                progress_label=f"NYC water HPD term {term!r}",
                seek_field="violationid",
            )
        )
    return snapshots


def _dedupe_hpd_rows(snapshots: Sequence[SourceSnapshot]) -> tuple[list[dict[str, Any]], int]:
    rows_by_id: dict[str, dict[str, Any]] = {}
    duplicate_count = 0
    for snapshot in snapshots:
        for row in snapshot.rows:
            violation_id = normalize_space(row.get("violationid")) or stable_id("hpd-water-source", row)
            if violation_id in rows_by_id:
                duplicate_count += 1
                continue
            rows_by_id[violation_id] = row
    return sorted(rows_by_id.values(), key=lambda row: normalize_space(row.get("violationid"))), duplicate_count


def classify_dob_work(row: Mapping[str, Any]) -> str:
    text = _lower_text(row.get("job_description"), row.get("work_type"))
    if any(term in text for term in ("sprinkler", "standpipe", "fire suppression")) and not any(term in text for term in ("domestic water", "potable", "backflow", "rpz")):
        return "FIRE_WATER_CONTEXT"
    if any(term in text for term in ("cooling tower", "condenser water")):
        return "COOLING_TOWER_ADJACENT"
    if any(term in text for term in ("backflow", "rpz", "reduced pressure zone")):
        return "BACKFLOW_PREVENTION"
    if any(term in text for term in ("roof tank", "water tank", "domestic tank", "storage tank")):
        return "DOMESTIC_WATER_STORAGE"
    if any(term in text for term in ("domestic water", "potable water", "cold water")):
        return "DOMESTIC_WATER_SYSTEM"
    if any(term in text for term in ("hot water", "water heater")):
        return "HOT_WATER_SYSTEM"
    if any(term in text for term in ("booster pump", "water pump", "pump")):
        return "WATER_PUMP"
    if "boiler" in text:
        return "BOILER_WATER_ADJACENT"
    if "plumb" in text:
        return "PLUMBING_WATER_RELATED"
    return "OTHER_WATER_MECHANICAL"


def _applicant_name(row: Mapping[str, Any]) -> str | None:
    value = normalize_space(" ".join(item for item in (
        normalize_space(row.get("applicant_first_name")),
        normalize_space(row.get("applicants_middle_initial") or row.get("applicant_middle_name")),
        normalize_space(row.get("applicant_last_name")),
    ) if item))
    return value or None


def normalize_dob_job(row: Mapping[str, Any]) -> dict[str, Any]:
    business = normalize_space(row.get("applicant_business_name")) or None
    bbl = _normalize_bbl(row.get("bbl"))
    bin_value = _normalize_bin(row.get("bin"))
    return {
        "activity_id": stable_id("dob-job-water", row.get("job_filing_number")),
        "source_record_id": normalize_space(row.get("job_filing_number")) or None,
        "record_type": "JOB_APPLICATION_FILING",
        "filing_status": normalize_space(row.get("filing_status")) or None,
        "filing_date": parse_source_date(row.get("filing_date")),
        "approved_date": parse_source_date(row.get("approved_date")),
        "signoff_date": parse_source_date(row.get("signoff_date")),
        "bbl": bbl,
        "bin": bin_value,
        "address": normalize_space(f"{normalize_space(row.get('house_no'))} {normalize_space(row.get('street_name'))}") or None,
        "borough": normalize_space(row.get("borough")) or None,
        "plumbing_work_type": normalize_space(row.get("plumbing_work_type")) or None,
        "mechanical_work_type": normalize_space(row.get("mechanical_systems_work_type_")) or None,
        "boiler_work_type": normalize_space(row.get("boiler_equipment_work_type_")) or None,
        "job_description": normalize_space(row.get("job_description")) or None,
        "category": classify_dob_work(row),
        "applicant_name": _applicant_name(row),
        "applicant_business_raw": business,
        "applicant_business_key": normalize_company_key(business) if business else None,
        "applicant_license": normalize_space(row.get("applicant_license")) or None,
        "applicant_professional_title": normalize_space(row.get("applicant_professional_title")) or None,
        "relationship_role": "JOB_APPLICANT_OF_RECORD" if business else None,
        "relationship_evidence": "RECORDED_DOB_ROLE" if business else None,
        "service_assignment_confidence": "NOT_PROOF_OF_SERVICE_CONTRACT" if business else None,
        "owner_business_name": normalize_space(row.get("owner_s_business_name")) or None,
        "property_link_confidence": "CONFIRMED_SOURCE_BBL" if bbl else ("CONFIRMED_SOURCE_BIN" if bin_value else "ADDRESS_CONTEXT"),
        "raw": dict(row),
    }


def normalize_dob_permit(row: Mapping[str, Any]) -> dict[str, Any]:
    business = normalize_space(row.get("applicant_business_name")) or None
    bbl = _normalize_bbl(row.get("bbl"))
    bin_value = _normalize_bin(row.get("bin"))
    record_id = normalize_space(row.get("work_permit")) or stable_id("dob-permit-source", row.get("job_filing_number"), row.get("sequence_number"), row.get("work_type"))
    return {
        "activity_id": stable_id("dob-permit-water", record_id),
        "source_record_id": record_id,
        "job_filing_number": normalize_space(row.get("job_filing_number")) or None,
        "record_type": "APPROVED_PERMIT",
        "sequence_number": normalize_space(row.get("sequence_number")) or None,
        "filing_reason": normalize_space(row.get("filing_reason")) or None,
        "approved_date": parse_source_date(row.get("approved_date")),
        "issued_date": parse_source_date(row.get("issued_date")),
        "expired_date": parse_source_date(row.get("expired_date")),
        "permit_status": normalize_space(row.get("permit_status")) or None,
        "bbl": bbl,
        "bin": bin_value,
        "address": normalize_space(f"{normalize_space(row.get('house_no'))} {normalize_space(row.get('street_name'))}") or None,
        "borough": normalize_space(row.get("borough")) or None,
        "work_type": normalize_space(row.get("work_type")) or None,
        "job_description": normalize_space(row.get("job_description")) or None,
        "estimated_job_costs": _number(row.get("estimated_job_costs")),
        "category": classify_dob_work(row),
        "applicant_name": _applicant_name(row),
        "applicant_business_raw": business,
        "applicant_business_key": normalize_company_key(business) if business else None,
        "applicant_license": normalize_space(row.get("applicant_license")) or None,
        "permittee_license_type": normalize_space(row.get("permittee_s_license_type")) or None,
        "relationship_role": "PERMIT_APPLICANT_OF_RECORD" if business else None,
        "relationship_evidence": "RECORDED_DOB_ROLE" if business else None,
        "service_assignment_confidence": "NOT_PROOF_OF_SERVICE_CONTRACT" if business else None,
        "owner_business_name": normalize_space(row.get("owner_business_name")) or None,
        "property_link_confidence": "CONFIRMED_SOURCE_BBL" if bbl else ("CONFIRMED_SOURCE_BIN" if bin_value else "ADDRESS_CONTEXT"),
        "raw": dict(row),
    }


def normalize_ll84(row: Mapping[str, Any]) -> dict[str, Any]:
    bbls = _identifier_list(row.get("nyc_borough_block_and_lot"), 10)
    bins = _identifier_list(row.get("nyc_building_identification"), 7)
    if len(bbls) == 1:
        link, property_key = "EXACT_SINGLE_BBL", f"NYC-BBL-{bbls[0]}"
    elif not bbls and len(bins) == 1:
        link, property_key = "EXACT_SINGLE_BIN", f"NYC-BIN-{bins[0]}"
    elif bbls or bins:
        link, property_key = "MULTI_IDENTIFIER_CONTEXT", None
    else:
        link, property_key = "UNLINKED", None
    return {
        "benchmark_id": stable_id("ll84-water", row.get("report_year"), row.get("property_id")),
        "report_year": normalize_space(row.get("report_year")) or None,
        "property_id": normalize_space(row.get("property_id")) or None,
        "property_name": normalize_space(row.get("property_name")) or None,
        "year_ending": parse_source_date(row.get("year_ending")),
        "bbls": bbls,
        "bins": bins,
        "property_key": property_key,
        "property_link_confidence": link,
        "address": normalize_space(row.get("address_1")) or None,
        "city": normalize_space(row.get("city")) or None,
        "postal_code": normalize_space(row.get("postal_code")) or None,
        "metered_areas_water": normalize_space(row.get("metered_areas_water")) or None,
        "water_use_all_sources_kgal": _number(row.get("water_use_all_water_sources")),
        "indoor_water_use_all_sources_kgal": _number(row.get("indoor_water_use_all_water")),
        "outdoor_water_use_all_sources_kgal": _number(row.get("outdoor_water_use_all_water")),
        "municipal_potable_mixed_kgal": _number(row.get("municipally_supplied_potable")),
        "municipal_potable_total_kgal": _number(row.get("municipally_supplied_potable_1")),
        "municipal_potable_indoor_kgal": _number(row.get("municipally_supplied_potable_2")),
        "municipal_potable_outdoor_kgal": _number(row.get("municipally_supplied_potable_3")),
        "estimated_values_water": normalize_space(row.get("estimated_values_water")) or None,
        "water_meter_alert_less_than_12_months": normalize_space(row.get("alert_water_meter_has_less")) or None,
        "last_modified_date_water": parse_source_date(row.get("last_modified_date_water")),
        "raw": dict(row),
    }


def _dob_business_profiles(*collections: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for rows in collections:
        for row in rows:
            key = normalize_space(row.get("applicant_business_key"))
            raw_name = normalize_space(row.get("applicant_business_raw"))
            if not key or not raw_name:
                continue
            profile = profiles.setdefault(key, {
                "business_id": stable_id("dob-business", key), "business_key": key, "aliases": Counter(),
                "record_count": 0, "job_filing_count": 0, "permit_count": 0, "bbls": set(), "licenses": set(),
                "categories": Counter(), "relationship_evidence": "RECORDED_DOB_ROLE",
                "service_assignment_confidence": "NOT_PROOF_OF_SERVICE_CONTRACT",
            })
            profile["aliases"][raw_name] += 1
            profile["record_count"] += 1
            if row.get("record_type") == "JOB_APPLICATION_FILING":
                profile["job_filing_count"] += 1
            elif row.get("record_type") == "APPROVED_PERMIT":
                profile["permit_count"] += 1
            if row.get("bbl"):
                profile["bbls"].add(str(row["bbl"]))
            if row.get("applicant_license"):
                profile["licenses"].add(str(row["applicant_license"]))
            if row.get("category"):
                profile["categories"][str(row["category"])] += 1
    result: list[dict[str, Any]] = []
    for profile in profiles.values():
        aliases = profile.pop("aliases")
        bbls = profile.pop("bbls")
        licenses = profile.pop("licenses")
        categories = profile.pop("categories")
        profile["aliases"] = [{"name": name, "record_count": count} for name, count in aliases.most_common()]
        profile["observed_bbl_count"] = len(bbls)
        profile["licenses"] = sorted(licenses)
        profile["category_counts"] = dict(sorted(categories.items()))
        result.append(profile)
    return sorted(result, key=lambda item: (-int(item["observed_bbl_count"]), str(item["business_key"])))


def build_payload(*, page_size: int = 50000) -> dict[str, Any]:
    requests_snapshot = fetch_snapshot(
        NYC_311_DATASET_ID, api_root=NYC_API_ROOT, order_by="unique_key",
        required_fields=("unique_key", "created_date", "closed_date", "agency", "agency_name", "complaint_type", "descriptor", "descriptor_2", "incident_zip", "incident_address", "street_name", "status", "resolution_description", "bbl", "borough"),
        where=NYC_311_WHERE,
        select="unique_key,created_date,closed_date,agency,agency_name,complaint_type,descriptor,descriptor_2,incident_zip,incident_address,street_name,status,resolution_description,bbl,borough",
        page_size=page_size,
        progress_label="NYC water 311 DEP requests",
    )
    hpd_snapshots = _fetch_hpd_snapshots(page_size=page_size)
    hpd_rows, hpd_duplicate_partition_count = _dedupe_hpd_rows(hpd_snapshots)
    job_snapshot = fetch_snapshot(
        DOB_JOB_FILINGS_DATASET_ID, api_root=NYC_API_ROOT, order_by="job_filing_number",
        required_fields=("job_filing_number", "filing_status", "house_no", "street_name", "borough", "bin", "bbl", "applicant_professional_title", "applicant_license", "applicant_first_name", "applicants_middle_initial", "applicant_last_name", "applicant_business_name", "owner_s_business_name", "plumbing_work_type", "boiler_equipment_work_type_", "mechanical_systems_work_type_", "filing_date", "approved_date", "signoff_date", "job_description"),
        where=DOB_JOB_WHERE,
        select="job_filing_number,filing_status,house_no,street_name,borough,bin,bbl,applicant_professional_title,applicant_license,applicant_first_name,applicants_middle_initial,applicant_last_name,applicant_business_name,owner_s_business_name,plumbing_work_type,boiler_equipment_work_type_,mechanical_systems_work_type_,filing_date,approved_date,signoff_date,job_description",
        page_size=page_size,
        progress_label="NYC water DOB job filings",
    )
    permit_snapshot = fetch_snapshot(
        DOB_APPROVED_PERMITS_DATASET_ID, api_root=NYC_API_ROOT, order_by="job_filing_number,work_permit,sequence_number",
        required_fields=("job_filing_number", "work_permit", "sequence_number", "filing_reason", "house_no", "street_name", "borough", "bin", "bbl", "work_type", "permittee_s_license_type", "applicant_license", "applicant_first_name", "applicant_last_name", "applicant_business_name", "approved_date", "issued_date", "expired_date", "job_description", "estimated_job_costs", "owner_business_name", "permit_status"),
        where=DOB_PERMIT_WHERE,
        select="job_filing_number,work_permit,sequence_number,filing_reason,house_no,street_name,borough,bin,bbl,work_type,permittee_s_license_type,applicant_license,applicant_first_name,applicant_last_name,applicant_business_name,approved_date,issued_date,expired_date,job_description,estimated_job_costs,owner_business_name,permit_status",
        page_size=page_size,
        progress_label="NYC water DOB approved permits",
    )
    ll84_snapshot = fetch_snapshot(
        LL84_DATASET_ID, api_root=NYC_API_ROOT, order_by="report_year,property_id",
        required_fields=("report_year", "property_id", "property_name", "year_ending", "nyc_borough_block_and_lot", "nyc_building_identification", "address_1", "city", "postal_code", "metered_areas_water", "water_use_all_water_sources", "indoor_water_use_all_water", "outdoor_water_use_all_water", "municipally_supplied_potable", "municipally_supplied_potable_1", "municipally_supplied_potable_2", "municipally_supplied_potable_3", "estimated_values_water", "alert_water_meter_has_less", "last_modified_date_water"),
        select="report_year,property_id,property_name,year_ending,nyc_borough_block_and_lot,nyc_building_identification,address_1,city,postal_code,metered_areas_water,water_use_all_water_sources,indoor_water_use_all_water,outdoor_water_use_all_water,municipally_supplied_potable,municipally_supplied_potable_1,municipally_supplied_potable_2,municipally_supplied_potable_3,estimated_values_water,alert_water_meter_has_less,last_modified_date_water",
        page_size=page_size,
        progress_label="NYC water LL84 benchmarks",
    )
    requests = [normalize_311(row) for row in requests_snapshot.rows]
    hpd = [normalize_hpd(row) for row in hpd_rows]
    jobs = [normalize_dob_job(row) for row in job_snapshot.rows]
    permits = [normalize_dob_permit(row) for row in permit_snapshot.rows]
    ll84 = [normalize_ll84(row) for row in ll84_snapshot.rows]
    dob_businesses = _dob_business_profiles(jobs, permits)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "domain": "NYC_BUILDING_WATER_SIGNALS",
        "query_boundaries": {"311_start": NYC_311_START, "hpd_scope": "Current open HPD violations fetched through uppercase source-description keyword partitions.", "hpd_terms": list(HPD_WATER_TERMS), "dob_start": DOB_START, "ll84_scope": "All rows in current consolidated 2022-present LL84 source, slim water fields only."},
        "evidence_semantics": {
            "311": "Service-request observations. Building signal only when classification is building-water; street/hydrant/sewer remain context.",
            "hpd": "Current HPD violation evidence directly tied to source BIN/BBL when present.",
            "dob": "Applicant/permit roles are recorded regulatory roles, not proof that the entity won or performs a service contract.",
            "ll84": "Self-reported benchmarking water data. Multi-BBL/BIN rows remain contextual and are not forced to a single property.",
        },
        "summary": {
            "water_311_request_count": len(requests),
            "water_311_building_signal_count": sum(1 for row in requests if row["is_building_water_signal"]),
            "hpd_open_water_violation_count": len(hpd),
            "hpd_source_fetch_strategy": "UPPERCASE_KEYWORD_PARTITIONS",
            "hpd_source_partition_count": len(hpd_snapshots),
            "hpd_source_partition_record_count": sum(snapshot.source_record_count for snapshot in hpd_snapshots),
            "hpd_duplicate_partition_violation_count": hpd_duplicate_partition_count,
            "dob_water_job_filing_count": len(jobs),
            "dob_water_permit_count": len(permits),
            "dob_observed_business_count": len(dob_businesses),
            "ll84_water_benchmark_count": len(ll84),
            "ll84_exact_single_property_count": sum(1 for row in ll84 if str(row["property_link_confidence"]).startswith("EXACT_SINGLE")),
            "ll84_multi_identifier_count": sum(1 for row in ll84 if row["property_link_confidence"] == "MULTI_IDENTIFIER_CONTEXT"),
            "ll84_rows_with_municipal_potable_total": sum(1 for row in ll84 if row["municipal_potable_total_kgal"] is not None),
        },
        "source_health": [
            source_health(requests_snapshot, normalized_count=len(requests)),
            *[source_health(snapshot, normalized_count=len(snapshot.rows)) for snapshot in hpd_snapshots],
            source_health(job_snapshot, normalized_count=len(jobs)),
            source_health(permit_snapshot, normalized_count=len(permits)),
            source_health(ll84_snapshot, normalized_count=len(ll84)),
        ],
        "water_311_requests": requests,
        "hpd_open_water_violations": hpd,
        "dob_water_job_filings": jobs,
        "dob_water_permits": permits,
        "dob_observed_businesses": dob_businesses,
        "ll84_water_benchmarks": ll84,
    }
