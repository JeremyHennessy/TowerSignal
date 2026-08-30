from __future__ import annotations

import csv
import io
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from toronto_market_common import clean_text, get_value, read_json, request_bytes, utc_now, write_json

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data" / "toronto" / "market" / "current"
WAREHOUSE = ROOT / "data" / "toronto" / "warehouse" / "current"
POC_CSV = ROOT / "data" / "toronto" / "poc" / "current" / "properties.csv"
ADDRESS_POINTS_CSV = "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/abedd8bc-e3dd-4d45-8e69-79165a76e4fa/resource/64d4e54b-738f-4cd9-a9e7-8050fac8a52f/download/address-points-4326.csv"

STREET_TYPES = {
    "STREET": "ST", "ST": "ST", "ROAD": "RD", "RD": "RD", "AVENUE": "AVE", "AVE": "AVE",
    "BOULEVARD": "BLVD", "BLVD": "BLVD", "DRIVE": "DR", "DR": "DR", "COURT": "CRT", "CRT": "CRT", "CT": "CRT",
    "CRESCENT": "CRES", "CRES": "CRES", "LANE": "LANE", "LN": "LANE", "PLACE": "PL", "PL": "PL",
    "PARKWAY": "PKWY", "PKWY": "PKWY", "HIGHWAY": "HWY", "HWY": "HWY", "TRAIL": "TRL", "TRL": "TRL",
    "TERRACE": "TER", "TER": "TER", "GATE": "GT", "GT": "GT", "GARDENS": "GDNS", "GARDEN": "GDN",
    "GDNS": "GDNS", "GDN": "GDN", "WAY": "WAY", "SQUARE": "SQ", "SQ": "SQ",
}
DIRECTIONS = {"NORTH":"N","SOUTH":"S","EAST":"E","WEST":"W","N":"N","S":"S","E":"E","W":"W"}
PROPERTY_ADDRESS_KEYS = {"address", "siteaddress", "facilityaddress", "propertyaddress", "fulladdress", "premisesaddress", "locationaddress", "streetaddress", "address1"}
EXCLUDED = {"mail", "email", "owner", "contractor", "vendor", "consultant", "manager", "certifier", "billing", "contact", "head", "office"}

SOURCE_FILES = [
    ("chemtrac_history", WAREHOUSE / "open_licensed/chemtrac_history.json"),
    ("ontario_ewrb_large_buildings", WAREHOUSE / "open_licensed/ontario_ewrb_large_buildings.json"),
    ("ontario_environmental_compliance_reports", WAREHOUSE / "open_licensed/ontario_environmental_compliance_reports.json"),
    ("toronto_highrise_residential_health_hazards", MARKET / "open_licensed/toronto_highrise_residential_health_hazards.json"),
    ("toronto_aic_applications", MARKET / "open_licensed/toronto_aic_applications.json"),
]


def key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def canonical_address(value: Any) -> str:
    """Canonicalize the civic-address portion only; never strip words like YORK/TORONTO from a street name."""
    text = clean_text(value).upper()
    if not text:
        return ""
    # Published Toronto/Ontario sources normally append municipality/province/postal
    # after a comma. Keep only the street-address segment; do not remove municipality
    # words from the interior because ROYAL YORK RD, YORK RD and NEW TORONTO ST are valid streets.
    text = text.split(",", 1)[0].strip()
    text = re.sub(r"\bUNIT\s+[A-Z0-9-]+\b", "", text)
    text = re.sub(r"\b(?:SUITE|STE)\s+[A-Z0-9-]+\b", "", text)
    text = re.sub(r"[^A-Z0-9-]+", " ", text)
    tokens = [t for t in text.split() if t]
    out: list[str] = []
    for token in tokens:
        if token in STREET_TYPES:
            out.append(STREET_TYPES[token])
        elif token in DIRECTIONS:
            out.append(DIRECTIONS[token])
        else:
            out.append(token)
    return " ".join(out)


