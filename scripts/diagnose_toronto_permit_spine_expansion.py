from __future__ import annotations

import argparse
import csv
import io
import json
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from diagnose_toronto_building_permit_targeted_v2 import (
    DISCOVERY_QUERIES,
    SOURCES,
    fetch_query_rows,
    permit_identity,
    property_indexes,
    row_address,
    signal_keys,
)
from toronto_final_identity_cleanup import canonical_address
from toronto_market_common import clean_text, read_json

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data/toronto/market/current"
ADDRESS_POINTS_CSV = "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/abedd8bc-e3dd-4d45-8e69-79165a76e4fa/resource/64d4e54b-738f-4cd9-a9e7-8050fac8a52f/download/address-points-4326.csv"


def targeted_rows(resource_id: str) -> dict[str, dict[str, Any]]:
    discovered: dict[str, dict[str, Any]] = {}
    for query in DISCOVERY_QUERIES:
        _, rows = fetch_query_rows(resource_id, query)
        for row in rows:
            discovered.setdefault(permit_identity(row), row)
    return {identity: row for identity, row in discovered.items() if signal_keys(row)}


def load_current_address_points(target_ids: set[str], target_addresses: set[str]) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    request = urllib.request.Request(ADDRESS_POINTS_CSV, headers={"User-Agent": "TowerSignal-Permit-Spine-Diagnostic/1.0"})
    with urllib.request.urlopen(request, timeout=240) as response:
        raw = response.read()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig", errors="replace")))
    by_id: dict[str, dict[str, Any]] = {}
    by_address: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in reader:
        apid = clean_text(row.get("ADDRESS_POINT_ID"))
        address = canonical_address(row.get("ADDRESS_FULL"))
        if apid in target_ids:
            by_id[apid] = row
        if address in target_addresses:
            by_address[address].append(row)
    return by_id, by_address


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only audit of targeted permit rows that can expand the Toronto Address Point property spine")
    parser.add_argument("--output", type=Path, default=Path("toronto-permit-spine-expansion.json"))
    args = parser.parse_args()

    spine = read_json(MARKET / "property_spine.json") or {}
    properties = [row for row in spine.get("properties", []) if isinstance(row, dict)]
    current_by_apid, current_by_address = property_indexes(properties)

    source_rows = {source: targeted_rows(resource_id) for source, resource_id in SOURCES.items()}
    unmatched: list[dict[str, Any]] = []
    target_ids: set[str] = set()
    target_addresses: set[str] = set()

    for source, rows in source_rows.items():
        for identity, row in rows.items():
            apid = clean_text(row.get("GEO_ID"))
            address = canonical_address(row_address(row))
            if apid and apid in current_by_apid:
                continue
            current_matches = set(current_by_address.get(address, [])) if address else set()
            if len(current_matches) == 1:
                continue
            record = {
                "source": source,
                "permit_identity": identity,
                "permit_geo_id": apid or None,
                "permit_address": row_address(row),
                "canonical_permit_address": address or None,
                "signals": signal_keys(row),
                "status": clean_text(row.get("STATUS")) or None,
                "description": clean_text(row.get("DESCRIPTION")) or None,
            }
            unmatched.append(record)
            if apid:
                target_ids.add(apid)
            if address:
                target_addresses.add(address)

    address_points_by_id, address_points_by_address = load_current_address_points(target_ids, target_addresses)

    resolution_counts = Counter()
    source_resolution_counts: dict[str, Counter] = defaultdict(Counter)
    resolved_properties: dict[str, dict[str, Any]] = {}
    unresolved: list[dict[str, Any]] = []
    id_address_mismatches: list[dict[str, Any]] = []

    for record in unmatched:
        apid = clean_text(record.get("permit_geo_id"))
        permit_address = clean_text(record.get("canonical_permit_address"))
        id_row = address_points_by_id.get(apid) if apid else None
        resolution = None
        resolved_row = None
        if id_row is not None:
            ap_address = canonical_address(id_row.get("ADDRESS_FULL"))
            if permit_address and ap_address and permit_address != ap_address:
                id_address_mismatches.append({
                    **record,
                    "address_point_address": id_row.get("ADDRESS_FULL"),
                    "address_point_id": id_row.get("ADDRESS_POINT_ID"),
                })
                resolution = "CURRENT_ADDRESS_POINT_ID_ADDRESS_MISMATCH_REVIEW_REQUIRED"
            else:
                resolved_row = id_row
                resolution = "CURRENT_ADDRESS_POINT_ID_WITH_MATCHING_CIVIC_ADDRESS"
        elif permit_address:
            candidates = address_points_by_address.get(permit_address, [])
            unique = {clean_text(row.get("ADDRESS_POINT_ID")): row for row in candidates if clean_text(row.get("ADDRESS_POINT_ID"))}
            if len(unique) == 1:
                resolved_row = next(iter(unique.values()))
                resolution = "EXACT_UNIQUE_CURRENT_ADDRESS_POINT_CIVIC_ADDRESS"
            elif len(unique) > 1:
                resolution = "AMBIGUOUS_CURRENT_ADDRESS_POINT_CIVIC_ADDRESS_REVIEW_REQUIRED"
            else:
                resolution = "NO_CURRENT_ADDRESS_POINT_MATCH"
        else:
            resolution = "NO_USABLE_PERMIT_ADDRESS_OR_CURRENT_ADDRESS_POINT_ID"

        resolution_counts[resolution] += 1
        source_resolution_counts[record["source"]][resolution] += 1
        if resolved_row is not None:
            resolved_apid = clean_text(resolved_row.get("ADDRESS_POINT_ID"))
            candidate = resolved_properties.setdefault(resolved_apid, {
                "address_point_id": resolved_apid,
                "address_id": clean_text(resolved_row.get("ADDRESS_ID")) or None,
                "address_full": clean_text(resolved_row.get("ADDRESS_FULL")) or None,
                "place_name": clean_text(resolved_row.get("PLACE_NAME")) or None,
                "general_use": clean_text(resolved_row.get("GENERAL_USE")) or None,
                "address_status": clean_text(resolved_row.get("ADDRESS_STATUS")) or None,
                "municipality_name": clean_text(resolved_row.get("MUNICIPALITY_NAME")) or None,
                "ward_name": clean_text(resolved_row.get("WARD_NAME")) or None,
                "geometry": resolved_row.get("geometry"),
                "permit_records": [],
                "signals": set(),
                "sources": set(),
            })
            candidate["permit_records"].append(record["permit_identity"])
            candidate["signals"].update(record["signals"])
            candidate["sources"].add(record["source"])
        else:
            unresolved.append({**record, "resolution_status": resolution})

    serializable_properties = []
    for item in resolved_properties.values():
        serializable_properties.append({
            **item,
            "permit_records": sorted(set(item["permit_records"])),
            "signals": sorted(item["signals"]),
            "sources": sorted(item["sources"]),
        })
    serializable_properties.sort(key=lambda item: (item.get("address_full") or "", item["address_point_id"]))

    existing_apids = set(current_by_apid)
    accidental_existing = sorted(existing_apids & set(resolved_properties))
    if accidental_existing:
        raise RuntimeError(f"Permit spine diagnostic selected properties already in current spine: {accidental_existing[:20]}")

    report = {
        "schema_version": "toronto-permit-spine-expansion-diagnostic-1.0",
        "status": "PASSED_DIAGNOSTIC",
        "scope": "Read-only resolution of targeted permit rows not already joined to the current Toronto property spine. Current Address Point ID plus matching civic address is preferred; exact unique current civic address is fallback; mismatches and ambiguities are withheld.",
        "current_property_spine_count": len(properties),
        "targeted_rows_by_source": {source: len(rows) for source, rows in source_rows.items()},
        "currently_unmatched_targeted_rows": len(unmatched),
        "permit_geo_ids_checked": len(target_ids),
        "permit_addresses_checked": len(target_addresses),
        "resolution_counts": dict(sorted(resolution_counts.items())),
        "source_resolution_counts": {source: dict(sorted(counts.items())) for source, counts in sorted(source_resolution_counts.items())},
        "new_current_address_point_properties": len(serializable_properties),
        "new_properties": serializable_properties,
        "id_address_mismatch_rows": id_address_mismatches,
        "unresolved_rows": unresolved,
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "current_property_spine_count": report["current_property_spine_count"],
        "targeted_rows_by_source": report["targeted_rows_by_source"],
        "currently_unmatched_targeted_rows": report["currently_unmatched_targeted_rows"],
        "resolution_counts": report["resolution_counts"],
        "source_resolution_counts": report["source_resolution_counts"],
        "new_current_address_point_properties": report["new_current_address_point_properties"],
        "id_address_mismatch_rows": len(report["id_address_mismatch_rows"]),
        "unresolved_rows": len(report["unresolved_rows"]),
        "new_property_sample": serializable_properties[:30],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
