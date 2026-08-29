from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from toronto_market_common import canonical_street_address, clean_text, get_value, read_json, request_bytes, utc_now, write_json

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data" / "toronto" / "market" / "current"
POC_CSV = ROOT / "data" / "toronto" / "poc" / "current" / "properties.csv"
ADDRESS_POINTS_CSV = "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/abedd8bc-e3dd-4d45-8e69-79165a76e4fa/resource/64d4e54b-738f-4cd9-a9e7-8050fac8a52f/download/address-points-4326.csv"


def text(value: Any) -> str:
    return clean_text(value)


def point_id(row: dict[str, Any]) -> str:
    return text(get_value(row, "ADDRESS_POINT_ID"))


def point_address(row: dict[str, Any]) -> str:
    direct = text(get_value(row, "ADDRESS_FULL", "ADDRESS", "FULL_ADDRESS", "SITE_ADDRESS"))
    if direct:
        return direct
    number = text(get_value(row, "ADDRESS_NUMBER", "LO_NUM", "HOUSE_NUMBER", "STREET_NUM"))
    street = text(get_value(row, "LINEAR_NAME_FULL", "STREET_NAME", "LF_NAME"))
    return " ".join(x for x in (number, street) if x)


def load_poc() -> list[dict[str, str]]:
    with POC_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_address_points(target_addresses: set[str], target_ids: set[str]) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]], int]:
    raw = request_bytes(ADDRESS_POINTS_CSV, timeout=240, max_bytes=350_000_000)
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig", errors="replace")))
    by_id: dict[str, dict[str, Any]] = {}
    by_address: dict[str, list[dict[str, Any]]] = defaultdict(list)
    scanned = 0
    for row in reader:
        scanned += 1
        pid = point_id(row)
        address = point_address(row)
        canon = canonical_street_address(address)
        if pid not in target_ids and canon not in target_addresses:
            continue
        record = {
            "address_point_id": pid or None,
            "address_id": text(get_value(row, "ADDRESS_ID")) or None,
            "address_string_id": text(get_value(row, "ADDRESS_STRING_ID")) or None,
            "centreline_id": text(get_value(row, "CENTRELINE_ID")) or None,
            "address_point_id_link": text(get_value(row, "ADDRESS_POINT_ID_LINK")) or None,
            "address_id_link": text(get_value(row, "ADDRESS_ID_LINK")) or None,
            "address_link": text(get_value(row, "ADDRESS_LINK")) or None,
            "address_status": text(get_value(row, "ADDRESS_STATUS")) or None,
            "date_effective": text(get_value(row, "DATE_EFFECTIVE")) or None,
            "date_expiry": text(get_value(row, "DATE_EXPIRY")) or None,
            "address": address or None,
            "canonical_address": canon or None,
            "place_name": text(get_value(row, "PLACE_NAME")) or None,
            "municipality": text(get_value(row, "MUNICIPALITY")) or None,
            "municipality_name": text(get_value(row, "MUNICIPALITY_NAME")) or None,
            "longitude": get_value(row, "LONGITUDE", "LON", "X"),
            "latitude": get_value(row, "LATITUDE", "LAT", "Y"),
        }
        if pid:
            by_id[pid] = record
        if canon:
            by_address[canon].append(record)
    return by_id, by_address, scanned