def iter_records(payload: Any) -> Iterable[dict[str, Any]]:
    if isinstance(payload, list):
        for item in payload:
            yield from iter_records(item)
    elif isinstance(payload, dict):
        for name in ("records", "rows", "toronto_rows", "features", "applications", "matches", "properties", "notices"):
            value = payload.get(name)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and name == "features" and isinstance(item.get("attributes"), dict):
                        yield item["attributes"]
                    elif isinstance(item, dict):
                        yield item
                return
        if any("address" in key(k) for k in payload):
            yield payload


def record_addresses(record: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for field, value in record.items():
        nk = key(field)
        if any(fragment in nk for fragment in EXCLUDED):
            continue
        if nk in PROPERTY_ADDRESS_KEYS or ("address" in nk and not any(fragment in nk for fragment in EXCLUDED)):
            if isinstance(value, (str, int, float)):
                canon = canonical_address(value)
                if re.match(r"^\d+[A-Z]?(?:-\d+[A-Z]?)?\s+", canon):
                    found.append(clean_text(value))
    return list(dict.fromkeys(found))


def parse_geometry(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return None
    coords = payload.get("coordinates") if isinstance(payload, dict) else None
    while isinstance(coords, list) and len(coords) == 1 and isinstance(coords[0], list):
        coords = coords[0]
    if not isinstance(coords, list) or len(coords) < 2:
        return None
    try:
        lon, lat = float(coords[0]), float(coords[1])
    except (TypeError, ValueError):
        return None
    return (lon, lat) if -180 <= lon <= 180 and -90 <= lat <= 90 else None


def address_point_root(record: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    current = record
    seen: set[str] = set()
    while clean_text(current.get("address_point_id_link")):
        current_id = clean_text(current.get("address_point_id"))
        if current_id in seen:
            raise RuntimeError(f"Address Point link cycle detected at {current_id}")
        seen.add(current_id)
        linked = by_id.get(clean_text(current.get("address_point_id_link")))
        if not linked:
            break
        current = linked
    return current


def linked_range_parent(value: Any, by_address: dict[str, list[dict[str, Any]]], by_id: dict[str, dict[str, Any]]) -> tuple[dict[str, Any] | None, list[str]]:
    normalized = canonical_address(value)
    match = re.match(r"^(\d+[A-Z]?)-(\d+[A-Z]?)\s+(.+)$", normalized)
    if not match:
        return None, []
    endpoint_addresses = [f"{match.group(1)} {match.group(3)}", f"{match.group(2)} {match.group(3)}"]
    endpoints = []
    for address in endpoint_addresses:
        candidates = by_address.get(address, [])
        if len(candidates) != 1:
            return None, [clean_text(item.get("address_point_id")) for item in endpoints]
        endpoints.append(candidates[0])
    roots = [address_point_root(item, by_id) for item in endpoints]
    root_ids = {clean_text(item.get("address_point_id")) for item in roots}
    endpoint_ids = [clean_text(item.get("address_point_id")) for item in endpoints]
    return (roots[0], endpoint_ids) if len(root_ids) == 1 else (None, endpoint_ids)


def load_address_points() -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]], int]:
    raw = request_bytes(ADDRESS_POINTS_CSV, timeout=240, max_bytes=350_000_000)
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig", errors="replace")))
    by_id: dict[str, dict[str, Any]] = {}
    by_addr: dict[str, list[dict[str, Any]]] = defaultdict(list)
    scanned = 0
    for row in reader:
        scanned += 1
        pid = clean_text(row.get("ADDRESS_POINT_ID"))
        address = clean_text(row.get("ADDRESS_FULL"))
        canon = canonical_address(address)
        coords = parse_geometry(row.get("geometry"))
        rec = {
            "address_point_id": pid or None,
            "address_id": clean_text(row.get("ADDRESS_ID")) or None,
            "address_string_id": clean_text(row.get("ADDRESS_STRING_ID")) or None,
            "centreline_id": clean_text(row.get("CENTRELINE_ID")) or None,
            "address_point_id_link": clean_text(row.get("ADDRESS_POINT_ID_LINK")) or None,
            "address_id_link": clean_text(row.get("ADDRESS_ID_LINK")) or None,
            "address_link": clean_text(row.get("ADDRESS_LINK")) or None,
            "address": address or None,
            "canonical_address": canon or None,
            "place_name": clean_text(row.get("PLACE_NAME")) or None,
            "municipality": clean_text(row.get("MUNICIPALITY")) or None,
            "municipality_name": clean_text(row.get("MUNICIPALITY_NAME")) or None,
            "longitude": coords[0] if coords else None,
            "latitude": coords[1] if coords else None,
        }
        if pid:
            by_id[pid] = rec
        if canon:
            by_addr[canon].append(rec)
    return by_id, by_addr, scanned


