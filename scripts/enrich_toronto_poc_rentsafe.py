from __future__ import annotations

import argparse
import csv
import json
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CKAN_ACTION = "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/datastore_search"
RESOURCE_ID = "3ad76a8c-0518-4df2-b94e-8c747d62f8c1"
SOURCE_URL = "https://open.toronto.ca/dataset/apartment-building-registration/"
USER_AGENT = "TowerSignal-Toronto-POC/0.1 (+https://github.com/JeremyHennessy/TowerSignal)"
MIN_EXPECTED_ROWS = 2500
MAX_EXPECTED_ROWS = 5000

TOKEN_MAP = {
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
    "LANE": "LANE",
    "TRAIL": "TRL",
    "TRL": "TRL",
    "PLACE": "PL",
    "PL": "PL",
    "HIGHWAY": "HWY",
    "HWY": "HWY",
    "EAST": "E",
    "E": "E",
    "WEST": "W",
    "W": "W",
    "NORTH": "N",
    "N": "N",
    "SOUTH": "S",
    "S": "S",
}


def clean(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def normalize_field_name(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def value_for(record: dict[str, Any], *candidate_names: str) -> Any:
    normalized = {normalize_field_name(str(key)): value for key, value in record.items()}
    for name in candidate_names:
        key = normalize_field_name(name)
        if key in normalized:
            return normalized[key]
    return None


def request_json(url: str, *, timeout: int = 45, retries: int = 3) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json,*/*;q=0.8",
                    "Accept-Language": "en-CA,en;q=0.9",
                },
            )
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict):
                raise RuntimeError("CKAN response was not a JSON object")
            return payload
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed to retrieve {url}: {last_error}")


def fetch_all_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    limit = 1000
    total: int | None = None
    fields: list[str] = []
    while total is None or offset < total:
        params = urlencode({"resource_id": RESOURCE_ID, "limit": limit, "offset": offset})
        payload = request_json(f"{CKAN_ACTION}?{params}")
        if payload.get("success") is not True:
            raise RuntimeError("RentSafeTO CKAN datastore_search returned success != true")
        result = payload.get("result") or {}
        batch = result.get("records") or []
        if not isinstance(batch, list):
            raise RuntimeError("RentSafeTO CKAN records were not a list")
        if total is None:
            total = int(result.get("total") or 0)
            fields = [str(item.get("id")) for item in (result.get("fields") or []) if isinstance(item, dict)]
            if not (MIN_EXPECTED_ROWS <= total <= MAX_EXPECTED_ROWS):
                raise RuntimeError(
                    f"RentSafeTO row count {total} outside fail-closed range "
                    f"{MIN_EXPECTED_ROWS}..{MAX_EXPECTED_ROWS}"
                )
        rows.extend(item for item in batch if isinstance(item, dict))
        offset += len(batch)
        if not batch:
            break
    if len(rows) != total:
        raise RuntimeError(f"RentSafeTO pagination returned {len(rows)} rows, expected {total}")
    return rows, {"row_count": total, "fields": fields}


def strip_city_postal(address: str) -> str:
    value = address.upper().strip()
    # Remove common comma-separated locality/postal suffixes from canonical TDSB addresses.
    value = value.split(",", 1)[0]
    # Defensive removal if locality was provided without a comma.
    value = re.sub(r"\s+(?:TORONTO|ETOBICOKE|NORTH YORK|SCARBOROUGH|EAST YORK|YORK)\s*,?\s*ON\b.*$", "", value)
    value = re.sub(r"\s+[A-Z]\d[A-Z]\s*\d[A-Z]\d\s*$", "", value)
    return value.strip()


def canonical_address(address: Any) -> str | None:
    text = clean(address)
    if not text:
        return None
    text = strip_city_postal(text)
    text = re.sub(r"\b(?:UNIT|SUITE|APT|APARTMENT)\s*#?\s*[A-Z0-9-]+\b.*$", "", text, flags=re.I)
    text = re.sub(r"[^A-Z0-9]+", " ", text.upper()).strip()
    if not text:
        return None
    tokens = [TOKEN_MAP.get(token, token) for token in text.split()]
    return " ".join(tokens)


def safe_int(value: Any) -> int | None:
    text = clean(value)
    if not text:
        return None
    match = re.search(r"-?\d+", text.replace(",", ""))
    return int(match.group(0)) if match else None


def context_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_key": "toronto_apartment_building_registration",
        "source_url": SOURCE_URL,
        "rsn": clean(value_for(row, "RSN")),
        "site_address": clean(value_for(row, "SITE_ADDRESS")),
        "postal_code": clean(value_for(row, "PCODE", "POSTAL_CODE")),
        "property_management_company": clean(value_for(row, "PROP_MANAGEMENT_COMPANY_NAME")),
        "property_type": clean(value_for(row, "PROPERTY_TYPE")),
        "confirmed_storeys": safe_int(value_for(row, "CONFIRMED_STOREYS", "NO_OF_STOREYS")),
        "confirmed_units": safe_int(value_for(row, "CONFIRMED_UNITS", "NO_OF_UNITS")),
        "year_built": safe_int(value_for(row, "YEAR_BUILT")),
        "year_registered": safe_int(value_for(row, "YEAR_REGISTERED")),
        "air_conditioning_type": clean(value_for(row, "AIR_CONDITIONING_TYPE")),
        "heating_type": clean(value_for(row, "HEATING_TYPE")),
        "heating_equipment_status": clean(value_for(row, "HEATING_EQUIPMENT_STATUS")),
        "heating_equipment_year_installed": safe_int(value_for(row, "HEATING_EQUIPMENT_YEAR_INSTALLED")),
        "date_of_last_inspection_by_tssa": clean(value_for(row, "DATE_OF_LAST_INSPECTION_BY_TSSA")),
        "tssa_test_records": clean(value_for(row, "TSSA_TEST_RECORDS")),
        # Cooling-room data is property context only. It is not evidence of a cooling tower.
        "cooling_room": clean(value_for(row, "IS_THERE_A_COOLING_ROOM", "IS_THERE_A_COOLING_ROOM?")),
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            serialized = dict(row)
            for key, value in list(serialized.items()):
                if isinstance(value, (list, dict)):
                    serialized[key] = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
            writer.writerow(serialized)


def enrich(output_dir: Path) -> dict[str, Any]:
    properties_path = output_dir / "properties.json"
    evidence_path = output_dir / "evidence.json"
    summary_path = output_dir / "summary.json"
    properties_payload = json.loads(properties_path.read_text(encoding="utf-8"))
    evidence_payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    properties = properties_payload.get("properties") or []

    rows, source_meta = fetch_all_rows()
    by_address: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_rows_without_address = 0
    for row in rows:
        source_address = canonical_address(value_for(row, "SITE_ADDRESS"))
        if not source_address:
            source_rows_without_address += 1
            continue
        by_address[source_address].append(row)

    ambiguous_source_addresses = {address for address, matched in by_address.items() if len(matched) > 1}
    matched_properties = 0
    matched_confirmed_towers = 0
    unmatched_properties = 0
    ambiguous_property_matches = 0
    matches_by_property_key: dict[str, str] = {}

    for property_item in properties:
        address = canonical_address(property_item.get("address"))
        if not address:
            unmatched_properties += 1
            continue
        candidates = by_address.get(address) or []
        if not candidates:
            unmatched_properties += 1
            continue
        if len(candidates) != 1:
            ambiguous_property_matches += 1
            continue
        row = candidates[0]
        context = context_from_row(row)
        context["match_basis"] = "EXACT_CANONICAL_MUNICIPAL_ADDRESS"
        context["canonical_address"] = address
        property_item["rentsafe"] = context
        matches_by_property_key[property_item["property_key"]] = str(context.get("rsn") or "")
        matched_properties += 1
        if property_item.get("tower_status") == "CONFIRMED":
            matched_confirmed_towers += 1

    source_fields = source_meta.get("fields") or []
    required_fields = {"SITE_ADDRESS", "RSN", "PROP_MANAGEMENT_COMPANY_NAME", "CONFIRMED_STOREYS", "CONFIRMED_UNITS"}
    normalized_source_fields = {str(field).upper() for field in source_fields}
    missing_required = sorted(required_fields - normalized_source_fields)
    if missing_required:
        raise RuntimeError(f"RentSafeTO source missing required fields: {missing_required}")

    summary.setdefault("sources", {})["rentsafe_registration"] = {
        "resource_id": RESOURCE_ID,
        "source_url": SOURCE_URL,
        "row_count": source_meta["row_count"],
        "field_count": len(source_fields),
        "fields": source_fields,
        "source_rows_without_address": source_rows_without_address,
        "ambiguous_canonical_source_addresses": len(ambiguous_source_addresses),
        "join_contract": {
            "match_basis": "EXACT_CANONICAL_MUNICIPAL_ADDRESS",
            "fuzzy_matching": False,
            "ambiguous_matches": "SKIPPED",
            "tower_semantics": "RentSafeTO never creates or upgrades cooling-tower status.",
            "cooling_room_semantics": "RentSafeTO cooling-room fields are retained only as building context and are not cooling-tower evidence.",
        },
        "matched_poc_properties": matched_properties,
        "matched_confirmed_cooling_tower_properties": matched_confirmed_towers,
        "unmatched_poc_properties": unmatched_properties,
        "ambiguous_poc_property_matches_skipped": ambiguous_property_matches,
    }
    summary.setdefault("counts", {})["properties_with_rentsafe_context"] = matched_properties
    summary["counts"]["confirmed_cooling_tower_properties_with_rentsafe_context"] = matched_confirmed_towers

    properties_payload["metadata"] = summary
    evidence_payload["metadata"] = summary
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    properties_path.write_text(json.dumps(properties_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    evidence_path.write_text(json.dumps(evidence_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    write_csv(
        output_dir / "properties.csv",
        properties,
        [
            "property_key",
            "tower_status",
            "address",
            "property_name",
            "organization",
            "geo_id",
            "equipment_types",
            "commercial_signals",
            "renewal_priorities",
            "latest_source_event_date",
            "source_active_permit_record",
            "recent_source_active_permit_activity_365d",
            "latest_recent_permit_activity_date",
            "rentsafe",
            "source_keys",
            "evidence_count",
        ],
    )

    (output_dir / "rentsafe_matches.json").write_text(
        json.dumps(
            {
                "metadata": summary["sources"]["rentsafe_registration"],
                "matches_by_property_key": matches_by_property_key,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "rentsafe_rows": source_meta["row_count"],
                "matched_poc_properties": matched_properties,
                "matched_confirmed_cooling_tower_properties": matched_confirmed_towers,
                "ambiguous_matches_skipped": ambiguous_property_matches,
            },
            indent=2,
        )
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Join RentSafeTO building context to Toronto POC properties")
    parser.add_argument("--output", type=Path, default=ROOT / "data/toronto/poc/current")
    args = parser.parse_args()
    enrich(args.output)


if __name__ == "__main__":
    main()
