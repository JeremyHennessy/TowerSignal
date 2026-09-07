from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.bbl_identity import apply_bbl_identity_recovery  # noqa: E402
from towersignal.building_footprints import fetch_building_footprints_by_bin  # noqa: E402
from towersignal.fetch import fetch_dataset  # noqa: E402
from towersignal.normalize import normalize_registrations  # noqa: E402

CMS_API_ROOT = "https://data.cms.gov/provider-data/api/1/datastore/query"
GEOSEARCH_URL = "https://geosearch.planninglabs.nyc/v2/search"
HOSPITAL_DATASET = "xubh-q36u"
NURSING_HOME_DATASET = "4pq5-n9py"
REGISTRATION_DATASET = "y4fw-iqfr"
CMS_PAGE_SIZE = 2000
USER_AGENT = "TowerSignal/1.0 (+https://github.com/JeremyHennessy/TowerSignal)"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_space(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def digits(value: Any) -> str:
    return re.sub(r"\D", "", normalize_space(value))


def normalize_bbl(value: Any) -> str | None:
    value_digits = digits(value)
    return value_digits if len(value_digits) == 10 and value_digits[0] in "12345" else None


def normalize_bin(value: Any) -> str | None:
    value_digits = digits(value)
    return value_digits if len(value_digits) == 7 else None


def normalize_zip(value: Any) -> str | None:
    value_digits = digits(value)
    return value_digits[:5] if len(value_digits) >= 5 else None


def is_nyc_zip(value: Any) -> bool:
    postal = normalize_zip(value)
    if not postal:
        return False
    number = int(postal)
    return (
        10001 <= number <= 10292
        or 10301 <= number <= 10314
        or 10451 <= number <= 10475
        or 11004 <= number <= 11005
        or 11101 <= number <= 11109
        or 11201 <= number <= 11256
        or 11351 <= number <= 11697
    )


def _json_request(url: str, *, retries: int = 4, timeout: int = 45) -> Any:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
            with urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(2**attempt)
    raise RuntimeError(f"Source request failed after {retries} attempts: {url}: {last_error}")


def fetch_cms_dataset(dataset_id: str, *, page_size: int = CMS_PAGE_SIZE) -> tuple[list[dict[str, Any]], int]:
    if page_size <= 0 or page_size > CMS_PAGE_SIZE:
        raise ValueError(f"CMS page size must be 1..{CMS_PAGE_SIZE}")
    rows: list[dict[str, Any]] = []
    offset = 0
    expected_count: int | None = None
    while expected_count is None or offset < expected_count:
        url = f"{CMS_API_ROOT}/{dataset_id}/0?{urlencode({'offset': offset, 'limit': page_size})}"
        payload = _json_request(url)
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise RuntimeError(f"CMS dataset {dataset_id} returned an unexpected payload at offset {offset}")
        if expected_count is None:
            try:
                expected_count = int(payload.get("count"))
            except (TypeError, ValueError) as exc:
                raise RuntimeError(f"CMS dataset {dataset_id} did not report a usable source count") from exc
        page = [row for row in payload["results"] if isinstance(row, dict)]
        if len(page) != len(payload["results"]):
            raise RuntimeError(f"CMS dataset {dataset_id} returned a non-object row")
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    if expected_count is None or len(rows) != expected_count:
        raise RuntimeError(
            f"CMS dataset {dataset_id} pagination incomplete: expected {expected_count}, fetched {len(rows)}"
        )
    return rows, expected_count


def first_value(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def normalize_cms_facility(source: str, row: Mapping[str, Any]) -> dict[str, Any] | None:
    if source == "HOSPITAL":
        source_id = normalize_space(first_value(row, "facility_id"))
        name = normalize_space(first_value(row, "facility_name"))
        address = normalize_space(first_value(row, "address"))
        city = normalize_space(first_value(row, "citytown", "city_town", "city"))
        state = normalize_space(first_value(row, "state")).upper()
        postal = normalize_zip(first_value(row, "zip_code", "zip"))
        facility_type = normalize_space(first_value(row, "hospital_type")) or None
        ownership = normalize_space(first_value(row, "hospital_ownership")) or None
        chain = None
        ownership_change = None
    elif source == "NURSING_HOME":
        source_id = normalize_space(first_value(row, "cms_certification_number_ccn", "federal_provider_number", "ccn"))
        name = normalize_space(first_value(row, "provider_name", "federal_provider_name"))
        address = normalize_space(first_value(row, "provider_address", "address"))
        city = normalize_space(first_value(row, "citytown", "provider_city", "city"))
        state = normalize_space(first_value(row, "state", "provider_state")).upper()
        postal = normalize_zip(first_value(row, "zip_code", "provider_zip_code", "zip"))
        facility_type = "Nursing home"
        ownership = normalize_space(first_value(row, "ownership_type")) or None
        chain = normalize_space(first_value(row, "chain_name", "chain_name_as_reported")) or None
        ownership_change = normalize_space(
            first_value(row, "date_first_approved_to_provide_medicare_and_medicaid_services", "date_of_last_change_of_ownership")
        ) or None
    else:
        raise ValueError(f"Unknown CMS source {source}")

    if not source_id or not address or not postal or state != "NY" or not is_nyc_zip(postal):
        return None
    return {
        "source": source,
        "source_dataset_id": HOSPITAL_DATASET if source == "HOSPITAL" else NURSING_HOME_DATASET,
        "source_facility_id": source_id,
        "facility_name": name or None,
        "address": address,
        "city": city or None,
        "state": state,
        "zip": postal,
        "facility_type": facility_type,
        "ownership_type": ownership,
        "chain_name": chain,
        "source_ownership_change_context": ownership_change,
    }


def _address_parts(address: str) -> tuple[str | None, str | None]:
    match = re.match(r"^\s*([0-9]+[A-Z]?(?:-[0-9]+[A-Z]?)?)\s+(.+?)\s*$", address.upper())
    if not match:
        return None, None
    house = normalize_space(match.group(1)).upper()
    street = normalize_space(re.sub(r"[^A-Z0-9 ]+", " ", match.group(2))).upper()
    return house, street


def _normalized_street(value: Any) -> str:
    return normalize_space(re.sub(r"[^A-Z0-9 ]+", " ", normalize_space(value).upper()))


def _walk_values(value: Any, key_name: str) -> list[Any]:
    found: list[Any] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() == key_name.lower():
                found.append(item)
            found.extend(_walk_values(item, key_name))
    elif isinstance(value, list):
        for item in value:
            found.extend(_walk_values(item, key_name))
    return found


def _feature_identifiers(feature: Mapping[str, Any]) -> tuple[set[str], set[str]]:
    properties = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
    addendum = properties.get("addendum") if isinstance(properties, dict) else None
    bbls = {value for raw in _walk_values(addendum, "bbl") if (value := normalize_bbl(raw))}
    bins = {value for raw in _walk_values(addendum, "bin") if (value := normalize_bin(raw))}
    return bbls, bins


def reconcile_geosearch(facility: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    features = payload.get("features")
    if not isinstance(features, list):
        return {"status": "SOURCE_RESPONSE_INVALID", "bbl": None, "bin": None, "candidate_count": 0}
    cms_house, cms_street = _address_parts(str(facility.get("address") or ""))
    cms_zip = normalize_zip(facility.get("zip"))
    candidates: list[dict[str, Any]] = []
    for feature in features:
        if not isinstance(feature, dict):
            continue
        properties = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
        result_zip = normalize_zip(first_value(properties, "postalcode", "postal_code", "zip"))
        result_house = normalize_space(first_value(properties, "housenumber", "house_number")).upper() or None
        result_street = _normalized_street(first_value(properties, "street")) or None
        bbls, bins = _feature_identifiers(feature)
        if cms_zip and result_zip != cms_zip:
            continue
        if cms_house and result_house != cms_house:
            continue
        if cms_street and result_street != cms_street:
            continue
        if len(bbls) != 1:
            continue
        candidates.append(
            {
                "bbl": next(iter(bbls)),
                "bin": next(iter(bins)) if len(bins) == 1 else None,
                "label": properties.get("label"),
                "confidence": properties.get("confidence"),
                "result_zip": result_zip,
            }
        )
    unique = {(candidate["bbl"], candidate["bin"]) for candidate in candidates}
    if len(unique) == 1:
        bbl, bin_value = next(iter(unique))
        return {
            "status": "RESOLVED_UNIQUE_PAD_EXACT_ADDRESS",
            "bbl": bbl,
            "bin": bin_value,
            "candidate_count": len(candidates),
            "evidence": candidates[0],
        }
    return {
        "status": "UNRESOLVED_NO_EXACT_PAD_RESULT" if not unique else "UNRESOLVED_MULTIPLE_PAD_PROPERTIES",
        "bbl": None,
        "bin": None,
        "candidate_count": len(candidates),
    }


def fetch_geosearch(facility: Mapping[str, Any]) -> dict[str, Any]:
    query_text = " ".join(
        value
        for value in (
            normalize_space(facility.get("address")),
            normalize_space(facility.get("city")),
            "NY",
            normalize_space(facility.get("zip")),
        )
        if value
    )
    url = f"{GEOSEARCH_URL}?{urlencode({'text': query_text, 'size': 5})}"
    payload = _json_request(url)
    if not isinstance(payload, dict):
        raise RuntimeError("NYC GeoSearch returned a non-object payload")
    result = reconcile_geosearch(facility, payload)
    return {**facility, "property_resolution": result}


def current_towersignal_properties() -> tuple[set[str], set[str], dict[str, Any]]:
    registrations = fetch_dataset(REGISTRATION_DATASET, "system_id")
    systems, _ = normalize_registrations(registrations.rows)
    bin_values = {str(system["bin"]) for system in systems if system.get("bin")}
    footprints, footprint_meta = fetch_building_footprints_by_bin(bin_values)
    identity_meta = apply_bbl_identity_recovery(systems, footprints)
    bbls = {str(system["bbl"]) for system in systems if system.get("bbl")}
    bins = {str(system["bin"]) for system in systems if system.get("bin")}
    return bbls, bins, {
        "registration_source_count": registrations.source_record_count,
        "normalized_system_count": len(systems),
        "canonical_bbl_count": len(bbls),
        "bin_count": len(bins),
        "bbl_identity": identity_meta,
        "building_footprints": footprint_meta,
    }


def build_report(*, geosearch_workers: int = 4) -> dict[str, Any]:
    hospitals_raw, hospital_count = fetch_cms_dataset(HOSPITAL_DATASET)
    nursing_raw, nursing_count = fetch_cms_dataset(NURSING_HOME_DATASET)
    facilities = [
        facility
        for source, rows in (("HOSPITAL", hospitals_raw), ("NURSING_HOME", nursing_raw))
        for row in rows
        if (facility := normalize_cms_facility(source, row)) is not None
    ]
    ids = {(facility["source"], facility["source_facility_id"]) for facility in facilities}
    if len(ids) != len(facilities):
        raise RuntimeError("CMS NYC facility identity is not unique by source + facility ID")

    resolved_rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(8, geosearch_workers))) as executor:
        futures = {executor.submit(fetch_geosearch, facility): facility for facility in facilities}
        for completed, future in enumerate(as_completed(futures), start=1):
            resolved_rows.append(future.result())
            if completed % 50 == 0 or completed == len(futures):
                print(f"[cms-diagnostic] GeoSearch resolved {completed:,}/{len(futures):,} CMS NYC facilities", flush=True)

    tower_bbls, tower_bins, tower_meta = current_towersignal_properties()
    statuses = Counter(str(row["property_resolution"]["status"]) for row in resolved_rows)
    resolved = [row for row in resolved_rows if row["property_resolution"]["status"] == "RESOLVED_UNIQUE_PAD_EXACT_ADDRESS"]
    overlap = [
        row
        for row in resolved
        if row["property_resolution"].get("bbl") in tower_bbls
        or (row["property_resolution"].get("bin") and row["property_resolution"].get("bin") in tower_bins)
    ]
    resolved_bbls = {str(row["property_resolution"]["bbl"]) for row in resolved if row["property_resolution"].get("bbl")}
    new_property_bbls = resolved_bbls - tower_bbls
    source_counts = Counter(row["source"] for row in resolved_rows)
    resolved_source_counts = Counter(row["source"] for row in resolved)
    overlap_source_counts = Counter(row["source"] for row in overlap)

    examples = []
    for row in sorted(overlap, key=lambda item: (str(item.get("source")), str(item.get("facility_name"))))[:30]:
        examples.append(
            {
                "source": row["source"],
                "source_facility_id": row["source_facility_id"],
                "facility_name": row.get("facility_name"),
                "address": row.get("address"),
                "zip": row.get("zip"),
                "facility_type": row.get("facility_type"),
                "ownership_type": row.get("ownership_type"),
                "chain_name": row.get("chain_name"),
                "bbl": row["property_resolution"].get("bbl"),
                "bin": row["property_resolution"].get("bin"),
            }
        )

    return {
        "schema_version": "1.0",
        "generated_at": utc_now(),
        "domain": "CMS_NYC_INSTITUTIONAL_FACILITY_PROPERTY_IDENTITY_DIAGNOSTIC",
        "source_contracts": {
            "cms_hospital_dataset": HOSPITAL_DATASET,
            "cms_nursing_home_dataset": NURSING_HOME_DATASET,
            "cms_api": CMS_API_ROOT,
            "nyc_property_resolver": GEOSEARCH_URL,
            "identity_rule": "CMS source facility ID remains source identity; property linkage requires one unique NYC GeoSearch/PAD result with exact normalized house number, street, ZIP and published BBL. BIN is retained only when uniquely published in the same result.",
        },
        "cms_source_counts": {
            "hospital_all_rows": hospital_count,
            "nursing_home_all_rows": nursing_count,
            "nyc_facilities": len(facilities),
            "nyc_by_source": dict(sorted(source_counts.items())),
        },
        "property_resolution": {
            "status_counts": dict(sorted(statuses.items())),
            "resolved_facility_count": len(resolved),
            "resolved_unique_bbl_count": len(resolved_bbls),
            "resolved_by_source": dict(sorted(resolved_source_counts.items())),
            "towersignal_overlap_facility_count": len(overlap),
            "towersignal_overlap_by_source": dict(sorted(overlap_source_counts.items())),
            "incremental_resolved_bbl_count_outside_current_tower_universe": len(new_property_bbls),
            "overlap_examples": examples,
        },
        "towersignal_baseline": tower_meta,
        "decision_semantics": {
            "who": "A resolved CMS facility can identify an institutional operator/facility class at an authoritative NYC tax lot; it does not prove a cooling-tower service relationship.",
            "when": "This base diagnostic does not authorize CMS as a timing trigger. Ownership/change-of-ownership datasets require a separate source-contract and lift evaluation after property identity is proven.",
            "why": "Facility type, ownership and chain context may enrich institutional account qualification only where authoritative property identity is deterministic.",
        },
        "governance": {
            "diagnostic_only": True,
            "priority_score_1_0_changed": False,
            "ui_changed": False,
            "durable_history_changed": False,
            "fuzzy_matching_used": False,
            "provider_or_incumbent_inference": False,
            "cms_authorized_for_production": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose exact NYC property identity for CMS hospitals and nursing homes")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--geosearch-workers", type=int, default=4)
    args = parser.parse_args()
    report = build_report(geosearch_workers=args.geosearch_workers)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "nyc_facilities": report["cms_source_counts"]["nyc_facilities"],
        "resolved_facilities": report["property_resolution"]["resolved_facility_count"],
        "towersignal_overlap_facilities": report["property_resolution"]["towersignal_overlap_facility_count"],
        "incremental_resolved_bbls": report["property_resolution"]["incremental_resolved_bbl_count_outside_current_tower_universe"],
    }, indent=2))


if __name__ == "__main__":
    main()
