from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SCHEMA_VERSION = "1.0"
NYC_API_ROOT = "https://data.cityofnewyork.us"
NYS_API_ROOT = "https://data.ny.gov"
USER_AGENT = "TowerSignal/1.0 (+https://github.com/JeremyHennessy/TowerSignal)"

TANK_INSPECTION_DATASET_ID = "gjm4-k24g"
TANK_COMPLIANCE_DATASET_ID = "rytv-g5ui"
DEC_BUSINESS_DATASET_ID = "h8u2-6ejg"
DEC_APPLICATOR_DATASET_ID = "c7db-kwpj"
FREE_LEAD_COPPER_DATASET_ID = "k5us-nav4"
COMPLIANCE_LEAD_COPPER_DATASET_ID = "3wxk-qa8q"

LEGAL_SUFFIXES = {
    "CORP",
    "CORPORATION",
    "INC",
    "INCORPORATED",
    "LLC",
    "LTD",
    "LIMITED",
    "LP",
    "LLP",
    "CO",
    "COMPANY",
    "PC",
    "PLLC",
}

BOROUGH_CODES = {
    "MANHATTAN": "1",
    "NEW YORK": "1",
    "BRONX": "2",
    "BROOKLYN": "3",
    "QUEENS": "4",
    "STATEN ISLAND": "5",
}


class DomesticWaterSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceSnapshot:
    dataset_id: str
    name: str
    api_root: str
    rows: list[dict[str, Any]]
    retrieved_at: str
    source_record_count: int
    source_last_updated_at: str | None
    source_query_scope: str
    fields: tuple[str, ...]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_space(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def stable_id(prefix: str, *parts: Any) -> str:
    material = "|".join(normalize_space(part) for part in parts)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}-{digest}"


def normalize_company_key(value: Any) -> str:
    text = normalize_space(value).upper().replace("&", " AND ")
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    tokens = [token for token in text.split() if token]
    while tokens and tokens[-1] in LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def looks_like_entity_name(value: Any) -> bool:
    text = normalize_company_key(value)
    return bool(text and len(re.findall(r"[A-Z]", text)) >= 2)


