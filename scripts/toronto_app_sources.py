from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse
try:
    from .toronto_source_identity import find_source_record
except ImportError:
    from toronto_source_identity import find_source_record


OFFICIAL_DATASET_URLS = {
    "311_matches_prior_poc": "https://open.toronto.ca/dataset/311-service-requests-customer-initiated/",
    "affordable_housing_pipeline": "https://open.toronto.ca/dataset/upcoming-and-recently-completed-affordable-housing-units/",
    "apartment_building_evaluation": "https://open.toronto.ca/dataset/apartment-building-evaluation/",
    "business_licence_matches_prior_poc": "https://open.toronto.ca/dataset/municipal-licensing-and-standards-business-licences-and-permits/",
    "chemtrac_2024": "https://open.toronto.ca/dataset/chemical-tracking-chemtrac/",
    "chemtrac_history": "https://open.toronto.ca/dataset/chemical-tracking-chemtrac/",
    "development_pipeline": "https://open.toronto.ca/dataset/development-pipeline/",
    "ontario_environmental_compliance_reports": "https://data.ontario.ca/dataset/environmental-compliance-reports",
    "ontario_bps_energy_2024": "https://data.ontario.ca/dataset/energy-use-and-greenhouse-gas-emissions-for-the-broader-public-sector",
    "renewable_energy_installations": "https://open.toronto.ca/dataset/renewable-energy-installations/",
    "tobids_awarded_contracts_exact_document_address_prior_poc": "https://open.toronto.ca/dataset/tobids-awarded-contracts/",
    "toronto_aic_applications": "https://www.toronto.ca/city-government/planning-development/application-details/",
    "toronto_highrise_residential_health_hazards": "https://open.toronto.ca/dataset/residential-health-hazards/",
    "toronto_building_permits_active_targeted": "https://open.toronto.ca/dataset/building-permits-active-permits/",
    "toronto_building_permits_cleared_targeted_since_2017": "https://open.toronto.ca/dataset/building-permits-cleared-permits/",
    "tdsb_facility_condition_renewal": "https://www.tdsb.on.ca/Community/Planning/School-Facilities/Facility-Condition-Index",
    "toronto_public_notices_exact_prior_poc": "https://open.toronto.ca/dataset/public-notices/",
}

ALLOWED_HOSTS = {
    "data.ontario.ca",
    "open.toronto.ca",
    "secure.toronto.ca",
    "www.toronto.ca",
    "www.tdsb.on.ca",
}


def text(value: Any, limit: int = 240) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", " ", html.unescape(str(value))).strip()
    if not normalized or normalized.lower() in {"none", "null", "nan"}:
        return None
    return normalized if len(normalized) <= limit else f"{normalized[: limit - 1].rstrip()}…"


