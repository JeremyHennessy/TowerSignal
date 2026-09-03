from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from toronto_final_identity_cleanup import canonical_address
from toronto_market_common import clean_text, read_json, request_json

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data/toronto/market/current"
CKAN = "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/datastore_search"

SOURCES = {
    "building_permits_active": "6d0229af-bc54-46de-9c2b-26759b01dd05",
    "building_permits_cleared_since_2017": "a96c0ba4-3026-402b-b09d-5b1268b8f810",
}

TERMS = (
    "cooling tower",
    "cooling towers",
    "chiller",
    "condenser",
    "HVAC",
    "mechanical",
    "boiler",
    "water treatment",
)


def query(resource_id: str, q: str | None = None, limit: int = 1, offset: int = 0) -> dict[str, Any]:
    params: dict[str, Any] = {"resource_id": resource_id, "limit": limit, "offset": offset}
    if q:
        params["q"] = q
    payload = request_json(f"{CKAN}?{urlencode(params)}", timeout=120)
    if payload.get("success") is not True:
        raise RuntimeError(f"CKAN datastore_search failed for {resource_id}: {q}")
    result = payload.get("result") or {}
    if not isinstance(result, dict):
        raise RuntimeError("Unexpected CKAN datastore response")
    return result


def value(row: dict[str, Any], *names: str) -> str:
    for name in names:
        text = clean_text(row.get(name))
        if text:
            return text
    return ""


def permit_address(row: dict[str, Any]) -> str:
    direct = value(row, "ADDRESS", "Address", "FULL_ADDRESS", "Full Address")
    if direct:
        return direct
    parts = [
        value(row, "STREET_NUM", "Street Num", "STREET NUMBER", "Street Number"),
        value(row, "STREET_NAME", "Street Name"),
        value(row, "STREET_TYPE", "Street Type"),
        value(row, "STREET_DIRECTION", "Street Direction"),
    ]
    return " ".join(part for part in parts if part)


def property_index(properties: list[dict[str, Any]]) -> dict[str, list[str]]:
    by_address: dict[str, list[str]] = defaultdict(list)
    for prop in properties:
        pid = clean_text(prop.get("property_id"))
        if not pid:
            continue
        seen: set[str] = set()
        for raw in [prop.get("display_address"), prop.get("canonical_address"), *(prop.get("address_aliases") or [])]:
            address = canonical_address(raw)
            if address and address not in seen:
                seen.add(address)
                by_address[address].append(pid)
    return by_address


def summarize_source(name: str, resource_id: str, by_address: dict[str, list[str]], address_point_ids: set[str]) -> dict[str, Any]:
    overview = query(resource_id, limit=1)
    fields = [str(item.get("id") or item.get("name") or "") for item in overview.get("fields", []) if isinstance(item, dict)]
    total = int(overview.get("total") or 0)
    term_counts: dict[str, int] = {}
    sampled_by_identity: dict[str, dict[str, Any]] = {}
    sampled_truncated_terms: list[str] = []

    for term in TERMS:
        result = query(resource_id, q=term, limit=1000)
        term_total = int(result.get("total") or 0)
        term_counts[term] = term_total
        if term_total > 1000:
            sampled_truncated_terms.append(term)
        for row in result.get("records", []) or []:
            if not isinstance(row, dict):
                continue
            identity = value(row, "PERMIT_NUM", "Permit Num", "PERMIT_NUMBER", "Permit Number")
            revision = value(row, "REVISION_NUM", "Revision Num", "REVISION_NUMBER", "Revision Number")
            if identity:
                identity = f"{identity}:{revision}" if revision else identity
            else:
                identity = json.dumps(row, sort_keys=True, default=str)
            sampled_by_identity.setdefault(identity, row)

    exact_rows = 0
    exact_properties: set[str] = set()
    ambiguous_rows = 0
    no_address_rows = 0
    geoid_matches_current_address_point = 0
    relevant_type_counts: dict[str, int] = defaultdict(int)
    examples: list[dict[str, Any]] = []

    for row in sampled_by_identity.values():
        raw_address = permit_address(row)
        address = canonical_address(raw_address)
        if not address:
            no_address_rows += 1
            continue
        matches = set(by_address.get(address, []))
        if len(matches) > 1:
            ambiguous_rows += 1
        elif len(matches) == 1:
            exact_rows += 1
            pid = next(iter(matches))
            exact_properties.add(pid)
            if len(examples) < 25:
                examples.append({
                    "property_id": pid,
                    "address": raw_address,
                    "permit_number": value(row, "PERMIT_NUM", "Permit Num"),
                    "revision_number": value(row, "REVISION_NUM", "Revision Num"),
                    "permit_type": value(row, "PERMIT_TYPE", "Permit Type"),
                    "structure_type": value(row, "STRUCTURE_TYPE", "Structure Type"),
                    "work": value(row, "WORK", "Work"),
                    "description": value(row, "DESCRIPTION", "Description", "WORK_DESCRIPTION", "Work Description"),
                    "application_date": value(row, "APPLICATION_DATE", "Application Date"),
                    "issued_date": value(row, "ISSUED_DATE", "Issued Date"),
                    "status": value(row, "STATUS", "Status"),
                })
        geoid = value(row, "GEO_ID", "Geo ID", "GEOID", "GeoID")
        if geoid and geoid in address_point_ids:
            geoid_matches_current_address_point += 1
        permit_type = value(row, "PERMIT_TYPE", "Permit Type")
        if permit_type:
            relevant_type_counts[permit_type] += 1

    return {
        "resource_id": resource_id,
        "total_rows": total,
        "fields": fields,
        "term_match_totals": term_counts,
        "sampled_unique_relevant_rows": len(sampled_by_identity),
        "sample_truncated_terms": sampled_truncated_terms,
        "sample_exact_unique_address_rows": exact_rows,
        "sample_exact_unique_properties": len(exact_properties),
        "sample_ambiguous_address_rows_not_promotable": ambiguous_rows,
        "sample_rows_without_usable_address": no_address_rows,
        "sample_geo_id_equals_current_address_point_id": geoid_matches_current_address_point,
        "sample_permit_type_counts": dict(sorted(relevant_type_counts.items())),
        "examples": examples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only live diagnostic for Toronto active/cleared building-permit relevance")
    parser.add_argument("--output", type=Path, default=Path("toronto-building-permit-diagnostic.json"))
    args = parser.parse_args()

    spine = read_json(MARKET / "property_spine.json") or {}
    properties = [item for item in spine.get("properties", []) if isinstance(item, dict)]
    by_address = property_index(properties)
    address_point_ids = {clean_text(item.get("address_point_id")) for item in properties if clean_text(item.get("address_point_id"))}

    report = {
        "schema_version": "toronto-building-permit-diagnostic-1.0",
        "status": "PASSED_DIAGNOSTIC",
        "scope": "Read-only live Toronto Open Data diagnostic. Keyword matches are discovery signals only; only exact unique civic-address joins are counted as deterministic property opportunities.",
        "terms": list(TERMS),
        "canonical_properties": len(properties),
        "sources": {
            name: summarize_source(name, resource_id, by_address, address_point_ids)
            for name, resource_id in SOURCES.items()
        },
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    concise = {
        "status": report["status"],
        "canonical_properties": report["canonical_properties"],
        "sources": {
            name: {
                key: value
                for key, value in source.items()
                if key not in {"fields", "examples"}
            }
            for name, source in report["sources"].items()
        },
        "fields": {name: source["fields"] for name, source in report["sources"].items()},
        "examples": {name: source["examples"][:8] for name, source in report["sources"].items()},
    }
    print(json.dumps(concise, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
