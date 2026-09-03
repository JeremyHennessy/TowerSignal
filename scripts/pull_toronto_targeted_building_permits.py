from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from toronto_final_identity_cleanup import address_point_root, canonical_address, load_address_points
from toronto_market_common import clean_text, request_json, utc_now, write_json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/toronto/warehouse/current/open_licensed"
SEARCH_ENDPOINT = "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/datastore_search"

SOURCE_CONFIG = {
    "toronto_building_permits_active_targeted": {
        "resource_id": "6d0229af-bc54-46de-9c2b-26759b01dd05",
        "title": "Building Permits - Active Permits",
        "portal_url": "https://open.toronto.ca/dataset/building-permits-active-permits/",
        "snapshot": OUT / "toronto_building_permits_active_targeted.json",
        "lifecycle": "ACTIVE",
    },
    "toronto_building_permits_cleared_targeted_since_2017": {
        "resource_id": "a96c0ba4-3026-402b-b09d-5b1268b8f810",
        "title": "Building Permits - Cleared Permits Since 2017",
        "portal_url": "https://open.toronto.ca/dataset/building-permits-cleared-permits/",
        "snapshot": OUT / "toronto_building_permits_cleared_targeted_since_2017.json",
        "lifecycle": "CLEARED_SINCE_2017",
    },
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

EXPECTED = {
    "toronto_building_permits_active_targeted": {"targeted_rows": 573, "resolved_rows": 540, "unresolved_rows": 33},
    "toronto_building_permits_cleared_targeted_since_2017": {"targeted_rows": 721, "resolved_rows": 704, "unresolved_rows": 17},
}
EXPECTED_UNION_RESOLVED_PROPERTIES = 684
EXPECTED_UNION_NEW_PROPERTIES = 306

NON_TOWER_ALTERNATIVES = (
    "air source heat pump",
    "air source heat pumps",
    "dry cooler",
    "dry coolers",
    "air cooled chiller",
    "air-cooled chiller",
)


def search(resource_id: str, query: str, limit: int = 1000, offset: int = 0) -> dict[str, Any]:
    payload = request_json(
        f"{SEARCH_ENDPOINT}?{urlencode({'resource_id': resource_id, 'q': query, 'limit': limit, 'offset': offset})}",
        timeout=180,
    )
    if payload.get("success") is not True:
        raise RuntimeError(f"Toronto CKAN datastore_search failed for resource={resource_id}, query={query}")
    result = payload.get("result") or {}
    if not isinstance(result, dict):
        raise RuntimeError("Unexpected Toronto CKAN datastore_search response")
    return result


def fetch_query_rows(resource_id: str, query: str) -> tuple[int, list[dict[str, Any]]]:
    first = search(resource_id, query)
    total = int(first.get("total") or 0)
    rows = [row for row in first.get("records", []) if isinstance(row, dict)]
    offset = len(rows)
    while offset < total:
        result = search(resource_id, query, offset=offset)
        batch = [row for row in result.get("records", []) if isinstance(row, dict)]
        if not batch:
            break
        rows.extend(batch)
        offset += len(batch)
    if len(rows) != total:
        raise RuntimeError(f"Toronto permit pagination mismatch for {query}: expected {total}, found {len(rows)}")
    return total, rows


def permit_identity(row: dict[str, Any]) -> str:
    permit_num = clean_text(row.get("PERMIT_NUM"))
    revision = clean_text(row.get("REVISION_NUM")) or "00"
    if not permit_num:
        raise RuntimeError("Targeted permit row missing PERMIT_NUM")
    return f"{permit_num}::{revision}"


def source_address(row: dict[str, Any]) -> str:
    return " ".join(
        part for part in [
            clean_text(row.get("STREET_NUM")),
            clean_text(row.get("STREET_NAME")),
            clean_text(row.get("STREET_TYPE")),
            clean_text(row.get("STREET_DIRECTION")),
        ] if part
    )


def signal_keys(row: dict[str, Any]) -> list[str]:
    description = clean_text(row.get("DESCRIPTION")).lower()
    return [key for key, term in SIGNALS.items() if term in description]


def normalize_text(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def classify_cooling_tower_lifecycle(text: str) -> tuple[str, list[str]]:
    norm = normalize_text(text)
    reasons: list[str] = []
    remove = bool(re.search(r"\b(remove|removal|decommission|demolish|demolition)\w*\b.{0,100}\bcooling towers?\b|\bcooling towers?\b.{0,100}\b(remove|removal|decommission|demolish|demolition)\w*\b", norm))
    install = bool(re.search(r"\b(install|installation|new|provide|addition)\w*\b.{0,100}\bcooling towers?\b|\bcooling towers?\b.{0,100}\b(install|installation|new|provide|addition)\w*\b", norm))
    replace = bool(re.search(r"\b(replace|replacement|replacing)\w*\b.{0,100}\bcooling towers?\b|\bcooling towers?\b.{0,100}\b(replace|replacement|replacing)\w*\b", norm))
    repair = bool(re.search(r"\b(repair|upgrade|refurbish|rehabilitat|motor|vfd|fan|support)\w*\b.{0,100}\bcooling towers?\b|\bcooling towers?\b.{0,100}\b(repair|upgrade|refurbish|rehabilitat|motor|vfd|fan|support)\w*\b", norm))
    existing = bool(re.search(r"\bexisting\b.{0,100}\bcooling towers?\b|\bcooling towers?\b.{0,100}\bexisting\b", norm))
    alternative = any(term in norm for term in NON_TOWER_ALTERNATIVES)
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


def current_interpretation(source_lifecycle: str, status: str, lifecycle: str) -> str:
    status_norm = normalize_text(status)
    if "cancel" in status_norm or "refusal" in status_norm:
        return "PLANNED_OR_CANCELLED_ONLY_NO_CURRENT_TOWER_INFERENCE"
    if source_lifecycle == "CLEARED_SINCE_2017":
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


def discover_targeted_rows(resource_id: str) -> tuple[dict[str, int], list[dict[str, Any]]]:
    discovered: dict[str, dict[str, Any]] = {}
    query_totals: dict[str, int] = {}
    for query in DISCOVERY_QUERIES:
        total, rows = fetch_query_rows(resource_id, query)
        query_totals[query] = total
        for row in rows:
            discovered.setdefault(permit_identity(row), row)
    targeted = [row for row in discovered.values() if signal_keys(row)]
    targeted.sort(key=permit_identity)
    return query_totals, targeted


def resolve_permit(row: dict[str, Any], by_id: dict[str, dict[str, Any]], by_address: dict[str, list[dict[str, Any]]]) -> tuple[dict[str, Any] | None, str, bool]:
    permit_apid = clean_text(row.get("GEO_ID"))
    permit_address = canonical_address(source_address(row))
    conflict = False
    if permit_apid and permit_apid in by_id:
        municipal = by_id[permit_apid]
        root = address_point_root(municipal, by_id)
        municipal_address = canonical_address(municipal.get("address"))
        root_address = canonical_address(root.get("address"))
        if permit_address and permit_address == root_address:
            return root, "PERMIT_GEO_ID_TO_CURRENT_ADDRESS_POINT_ROOT_WITH_EXACT_CIVIC_ADDRESS", False
        if permit_address and permit_address == municipal_address and municipal.get("address_point_id") != root.get("address_point_id"):
            return root, "PERMIT_GEO_ID_LINKED_TO_ROOT_SOURCE_ADDRESS_MATCHES_CHILD", False
        conflict = True
    if permit_address:
        roots: dict[str, dict[str, Any]] = {}
        for candidate in by_address.get(permit_address, []):
            root = address_point_root(candidate, by_id)
            root_id = clean_text(root.get("address_point_id"))
            if root_id:
                roots[root_id] = root
        if len(roots) == 1:
            return next(iter(roots.values())), "EXACT_UNIQUE_CIVIC_ADDRESS_TO_CURRENT_ADDRESS_POINT_ROOT", conflict
        if len(roots) > 1:
            return None, "AMBIGUOUS_CURRENT_ADDRESS_POINT_ROOTS_NOT_FORCED", conflict
    return None, "NO_CURRENT_ADDRESS_POINT_IDENTITY", conflict


def enrich_row(row: dict[str, Any], source_lifecycle: str, root: dict[str, Any] | None, basis: str, conflict: bool) -> dict[str, Any]:
    output = dict(row)
    signals = signal_keys(row)
    description = clean_text(row.get("DESCRIPTION"))
    output.update({
        "_towersignal_permit_identity": permit_identity(row),
        "_towersignal_signals": signals,
        "_towersignal_source_lifecycle": source_lifecycle,
        "_towersignal_source_address": source_address(row),
        "_towersignal_resolution_status": basis,
        "_towersignal_permit_geo_id_address_conflict": conflict,
        "_towersignal_root_address_point_id": root.get("address_point_id") if root else None,
        "_towersignal_root_address_id": root.get("address_id") if root else None,
        "_towersignal_root_address": root.get("address") if root else None,
        "_towersignal_root_longitude": root.get("lon") if root else None,
        "_towersignal_root_latitude": root.get("lat") if root else None,
        "_towersignal_root_status": root.get("status") if root else None,
    })
    if "cooling_tower" in signals:
        lifecycle, reasons = classify_cooling_tower_lifecycle(description)
        output["_towersignal_cooling_tower_lifecycle"] = lifecycle
        output["_towersignal_cooling_tower_lifecycle_reasons"] = reasons
        output["_towersignal_cooling_tower_current_interpretation"] = current_interpretation(
            source_lifecycle,
            clean_text(row.get("STATUS")),
            lifecycle,
        )
    else:
        output["_towersignal_cooling_tower_lifecycle"] = None
        output["_towersignal_cooling_tower_lifecycle_reasons"] = []
        output["_towersignal_cooling_tower_current_interpretation"] = None
    return output


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    by_id, by_address, scanned = load_address_points()
    current_spine_path = ROOT / "data/toronto/market/current/property_spine.json"
    current_spine = json.loads(current_spine_path.read_text(encoding="utf-8"))
    current_apids = {
        clean_text(item.get("address_point_id"))
        for item in current_spine.get("properties", [])
        if isinstance(item, dict) and clean_text(item.get("address_point_id"))
    }

    union_resolved: set[str] = set()
    union_new: set[str] = set()
    summaries: dict[str, Any] = {}
    for source_key, config in SOURCE_CONFIG.items():
        query_totals, rows = discover_targeted_rows(config["resource_id"])
        enriched: list[dict[str, Any]] = []
        basis_counts = Counter()
        conflict_rows = 0
        resolved_rows = 0
        resolved_properties: set[str] = set()
        new_properties: set[str] = set()
        signal_counts = Counter()
        for row in rows:
            root, basis, conflict = resolve_permit(row, by_id, by_address)
            basis_counts[basis] += 1
            conflict_rows += int(conflict)
            for signal in signal_keys(row):
                signal_counts[signal] += 1
            if root is not None:
                resolved_rows += 1
                apid = clean_text(root.get("address_point_id"))
                resolved_properties.add(apid)
                union_resolved.add(apid)
                if apid not in current_apids:
                    new_properties.add(apid)
                    union_new.add(apid)
            enriched.append(enrich_row(row, config["lifecycle"], root, basis, conflict))

        expected = EXPECTED[source_key]
        actual = {
            "targeted_rows": len(rows),
            "resolved_rows": resolved_rows,
            "unresolved_rows": len(rows) - resolved_rows,
        }
        if actual != expected:
            raise RuntimeError(f"Toronto permit live source drift for {source_key}: expected {expected}, found {actual}")
        if len({permit_identity(row) for row in enriched}) != len(enriched):
            raise RuntimeError(f"Duplicate permit identity in {source_key} snapshot")

        snapshot = {
            "metadata": {
                "schema_version": "toronto-targeted-building-permits-1.0",
                "source_key": source_key,
                "title": config["title"],
                "portal_url": config["portal_url"],
                "resource_id": config["resource_id"],
                "license": "Open Government Licence - Toronto",
                "retrieved_at": utc_now(),
                "identity_contract": "PERMIT_NUM plus REVISION_NUM",
                "discovery_queries": list(DISCOVERY_QUERIES),
                "exact_signal_terms": SIGNALS,
                "source_lifecycle": config["lifecycle"],
                "targeted_row_count": len(enriched),
                "resolved_row_count": resolved_rows,
                "unresolved_row_count": len(enriched) - resolved_rows,
                "resolved_property_count": len(resolved_properties),
                "new_property_count": len(new_properties),
                "geo_id_address_conflict_rows": conflict_rows,
                "resolution_basis_counts": dict(sorted(basis_counts.items())),
                "signal_row_counts": dict(sorted(signal_counts.items())),
                "address_point_rows_scanned": scanned,
                "tower_status_policy": "Permit records are source evidence only in this apply; no TowerSignal tower_evidence_status is automatically promoted.",
                "builder_role_policy": "BUILDER_NAME is retained as a raw source field only; no contractor relationship is inferred.",
            },
            "rows": enriched,
        }
        write_json(config["snapshot"], snapshot)
        summaries[source_key] = actual | {
            "resolved_properties": len(resolved_properties),
            "new_properties": len(new_properties),
            "geo_id_address_conflict_rows": conflict_rows,
        }

    if len(union_resolved) != EXPECTED_UNION_RESOLVED_PROPERTIES:
        raise RuntimeError(f"Permit resolved-property union drift: expected {EXPECTED_UNION_RESOLVED_PROPERTIES}, found {len(union_resolved)}")
    if len(union_new) != EXPECTED_UNION_NEW_PROPERTIES:
        raise RuntimeError(f"Permit new-property union drift: expected {EXPECTED_UNION_NEW_PROPERTIES}, found {len(union_new)}")

    print(json.dumps({
        "status": "TARGETED_PERMIT_SNAPSHOTS_WRITTEN",
        "sources": summaries,
        "union_resolved_properties": len(union_resolved),
        "union_new_properties": len(union_new),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
