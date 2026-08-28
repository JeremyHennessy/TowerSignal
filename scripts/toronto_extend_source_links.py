from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from toronto_final_identity_cleanup import canonical_address, iter_records, record_addresses
from toronto_market_common import clean_text, read_json, utc_now, write_json

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data" / "toronto" / "market" / "current"
WAREHOUSE = ROOT / "data" / "toronto" / "warehouse" / "current"

EXTENDED_SOURCES = [
    ("development_pipeline", WAREHOUSE / "open_licensed/development_pipeline.json"),
    ("apartment_building_evaluation", WAREHOUSE / "open_licensed/apartment_building_evaluation.json"),
    ("ontario_bps_energy_2024", WAREHOUSE / "open_licensed/ontario_bps_energy_2024.json"),
    ("affordable_housing_pipeline", WAREHOUSE / "open_licensed/affordable_housing_pipeline.json"),
    ("renewable_energy_installations", WAREHOUSE / "open_licensed/renewable_energy_installations.json"),
    ("capital_project_pipeline", WAREHOUSE / "open_licensed/capital_project_pipeline.json"),
    ("chemtrac_2024", WAREHOUSE / "open_licensed/chemtrac_2024.json"),
    ("business_licence_matches_prior_poc", WAREHOUSE / "business_licence_matches.json"),
    ("311_matches_prior_poc", WAREHOUSE / "311_matches.json"),
]


