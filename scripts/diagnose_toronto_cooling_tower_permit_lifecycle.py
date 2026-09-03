from __future__ import annotations

import argparse
import json
import re
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

# Multiple broad queries are required because Toronto CKAN full-text search does
# not return the same set for a phrase as for related terms. Exact cooling-tower
# filtering is performed locally after unioning the retrieved publisher rows.
DISCOVERY_QUERIES = ("cooling", "chiller", "boiler", "water treatment")

REMOVAL_REPLACEMENT_ALTERNATIVES = (
    "air source heat pump",
    "air source heat pumps",
    "dry cooler",
    "dry coolers",
    "air cooled chiller",
    "air-cooled chiller",
)


def search(resource_id: str, q: str, limit: int = 1000, offset: int = 0) -> dict[str, Any]:
    payload = request_json(
        f"{SEARCH_ENDPOINT}?{urlencode({'resource_id': resource_id, 'q': q, 'limit': limit, 'offset': offset})}",
        timeout=180,
    )
    if payload.get("success") is not True:
        raise RuntimeError(f"Toronto CKAN datastore_search failed for {q}")
    result = payload.get("result") or {}
    if not isinstance(result, dict):
        raise RuntimeError("Unexpected Toronto CKAN datastore_search result")
    return result


def fetch_all(resource_id: str, q: str) -> list[dict[str, Any]]:
    first = search(resource_id, q)
    total = int(first.get("total") or 0)
    rows = [row for row in first.get("records", []) if isinstance(row, dict)]
    offset = len(rows)
    while offset < total:
        result = search(resource_id, q, offset=offset)
        batch = [row for row in result.get("records", []) if isinstance(row, dict)]
        if not batch:
            break
        rows.extend(batch)
        offset += len(batch)
    if len(rows) != total:
        raise RuntimeError(f"Permit lifecycle pagination mismatch for {q}: expected {total}, found {len(rows)}")
    return rows


def permit_identity(row: dict[str, Any]) -> str:
    permit_num = clean_text(row.get("PERMIT_NUM"))
    revision = clean_text(row.get("REVISION_NUM"))
    if not permit_num:
        raise RuntimeError("Cooling-tower permit row missing PERMIT_NUM")
    return f"{permit_num}::{revision or '00'}"


def description(row: dict[str, Any]) -> str:
    return clean_text(row.get("DESCRIPTION"))