def normalize() -> dict[str, Any]:
    spine_path = MARKET / "property_spine.json"
    links_path = MARKET / "property_source_links.json"
    spine = read_json(spine_path)
    if not isinstance(spine, dict) or not isinstance(spine.get("properties"), list):
        raise RuntimeError("Toronto core property_spine.json is missing or invalid")
    poc = load_poc()
    if len(poc) != 177:
        raise RuntimeError(f"Expected 177 original Toronto POC properties, found {len(poc)}")

    poc_by_key = {text(r.get("property_key")): r for r in poc if text(r.get("property_key"))}
    target_addresses = {canonical_street_address(text(r.get("address"))) for r in poc if canonical_street_address(text(r.get("address")))}
    target_addresses.update(text(p.get("canonical_address")) for p in spine["properties"] if text(p.get("canonical_address")))
    target_ids = {
        text(p.get("address_point_id") or p.get("canonical_identifier") or p.get("geo_id"))
        for p in spine["properties"]
        if text(p.get("address_point_id") or p.get("canonical_identifier") or p.get("geo_id"))
    }
    target_ids.update(text(r.get("geo_id")) for r in poc if text(r.get("geo_id")))

    by_id, by_address, scanned = load_address_points(target_addresses, target_ids)
    old_to_new: dict[str, str] = {}
    normalized_props: list[dict[str, Any]] = []
    prop_by_poc_key: dict[str, dict[str, Any]] = {}

    for prop in spine["properties"]:
        current_id = text(prop.get("address_point_id") or prop.get("canonical_identifier") or prop.get("geo_id"))
        canon = text(prop.get("canonical_address"))
        municipal = by_id.get(current_id)
        if municipal is None and canon:
            candidates = by_address.get(canon, [])
            if len(candidates) == 1:
                municipal = candidates[0]
                current_id = text(municipal.get("address_point_id"))
        if not municipal or not current_id:
            raise RuntimeError(f"Resolved spine property lost municipal Address Point identity: {prop.get('property_id')}")

        legacy_geo_ids = sorted({text(poc_by_key[k].get("geo_id")) for k in prop.get("poc_property_keys", []) if k in poc_by_key and text(poc_by_key[k].get("geo_id"))})
        old_property_id = text(prop.get("property_id"))
        new_property_id = f"toronto-address-point:{current_id}"
        old_to_new[old_property_id] = new_property_id

        legacy_match = current_id in legacy_geo_ids
        identity_basis = "LEGACY_PERMIT_GEOID_EQUALS_CURRENT_ADDRESS_POINT_ID" if legacy_match else "EXACT_UNIQUE_CIVIC_ADDRESS_TO_CURRENT_ADDRESS_POINT_ID"
        if not prop.get("is_original_poc_property"):
            identity_basis = "EXACT_SOURCE_ADDRESS_TO_CURRENT_ADDRESS_POINT_ID"

        out = dict(prop)
        out.update({
            "property_id": new_property_id,
            "canonical_identifier_type": "CITY_OF_TORONTO_ADDRESS_POINT_ID",
            "canonical_identifier": current_id,
            "address_point_id": current_id,
            "address_id": municipal.get("address_id"),
            "address_string_id": municipal.get("address_string_id"),
            "centreline_id": municipal.get("centreline_id"),
            "address_point_id_link": municipal.get("address_point_id_link"),
            "address_id_link": municipal.get("address_id_link"),
            "address_link": municipal.get("address_link"),
            "address_status": municipal.get("address_status"),
            "date_effective": municipal.get("date_effective"),
            "date_expiry": municipal.get("date_expiry"),
            "place_name": municipal.get("place_name"),
            "municipality_name": municipal.get("municipality_name"),
            "legacy_geo_ids": legacy_geo_ids,
            "identity_basis": identity_basis,
            "identity_confidence": "DETERMINISTIC",
            "identity_contract_version": "toronto-address-point-1.0",
            "geo_id": current_id,
            "geo_id_compatibility_note": "Deprecated compatibility field. Current value is City ADDRESS_POINT_ID; legacy permit GEO_ID values were verified to correspond to ADDRESS_POINT_ID where still current.",
        })
        normalized_props.append(out)
        for key in prop.get("poc_property_keys", []):
            prop_by_poc_key[text(key)] = out

    reconciliation: list[dict[str, Any]] = []
    status_counts: dict[str, int] = defaultdict(int)
    for row in poc:
        key = text(row.get("property_key"))
        address = text(row.get("address"))
        canon = canonical_street_address(address)
        legacy = text(row.get("geo_id")) or None
        prop = prop_by_poc_key.get(key)
        if prop:
            apid = text(prop.get("address_point_id"))
            municipal = by_id.get(apid) or {}
            if legacy and legacy == apid:
                status = "LEGACY_GEOID_MATCHED_CURRENT_ADDRESS_POINT_ID"
            elif legacy and legacy == text(municipal.get("address_point_id_link")):
                status = "LEGACY_GEOID_MATCHED_EXPLICIT_ADDRESS_POINT_LINK"
            else:
                status = "EXACT_UNIQUE_CIVIC_ADDRESS_MATCH"
            entry = {
                "property_key": key,
                "input_address": address,
                "input_legacy_geo_id": legacy,
                "resolution_status": status,
                "resolved": True,
                "property_id": prop["property_id"],
                "address_point_id": prop.get("address_point_id"),
                "address_id": prop.get("address_id"),
                "address_point_id_link": prop.get("address_point_id_link"),
                "address_id_link": prop.get("address_id_link"),
                "canonical_address": prop.get("canonical_address"),
            }
        else:
            candidates = by_address.get(canon, []) if canon else []
            if len(candidates) > 1:
                status = "AMBIGUOUS_CURRENT_ADDRESS_POINTS"
            elif len(candidates) == 1:
                status = "UNRESOLVED_CORE_DESPITE_UNIQUE_CURRENT_ADDRESS_POINT"
            else:
                status = "NO_CURRENT_ADDRESS_POINT_MATCH"
            entry = {
                "property_key": key,
                "input_address": address,
                "input_legacy_geo_id": legacy,
                "resolution_status": status,
                "resolved": False,
                "candidate_address_point_ids": [c.get("address_point_id") for c in candidates],
                "candidate_addresses": [c.get("address") for c in candidates],
            }
        reconciliation.append(entry)
        status_counts[status] += 1

    if len(reconciliation) != 177 or len({r["property_key"] for r in reconciliation}) != 177:
        raise RuntimeError("POC reconciliation ledger must contain exactly 177 unique property keys")

    normalized_props.sort(key=lambda p: p["property_id"])
    spine["schema_version"] = "toronto-property-spine-1.0"
    spine["identity_contract"] = {
        "canonical_id": "toronto-address-point:<ADDRESS_POINT_ID>",
        "canonical_identifier_type": "City of Toronto One Address Repository ADDRESS_POINT_ID",
        "address_id_role": "Related municipal address identifier retained as an attribute; not used as TowerSignal canonical key in this phase.",
        "link_fields": "ADDRESS_POINT_ID_LINK and ADDRESS_ID_LINK are retained as explicit City-provided relationships and are not assumed to be ownership/parcel-parent relationships.",
        "legacy_geo_id": "Toronto building-permit GEO_ID values were empirically verified to correspond to current ADDRESS_POINT_ID where the historical identifier remains current. Legacy values are retained for provenance/backward mapping.",
        "fuzzy_matching": False,
        "tower_semantics": "Property identity never creates or upgrades cooling-tower confirmation.",
    }
    spine["properties"] = normalized_props
    spine["counts"]["original_poc_properties"] = 177
    spine["counts"]["original_poc_reconciled_to_address_point_id"] = sum(1 for r in reconciliation if r["resolved"])
    spine["counts"]["original_poc_unreconciled"] = sum(1 for r in reconciliation if not r["resolved"])
    spine["counts"]["address_point_rows_scanned"] = scanned
    spine["counts"].pop("original_poc_reconciled_to_geoid", None)

    write_json(spine_path, spine)
    write_json(MARKET / "reconciliation_details.json", {
        "schema_version": "toronto-poc-reconciliation-1.0",
        "generated_at": utc_now(),
        "source_poc_count": 177,
        "resolved_count": sum(1 for r in reconciliation if r["resolved"]),
        "unresolved_count": sum(1 for r in reconciliation if not r["resolved"]),
        "resolution_status_counts": dict(sorted(status_counts.items())),
        "records": reconciliation,
    })
    write_json(MARKET / "identity_contract.json", {
        "schema_version": "toronto-address-identity-contract-1.0",
        "generated_at": utc_now(),
        "canonical_property_key": "toronto-address-point:<ADDRESS_POINT_ID>",
        "canonical_source": "City of Toronto One Address Repository / Address Points",
        "fields": {
            "ADDRESS_POINT_ID": "Canonical TowerSignal Toronto civic-address identifier.",
            "ADDRESS_ID": "Related City address identifier retained for joins/provenance.",
            "ADDRESS_POINT_ID_LINK": "City-provided linked Address Point identifier; relationship retained without inventing parent/ownership semantics.",
            "ADDRESS_ID_LINK": "City-provided linked Address identifier; relationship retained without inventing parent/ownership semantics.",
            "ADDRESS_STRING_ID": "Address-string identifier retained as provenance.",
            "CENTRELINE_ID": "Street centreline identifier retained as provenance/context.",
        },
        "legacy_mapping": "Building-permit GEO_ID values were directly checked against the current Address Points source and correspond to ADDRESS_POINT_ID where the historical ID remains represented. Missing historical values are not silently treated as current IDs; exact civic address resolution is recorded separately.",
        "fuzzy_matching": False,
    })
    write_json(MARKET / "reconciliation_summary.json", {
        "schema_version": "toronto-reconciliation-summary-1.0",
        "generated_at": utc_now(),
        "identity_contract": spine["identity_contract"],
        "counts": spine["counts"],
        "resolution_status_counts": dict(sorted(status_counts.items())),
    })

    links = read_json(links_path)
    if isinstance(links, dict):
        for link in links.get("links", []):
            old = text(link.get("property_id"))
            if old in old_to_new:
                link["property_id"] = old_to_new[old]
            if link.get("match_basis") == "EXACT_CANONICAL_PROPERTY_ADDRESS_TO_GEOID_SPINE":
                link["match_basis"] = "EXACT_CANONICAL_PROPERTY_ADDRESS_TO_ADDRESS_POINT_SPINE"
        if isinstance(links.get("join_contract"), dict):
            links["join_contract"]["basis"] = "Exact canonical property-address equality to City ADDRESS_POINT_ID spine"
        links["schema_version"] = "toronto-market-property-links-1.0"
        write_json(links_path, links)

    summary = {
        "resolved": sum(1 for r in reconciliation if r["resolved"]),
        "unresolved": sum(1 for r in reconciliation if not r["resolved"]),
        "canonical_properties": len(normalized_props),
        "expanded_properties": sum(1 for p in normalized_props if not p.get("is_original_poc_property")),
        "resolution_status_counts": dict(sorted(status_counts.items())),
    }
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    normalize()