def parse_source_date(value: Any) -> str | None:
    text = normalize_space(value)
    if not text:
        return None
    for candidate in (text, text[:10]):
        try:
            return datetime.fromisoformat(candidate.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            pass
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y%m%d", "%Y-%m-%d", "%b %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def normalize_bbl(borough: Any, block: Any, lot: Any) -> str | None:
    borough_text = normalize_space(borough).upper()
    borough_code = BOROUGH_CODES.get(borough_text)
    block_digits = re.sub(r"\D", "", normalize_space(block))
    lot_digits = re.sub(r"\D", "", normalize_space(lot))
    if not borough_code or not block_digits or not lot_digits:
        return None
    try:
        block_number = int(block_digits)
        lot_number = int(lot_digits)
    except ValueError:
        return None
    if not (1 <= block_number <= 99999 and 1 <= lot_number <= 9999):
        return None
    return f"{borough_code}{block_number:05d}{lot_number:04d}"


def building_key(row: Mapping[str, Any]) -> tuple[str, str | None]:
    bin_value = normalize_space(row.get("bin"))
    bbl_value = normalize_bbl(row.get("borough"), row.get("block"), row.get("lot"))
    if bin_value:
        return f"NYC-BIN-{bin_value}", bbl_value
    if bbl_value:
        return f"NYC-BBL-{bbl_value}", bbl_value
    address = normalize_space(
        " ".join(
            value
            for value in (
                normalize_space(row.get("house_num") or row.get("house")),
                normalize_space(row.get("street_name")),
                normalize_space(row.get("borough")),
                normalize_space(row.get("zip") or row.get("zip_code")),
            )
            if value
        )
    ).upper()
    return (f"NYC-ADDRESS-{stable_id('address', address).split('-', 1)[1]}" if address else stable_id("building", json.dumps(dict(row), sort_keys=True))), bbl_value


def _request_json(url: str, *, retries: int = 4, timeout: int = 90) -> Any:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(2**attempt)
    raise DomesticWaterSourceError(f"Failed to retrieve authoritative source after {retries} attempts: {url}: {last_error}")


def _iso_from_epoch(value: Any) -> str | None:
    try:
        epoch = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_metadata(dataset_id: str, *, api_root: str) -> dict[str, Any]:
    payload = _request_json(f"{api_root}/api/views/{dataset_id}")
    if not isinstance(payload, dict):
        raise DomesticWaterSourceError(f"Metadata for {dataset_id} returned a non-object payload")
    fields = tuple(
        str(column.get("fieldName"))
        for column in payload.get("columns", [])
        if isinstance(column, dict) and column.get("fieldName")
    )
    return {
        "name": normalize_space(payload.get("name")) or dataset_id,
        "source_last_updated_at": _iso_from_epoch(payload.get("rowsUpdatedAt") or payload.get("dataUpdatedAt")),
        "fields": fields,
    }


def _query(dataset_id: str, *, api_root: str, params: Mapping[str, Any]) -> Any:
    return _request_json(f"{api_root}/resource/{dataset_id}.json?{urlencode(params)}")


def fetch_count(dataset_id: str, *, api_root: str, where: str | None = None) -> int:
    params: dict[str, Any] = {"$select": "count(*) as count"}
    if where:
        params["$where"] = where
    payload = _query(dataset_id, api_root=api_root, params=params)
    if not isinstance(payload, list) or not payload or "count" not in payload[0]:
        raise DomesticWaterSourceError(f"Count query for {dataset_id} returned an unexpected payload")
    return int(payload[0]["count"])


def fetch_snapshot(
    dataset_id: str,
    *,
    api_root: str,
    order_by: str,
    required_fields: Sequence[str],
    where: str | None = None,
    select: str | None = None,
    page_size: int = 50000,
    minimum_page_size: int = 1000,
    allow_count_fallback: bool = False,
    max_pages_without_count: int = 10000,
) -> SourceSnapshot:
    metadata = fetch_metadata(dataset_id, api_root=api_root)
    available = set(metadata["fields"])
    missing = [field for field in required_fields if field not in available]
    if missing:
        raise DomesticWaterSourceError(f"Dataset {dataset_id} is missing required fields: {', '.join(missing)}")

    try:
        expected_count: int | None = fetch_count(dataset_id, api_root=api_root, where=where)
    except DomesticWaterSourceError:
        if not allow_count_fallback:
            raise
        expected_count = None
    rows: list[dict[str, Any]] = []
    offset = 0
    active_page_size = page_size
    pages_without_count = 0
    while expected_count is None or offset < expected_count:
        params: dict[str, Any] = {"$limit": active_page_size, "$offset": offset, "$order": order_by}
        if where:
            params["$where"] = where
        if select:
            params["$select"] = select
        try:
            page = _query(dataset_id, api_root=api_root, params=params)
        except DomesticWaterSourceError:
            if active_page_size <= minimum_page_size:
                raise
            active_page_size = max(minimum_page_size, active_page_size // 2)
            continue
        if not isinstance(page, list):
            raise DomesticWaterSourceError(f"Dataset {dataset_id} returned a non-list page at offset {offset}")
        rows.extend(row for row in page if isinstance(row, dict))
        if len(page) < active_page_size:
            break
        offset += active_page_size
        if expected_count is None:
            pages_without_count += 1
            if pages_without_count >= max_pages_without_count:
                raise DomesticWaterSourceError(
                    f"Dataset {dataset_id} exceeded {max_pages_without_count:,} pages without a source count. Refusing unbounded crawl."
                )

    source_record_count = expected_count if expected_count is not None else len(rows)
    if expected_count is not None and len(rows) != expected_count:
        raise DomesticWaterSourceError(
            f"Dataset {dataset_id} pagination incomplete: expected {expected_count:,} rows, fetched {len(rows):,}. Refusing partial snapshot."
        )

    scope = where or "ALL_ROWS"
    return SourceSnapshot(
        dataset_id=dataset_id,
        name=str(metadata["name"]),
        api_root=api_root,
        rows=rows,
        retrieved_at=utc_now(),
        source_record_count=source_record_count,
        source_last_updated_at=metadata.get("source_last_updated_at"),
        source_query_scope=scope,
        fields=tuple(metadata["fields"]),
    )


def normalize_tank_inspection(row: Mapping[str, Any]) -> dict[str, Any]:
    key, bbl = building_key(row)
    provider_raw = normalize_space(row.get("inspection_by_firm")) or None
    lab_raw = normalize_space(row.get("lab_name")) or None
    provider_key = normalize_company_key(provider_raw) if provider_raw and looks_like_entity_name(provider_raw) else None
    lab_key = normalize_company_key(lab_raw) if lab_raw and looks_like_entity_name(lab_raw) else None
    inspection_date = parse_source_date(row.get("inspection_date"))
    reporting_year = normalize_space(row.get("reporting_year")) or None
    tank_num = normalize_space(row.get("tank_num")) or None
    address = normalize_space(f"{normalize_space(row.get('house_num'))} {normalize_space(row.get('street_name'))}") or None
    inspection_id = stable_id(
        "dwt-inspection",
        row.get("bin"),
        bbl,
        reporting_year,
        tank_num,
        row.get("inspection_date"),
        provider_raw,
        lab_raw,
    )
    findings = {
        str(field): value
        for field, value in row.items()
        if value not in (None, "")
        and (
            str(field).startswith("gi_")
            or str(field).startswith("si_")
            or str(field) in {"analytes", "coliform", "ecoli", "nys_certified"}
            or "sample" in str(field).lower()
            or "clean" in str(field).lower()
            or "disinfect" in str(field).lower()
        )
    }
    return {
        "inspection_id": inspection_id,
        "building_key": key,
        "bin": normalize_space(row.get("bin")) or None,
        "bbl": bbl,
        "borough": normalize_space(row.get("borough")) or None,
        "zip": normalize_space(row.get("zip")) or None,
        "address": address,
        "reporting_year": reporting_year,
        "tank_num": tank_num,
        "inspection_date": inspection_date,
        "provider_raw": provider_raw,
        "provider_key": provider_key,
        "provider_id": stable_id("provider", provider_key) if provider_key else None,
        "provider_source_field": "inspection_by_firm" if provider_raw else None,
        "provider_data_quality": "VALID_NAME" if provider_key else ("INVALID_OR_PLACEHOLDER" if provider_raw else "MISSING"),
        "provider_relationship_evidence": "OBSERVED_SERVICE" if provider_raw else None,
        "provider_asset_link_confidence": "CONFIRMED_ASSET" if provider_raw else None,
        "inspection_performed_flag": normalize_space(row.get("inspection_performed")) or None,
        "lab_raw": lab_raw,
        "lab_key": lab_key,
        "lab_id": stable_id("laboratory", lab_key) if lab_key else None,
        "laboratory_relationship_evidence": "OBSERVED_SERVICE" if lab_key else None,
        "laboratory_data_quality": "VALID_NAME" if lab_key else ("INVALID_OR_PLACEHOLDER" if lab_raw else "MISSING"),
        "findings": findings,
        "raw": dict(row),
    }


def normalize_compliance_activity(row: Mapping[str, Any]) -> dict[str, Any]:
    adapted = dict(row)
    if "house_num" not in adapted and row.get("house") not in (None, ""):
        adapted["house_num"] = row.get("house")
    if "zip" not in adapted and row.get("zip_code") not in (None, ""):
        adapted["zip"] = row.get("zip_code")
    key, _ = building_key(adapted)
    violation_code = normalize_space(row.get("violation_code")) or None
    violation_text = normalize_space(row.get("violation_text")) or None
    activity_date = parse_source_date(row.get("date_of_occurrence"))
    return {
        "activity_id": stable_id(
            "dwt-activity",
            row.get("bin"),
            row.get("activity_type"),
            row.get("activity_year"),
            row.get("compliance_year"),
            row.get("summons_number"),
            row.get("date_of_occurrence"),
            violation_code,
        ),
        "building_key": key,
        "bin": normalize_space(row.get("bin")) or None,
        "address": normalize_space(f"{normalize_space(row.get('house'))} {normalize_space(row.get('street_name'))}") or None,
        "borough": normalize_space(row.get("borough")) or None,
        "zip": normalize_space(row.get("zip_code")) or None,
        "status": normalize_space(row.get("status")) or None,
        "number_of_dwt": row.get("number_of_dwt"),
        "activity_type": normalize_space(row.get("activity_type")) or None,
        "activity_year": normalize_space(row.get("activity_year")) or None,
        "compliance_year": normalize_space(row.get("compliance_year")) or None,
        "violation_code": violation_code,
        "law_section": normalize_space(row.get("law_section")) or None,
        "violation_text": violation_text,
        "date_of_occurrence": activity_date,
        "summons_number": normalize_space(row.get("summons_number")) or None,
        "is_violation": bool(violation_code or violation_text or normalize_space(row.get("summons_number"))),
        "raw": dict(row),
    }


def normalize_dec_business(row: Mapping[str, Any]) -> dict[str, Any]:
    name = normalize_space(row.get("business_agency_name"))
    registration_number = normalize_space(row.get("registration_number"))
    return {
        "qualification_id": stable_id("dec-7g-business", registration_number, name),
        "provider_key": normalize_company_key(name),
        "provider_name": name or None,
        "registration_number": registration_number or None,
        "city": normalize_space(row.get("city")) or None,
        "state": normalize_space(row.get("state")) or None,
        "zip": normalize_space(row.get("zip_code")) or None,
        "dec_region": normalize_space(row.get("dec_region")) or None,
        "registration_effective_date": parse_source_date(row.get("registration_effective_date")),
        "registration_expiration_date": parse_source_date(row.get("registration_expiration_date")),
        "category": normalize_space(row.get("pesticide_category_code")) or None,
        "category_description": normalize_space(row.get("pesticide_category_desc")) or None,
        "relationship_evidence": "QUALIFIED_PROVIDER",
        "qualification_scope": "NYS DEC Category 7G Cooling Towers",
        "raw": dict(row),
    }


def normalize_dec_applicator(row: Mapping[str, Any]) -> dict[str, Any]:
    cert_number = normalize_space(row.get("cert_number"))
    first = normalize_space(row.get("first_name"))
    middle = normalize_space(row.get("middle_initial") or row.get("middle_name"))
    last = normalize_space(row.get("last_name"))
    suffix = normalize_space(row.get("suffix"))
    name = normalize_space(" ".join(value for value in (first, middle, last, suffix) if value))
    return {
        "qualification_id": stable_id("dec-7g-applicator", cert_number, name),
        "cert_number": cert_number or None,
        "name": name or None,
        "dec_region": normalize_space(row.get("dec_region")) or None,
        "renewal_date": parse_source_date(row.get("renewal_date")),
        "expiration_date": parse_source_date(row.get("expiration_date")),
        "applicator_type": normalize_space(row.get("applicator_type")) or None,
        "category": normalize_space(row.get("category")) or None,
        "category_description": normalize_space(row.get("category_description")) or None,
        "relationship_evidence": "QUALIFIED_PROVIDER",
        "qualification_scope": "NYS DEC Category 7G Cooling Towers",
        "raw": dict(row),
    }


def normalize_free_lead_copper_sample(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "sample_id": stable_id("free-lead-copper", row.get("kit_id"), row.get("date_collected")),
        "kit_id": normalize_space(row.get("kit_id")) or None,
        "borough": normalize_space(row.get("borough")) or None,
        "zip": normalize_space(row.get("zipcode")) or None,
        "date_collected": parse_source_date(row.get("date_collected")),
        "date_received": parse_source_date(row.get("date_received")),
        "lead_first_draw_mg_l": row.get("lead_first_draw_mg_l"),
        "lead_1_2_minute_flush_mg_l": row.get("lead_1_2_minute_flush_mg_l"),
        "lead_5_minute_flush_mg_l": row.get("lead_5_minute_flush_mg_l"),
        "copper_first_draw_mg_l": row.get("copper_first_draw_mg_l"),
        "copper_1_2_minute_flush_mg_l": row.get("copper_1_2_minute_flush_mg_l"),
        "copper_5_minute_flush_mg_l": row.get("copper_5_minute_flush_mg_l"),
        "geographic_resolution": "ZIP_BOROUGH_ONLY",
        "property_link_confidence": "UNLINKED",
        "raw": dict(row),
    }


def normalize_compliance_lead_copper_sample(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "sample_id": stable_id("compliance-lead-copper", row.get("kit_id_number"), row.get("date_collected")),
        "kit_id": normalize_space(row.get("kit_id_number")) or None,
        "borough": normalize_space(row.get("borough")) or None,
        "zip": normalize_space(row.get("zipcode")) or None,
        "date_collected": parse_source_date(row.get("date_collected")),
        "date_received": parse_source_date(row.get("received_date")),
        "lead_first_draw_ug_l": row.get("first_draw_at_the_tap_lead"),
        "copper_first_draw_mg_l": row.get("first_draw_at_the_tap_copper"),
        "geographic_resolution": "ZIP_BOROUGH_ONLY",
        "property_link_confidence": "UNLINKED",
        "raw": dict(row),
    }


def _provider_profiles(inspections: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for row in inspections:
        provider_id = row.get("provider_id")
        provider_key = row.get("provider_key")
        provider_raw = row.get("provider_raw")
        if not provider_id or not provider_key or not provider_raw:
            continue
        profile = profiles.setdefault(
            str(provider_id),
            {
                "provider_id": provider_id,
                "provider_key": provider_key,
                "aliases": Counter(),
                "inspection_count": 0,
                "building_keys": set(),
                "tank_keys": set(),
                "reporting_years": set(),
                "first_observed_date": None,
                "latest_observed_date": None,
                "relationship_basis": "OBSERVED_SERVICE",
                "market_share_semantics": "Observed inspection relationships only; not total company revenue or total customer book.",
            },
        )
        profile["aliases"][str(provider_raw)] += 1
        profile["inspection_count"] += 1
        profile["building_keys"].add(str(row.get("building_key")))
        tank_num = normalize_space(row.get("tank_num")) or "UNKNOWN"
        profile["tank_keys"].add(f"{row.get('building_key')}|{tank_num}")
        if row.get("reporting_year"):
            profile["reporting_years"].add(str(row["reporting_year"]))
        observed = row.get("inspection_date")
        if observed:
            if not profile["first_observed_date"] or observed < profile["first_observed_date"]:
                profile["first_observed_date"] = observed
            if not profile["latest_observed_date"] or observed > profile["latest_observed_date"]:
                profile["latest_observed_date"] = observed

    result: list[dict[str, Any]] = []
    for profile in profiles.values():
        aliases: Counter[str] = profile.pop("aliases")
        building_keys: set[str] = profile.pop("building_keys")
        tank_keys: set[str] = profile.pop("tank_keys")
        reporting_years: set[str] = profile.pop("reporting_years")
        profile["aliases"] = [
            {"name": alias, "inspection_count": count}
            for alias, count in aliases.most_common()
        ]
        profile["observed_building_count"] = len(building_keys)
        profile["observed_tank_count"] = len(tank_keys)
        profile["reporting_years"] = sorted(reporting_years)
        result.append(profile)
    return sorted(result, key=lambda item: (-int(item["observed_building_count"]), str(item["provider_key"])))


def _laboratory_profiles(inspections: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for row in inspections:
        lab_id = row.get("lab_id")
        lab_key = row.get("lab_key")
        lab_raw = row.get("lab_raw")
        if not lab_id or not lab_key or not lab_raw:
            continue
        profile = profiles.setdefault(
            str(lab_id),
            {"lab_id": lab_id, "lab_key": lab_key, "aliases": Counter(), "inspection_count": 0, "building_keys": set()},
        )
        profile["aliases"][str(lab_raw)] += 1
        profile["inspection_count"] += 1
        profile["building_keys"].add(str(row.get("building_key")))

    result: list[dict[str, Any]] = []
    for profile in profiles.values():
        aliases: Counter[str] = profile.pop("aliases")
        building_keys: set[str] = profile.pop("building_keys")
        profile["aliases"] = [{"name": alias, "inspection_count": count} for alias, count in aliases.most_common()]
        profile["observed_building_count"] = len(building_keys)
        result.append(profile)
    return sorted(result, key=lambda item: (-int(item["observed_building_count"]), str(item["lab_key"])))


def _property_profiles(
    inspections: Sequence[Mapping[str, Any]], compliance: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    by_building: dict[str, dict[str, Any]] = {}
    for row in inspections:
        key = str(row["building_key"])
        profile = by_building.setdefault(
            key,
            {
                "building_key": key,
                "bin": row.get("bin"),
                "bbl": row.get("bbl"),
                "address": row.get("address"),
                "borough": row.get("borough"),
                "zip": row.get("zip"),
                "inspection_count": 0,
                "tank_numbers": set(),
                "provider_ids": set(),
                "lab_ids": set(),
                "latest_inspection_date": None,
                "latest_reporting_year": None,
                "current_observed_provider_id": None,
                "current_observed_provider_raw": None,
                "current_observed_lab_id": None,
                "current_observed_lab_raw": None,
                "compliance_activity_count": 0,
                "violation_count": 0,
                "latest_violation_date": None,
            },
        )
        profile["inspection_count"] += 1
        if row.get("tank_num"):
            profile["tank_numbers"].add(str(row["tank_num"]))
        if row.get("provider_id"):
            profile["provider_ids"].add(str(row["provider_id"]))
        if row.get("lab_id"):
            profile["lab_ids"].add(str(row["lab_id"]))
        date_value = row.get("inspection_date")
        reporting_year = row.get("reporting_year")
        chronology = str(date_value or reporting_year or "")
        current_chronology = str(profile["latest_inspection_date"] or profile["latest_reporting_year"] or "")
        if chronology and chronology >= current_chronology:
            profile["latest_inspection_date"] = date_value
            profile["latest_reporting_year"] = reporting_year
            profile["current_observed_provider_id"] = row.get("provider_id")
            profile["current_observed_provider_raw"] = row.get("provider_raw")
            profile["current_observed_lab_id"] = row.get("lab_id")
            profile["current_observed_lab_raw"] = row.get("lab_raw")

    for row in compliance:
        key = str(row["building_key"])
        profile = by_building.setdefault(
            key,
            {
                "building_key": key,
                "bin": row.get("bin"),
                "bbl": None,
                "address": row.get("address"),
                "borough": row.get("borough"),
                "zip": row.get("zip"),
                "inspection_count": 0,
                "tank_numbers": set(),
                "provider_ids": set(),
                "lab_ids": set(),
                "latest_inspection_date": None,
                "latest_reporting_year": None,
                "current_observed_provider_id": None,
                "current_observed_provider_raw": None,
                "current_observed_lab_id": None,
                "current_observed_lab_raw": None,
                "compliance_activity_count": 0,
                "violation_count": 0,
                "latest_violation_date": None,
            },
        )
        profile["compliance_activity_count"] += 1
        if row.get("is_violation"):
            profile["violation_count"] += 1
            violation_date = row.get("date_of_occurrence")
            if violation_date and (not profile["latest_violation_date"] or violation_date > profile["latest_violation_date"]):
                profile["latest_violation_date"] = violation_date

    result: list[dict[str, Any]] = []
    for profile in by_building.values():
        tank_numbers: set[str] = profile.pop("tank_numbers")
        provider_ids: set[str] = profile.pop("provider_ids")
        lab_ids: set[str] = profile.pop("lab_ids")
        profile["observed_tank_count"] = len(tank_numbers)
        profile["observed_provider_ids"] = sorted(provider_ids)
        profile["observed_lab_ids"] = sorted(lab_ids)
        result.append(profile)
    return sorted(result, key=lambda item: str(item["building_key"]))


def source_health(snapshot: SourceSnapshot, *, normalized_count: int) -> dict[str, Any]:
    return {
        "dataset_id": snapshot.dataset_id,
        "name": snapshot.name,
        "api_root": snapshot.api_root,
        "status": "HEALTHY",
        "retrieved_at": snapshot.retrieved_at,
        "source_last_updated_at": snapshot.source_last_updated_at,
        "source_record_count": snapshot.source_record_count,
        "fetched_record_count": len(snapshot.rows),
        "normalized_record_count": normalized_count,
        "pagination_complete": len(snapshot.rows) == snapshot.source_record_count,
        "schema_valid": True,
        "source_query_scope": snapshot.source_query_scope,
    }


def build_payload(*, page_size: int = 50000) -> dict[str, Any]:
    tank_snapshot = fetch_snapshot(
        TANK_INSPECTION_DATASET_ID,
        api_root=NYC_API_ROOT,
        order_by="bin,reporting_year,tank_num,inspection_date",
        required_fields=(
            "bin",
            "borough",
            "block",
            "lot",
            "reporting_year",
            "tank_num",
            "inspection_by_firm",
            "inspection_performed",
            "inspection_date",
            "lab_name",
        ),
        page_size=page_size,
    )
    compliance_snapshot = fetch_snapshot(
        TANK_COMPLIANCE_DATASET_ID,
        api_root=NYC_API_ROOT,
        order_by="bin,activity_year,date_of_occurrence,summons_number",
        required_fields=(
            "bin",
            "borough",
            "activity_type",
            "activity_year",
            "violation_code",
            "violation_text",
            "date_of_occurrence",
            "summons_number",
        ),
        page_size=page_size,
    )
    dec_business_snapshot = fetch_snapshot(
        DEC_BUSINESS_DATASET_ID,
        api_root=NYS_API_ROOT,
        order_by="registration_number",
        required_fields=("business_agency_name", "registration_number", "pesticide_category_code", "pesticide_category_desc"),
        where="lower(pesticide_category_code)='7g'",
        page_size=page_size,
    )
    dec_applicator_snapshot = fetch_snapshot(
        DEC_APPLICATOR_DATASET_ID,
        api_root=NYS_API_ROOT,
        order_by="cert_number",
        required_fields=("cert_number", "first_name", "last_name", "applicator_type", "category", "category_description"),
        where="lower(category)='7g'",
        page_size=page_size,
    )
    free_lead_snapshot = fetch_snapshot(
        FREE_LEAD_COPPER_DATASET_ID,
        api_root=NYC_API_ROOT,
        order_by="kit_id,date_collected",
        required_fields=(
            "kit_id", "borough", "zipcode", "date_collected", "date_received",
            "lead_first_draw_mg_l", "lead_1_2_minute_flush_mg_l", "lead_5_minute_flush_mg_l",
            "copper_first_draw_mg_l", "copper_1_2_minute_flush_mg_l", "copper_5_minute_flush_mg_l",
        ),
        page_size=page_size,
    )
    compliance_lead_snapshot = fetch_snapshot(
        COMPLIANCE_LEAD_COPPER_DATASET_ID,
        api_root=NYC_API_ROOT,
        order_by="kit_id_number,date_collected",
        required_fields=(
            "kit_id_number", "borough", "zipcode", "date_collected", "received_date",
            "first_draw_at_the_tap_lead", "first_draw_at_the_tap_copper",
        ),
        page_size=page_size,
    )

    inspections = [normalize_tank_inspection(row) for row in tank_snapshot.rows]
    compliance = [normalize_compliance_activity(row) for row in compliance_snapshot.rows]
    dec_businesses = [normalize_dec_business(row) for row in dec_business_snapshot.rows]
    dec_applicators = [normalize_dec_applicator(row) for row in dec_applicator_snapshot.rows]
    free_lead_samples = [normalize_free_lead_copper_sample(row) for row in free_lead_snapshot.rows]
    compliance_lead_samples = [normalize_compliance_lead_copper_sample(row) for row in compliance_lead_snapshot.rows]
    providers = _provider_profiles(inspections)
    laboratories = _laboratory_profiles(inspections)
    properties = _property_profiles(inspections, compliance)

    generated_at = utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "domain": "NY_DOMESTIC_WATER_PROVIDER_INTELLIGENCE",
        "evidence_semantics": {
            "OBSERVED_SERVICE": "A source-reported inspection or laboratory event names the provider at the asset.",
            "CONFIRMED_ASSET": "The source row directly identifies the building/tank associated with the observed service.",
            "QUALIFIED_PROVIDER": "DEC credential supports legal qualification in Category 7G; it does not prove an incumbent service relationship.",
            "provider_counts": "Observed source relationships only; not total revenue, total customers, or complete market share.",
        },
        "summary": {
            "tank_inspection_count": len(inspections),
            "tank_compliance_activity_count": len(compliance),
            "observed_provider_count": len(providers),
            "observed_laboratory_count": len(laboratories),
            "observed_property_count": len(properties),
            "dec_7g_business_registration_count": len(dec_businesses),
            "dec_7g_applicator_certification_count": len(dec_applicators),
            "free_residential_lead_copper_sample_count": len(free_lead_samples),
            "compliance_lead_copper_sample_count": len(compliance_lead_samples),
            "violation_activity_count": sum(1 for row in compliance if row["is_violation"]),
            "inspection_rows_with_provider": sum(1 for row in inspections if row["provider_id"]),
            "inspection_rows_with_lab": sum(1 for row in inspections if row["lab_id"]),
        },
        "source_health": [
            source_health(tank_snapshot, normalized_count=len(inspections)),
            source_health(compliance_snapshot, normalized_count=len(compliance)),
            source_health(dec_business_snapshot, normalized_count=len(dec_businesses)),
            source_health(dec_applicator_snapshot, normalized_count=len(dec_applicators)),
            source_health(free_lead_snapshot, normalized_count=len(free_lead_samples)),
            source_health(compliance_lead_snapshot, normalized_count=len(compliance_lead_samples)),
        ],
        "providers": providers,
        "laboratories": laboratories,
        "properties": properties,
        "dec_7g_businesses": dec_businesses,
        "dec_7g_applicators": dec_applicators,
        "free_residential_lead_copper_samples": free_lead_samples,
        "compliance_lead_copper_samples": compliance_lead_samples,
        "tank_inspections": inspections,
        "tank_compliance_activities": compliance,
    }
