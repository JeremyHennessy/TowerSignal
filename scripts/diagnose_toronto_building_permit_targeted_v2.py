from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from toronto_final_identity_cleanup import canonical_address
from toronto_market_common import clean_text, read_json, request_json

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data/toronto/market/current"
SEARCH_ENDPOINT = "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/datastore_search"

SOURCES = {
    "active": "6d0229af-bc54-46de-9c2b-26759b01dd05",
    "cleared_since_2017": "a96c0ba4-3026-402b-b09d-5b1268b8f810",
}

SIGNALS = {
    "cooling_tower": "cooling tower",
    "evaporative_condenser": "evaporative condenser",
    "condenser_water": "condenser water",
    "cooling_water": "cooling water",
    "chiller": "chiller",
    "water_treatment": "water treatment",
    "chemical_feed": "chemical feed",
    "legionella": "legionella",
    "boiler": "boiler",
}

DISCOVERY_QUERIES = (
    "cooling",
    "chiller",
    "condenser",
    "water treatment",
    "chemical feed",
    "legionella",
    "boiler",
)


def search(resource_id: str, q: str, limit: int = 1000, offset: int = 0) -> dict[str, Any]:
    params = {"resource_id": resource_id, "q": q, "limit": limit, "offset": offset}
    payload = request_json(f"{SEARCH_ENDPOINT}?{urlencode(params)}", timeout=180)
    if payload.get("success") is not True:
        raise RuntimeError(f"Toronto CKAN datastore_search failed for {q}")
    result = payload.get("result") or {}
    if not isinstance(result, dict):
        raise RuntimeError("Unexpected Toronto CKAN datastore_search result")
    return result


def fetch_query_rows(resource_id: str, q: str) -> tuple[int, list[dict[str, Any]]]:
    first = search(resource_id, q, limit=1000, offset=0)
    total = int(first.get("total") or 0)
    rows = [row for row in first.get("records", []) if isinstance(row, dict)]
    offset = len(rows)
    while offset < total:
        result = search(resource_id, q, limit=1000, offset=offset)
        batch = [row for row in result.get("records", []) if isinstance(row, dict)]
        if not batch:
            break
        rows.extend(batch)
        offset += len(batch)
    if len(rows) != total:
        raise RuntimeError(f"Permit search pagination mismatch for {q}: expected {total}, found {len(rows)}")
    return total, rows


def permit_identity(row: dict[str, Any]) -> str:
    permit_num = clean_text(row.get("PERMIT_NUM"))
    revision = clean_text(row.get("REVISION_NUM"))
    if not permit_num:
        raise RuntimeError("Targeted permit row missing PERMIT_NUM")
    return f"{permit_num}::{revision or '00'}"


def row_address(row: dict[str, Any]) -> str:
    return " ".join(part for part in [
        clean_text(row.get("STREET_NUM")),
        clean_text(row.get("STREET_NAME")),
        clean_text(row.get("STREET_TYPE")),
        clean_text(row.get("STREET_DIRECTION")),
    ] if part)


def signal_keys(row: dict[str, Any]) -> list[str]:
    description = clean_text(row.get("DESCRIPTION")).lower()
    return [key for key, term in SIGNALS.items() if term in description]


def property_indexes(properties: list[dict[str, Any]]) -> tuple[dict[str, str], dict[str, list[str]]]:
    by_apid: dict[str, str] = {}
    by_address: dict[str, list[str]] = defaultdict(list)
    for prop in properties:
        pid = clean_text(prop.get("property_id"))
        apid = clean_text(prop.get("address_point_id"))
        if pid and apid:
            by_apid[apid] = pid
        if not pid:
            continue
        seen: set[str] = set()
        for raw in [prop.get("display_address"), prop.get("canonical_address"), *(prop.get("address_aliases") or [])]:
            address = canonical_address(raw)
            if address and address not in seen:
                seen.add(address)
                by_address[address].append(pid)
    return by_apid, by_address


