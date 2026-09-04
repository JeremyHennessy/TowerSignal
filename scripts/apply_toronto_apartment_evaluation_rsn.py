from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from toronto_final_identity_cleanup import iter_records
from toronto_market_common import clean_text, read_json, utc_now, write_json
from toronto_source_identity import find_source_record, stable_source_record_id

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data" / "toronto" / "market" / "current"
WAREHOUSE = ROOT / "data" / "toronto" / "warehouse" / "current" / "open_licensed"
SOURCE_KEY = "apartment_building_evaluation"
RENTSAFE_SOURCE = "rentsafe_registration"

EXPECTED_PROPERTIES = 13380
EXPECTED_TOTAL_LINKS = 40060
EXPECTED_GRAPH_EDGES = 6344
EXPECTED_SOURCE_ROWS = 6252
EXPECTED_EXISTING_SOURCE_LINKS = 5288
EXPECTED_RECOVERIES = 26
EXPECTED_RECOVERY_PROPERTIES = 14
EXPECTED_FINAL_SOURCE_LINKS = 5314
EXPECTED_FINAL_TOTAL_LINKS = 40086
EXPECTED_UNMATCHED = 938
EXPECTED_LINKED_RSN_AGREEMENTS = 4509
EXPECTED_LINKED_RSN_CONFLICTS = 0


def rows() -> list[dict[str, Any]]:
    payload = read_json(WAREHOUSE / "apartment_building_evaluation.json") or {}
    return [row for row in iter_records(payload) if isinstance(row, dict)]


