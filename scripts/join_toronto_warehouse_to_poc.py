from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

STREET_SUFFIXES = {
    "STREET": "ST",
    "ST": "ST",
    "AVENUE": "AVE",
    "AVE": "AVE",
    "ROAD": "RD",
    "RD": "RD",
    "BOULEVARD": "BLVD",
    "BLVD": "BLVD",
    "DRIVE": "DR",
    "DR": "DR",
    "COURT": "CT",
    "CT": "CT",
    "CRESCENT": "CRES",
    "CRES": "CRES",
    "PARKWAY": "PKWY",
    "PKWY": "PKWY",
    "TRAIL": "TRL",
    "TRL": "TRL",
    "PLACE": "PL",
    "PL": "PL",
    "TERRACE": "TER",
    "TER": "TER",
    "HIGHWAY": "HWY",
    "HWY": "HWY",
}
DIRECTIONS = {
    "EAST": "E",
    "WEST": "W",
    "NORTH": "N",
    "SOUTH": "S",
    "E": "E",
    "W": "W",
    "N": "N",
    "S": "S",
}


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def write_json(path: Path, payload: Any, *, pretty: bool = False) -> None:
    path.write_text(
        json.dumps(
            payload,
            indent=2 if pretty else None,
            separators=None if pretty else (",", ":"),
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )


def canonical_address(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).upper()
    text = re.sub(r"\b[A-Z]\d[A-Z]\s*\d[A-Z]\d\b.*$", "", text)
    text = text.split(",", 1)[0]
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    tokens = []
    for token in text.split():
        token = STREET_SUFFIXES.get(token, DIRECTIONS.get(token, token))
        tokens.append(token)
    return " ".join(tokens).strip() or None


def normalized_document_text(record: dict[str, Any]) -> str:
    text = " | ".join(str(value) for value in record.values() if value not in (None, ""))
    text = text.upper()
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    tokens = [STREET_SUFFIXES.get(token, DIRECTIONS.get(token, token)) for token in text.split()]
    return " ".join(tokens)


def source_payload(warehouse_dir: Path, key: str) -> dict[str, Any]:
    path = warehouse_dir / "open_licensed" / f"{key}.json"
    if not path.exists():
        raise RuntimeError(f"Required Toronto warehouse source missing: {path}")
    return read_json(path)


def rows_for(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("rows", "toronto_candidates"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def compact_development(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "pipeline_status": row.get("Pipeline Status"),
        "application_number": row.get("Application Number"),
        "date_received": row.get("Date Received"),
        "description": row.get("Description"),
        "address": row.get("Address"),
        "proposed_gfa": row.get("Proposed Gross Floor Area"),
        "proposed_residential_units": row.get("Proposed Residential Units"),
        "aic_link": row.get("Application Information Centre Link"),
    }


def compact_evaluation(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "rsn": row.get("RSN"),
        "year_evaluated": row.get("YEAR EVALUATED"),
        "evaluation_completed_on": row.get("EVALUATION COMPLETED ON"),
        "current_building_eval_score": row.get("CURRENT BUILDING EVAL SCORE"),
        "proactive_building_score": row.get("PROACTIVE BUILDING SCORE"),
        "current_reactive_score": row.get("CURRENT REACTIVE SCORE"),
        "common_area_ventilation": row.get("COMMON AREA VENTILATION"),
        "electrical_services_outlets": row.get("ELECTRICAL SERVICES / OUTLETS"),
        "site_address": row.get("SITE ADDRESS"),
    }


def compact_bps(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "sector": row.get("Sector"),
        "subsector": row.get("Subsector"),
        "organization": row.get("Organization"),
        "property_name": row.get("Property Name"),
        "property_type": row.get("Primary Property Type - Self Selected"),
        "address": row.get("Address"),
        "city": row.get("City"),
        "postal_code": row.get("Postal Code"),
        "gfa_m2": row.get("Property GFA - Self-Reported (m²)"),
        "number_of_buildings": row.get("Number of Buildings"),
        "district_chilled_water_gj": row.get("District Chilled Water Use (GJ)"),
        "site_energy_gj": row.get("Site Energy Use (GJ)"),
        "ghg_tonnes": row.get("Total (Location-Based) GHG Emissions (Metric Tons CO2e)"),
    }


def compact_chemtrac(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "facility_id": row.get("FACILITY_ID"),
        "facility_name": row.get("FACILITY_NAME"),
        "address": row.get("FA_ADDRESS_GIVEN"),
        "postal_code": row.get("FA_POSTAL_CODE"),
        "latitude": row.get("FA_LAT"),
        "longitude": row.get("FA_LON"),
        "naics_code": row.get("NAICS_CODE_6"),
        "naics_description": row.get("NAICS_CODE_6_DESC_ENG"),
        "employee_count": row.get("EMPLOYEE_COUNT"),
        "website": row.get("WEB_SITE"),
        "contact_name": row.get("PC_FULL_NAME"),
        "contact_title": row.get("PC_JOB_TITLE"),
        "contact_phone": row.get("PC_PHONE_NO"),
        "chemical_name": row.get("CHEMICAL_NAME"),
    }


def compact_affordable(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "project_id": row.get("Project ID"),
        "addresses": row.get("Addresses"),
        "anchor_address": row.get("Anchor Address"),
        "status": row.get("Status"),
        "ward_number": row.get("Ward Number"),
        "ward_name": row.get("Ward Name"),
        "affordable_homes_approved": row.get("Affordable Homes Approved"),
        "rent_controlled_market_units_approved": row.get("Rent-Controlled Market Units Approved"),
        "rgi_homes_approved": row.get("RGI Homes Approved"),
    }


def compact_tobids(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "document_number": row.get("Document Number"),
        "rfx_type": row.get("RFx (Solicitation) Type"),
        "category": row.get("High Level Category"),
        "successful_supplier": row.get("Successful Supplier"),
        "award": row.get("Award"),
        "award_date": row.get("Award Authority Obtained Date"),
        "division": row.get("Division"),
        "buyer_name": row.get("Buyer Name"),
        "buyer_email": row.get("Buyer Email"),
        "buyer_phone": row.get("Buyer Phone Number"),
        "description": row.get("Solicitation Document Description"),
        "wards": row.get("Wards"),
        "match_basis": "EXACT_CANONICAL_PROPERTY_ADDRESS_TOKEN_IN_DOCUMENT_TEXT",
    }


def compact_capital(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "number": row.get("No."),
        "name_contract_number": row.get("Name and Construction Contract Number"),
        "type_of_work": row.get("Type of Work"),
        "scope": row.get("Scope of Work: Detailed Description"),
        "delivery_division": row.get("Delivery Division"),
        "project_owner": row.get("Project Owner (Division)"),
        "target_sourcing_year": row.get("Target Sourcing Year"),
        "target_award_year": row.get("Target Award Year"),
        "sourcing_type": row.get("Sourcing Type"),
        "estimated_range": row.get("Estimated Range"),
        "estimated_contract_term_months": row.get("Estimated Contract Term (Months)"),
        "match_basis": "EXACT_CANONICAL_PROPERTY_ADDRESS_TOKEN_IN_DOCUMENT_TEXT",
    }


def build_address_index(rows: list[dict[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        address = canonical_address(row.get(field))
        if address:
            index[address].append(row)
    return index


def text_matches(rows: list[dict[str, Any]], address: str) -> list[dict[str, Any]]:
    needle = f" {address} "
    matches = []
    for row in rows:
        haystack = f" {normalized_document_text(row)} "
        if needle in haystack:
            matches.append(row)
    return matches


def build(poc_dir: Path, warehouse_dir: Path) -> dict[str, Any]:
    properties_payload = read_json(poc_dir / "properties.json")
    properties = properties_payload.get("properties") or []
    if not isinstance(properties, list):
        raise RuntimeError("Toronto POC properties are not a list")

    development = rows_for(source_payload(warehouse_dir, "development_pipeline"))
    evaluations = rows_for(source_payload(warehouse_dir, "apartment_building_evaluation"))
    bps = rows_for(source_payload(warehouse_dir, "ontario_bps_energy_2024"))
    chemtrac = rows_for(source_payload(warehouse_dir, "chemtrac_2024"))
    affordable = rows_for(source_payload(warehouse_dir, "affordable_housing_pipeline"))
    tobids = rows_for(source_payload(warehouse_dir, "tobids_awarded_contracts"))
    capital = rows_for(source_payload(warehouse_dir, "capital_project_pipeline"))

    indexes = {
        "development_pipeline": build_address_index(development, "Address"),
        "apartment_building_evaluation": build_address_index(evaluations, "SITE ADDRESS"),
        "ontario_bps_energy_2024": build_address_index(bps, "Address"),
        "chemtrac_2024": build_address_index(chemtrac, "FA_ADDRESS_GIVEN"),
        "affordable_housing_pipeline": build_address_index(affordable, "Anchor Address"),
    }

    joins = []
    counts = defaultdict(int)
    confirmed_counts = defaultdict(int)

    for property_item in properties:
        if not isinstance(property_item, dict):
            continue
        address = canonical_address(property_item.get("address"))
        if not address:
            continue
        match_sets = {
            "development_pipeline": [
                compact_development(row) for row in indexes["development_pipeline"].get(address, [])
            ],
            "apartment_building_evaluation": [
                compact_evaluation(row) for row in indexes["apartment_building_evaluation"].get(address, [])
            ],
            "ontario_bps_energy_2024": [
                compact_bps(row) for row in indexes["ontario_bps_energy_2024"].get(address, [])
            ],
            "chemtrac_2024": [
                compact_chemtrac(row) for row in indexes["chemtrac_2024"].get(address, [])
            ],
            "affordable_housing_pipeline": [
                compact_affordable(row) for row in indexes["affordable_housing_pipeline"].get(address, [])
            ],
            "tobids_awarded_contracts": [
                compact_tobids(row) for row in text_matches(tobids, address)
            ],
            "capital_project_pipeline": [
                compact_capital(row) for row in text_matches(capital, address)
            ],
        }
        matched_keys = [key for key, value in match_sets.items() if value]
        if not matched_keys:
            continue
        for key in matched_keys:
            counts[key] += 1
            if property_item.get("tower_status") == "CONFIRMED":
                confirmed_counts[key] += 1
        joins.append(
            {
                "property_key": property_item.get("property_key"),
                "tower_status": property_item.get("tower_status"),
                "address": property_item.get("address"),
                "canonical_address": address,
                "property_name": property_item.get("property_name"),
                "organization": property_item.get("organization"),
                "commercial_disposition": property_item.get("commercial_disposition"),
                "matched_source_keys": matched_keys,
                "matches": match_sets,
            }
        )

    joins.sort(
        key=lambda item: (
            0 if item.get("tower_status") == "CONFIRMED" else 1,
            -len(item.get("matched_source_keys") or []),
            str(item.get("canonical_address") or ""),
        )
    )
    confirmed_joined = [item for item in joins if item.get("tower_status") == "CONFIRMED"]
    payload = {
        "metadata": {
            "schema_version": "toronto-warehouse-join-0.1",
            "jurisdiction": "TORONTO_ON",
            "join_contract": {
                "structured_sources": "Exact canonical municipal street-address equality only.",
                "document_sources": "Exact canonical full property-address token sequence in normalized document text only.",
                "fuzzy_matching": False,
                "no_match_semantics": "No exact match does not mean the source lacks relevant records; it means this deterministic join did not establish identity.",
                "tower_semantics": "Warehouse context never creates or upgrades cooling-tower confirmation.",
            },
            "poc_property_count": len(properties),
            "joined_property_count": len(joins),
            "confirmed_tower_joined_property_count": len(confirmed_joined),
            "properties_with_matches_by_source": dict(sorted(counts.items())),
            "confirmed_tower_properties_with_matches_by_source": dict(sorted(confirmed_counts.items())),
        },
        "properties": joins,
    }
    write_json(warehouse_dir / "property_joins.json", payload)
    write_json(warehouse_dir / "join_summary.json", payload["metadata"], pretty=True)
    print(json.dumps(payload["metadata"], indent=2))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Join open Toronto warehouse context to TowerSignal Toronto POC properties")
    parser.add_argument("--poc", type=Path, default=ROOT / "data/toronto/poc/current")
    parser.add_argument("--warehouse", type=Path, default=ROOT / "data/toronto/warehouse/current")
    args = parser.parse_args()
    build(args.poc, args.warehouse)


if __name__ == "__main__":
    main()