def main() -> None:
    spine = read_json(MARKET / "property_spine.json") or {}
    link_payload = read_json(MARKET / "property_source_links.json") or {}
    props = [p for p in spine.get("properties", []) if isinstance(p, dict)]
    if not props:
        raise RuntimeError("property spine missing")

    by_addr: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for prop in props:
        by_addr[canonical_address(prop.get("display_address") or prop.get("canonical_address"))].append(prop)

    links = [l for l in link_payload.get("links", []) if isinstance(l, dict)]
    existing = {(l.get("property_id"), l.get("source_key"), l.get("source_record_id")) for l in links}
    sources = dict(link_payload.get("sources") or {})
    extension_report: dict[str, Any] = {}

    for source, path in EXTENDED_SOURCES:
        payload = read_json(path)
        if payload is None:
            extension_report[source] = {"status": "SOURCE_FILE_MISSING"}
            continue
        records = list(iter_records(payload))
        rows_with_address = 0
        matched_rows = 0
        matched_props: set[str] = set()
        ambiguous_rows = 0
        added = 0
        for idx, rec in enumerate(records):
            addresses = record_addresses(rec)
            rows_with_address += bool(addresses)
            row_matched = False
            for address in addresses:
                matches = by_addr.get(canonical_address(address), [])
                if len(matches) > 1:
                    ambiguous_rows += 1
                    continue
                if len(matches) != 1:
                    continue
                prop = matches[0]
                rid = next((rec.get(k) for k in ("_id", "OBJECTID", "id", "APPLICATION_NUMBER", "FOLDERRSN", "RSN", "document_number", "noticeId") if rec.get(k) not in (None, "")), None)
                source_record_id = f"{source}:{rid if rid is not None else idx}"
                key = (prop["property_id"], source, source_record_id)
                if key not in existing:
                    links.append({
                        "property_id": prop["property_id"],
                        "source_key": source,
                        "source_record_id": source_record_id,
                        "source_row_index": idx,
                        "match_basis": "EXACT_CORRECTED_CANONICAL_PROPERTY_ADDRESS_TO_ADDRESS_POINT_SPINE",
                        "source_address": address,
                    })
                    existing.add(key)
                    added += 1
                matched_props.add(prop["property_id"])
                row_matched = True
                break
            matched_rows += row_matched
        summary = {
            "status": "JOINED",
            "source_records": len(records),
            "records_with_property_address": rows_with_address,
            "matched_records": matched_rows,
            "matched_canonical_properties": len(matched_props),
            "ambiguous_address_rows_not_forced": ambiguous_rows,
            "links_added": added,
            "identity_limitation": None if rows_with_address else "NO_DETERMINISTIC_PROPERTY_ADDRESS_EXTRACTED_FROM_PERSISTED_SOURCE_FILE",
        }
        sources[source] = summary
        extension_report[source] = summary

    # Remap the previously reviewed POC-level document-text joins for TOBids and
    # Toronto Public Notices by the POC property's exact current civic address.
    old = read_json(WAREHOUSE / "property_joins.json") or {}
    remap_sources = {
        "tobids_awarded_contracts": "tobids_awarded_contracts_exact_document_address_prior_poc",
        "capital_project_pipeline": "capital_project_pipeline_exact_document_address_prior_poc",
    }
    remap_counts: dict[str, Any] = {}
    for old_key, new_key in remap_sources.items():
        added = 0
        matched_props: set[str] = set()
        row_count = 0
        for item in old.get("properties", []) or []:
            matches = by_addr.get(canonical_address(item.get("address")), [])
            if len(matches) != 1:
                continue
            prop = matches[0]
            rows = (item.get("matches") or {}).get(old_key, []) or []
            for idx, rec in enumerate(rows):
                if not isinstance(rec, dict):
                    continue
                row_count += 1
                rid = rec.get("document_number") or rec.get("id") or f"{clean_text(item.get('property_key'))}:{idx}"
                source_record_id = f"{new_key}:{rid}"
                key = (prop["property_id"], new_key, source_record_id)
                if key in existing:
                    continue
                links.append({
                    "property_id": prop["property_id"],
                    "source_key": new_key,
                    "source_record_id": source_record_id,
                    "match_basis": "PREVIOUSLY_VALIDATED_EXACT_PROPERTY_ADDRESS_TOKEN_IN_DOCUMENT_TEXT_REMAPPED_TO_CURRENT_ADDRESS_POINT",
                    "source_address": item.get("address"),
                })
                existing.add(key)
                matched_props.add(prop["property_id"])
                added += 1
        summary = {
            "status": "JOINED_FROM_PREVIOUSLY_VALIDATED_POC_DOCUMENT_MATCHES",
            "matched_records": row_count,
            "matched_canonical_properties": len(matched_props),
            "links_added": added,
            "scope_limitation": "This retains only the earlier exact POC document-address matches; it does not claim a citywide document-address extraction from all award/capital text.",
        }
        sources[new_key] = summary
        remap_counts[new_key] = summary

    # Public-notice prior POC matches carry explicit matched canonical addresses.
    notices = read_json(WAREHOUSE / "open_licensed/toronto_public_notices.json") or {}
    notice_added = 0
    notice_props: set[str] = set()
    for idx, match in enumerate(notices.get("poc_matches", []) or []):
        if not isinstance(match, dict):
            continue
        for address in match.get("matched_canonical_addresses", []) or []:
            matches = by_addr.get(canonical_address(address), [])
            if len(matches) != 1:
                continue
            prop = matches[0]
            rid = match.get("noticeId") or idx
            source_record_id = f"toronto_public_notices_exact_prior_poc:{rid}"
            key = (prop["property_id"], "toronto_public_notices_exact_prior_poc", source_record_id)
            if key in existing:
                continue
            links.append({
                "property_id": prop["property_id"],
                "source_key": "toronto_public_notices_exact_prior_poc",
                "source_record_id": source_record_id,
                "match_basis": "EXPLICIT_NOTICE_ADDRESS_LIST_EXACT_MATCH_REMAPPED_TO_CURRENT_ADDRESS_POINT",
                "source_address": address,
            })
            existing.add(key)
            notice_props.add(prop["property_id"])
            notice_added += 1
    notice_summary = {
        "status": "JOINED_FROM_EXPLICIT_NOTICE_ADDRESS_LIST",
        "matched_records": notice_added,
        "matched_canonical_properties": len(notice_props),
        "links_added": notice_added,
    }
    sources["toronto_public_notices_exact_prior_poc"] = notice_summary
    remap_counts["toronto_public_notices_exact_prior_poc"] = notice_summary

    links.sort(key=lambda l: (str(l.get("property_id")), str(l.get("source_key")), str(l.get("source_record_id"))))
    link_payload["schema_version"] = "toronto-market-property-links-1.2"
    link_payload["generated_at"] = utc_now()
    link_payload["sources"] = sources
    link_payload["links"] = links
    link_payload["counts"] = {
        "canonical_properties": len(props),
        "total_source_links": len(links),
        "properties_with_any_new_link": len({l.get("property_id") for l in links}),
        "source_family_count": len(sources),
    }
    link_payload["extension_contract"] = {
        "structured_sources": "Exact corrected civic-address equality to one unique current Address Point only.",
        "prior_document_matches": "Previously validated POC document-address matches are preserved and remapped to current Address Point IDs; no new fuzzy document matching is introduced.",
        "tower_semantics": "These context links never create or upgrade cooling-tower confirmation.",
    }
    write_json(MARKET / "property_source_links.json", link_payload)
    report = {
        "schema_version": "toronto-source-link-extension-1.0",
        "generated_at": utc_now(),
        "total_links_after_extension": len(links),
        "properties_with_any_link": len({l.get("property_id") for l in links}),
        "structured_extensions": extension_report,
        "prior_document_match_extensions": remap_counts,
    }
    write_json(MARKET / "source_link_extension_report.json", report)
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