def summarize(source_name: str, resource_id: str, by_apid: dict[str, str], by_address: dict[str, list[str]]) -> tuple[dict[str, Any], set[str]]:
    discovered: dict[str, dict[str, Any]] = {}
    query_totals: dict[str, int] = {}
    query_duplicate_hits = 0
    for q in DISCOVERY_QUERIES:
        total, rows = fetch_query_rows(resource_id, q)
        query_totals[q] = total
        for row in rows:
            identity = permit_identity(row)
            if identity in discovered:
                query_duplicate_hits += 1
            discovered.setdefault(identity, row)

    targeted = {identity: row for identity, row in discovered.items() if signal_keys(row)}
    match_basis = Counter()
    matched_properties: set[str] = set()
    signal_counts = Counter()
    status_counts = Counter()
    permit_type_counts = Counter()
    work_counts = Counter()
    builders: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []
    ambiguous_addresses = 0
    unmatched = 0

    for identity, row in targeted.items():
        for key in signal_keys(row):
            signal_counts[key] += 1
        status_counts[clean_text(row.get("STATUS")) or "UNKNOWN"] += 1
        permit_type_counts[clean_text(row.get("PERMIT_TYPE")) or "UNKNOWN"] += 1
        work_counts[clean_text(row.get("WORK")) or "UNKNOWN"] += 1
        builder = clean_text(row.get("BUILDER_NAME"))
        if builder:
            builders[builder] += 1

        pid = None
        apid = clean_text(row.get("GEO_ID"))
        if apid and apid in by_apid:
            pid = by_apid[apid]
            match_basis["CURRENT_ADDRESS_POINT_ID"] += 1
        else:
            address = canonical_address(row_address(row))
            matches = set(by_address.get(address, [])) if address else set()
            if len(matches) == 1:
                pid = next(iter(matches))
                match_basis["EXACT_UNIQUE_CIVIC_ADDRESS"] += 1
            elif len(matches) > 1:
                ambiguous_addresses += 1
            else:
                unmatched += 1
        if pid:
            matched_properties.add(pid)
            if len(examples) < 50:
                examples.append({
                    "property_id": pid,
                    "permit_identity": identity,
                    "permit_num": row.get("PERMIT_NUM"),
                    "revision_num": row.get("REVISION_NUM"),
                    "address": row_address(row),
                    "geo_id": row.get("GEO_ID"),
                    "permit_type": row.get("PERMIT_TYPE"),
                    "work": row.get("WORK"),
                    "status": row.get("STATUS"),
                    "application_date": row.get("APPLICATION_DATE"),
                    "issued_date": row.get("ISSUED_DATE"),
                    "completed_date": row.get("COMPLETED_DATE"),
                    "est_const_cost": row.get("EST_CONST_COST"),
                    "builder_name": row.get("BUILDER_NAME"),
                    "signals": signal_keys(row),
                    "description": row.get("DESCRIPTION"),
                })

    return {
        "resource_id": resource_id,
        "discovery_query_totals": query_totals,
        "discovered_unique_permit_revisions": len(discovered),
        "duplicate_query_hits_collapsed": query_duplicate_hits,
        "targeted_rows_after_exact_local_term_filter": len(targeted),
        "signal_row_counts": dict(sorted(signal_counts.items())),
        "matched_rows": sum(match_basis.values()),
        "matched_properties": len(matched_properties),
        "match_basis_counts": dict(sorted(match_basis.items())),
        "ambiguous_address_rows_not_promotable": ambiguous_addresses,
        "unmatched_rows": unmatched,
        "builder_name_nonempty_rows": sum(builders.values()),
        "builder_name_unique_values": len(builders),
        "builder_name_top_values": builders.most_common(20),
        "permit_type_counts": dict(permit_type_counts.most_common()),
        "work_counts_top": work_counts.most_common(30),
        "status_counts": dict(status_counts.most_common()),
        "examples": examples,
    }, set(targeted)


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only targeted Toronto mechanical building-permit diagnostic using supported datastore search")
    parser.add_argument("--output", type=Path, default=Path("toronto-building-permit-targeted-v2.json"))
    args = parser.parse_args()
    spine = read_json(MARKET / "property_spine.json") or {}
    properties = [row for row in spine.get("properties", []) if isinstance(row, dict)]
    by_apid, by_address = property_indexes(properties)
    source_results: dict[str, Any] = {}
    identity_sets: dict[str, set[str]] = {}
    for source_name, resource_id in SOURCES.items():
        source_results[source_name], identity_sets[source_name] = summarize(source_name, resource_id, by_apid, by_address)
    overlap = sorted(identity_sets["active"] & identity_sets["cleared_since_2017"])
    report = {
        "schema_version": "toronto-building-permit-targeted-diagnostic-1.1",
        "status": "PASSED_DIAGNOSTIC",
        "scope": "Read-only live source diagnostic. Broad supported CKAN search discovers candidates; exact local description terms select the corpus. No permit row promotes cooling-tower confirmation or organization relationships.",
        "identity_contract": "PERMIT_NUM plus REVISION_NUM, following City Open Data guidance for the complete permit identifier.",
        "signals": SIGNALS,
        "discovery_queries": list(DISCOVERY_QUERIES),
        "canonical_properties": len(properties),
        "sources": source_results,
        "active_cleared_identity_overlap_count": len(overlap),
        "active_cleared_identity_overlap_sample": overlap[:50],
        "builder_role_status": "UNVERIFIED_FIELD_SEMANTICS_NO_RELATIONSHIP_PROMOTION",
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    concise = {**report, "sources": {name: {key: value for key, value in source.items() if key not in {"examples", "work_counts_top", "builder_name_top_values"}} for name, source in source_results.items()}}
    print(json.dumps(concise, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