def normalize_text(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def has_cooling_tower(text: str) -> bool:
    return bool(re.search(r"\bcooling\s+towers?\b", text, flags=re.I))


def classify_lifecycle(text: str) -> tuple[str, list[str]]:
    norm = normalize_text(text)
    reasons: list[str] = []
    remove = bool(re.search(r"\b(remove|removal|decommission|demolish|demolition)\w*\b.{0,100}\bcooling towers?\b|\bcooling towers?\b.{0,100}\b(remove|removal|decommission|demolish|demolition)\w*\b", norm))
    install = bool(re.search(r"\b(install|installation|new|provide|addition)\w*\b.{0,100}\bcooling towers?\b|\bcooling towers?\b.{0,100}\b(install|installation|new|provide|addition)\w*\b", norm))
    replace = bool(re.search(r"\b(replace|replacement|replacing)\w*\b.{0,100}\bcooling towers?\b|\bcooling towers?\b.{0,100}\b(replace|replacement|replacing)\w*\b", norm))
    repair = bool(re.search(r"\b(repair|upgrade|refurbish|rehabilitat|motor|vfd|fan|support)\w*\b.{0,100}\bcooling towers?\b|\bcooling towers?\b.{0,100}\b(repair|upgrade|refurbish|rehabilitat|motor|vfd|fan|support)\w*\b", norm))
    alternative = any(term in norm for term in REMOVAL_REPLACEMENT_ALTERNATIVES)
    existing = bool(re.search(r"\bexisting\b.{0,100}\bcooling towers?\b|\bcooling towers?\b.{0,100}\bexisting\b", norm))

    if existing:
        reasons.append("EXPLICIT_EXISTING_TOWER")
    if remove:
        reasons.append("REMOVAL_LANGUAGE")
    if replace:
        reasons.append("REPLACEMENT_LANGUAGE")
    if install:
        reasons.append("INSTALLATION_OR_NEW_LANGUAGE")
    if repair:
        reasons.append("REPAIR_OR_MODIFICATION_LANGUAGE")
    if alternative:
        reasons.append("NON_TOWER_REPLACEMENT_ALTERNATIVE")

    if remove and alternative and not replace:
        return "REMOVE_OR_DECOMMISSION_WITH_NON_TOWER_ALTERNATIVE", reasons
    if replace:
        return "REPLACE_COOLING_TOWER", reasons
    if install:
        return "INSTALL_OR_ADD_COOLING_TOWER", reasons
    if repair:
        return "REPAIR_OR_MODIFY_COOLING_TOWER", reasons
    if remove:
        return "REMOVE_OR_DECOMMISSION_COOLING_TOWER_UNCLEAR_REPLACEMENT", reasons
    if existing:
        return "EXISTING_COOLING_TOWER_WORK_UNCLEAR", reasons
    return "COOLING_TOWER_MENTION_LIFECYCLE_UNCLEAR", reasons


def row_address(row: dict[str, Any]) -> str:
    return " ".join(part for part in [
        clean_text(row.get("STREET_NUM")), clean_text(row.get("STREET_NAME")),
        clean_text(row.get("STREET_TYPE")), clean_text(row.get("STREET_DIRECTION")),
    ] if part)


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
            addr = canonical_address(raw)
            if addr and addr not in seen:
                seen.add(addr)
                by_address[addr].append(pid)
    return by_apid, by_address


def match_property(row: dict[str, Any], by_apid: dict[str, str], by_address: dict[str, list[str]]) -> tuple[str | None, str]:
    apid = clean_text(row.get("GEO_ID"))
    if apid and apid in by_apid:
        return by_apid[apid], "CURRENT_ADDRESS_POINT_ID"
    addr = canonical_address(row_address(row))
    matches = set(by_address.get(addr, [])) if addr else set()
    if len(matches) == 1:
        return next(iter(matches)), "EXACT_UNIQUE_CIVIC_ADDRESS"
    if len(matches) > 1:
        return None, "AMBIGUOUS_CIVIC_ADDRESS_NOT_PROMOTABLE"
    return None, "UNMATCHED"


def source_rows(resource_id: str) -> dict[str, dict[str, Any]]:
    union: dict[str, dict[str, Any]] = {}
    for q in DISCOVERY_QUERIES:
        for row in fetch_all(resource_id, q):
            union.setdefault(permit_identity(row), row)
    return {identity: row for identity, row in union.items() if has_cooling_tower(description(row))}


def effective_date(row: dict[str, Any], source: str) -> str:
    fields = ("COMPLETED_DATE", "ISSUED_DATE", "APPLICATION_DATE") if source.startswith("cleared") else ("ISSUED_DATE", "APPLICATION_DATE", "COMPLETED_DATE")
    for field in fields:
        value = clean_text(row.get(field))
        if value:
            return value[:10]
    return ""


def current_interpretation(source: str, status: str, lifecycle: str) -> str:
    status_norm = normalize_text(status)
    cancelled = "cancel" in status_norm or "refusal" in status_norm
    if cancelled:
        return "PLANNED_OR_CANCELLED_ONLY_NO_CURRENT_TOWER_INFERENCE"
    if source.startswith("cleared"):
        if lifecycle == "REMOVE_OR_DECOMMISSION_WITH_NON_TOWER_ALTERNATIVE":
            return "HISTORICAL_TOWER_AND_EXPLICIT_REMOVAL_SIGNAL"
        if lifecycle == "REMOVE_OR_DECOMMISSION_COOLING_TOWER_UNCLEAR_REPLACEMENT":
            return "HISTORICAL_TOWER_REMOVAL_SIGNAL_CURRENT_STATE_UNCERTAIN"
        if lifecycle in {"REPLACE_COOLING_TOWER", "INSTALL_OR_ADD_COOLING_TOWER"}:
            return "COMPLETED_TOWER_INSTALL_OR_REPLACEMENT_SIGNAL_SUBJECT_TO_LATER_LIFECYCLE"
        if lifecycle in {"REPAIR_OR_MODIFY_COOLING_TOWER", "EXISTING_COOLING_TOWER_WORK_UNCLEAR"}:
            return "HISTORICAL_EXISTING_TOWER_SIGNAL_SUBJECT_TO_LATER_LIFECYCLE"
        return "HISTORICAL_TOWER_MENTION_CURRENT_STATE_UNCERTAIN"
    if lifecycle == "REMOVE_OR_DECOMMISSION_WITH_NON_TOWER_ALTERNATIVE":
        return "ACTIVE_REMOVAL_OR_DECOMMISSION_SIGNAL_CURRENT_STATE_IN_TRANSITION"
    if lifecycle == "REMOVE_OR_DECOMMISSION_COOLING_TOWER_UNCLEAR_REPLACEMENT":
        return "ACTIVE_REMOVAL_SIGNAL_CURRENT_STATE_IN_TRANSITION"
    if lifecycle == "REPLACE_COOLING_TOWER":
        return "ACTIVE_EXISTING_AND_REPLACEMENT_TOWER_SIGNAL"
    if lifecycle == "INSTALL_OR_ADD_COOLING_TOWER":
        return "ACTIVE_PLANNED_OR_IN_PROGRESS_TOWER_INSTALLATION_SIGNAL"
    if lifecycle in {"REPAIR_OR_MODIFY_COOLING_TOWER", "EXISTING_COOLING_TOWER_WORK_UNCLEAR"}:
        return "ACTIVE_EXISTING_TOWER_WORK_SIGNAL"
    return "ACTIVE_TOWER_MENTION_CURRENT_STATE_UNCERTAIN"


def summarize(source: str, resource_id: str, by_apid: dict[str, str], by_address: dict[str, list[str]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = source_rows(resource_id)
    lifecycle_counts = Counter()
    interpretation_counts = Counter()
    status_counts = Counter()
    match_counts = Counter()
    matched_properties: set[str] = set()
    records: list[dict[str, Any]] = []
    for identity, row in sorted(rows.items()):
        text = description(row)
        lifecycle, reasons = classify_lifecycle(text)
        status = clean_text(row.get("STATUS"))
        interpretation = current_interpretation(source, status, lifecycle)
        pid, match_basis = match_property(row, by_apid, by_address)
        lifecycle_counts[lifecycle] += 1
        interpretation_counts[interpretation] += 1
        status_counts[status or "UNKNOWN"] += 1
        match_counts[match_basis] += 1
        if pid:
            matched_properties.add(pid)
        records.append({
            "source": source,
            "permit_identity": identity,
            "property_id": pid,
            "match_basis": match_basis,
            "address": row_address(row),
            "geo_id": clean_text(row.get("GEO_ID")) or None,
            "permit_type": clean_text(row.get("PERMIT_TYPE")) or None,
            "work": clean_text(row.get("WORK")) or None,
            "status": status or None,
            "effective_date": effective_date(row, source) or None,
            "application_date": clean_text(row.get("APPLICATION_DATE")) or None,
            "issued_date": clean_text(row.get("ISSUED_DATE")) or None,
            "completed_date": clean_text(row.get("COMPLETED_DATE")) or None,
            "lifecycle_class": lifecycle,
            "lifecycle_reasons": reasons,
            "current_interpretation": interpretation,
            "description": text,
        })
    return {
        "cooling_tower_permit_rows": len(records),
        "matched_rows": sum(count for basis, count in match_counts.items() if basis in {"CURRENT_ADDRESS_POINT_ID", "EXACT_UNIQUE_CIVIC_ADDRESS"}),
        "matched_properties": len(matched_properties),
        "match_basis_counts": dict(sorted(match_counts.items())),
        "lifecycle_counts": dict(sorted(lifecycle_counts.items())),
        "current_interpretation_counts": dict(sorted(interpretation_counts.items())),
        "status_counts": dict(status_counts.most_common()),
    }, records


def property_timeline(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_property: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        pid = record.get("property_id")
        if pid:
            by_property[str(pid)].append(record)
    timelines: list[dict[str, Any]] = []
    for pid, items in by_property.items():
        ordered = sorted(items, key=lambda item: (item.get("effective_date") or "", item.get("source") or "", item.get("permit_identity") or ""))
        latest = ordered[-1]
        timelines.append({
            "property_id": pid,
            "record_count": len(ordered),
            "latest_effective_date": latest.get("effective_date"),
            "latest_source": latest.get("source"),
            "latest_status": latest.get("status"),
            "latest_lifecycle_class": latest.get("lifecycle_class"),
            "latest_current_interpretation": latest.get("current_interpretation"),
            "records": ordered,
        })
    return sorted(timelines, key=lambda item: (item.get("latest_effective_date") or "", item["property_id"]), reverse=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only lifecycle audit of Toronto building permits explicitly mentioning cooling towers")
    parser.add_argument("--output", type=Path, default=Path("toronto-cooling-tower-permit-lifecycle.json"))
    args = parser.parse_args()
    spine = read_json(MARKET / "property_spine.json") or {}
    properties = [row for row in spine.get("properties", []) if isinstance(row, dict)]
    by_apid, by_address = property_indexes(properties)
    summaries: dict[str, Any] = {}
    all_records: list[dict[str, Any]] = []
    for source, resource_id in SOURCES.items():
        summaries[source], records = summarize(source, resource_id, by_apid, by_address)
        all_records.extend(records)
    timelines = property_timeline(all_records)
    report = {
        "schema_version": "toronto-cooling-tower-permit-lifecycle-diagnostic-1.0",
        "status": "PASSED_DIAGNOSTIC",
        "scope": "Read-only lifecycle classification of publisher permit descriptions explicitly mentioning cooling tower(s). Classification does not itself promote TowerSignal tower evidence.",
        "source_identity_contract": "PERMIT_NUM plus REVISION_NUM",
        "sources": summaries,
        "matched_property_timeline_count": len(timelines),
        "property_timelines": timelines,
        "unmatched_records": [record for record in all_records if not record.get("property_id")],
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "sources": summaries,
        "matched_property_timeline_count": len(timelines),
        "latest_timeline_sample": [{key: value for key, value in item.items() if key != "records"} for item in timelines[:20]],
        "unmatched_records": len(report["unmatched_records"]),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