def main() -> None:
    source_rows = rows()
    if len(source_rows) != EXPECTED_SOURCE_ROWS:
        raise RuntimeError(f"Apartment evaluation source drift: expected {EXPECTED_SOURCE_ROWS}, found {len(source_rows)}")

    spine = read_json(MARKET / "property_spine.json") or {}
    properties = [item for item in spine.get("properties", []) if isinstance(item, dict)]
    if len(properties) != EXPECTED_PROPERTIES:
        raise RuntimeError(f"Apartment RSN recovery requires {EXPECTED_PROPERTIES} canonical properties, found {len(properties)}")
    property_ids = {clean_text(item.get("property_id")) for item in properties}
    spine_before = json.dumps(spine, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)

    links_payload = read_json(MARKET / "property_source_links.json") or {}
    links = [item for item in links_payload.get("links", []) if isinstance(item, dict)]
    if len(links) != EXPECTED_TOTAL_LINKS:
        raise RuntimeError(f"Apartment RSN recovery requires {EXPECTED_TOTAL_LINKS} total links, found {len(links)}")
    source_links = [item for item in links if clean_text(item.get("source_key")) == SOURCE_KEY]
    if len(source_links) != EXPECTED_EXISTING_SOURCE_LINKS:
        raise RuntimeError(f"Apartment evaluation baseline drift: expected {EXPECTED_EXISTING_SOURCE_LINKS} links, found {len(source_links)}")

    graph = read_json(MARKET / "entity_graph.json") or {}
    graph_edges = [item for item in graph.get("edges", []) if isinstance(item, dict)]
    if len(graph_edges) != EXPECTED_GRAPH_EDGES:
        raise RuntimeError(f"Apartment RSN recovery requires {EXPECTED_GRAPH_EDGES} graph edges, found {len(graph_edges)}")
    graph_before = json.dumps(graph, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)

    existing_by_stable_id: dict[str, str] = {}
    unresolved_existing: list[dict[str, Any]] = []
    for link in source_links:
        record = find_source_record(SOURCE_KEY, clean_text(link.get("source_record_id")), source_rows)
        if not record:
            unresolved_existing.append(link)
            continue
        stable_id = stable_source_record_id(SOURCE_KEY, record)
        pid = clean_text(link.get("property_id"))
        previous = existing_by_stable_id.get(stable_id)
        if previous and previous != pid:
            raise RuntimeError(f"Apartment source row resolves to conflicting properties: {stable_id}: {previous} vs {pid}")
        existing_by_stable_id[stable_id] = pid
    if unresolved_existing:
        raise RuntimeError(f"Apartment baseline source links failed row resolution: {unresolved_existing[:5]}")
    if len(existing_by_stable_id) != EXPECTED_EXISTING_SOURCE_LINKS:
        raise RuntimeError("Apartment baseline stable source identities are not unique")

    rentsafe_by_rsn: dict[str, set[str]] = defaultdict(set)
    for edge in graph_edges:
        if clean_text(edge.get("source_key")) != RENTSAFE_SOURCE:
            continue
        rsn = clean_text((edge.get("evidence") or {}).get("rsn"))
        pid = clean_text(edge.get("property_id") or edge.get("to_node"))
        if rsn and pid:
            rentsafe_by_rsn[rsn].add(pid)
    ambiguous_rentsafe = {rsn: sorted(pids) for rsn, pids in rentsafe_by_rsn.items() if len(pids) > 1}
    if ambiguous_rentsafe:
        raise RuntimeError(f"RentSafe RSN identity is ambiguous: {list(ambiguous_rentsafe.items())[:5]}")

    linked_agree = 0
    linked_conflict = 0
    for row in source_rows:
        stable_id = stable_source_record_id(SOURCE_KEY, row)
        pid = existing_by_stable_id.get(stable_id)
        if not pid:
            continue
        rsn = clean_text(row.get("RSN"))
        mapped = rentsafe_by_rsn.get(rsn, set()) if rsn else set()
        if not mapped:
            continue
        if mapped == {pid}:
            linked_agree += 1
        else:
            linked_conflict += 1
    if linked_agree != EXPECTED_LINKED_RSN_AGREEMENTS or linked_conflict != EXPECTED_LINKED_RSN_CONFLICTS:
        raise RuntimeError(f"RentSafe/apartment linked-row consistency drift: agree={linked_agree}, conflict={linked_conflict}")

    recoveries: list[dict[str, Any]] = []
    new_links: list[dict[str, Any]] = []
    for index, row in enumerate(source_rows):
        stable_id = stable_source_record_id(SOURCE_KEY, row)
        if stable_id in existing_by_stable_id:
            continue
        rsn = clean_text(row.get("RSN"))
        mapped = rentsafe_by_rsn.get(rsn, set()) if rsn else set()
        if len(mapped) != 1:
            continue
        pid = next(iter(mapped))
        if pid not in property_ids:
            raise RuntimeError(f"RentSafe RSN points to property absent from canonical spine: {rsn}: {pid}")
        new_links.append({
            "property_id": pid,
            "source_key": SOURCE_KEY,
            "source_record_id": stable_id,
            "source_row_index": index,
            "match_basis": "EXACT_SHARED_RENTSAFE_RSN_TO_SOURCE_BACKED_CANONICAL_PROPERTY",
            "source_address": row.get("SITE ADDRESS"),
        })
        recoveries.append({
            "source_row_index": index,
            "source_record_id": stable_id,
            "property_id": pid,
            "rsn": rsn,
            "site_address": row.get("SITE ADDRESS"),
            "year_evaluated": row.get("YEAR EVALUATED"),
            "evaluation_completed_on": row.get("EVALUATION COMPLETED ON"),
            "current_building_eval_score": row.get("CURRENT BUILDING EVAL SCORE"),
        })

    if len(new_links) != EXPECTED_RECOVERIES:
        raise RuntimeError(f"Expected {EXPECTED_RECOVERIES} RSN recoveries, found {len(new_links)}")
    if len({item["property_id"] for item in new_links}) != EXPECTED_RECOVERY_PROPERTIES:
        raise RuntimeError(f"Expected {EXPECTED_RECOVERY_PROPERTIES} RSN recovery properties")

    combined = links + new_links
    identities = [
        (clean_text(item.get("property_id")), clean_text(item.get("source_key")), clean_text(item.get("source_record_id")))
        for item in combined
    ]
    if len(identities) != len(set(identities)):
        raise RuntimeError("Apartment RSN recovery would create duplicate property/source/record identities")
    combined.sort(key=lambda item: (clean_text(item.get("property_id")), clean_text(item.get("source_key")), clean_text(item.get("source_record_id"))))
    if len(combined) != EXPECTED_FINAL_TOTAL_LINKS:
        raise RuntimeError(f"Apartment RSN final total link drift: expected {EXPECTED_FINAL_TOTAL_LINKS}, found {len(combined)}")
    final_source_links = [item for item in combined if clean_text(item.get("source_key")) == SOURCE_KEY]
    if len(final_source_links) != EXPECTED_FINAL_SOURCE_LINKS:
        raise RuntimeError(f"Apartment RSN final source link drift: expected {EXPECTED_FINAL_SOURCE_LINKS}, found {len(final_source_links)}")

    sources = dict(links_payload.get("sources") or {})
    source_meta = dict(sources.get(SOURCE_KEY) or {})
    matched_properties = {clean_text(item.get("property_id")) for item in final_source_links if clean_text(item.get("property_id"))}
    source_meta.update({
        "status": "JOINED_EXACT_ADDRESS_PLUS_SHARED_RENTSAFE_RSN",
        "source_records": EXPECTED_SOURCE_ROWS,
        "matched_records": EXPECTED_FINAL_SOURCE_LINKS,
        "matched_canonical_properties": len(matched_properties),
        "unmatched_source_records": EXPECTED_UNMATCHED,
        "unmatched_records": EXPECTED_UNMATCHED,
        "links_added_by_rentsafe_rsn": EXPECTED_RECOVERIES,
        "rentsafe_rsn_recovery_properties": EXPECTED_RECOVERY_PROPERTIES,
        "rentsafe_linked_row_agreements": EXPECTED_LINKED_RSN_AGREEMENTS,
        "rentsafe_linked_row_conflicts": EXPECTED_LINKED_RSN_CONFLICTS,
        "identity_limitation": "Exact civic-address links remain primary. An additional evaluation row is joined only when its publisher RSN maps through a source-backed RentSafe relationship to exactly one canonical property; no fuzzy address matching is used.",
        "role_semantics": "Apartment evaluation records add property condition/evaluation context only and create no organization role or tower assertion.",
    })
    sources[SOURCE_KEY] = source_meta
    links_payload["generated_at"] = utc_now()
    links_payload["sources"] = sources
    links_payload["links"] = combined
    counts = dict(links_payload.get("counts") or {})
    counts["canonical_properties"] = EXPECTED_PROPERTIES
    counts["total_source_links"] = len(combined)
    counts["properties_with_any_new_link"] = len({clean_text(item.get("property_id")) for item in combined if clean_text(item.get("property_id"))})
    counts["source_family_count"] = len(sources)
    links_payload["counts"] = counts
    write_json(MARKET / "property_source_links.json", links_payload)

    if json.dumps(spine, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str) != spine_before:
        raise RuntimeError("Apartment RSN recovery mutated property spine")
    if json.dumps(graph, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str) != graph_before:
        raise RuntimeError("Apartment RSN recovery mutated entity graph")

    report = {
        "schema_version": "toronto-apartment-evaluation-rsn-recovery-1.0",
        "generated_at": utc_now(),
        "status": "PASSED",
        "source_key": SOURCE_KEY,
        "match_contract": "Unlinked apartment-evaluation rows are promoted only when the publisher RSN is present on a source-backed RentSafe relationship that maps to exactly one canonical Toronto property. Existing linked evaluation rows with a RentSafe RSN must show zero property conflicts.",
        "semantic_contract": "Adds source evidence only. No property identity, tower evidence, ownership, manager, operator, contractor, engineer, or other organization role is created or changed.",
        "metrics": {
            "source_records": EXPECTED_SOURCE_ROWS,
            "baseline_source_links": EXPECTED_EXISTING_SOURCE_LINKS,
            "baseline_total_links": EXPECTED_TOTAL_LINKS,
            "baseline_properties": EXPECTED_PROPERTIES,
            "baseline_graph_edges": EXPECTED_GRAPH_EDGES,
            "linked_rsn_agreements": linked_agree,
            "linked_rsn_conflicts": linked_conflict,
            "rentsafe_ambiguous_rsn": len(ambiguous_rentsafe),
            "recovered_rows": len(new_links),
            "recovered_properties": len({item["property_id"] for item in new_links}),
            "final_source_links": len(final_source_links),
            "final_total_links": len(combined),
            "remaining_unmatched_rows": EXPECTED_UNMATCHED,
            "property_spine_changes": 0,
            "relationship_edge_changes": 0,
            "tower_status_promotions": 0,
        },
        "recoveries": recoveries,
    }
    write_json(MARKET / "apartment_evaluation_rsn_recovery_report.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