def date_value(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value) / 1000, tz=timezone.utc).date().isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    raw = text(value, 40)
    if not raw:
        return None
    return raw[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", raw) else raw


def valid_public_url(value: Any) -> str | None:
    url = text(value, 1000)
    if not url:
        return None
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in ALLOWED_HOSTS:
        return None
    if host == "secure.toronto.ca" and parsed.path.lower() == "/aic/index.do":
        return None
    return url


def details(*items: tuple[str, Any]) -> list[dict[str, str]]:
    output = []
    for label, value in items:
        normalized = text(value)
        if normalized:
            output.append({"label": label, "value": normalized})
    return output


def aic_record_url(row: dict[str, Any]) -> str | None:
    folder_rsn = text(row.get("FOLDERRSN"), 80)
    property_rsn = text(row.get("PROPERTYRSN") or row.get("MAINPROPERTYRSN"), 80)
    if not folder_rsn or not property_rsn:
        return None
    query = urlencode({"id": folder_rsn, "pid": property_rsn})
    return valid_public_url(f"https://www.toronto.ca/city-government/planning-development/application-details/?{query}")


def rentsafe_record_url(row: dict[str, Any]) -> str | None:
    rsn = text(row.get("RSN") or row.get("rsn"), 80)
    if not rsn:
        return None
    query = urlencode({"id": rsn})
    return valid_public_url(
        "https://www.toronto.ca/community-people/housing-shelter/rental-housing-rights-information/"
        "housing-property-standards/apartment-building-standards/audits-evaluations/"
        f"rentsafeto-building-evaluation-report/?{query}"
    )


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("rows", "records", "applications", "toronto_rows", "toronto_candidates", "matches"):
        values = payload.get(key)
        if isinstance(values, list):
            return [item for item in values if isinstance(item, dict)]
    return []


def load_source_rows(root: Path, load_json: Any) -> dict[str, list[dict[str, Any]]]:
    warehouse = root / "data/toronto/warehouse/current"
    market = root / "data/toronto/market/current"
    files = {
        "311_matches_prior_poc": warehouse / "311_matches.json",
        "affordable_housing_pipeline": warehouse / "open_licensed/affordable_housing_pipeline.json",
        "apartment_building_evaluation": warehouse / "open_licensed/apartment_building_evaluation.json",
        "business_licence_matches_prior_poc": warehouse / "business_licence_matches.json",
        "chemtrac_2024": warehouse / "open_licensed/chemtrac_2024.json",
        "chemtrac_history": warehouse / "open_licensed/chemtrac_history.json",
        "development_pipeline": warehouse / "open_licensed/development_pipeline.json",
        "ontario_environmental_compliance_reports": warehouse / "open_licensed/ontario_environmental_compliance_reports.json",
        "ontario_bps_energy_2024": warehouse / "open_licensed/ontario_bps_energy_2024.json",
        "renewable_energy_installations": warehouse / "open_licensed/renewable_energy_installations.json",
        "tobids_awarded_contracts_exact_document_address_prior_poc": warehouse / "open_licensed/tobids_awarded_contracts.json",
        "toronto_aic_applications": market / "open_licensed/toronto_aic_applications.json",
        "toronto_highrise_residential_health_hazards": market / "open_licensed/toronto_highrise_residential_health_hazards.json",
        "toronto_building_permits_active_targeted": warehouse / "open_licensed/toronto_building_permits_active_targeted.json",
        "toronto_building_permits_cleared_targeted_since_2017": warehouse / "open_licensed/toronto_building_permits_cleared_targeted_since_2017.json",
        "tdsb_facility_condition_renewal": warehouse / "open_licensed/tdsb_facility_condition_renewal.json",
        "toronto_public_notices_exact_prior_poc": warehouse / "open_licensed/toronto_public_notices.json",
    }
    loaded = {key: _rows(load_json(path)) for key, path in files.items()}
    loaded["311_matches_prior_poc"] = [item.get("source_row") or {} for item in loaded["311_matches_prior_poc"]]
    loaded["business_licence_matches_prior_poc"] = [item.get("source_row") or {} for item in loaded["business_licence_matches_prior_poc"]]

    notices = load_json(files["toronto_public_notices_exact_prior_poc"])
    # Use the full planning-notice collection. Exact prior-POC links and newer
    # application-number links both resolve by stable noticeId below.
    loaded["toronto_public_notices_exact_prior_poc"] = _rows({"matches": notices.get("planning_notices") or []})
    return loaded


def _record_for_link(link: dict[str, Any], source_rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    key = str(link.get("source_key") or "")
    rows = source_rows.get(key) or []
    return find_source_record(key, str(link.get("source_record_id") or ""), rows)


def normalize_source_link(link: dict[str, Any], source_rows: dict[str, list[dict[str, Any]]], resolved_row: dict[str, Any] | None = None) -> dict[str, Any]:
    key = str(link.get("source_key") or "unknown")
    row = resolved_row if resolved_row is not None else _record_for_link(link, source_rows)
    result: dict[str, Any] = {
        "source_key": key,
        "source_record_id": str(link.get("source_record_id") or ""),
        "match_basis": str(link.get("match_basis") or ""),
        "source_address": text(link.get("source_address")),
        "dataset_url": valid_public_url(OFFICIAL_DATASET_URLS.get(key)),
        "dataset_link_label": "Open official dataset",
        "record_url": None,
        "record_link_label": None,
        "record_title": None,
        "record_date": None,
        "record_status": None,
        "record_details": [],
    }

    if key in {"chemtrac_history", "chemtrac_2024"}:
        result.update(record_title=text(row.get("FACILITY_NAME")), record_date=text(row.get("_towersignal_reporting_year") or (2024 if key == "chemtrac_2024" else None)), record_details=details(
            ("Facility ID", row.get("FACILITY_ID")), ("Chemical", row.get("CHEMICAL_NAME")),
            ("Industry", row.get("NAICS_CODE_6_DESC_ENG")), ("Air release", row.get("REL_AIR")),
        ))
    elif key == "apartment_building_evaluation":
        record_url = rentsafe_record_url(row)
        result.update(record_url=record_url, record_link_label="Open official RentSafeTO building report" if record_url else None, record_title=text(row.get("PROPERTY TYPE") or "Apartment building evaluation"), record_date=date_value(row.get("EVALUATION COMPLETED ON")), record_details=details(
            ("Evaluation score", row.get("CURRENT BUILDING EVAL SCORE")), ("Storeys", row.get("CONFIRMED STOREYS")),
            ("Units", row.get("CONFIRMED UNITS")), ("Year built", row.get("YEAR BUILT")),
        ))
    elif key == "development_pipeline":
        result.update(record_title=text(row.get("Application Number")), record_date=date_value(row.get("Date Received")), record_status=text(row.get("Pipeline Status")), record_details=details(
            ("Application type", "Development pipeline"), ("Proposed units", row.get("Proposed Residential Units")),
            ("Description", row.get("Description")),
        ))
    elif key == "affordable_housing_pipeline":
        result.update(record_title=text(row.get("Project ID")), record_status=text(row.get("Status")), record_details=details(
            ("Affordable homes approved", row.get("Affordable Homes Approved")), ("RGI homes approved", row.get("RGI Homes Approved")),
            ("Ward", row.get("Ward Name")),
        ))
    elif key == "renewable_energy_installations":
        result.update(record_title=text(row.get("BUILDING_NAME") or row.get("TYPE_INSTALL")), record_date=text(row.get("YEAR_INSTALL")), record_details=details(
            ("Installation type", row.get("TYPE_INSTALL")), ("Installation size", row.get("SIZE_INSTALL")),
            ("General use", row.get("GENERAL_USE")),
        ))
    elif key == "toronto_highrise_residential_health_hazards":
        result.update(record_title=text(row.get("case_id")), record_date=date_value(row.get("investigation_date")), record_status=text(row.get("status_desc")), record_details=details(
            ("Investigation", row.get("investigation_type")), ("Hazard type", row.get("hazard_type")),
            ("Finding", row.get("violation")), ("Last updated", date_value(row.get("last_updated_date"))),
        ))
    elif key == "toronto_aic_applications":
        record_url = aic_record_url(row)
        result.update(dataset_link_label="Open current AIC application search", record_url=record_url, record_link_label="Open official AIC application details" if record_url else None, record_title=text(row.get("APPLICATION_NUMBER") or row.get("REFERENCEFILE")), record_date=date_value(row.get("SUBMIT_DATE")), record_status=text(row.get("STATUS_DESC") or row.get("STATUS_GROUP")), record_details=details(
            ("Application type", row.get("FOLDERTYPE_DESC") or row.get("APPLICATION_TYPE")),
            ("Latest milestone", row.get("LATEST_MILESTONE")), ("Description", row.get("FOLDERDESCRIPTION")),
        ))
    elif key == "ontario_environmental_compliance_reports":
        result.update(record_title=text(row.get("Site Name")), record_date=date_value(row.get("Exceedance Start Date")), record_status=text(row.get("Ministry Action")), record_details=details(
            ("Facility owner", row.get("Facility Owner")), ("Report year", row.get("_towersignal_source_year")),
            ("Contaminant", row.get("Contaminant")), ("Exceedance type", row.get("Type of Exceedance") or row.get(" Type of Exceedance")),
        ))
    elif key == "ontario_bps_energy_2024":
        result.update(record_title=text(row.get("Property Name") or "Ontario BPS energy report"), record_date=date_value(row.get("Year Ending") or row.get("Report Submission Date")), record_status="Published BPS energy report", record_details=details(
            ("Organization", row.get("Organization")), ("Sector", row.get("Sector")),
            ("Subsector", row.get("Subsector")), ("Property type", row.get("Primary Property Type - Self Selected")),
            ("Reporting year", row.get("Year")),
        ))
    elif key == "business_licence_matches_prior_poc":
        result.update(record_title=text(row.get("Operating Name") or row.get("Client Name")), record_date=date_value(row.get("Issued")), record_status="Cancelled" if text(row.get("Cancel Date")) else "Published licence record", record_details=details(
            ("Licence number", row.get("Licence No.")), ("Category", row.get("Category")),
            ("Client", row.get("Client Name")), ("Cancel date", date_value(row.get("Cancel Date"))),
        ))
    elif key == "311_matches_prior_poc":
        result.update(record_title=text(row.get("Service Request Type")), record_date=date_value(row.get("Creation Date")), record_status=text(row.get("Status")), record_details=details(
            ("Division", row.get("Division")), ("Section", row.get("Section")), ("Ward", row.get("Ward")),
        ))
    elif key == "tobids_awarded_contracts_exact_document_address_prior_poc":
        result.update(record_title=text(row.get("Document Number")), record_date=date_value(row.get("Award Authority Obtained Date")), record_status="Awarded", record_details=details(
            ("Successful supplier", row.get("Successful Supplier")), ("Award", row.get("Award")),
            ("Division", row.get("Division")), ("Scope", row.get("Solicitation Document Description")),
        ))
    elif key in {"toronto_building_permits_active_targeted", "toronto_building_permits_cleared_targeted_since_2017"}:
        permit_num = text(row.get("PERMIT_NUM"), 100)
        revision_num = text(row.get("REVISION_NUM"), 40) or "00"
        record_title = f"{permit_num} · revision {revision_num}" if permit_num else text(row.get("_towersignal_permit_identity"))
        is_cleared = key == "toronto_building_permits_cleared_targeted_since_2017"
        record_date = date_value((row.get("COMPLETED_DATE") if is_cleared else row.get("ISSUED_DATE")) or row.get("ISSUED_DATE") or row.get("APPLICATION_DATE"))
        signals = ", ".join(str(value).replace("_", " ") for value in (row.get("_towersignal_signals") or []))
        lifecycle_reasons = ", ".join(str(value).replace("_", " ") for value in (row.get("_towersignal_cooling_tower_lifecycle_reasons") or []))
        result.update(record_title=record_title, record_date=record_date, record_status=text(row.get("STATUS")), record_details=details(
            ("Source lifecycle", row.get("_towersignal_source_lifecycle")), ("Permit type", row.get("PERMIT_TYPE")),
            ("Structure type", row.get("STRUCTURE_TYPE")), ("Work", row.get("WORK")),
            ("Description", row.get("DESCRIPTION")), ("Estimated construction cost", row.get("EST_CONST_COST")),
            ("Current use", row.get("CURRENT_USE")), ("Proposed use", row.get("PROPOSED_USE")),
            ("Builder name (publisher field)", row.get("BUILDER_NAME")), ("Mechanical signals", signals),
            ("Cooling tower lifecycle", row.get("_towersignal_cooling_tower_lifecycle")),
            ("Cooling tower lifecycle reasons", lifecycle_reasons),
            ("Cooling tower current interpretation", row.get("_towersignal_cooling_tower_current_interpretation")),
        ))
    elif key == "tdsb_facility_condition_renewal":
        record_url = valid_public_url(row.get("school_page_url"))
        signals = ", ".join(str(value).replace("_", " ") for value in (row.get("signals") or []))
        priority = text(row.get("priority"))
        result.update(
            dataset_link_label="Open TDSB facility condition source",
            record_url=record_url,
            record_link_label="Open official TDSB facility condition page" if record_url else None,
            record_title=text(row.get("school_name")),
            record_date=None,
            record_status=f"{priority.title()} priority renewal" if priority else "Published renewal evidence",
            record_details=details(
                ("School number", row.get("school_id")),
                ("Published school address", row.get("published_address")),
                ("Renewal priority", row.get("priority")),
                ("Mechanical signals", signals),
                ("Renewal scope", row.get("renewal_text")),
            ),
        )
    elif key == "toronto_public_notices_exact_prior_poc":
        notice_id = row.get("noticeId")
        result.update(dataset_link_label="Search official public-notices dataset", record_url=None, record_link_label=None, record_title=text(row.get("title")), record_date=date_value(row.get("noticeDate")), record_details=details(
            ("Notice ID", notice_id),
            ("Planning applications", ", ".join(str(value).strip() for value in (row.get("planningApplicationNumbers") or []) if value)),
            ("Topics", ", ".join(str(value).strip() for value in (row.get("topics") or []) if value)),
        ))
    return result