def main() -> None:
    spine = read_json(MARKET / "property_spine.json")
    if not isinstance(spine, dict) or not isinstance(spine.get("properties"), list):
        raise RuntimeError("property_spine.json missing")
    by_id, ap_by_addr, scanned = load_address_points()
    props = spine["properties"]

    # Correct canonical/display identity for every already-resolved municipal property.
    for prop in props:
        pid = clean_text(prop.get("address_point_id"))
        municipal = by_id.get(pid)
        if municipal:
            prop["display_address"] = municipal.get("address") or prop.get("display_address")
            prop["canonical_address"] = municipal.get("canonical_address") or canonical_address(prop.get("display_address"))
            prop["longitude"] = municipal.get("longitude")
            prop["latitude"] = municipal.get("latitude")
            prop["coordinate_basis"] = "CITY_ADDRESS_POINTS_4326_GEOMETRY_MULTIPOINT"
            for field in ("address_id","address_string_id","centreline_id","address_point_id_link","address_id_link","address_link","place_name","municipality","municipality_name"):
                prop[field] = municipal.get(field)

    # Recover original POC identities omitted only because the former canonicalizer
    # truncated a valid street name such as YORK RD. Range records remain unresolved.
    with POC_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        poc = list(csv.DictReader(handle))
    existing_poc = {clean_text(k) for p in props for k in p.get("poc_property_keys", [])}
    # Persist the resolution provenance across reruns.  The generated spine is an
    # input to later scheduled rebuilds, so an idempotent rerun must not degrade
    # an explicit City link resolution into a generic address match.
    recovered: dict[str, dict[str, Any]] = {}
    for prop in props:
        for resolution in prop.get("poc_identity_resolutions") or []:
            key = clean_text(resolution.get("property_key"))
            basis = clean_text(resolution.get("identity_basis"))
            if key and basis:
                recovered[key] = {
                    "status": basis,
                    "range_endpoint_address_point_ids": resolution.get("range_endpoint_address_point_ids") or [],
                }
    for row in poc:
        pkey = clean_text(row.get("property_key"))
        if pkey in existing_poc:
            continue
        canon = canonical_address(row.get("address"))
        candidates = ap_by_addr.get(canon, [])
        municipal = candidates[0] if len(candidates) == 1 else None
        recovery_status = "EXACT_UNIQUE_CIVIC_ADDRESS_AFTER_CANONICALIZER_FIX"
        range_endpoint_ids: list[str] = []
        if municipal is None:
            municipal, range_endpoint_ids = linked_range_parent(row.get("address"), ap_by_addr, by_id)
            recovery_status = "EXPLICIT_LINKED_RANGE_ENDPOINTS_TO_CANONICAL_PARENT"
        if municipal is None:
            continue
        pid = clean_text(municipal.get("address_point_id"))
        if not pid:
            continue
        legacy = clean_text(row.get("geo_id"))
        existing = next((p for p in props if clean_text(p.get("address_point_id")) == pid), None)
        if existing:
            existing["is_original_poc_property"] = True
            existing["poc_property_keys"] = list(dict.fromkeys([*(existing.get("poc_property_keys") or []), pkey]))
            existing["poc_tower_statuses"] = list(dict.fromkeys([*(existing.get("poc_tower_statuses") or []), *([clean_text(row.get("tower_status"))] if clean_text(row.get("tower_status")) else [])]))
            existing["legacy_geo_ids"] = list(dict.fromkeys([*(existing.get("legacy_geo_ids") or []), *([legacy] if legacy else [])]))
            existing["address_aliases"] = list(dict.fromkeys([*(existing.get("address_aliases") or []), clean_text(row.get("address"))]))
            resolutions = existing.setdefault("poc_identity_resolutions", [])
            if not any(clean_text(item.get("property_key")) == pkey for item in resolutions):
                resolutions.append({"property_key": pkey, "identity_basis": recovery_status, "range_endpoint_address_point_ids": range_endpoint_ids})
            existing_poc.add(pkey)
            recovered[pkey] = {"status": recovery_status, "range_endpoint_address_point_ids": range_endpoint_ids}
            continue
        prop = {
            "property_id": f"toronto-address-point:{pid}",
            "canonical_identifier_type": "CITY_OF_TORONTO_ADDRESS_POINT_ID",
            "canonical_identifier": pid,
            "address_point_id": pid,
            "address_id": municipal.get("address_id"),
            "address_string_id": municipal.get("address_string_id"),
            "centreline_id": municipal.get("centreline_id"),
            "address_point_id_link": municipal.get("address_point_id_link"),
            "address_id_link": municipal.get("address_id_link"),
            "address_link": municipal.get("address_link"),
            "canonical_address": municipal.get("canonical_address"),
            "display_address": municipal.get("address"),
            "longitude": municipal.get("longitude"),
            "latitude": municipal.get("latitude"),
            "municipality": municipal.get("municipality"),
            "municipality_name": municipal.get("municipality_name"),
            "place_name": municipal.get("place_name"),
            "address_aliases": [clean_text(row.get("address"))],
            "source_keys": ["toronto_poc"],
            "is_original_poc_property": True,
            "poc_property_keys": [pkey],
            "poc_tower_statuses": [clean_text(row.get("tower_status"))] if clean_text(row.get("tower_status")) else [],
            "legacy_geo_ids": [legacy] if legacy else [],
            "identity_basis": recovery_status,
            "identity_confidence": "DETERMINISTIC",
            "identity_contract_version": "toronto-address-point-1.1",
            "coordinate_basis": "CITY_ADDRESS_POINTS_4326_GEOMETRY_MULTIPOINT",
            "poc_identity_resolutions": [{"property_key": pkey, "identity_basis": recovery_status, "range_endpoint_address_point_ids": range_endpoint_ids}],
        }
        props.append(prop)
        existing_poc.add(pkey)
        recovered[pkey] = {"status": recovery_status, "range_endpoint_address_point_ids": range_endpoint_ids}

    props.sort(key=lambda p: p["property_id"])
    property_by_addr: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for prop in props:
        property_by_addr[clean_text(prop.get("canonical_address"))].append(prop)

    # Regenerate address-source joins under the corrected canonicalizer. An address
    # resolving to multiple current Address Points is deliberately left unmatched.
    links: list[dict[str, Any]] = []
    source_summaries: dict[str, Any] = {}
    for source, path in SOURCE_FILES:
        payload = read_json(path)
        if payload is None:
            source_summaries[source] = {"status": "SOURCE_FILE_MISSING"}
            continue
        records = list(iter_records(payload))
        rows_with_address = 0
        matched_rows = 0
        matched_props: set[str] = set()
        ambiguous_rows = 0
        for idx, rec in enumerate(records):
            addresses = record_addresses(rec)
            rows_with_address += bool(addresses)
            matched = False
            for address in addresses:
                matches = property_by_addr.get(canonical_address(address), [])
                if len(matches) > 1:
                    ambiguous_rows += 1
                    continue
                if len(matches) != 1:
                    continue
                prop = matches[0]
                rid = next((rec.get(k) for k in ("_id","OBJECTID","id","APPLICATION_NUMBER","FOLDERRSN") if rec.get(k) not in (None,"")), None)
                # Several historical source packages reuse their local `_id`
                # values across annual/partitioned record arrays. Keep the
                # persisted row index in the source identity so distinct
                # source observations cannot collapse into duplicate edges.
                source_record_id = f"{source}:{rid}:{idx}" if rid is not None else f"{source}:row:{idx}"
                links.append({
                    "property_id": prop["property_id"],
                    "source_key": source,
                    "source_record_id": source_record_id,
                    "source_row_index": idx,
                    "match_basis": "EXACT_CORRECTED_CANONICAL_PROPERTY_ADDRESS_TO_ADDRESS_POINT_SPINE",
                    "source_address": address,
                })
                matched_props.add(prop["property_id"])
                matched = True
                break
            matched_rows += matched
        source_summaries[source] = {
            "status": "JOINED",
            "source_records": len(records),
            "records_with_property_address": rows_with_address,
            "matched_records": matched_rows,
            "matched_canonical_properties": len(matched_props),
            "ambiguous_address_rows_not_forced": ambiguous_rows,
            "identity_limitation": None if rows_with_address else "PUBLIC_SOURCE_HAS_NO_DETERMINISTIC_PROPERTY_ADDRESS_FIELD",
        }

    # Rebuild full 177-record reconciliation ledger from corrected property membership.
    prop_by_poc = {clean_text(k): p for p in props for k in p.get("poc_property_keys", [])}
    reconciliation = []
    counts: dict[str, int] = defaultdict(int)
    for row in poc:
        pkey = clean_text(row.get("property_key"))
        legacy = clean_text(row.get("geo_id")) or None
        prop = prop_by_poc.get(pkey)
        if prop:
            apid = clean_text(prop.get("address_point_id"))
            if pkey in recovered:
                status = recovered[pkey]["status"]
            elif legacy and legacy == apid:
                status = "LEGACY_GEOID_MATCHED_CURRENT_ADDRESS_POINT_ID"
            else:
                status = "EXACT_UNIQUE_CIVIC_ADDRESS_MATCH"
            rec = {
                "property_key": pkey,
                "input_address": clean_text(row.get("address")),
                "input_legacy_geo_id": legacy,
                "resolution_status": status,
                "resolved": True,
                "property_id": prop["property_id"],
                "address_point_id": prop.get("address_point_id"),
                "address_id": prop.get("address_id"),
                "canonical_address": prop.get("canonical_address"),
            }
            if pkey in recovered and recovered[pkey]["range_endpoint_address_point_ids"]:
                rec["range_endpoint_address_point_ids"] = recovered[pkey]["range_endpoint_address_point_ids"]
        else:
            canon = canonical_address(row.get("address"))
            candidates = ap_by_addr.get(canon, [])
            is_range = bool(re.match(r"^\d+[A-Z]?-\d+[A-Z]?\s+", canon))
            if is_range:
                status = "MULTI_ADDRESS_RANGE_REVIEW_REQUIRED"
            elif len(candidates) > 1:
                status = "AMBIGUOUS_CURRENT_ADDRESS_POINTS"
            else:
                status = "NO_CURRENT_ADDRESS_POINT_MATCH"
            rec = {
                "property_key": pkey,
                "input_address": clean_text(row.get("address")),
                "input_legacy_geo_id": legacy,
                "resolution_status": status,
                "resolved": False,
                "candidate_address_point_ids": [c.get("address_point_id") for c in candidates],
                "candidate_addresses": [c.get("address") for c in candidates],
            }
        counts[status] += 1
        reconciliation.append(rec)

    resolved_count = sum(bool(r["resolved"]) for r in reconciliation)
    if len(reconciliation) != 177 or resolved_count + sum(not r["resolved"] for r in reconciliation) != 177:
        raise RuntimeError("Final reconciliation ledger invalid")

    spine["schema_version"] = "toronto-property-spine-1.1"
    spine["identity_contract"]["canonical_address_rule"] = "Canonicalize only the civic-address segment before the first comma; valid street-name tokens YORK/TORONTO are never stripped."
    spine["identity_contract"]["version"] = "toronto-address-point-1.1"
    spine["properties"] = props
    spine["counts"]["canonical_properties_resolved"] = len(props)
    # Keep the original summary fields synchronized with the authoritative
    # 177-row reconciliation ledger.  Older snapshots exposed both names.
    spine["counts"]["original_poc_resolved"] = resolved_count
    spine["counts"]["original_poc_unresolved"] = 177 - resolved_count
    spine["counts"]["original_poc_reconciled_to_address_point_id"] = resolved_count
    spine["counts"]["original_poc_unreconciled"] = 177 - resolved_count
    spine["counts"]["expanded_properties_beyond_original_poc"] = sum(not p.get("is_original_poc_property") for p in props)
    spine["counts"]["properties_with_usable_coordinates"] = sum(p.get("longitude") is not None and p.get("latitude") is not None for p in props)
    spine["counts"]["address_point_rows_scanned_final_cleanup"] = scanned
    write_json(MARKET / "property_spine.json", spine)

    write_json(MARKET / "property_source_links.json", {
        "schema_version": "toronto-market-property-links-1.1",
        "generated_at": utc_now(),
        "join_contract": {"basis": "Exact corrected civic-address canonical equality to unique City ADDRESS_POINT_ID property", "fuzzy_matching": False, "ambiguous_addresses": "NOT_FORCED"},
        "counts": {"canonical_properties": len(props), "total_source_links": len(links), "properties_with_any_new_link": len({l['property_id'] for l in links})},
        "sources": source_summaries,
        "links": links,
    })
    write_json(MARKET / "reconciliation_details.json", {
        "schema_version": "toronto-poc-reconciliation-1.1",
        "generated_at": utc_now(),
        "source_poc_count": 177,
        "resolved_count": resolved_count,
        "unresolved_count": 177-resolved_count,
        "resolution_status_counts": dict(sorted(counts.items())),
        "records": reconciliation,
    })
    write_json(MARKET / "reconciliation_summary.json", {
        "schema_version": "toronto-reconciliation-summary-1.1",
        "generated_at": utc_now(),
        "identity_contract": spine["identity_contract"],
        "counts": spine["counts"],
        "resolution_status_counts": dict(sorted(counts.items())),
    })
    identity = read_json(MARKET / "identity_contract.json") or {}
    identity["schema_version"] = "toronto-address-identity-contract-1.1"
    identity["canonical_address_rule"] = "Only the civic-address segment before the first comma is canonicalized; municipality names are not stripped from inside valid street names."
    identity["known_fix"] = "Pre-1.1 logic could truncate Royal York Rd, York Rd and New Toronto St. Final 1.1 cleanup repairs existing canonical addresses and regenerates joins."
    write_json(MARKET / "identity_contract.json", identity)

    report = {
        "schema_version": "toronto-final-identity-cleanup-1.0",
        "generated_at": utc_now(),
        "poc_resolved": resolved_count,
        "poc_unresolved": 177-resolved_count,
        "recovered_poc_keys": sorted(recovered),
        "recovered_poc_details": recovered,
        "canonical_properties": len(props),
        "properties_with_coordinates": spine["counts"]["properties_with_usable_coordinates"],
        "source_link_count": len(links),
        "source_summaries": source_summaries,
    }
    write_json(MARKET / "final_identity_cleanup_report.json", report)
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
