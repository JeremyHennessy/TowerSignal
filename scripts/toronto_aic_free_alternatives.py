from __future__ import annotations

import hashlib
import html
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from toronto_market_common import clean_text, read_json, utc_now, write_json
try:
    from .toronto_source_identity import find_source_record, stable_source_record_id
except ImportError:
    from toronto_source_identity import find_source_record, stable_source_record_id


ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data" / "toronto" / "market" / "current"
WAREHOUSE = ROOT / "data" / "toronto" / "warehouse" / "current"
SOURCE_KEY = "toronto_public_notices_exact_prior_poc"

TERMS = (
    "cooling tower", "cooling towers", "evaporative condenser", "evaporative cooling",
    "condenser water", "cooling water", "chiller", "chillers", "cooling plant",
    "central plant", "mechanical penthouse", "water treatment", "legionella",
    "tower replacement", "tower installation", "marley", "baltimore aircoil", "evapco",
)


def normalize_application_number(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", clean_text(value).upper())


def plain_text(value: Any) -> str:
    raw = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", html.unescape(raw)).strip()


def snippets(text: str, term: str, radius: int = 120) -> list[str]:
    lowered = text.lower()
    output: list[str] = []
    start = 0
    while len(output) < 3:
        index = lowered.find(term, start)
        if index < 0:
            break
        left = max(0, index - radius)
        right = min(len(text), index + len(term) + radius)
        output.append(text[left:right].strip())
        start = index + len(term)
    return output


def main() -> None:
    applications_payload = read_json(MARKET / "open_licensed/toronto_aic_applications.json") or {}
    applications = applications_payload.get("applications") or []
    notices_payload = read_json(WAREHOUSE / "open_licensed/toronto_public_notices.json") or {}
    notices = notices_payload.get("planning_notices") or []
    links_payload = read_json(MARKET / "property_source_links.json") or {}
    links = [item for item in links_payload.get("links", []) if isinstance(item, dict)]
    if not applications or not notices or not links:
        raise RuntimeError("AIC catalogue, public notices, and property links are required")

    # Reuse the already validated AIC row-to-property joins, then join public
    # notices by exact normalized municipal application number.
    app_properties: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for link in links:
        if link.get("source_key") != "toronto_aic_applications":
            continue
        row = find_source_record("toronto_aic_applications", clean_text(link.get("source_record_id")), applications)
        if not row:
            continue
        number = normalize_application_number(row.get("APPLICATION_NUMBER"))
        pid = clean_text(link.get("property_id"))
        if number and pid:
            app_properties[number][pid].add(clean_text(row.get("FULL_ADDRESS") or link.get("source_address")))

    existing = {(str(item.get("property_id")), str(item.get("source_key")), str(item.get("source_record_id"))) for item in links}
    linked_notice_ids: set[str] = set()
    linked_application_numbers: set[str] = set()
    linked_property_ids: set[str] = set()
    links_added = 0
    index_records: list[dict[str, Any]] = []
    signal_records = 0
    tower_term_records = 0

    for notice in notices:
        if not isinstance(notice, dict):
            continue
        notice_id = clean_text(notice.get("noticeId"))
        numbers = [normalize_application_number(value) for value in (notice.get("planningApplicationNumbers") or [])]
        numbers = [value for value in numbers if value]
        property_addresses: dict[str, set[str]] = defaultdict(set)
        for number in numbers:
            for pid, addresses in app_properties.get(number, {}).items():
                property_addresses[pid].update(addresses)
                linked_application_numbers.add(number)
        if not property_addresses:
            continue
        linked_notice_ids.add(notice_id)
        linked_property_ids.update(property_addresses)
        record_id = stable_source_record_id(SOURCE_KEY, notice)
        for pid, addresses in property_addresses.items():
            key = (pid, SOURCE_KEY, record_id)
            if key in existing:
                continue
            links.append({
                "property_id": pid,
                "source_key": SOURCE_KEY,
                "source_record_id": record_id,
                "match_basis": "EXACT_NORMALIZED_PUBLIC_NOTICE_APPLICATION_NUMBER_TO_DETERMINISTIC_AIC_PROPERTY_LINK",
                "source_address": sorted(address for address in addresses if address)[0] if addresses else None,
            })
            existing.add(key)
            links_added += 1

        text = plain_text(notice.get("noticeDescription"))
        counts = {term: text.lower().count(term) for term in TERMS if term in text.lower()}
        excerpts = {term: snippets(text, term) for term in counts}
        if counts:
            signal_records += 1
        if counts.get("cooling tower") or counts.get("cooling towers"):
            tower_term_records += 1
        index_records.append({
            "notice_id": notice_id,
            "title": clean_text(notice.get("title")),
            "notice_date_epoch_ms": notice.get("noticeDate"),
            "application_numbers": [clean_text(value) for value in (notice.get("planningApplicationNumbers") or []) if clean_text(value)],
            "property_ids": sorted(property_addresses),
            "record_url": f"https://secure.toronto.ca/nm/api/individual/notice/{notice_id}.do",
            "background_documents": [item for item in (notice.get("backgroundInformationList") or []) if isinstance(item, dict)],
            "notice_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "notice_text_chars": len(text),
            "matching_terms": counts,
            "relevant_excerpts": excerpts,
            "evidence_class": "PUBLIC_NOTICE_CONTEXT_NOT_AIC_SUPPORTING_DOCUMENT",
        })

    links.sort(key=lambda item: (str(item.get("property_id")), str(item.get("source_key")), str(item.get("source_record_id"))))
    all_notice_links = [item for item in links if item.get("source_key") == SOURCE_KEY]
    all_linked_notice_ids = {str(item.get("source_record_id") or "").rsplit(":", 1)[-1] for item in all_notice_links}
    all_linked_property_ids = {str(item.get("property_id")) for item in all_notice_links if item.get("property_id")}
    source_summary = {
        "status": "JOINED_PUBLIC_NOTICE_TEXT_BY_EXACT_APPLICATION_NUMBER",
        "source_records": len(notices),
        "records_with_property_address": sum(bool(item.get("addressList")) for item in notices if isinstance(item, dict)),
        "matched_records": len(all_linked_notice_ids),
        "matched_canonical_properties": len(all_linked_property_ids),
        "application_number_matched_records": len(linked_notice_ids),
        "application_number_matched_properties": len(linked_property_ids),
        "matched_application_numbers": len(linked_application_numbers),
        "property_links": len(all_notice_links),
        "links_added_by_application_number": links_added,
        "identity_limitation": "Only exact public-notice application numbers already joined through the deterministic AIC property spine are linked; no text/address fuzzy match is used.",
    }
    links_payload["links"] = links
    links_payload.setdefault("sources", {})[SOURCE_KEY] = source_summary
    links_payload.setdefault("counts", {})["total_source_links"] = len(links)
    links_payload["counts"]["properties_with_any_new_link"] = len({item.get("property_id") for item in links})
    links_payload["counts"]["source_family_count"] = len(links_payload.get("sources") or {})
    links_payload["generated_at"] = utc_now()
    write_json(MARKET / "property_source_links.json", links_payload)

    alternatives = {
        "schema_version": "toronto-aic-free-alternatives-1.0",
        "generated_at": utc_now(),
        "status": "PARTIAL_OPEN_PUBLIC_NOTICE_CORPUS_AVAILABLE_SUPPORTING_DOCUMENTS_STILL_BLOCKED",
        "paths": [
            {
                "path": "Development Applications open data",
                "url": "https://open.toronto.ca/dataset/development-applications/",
                "status": "OPEN_REUSE_METADATA_ONLY",
                "result": "Catalogue/application metadata is reusable under the Toronto Open Government Licence, but this source does not expose the AIC supporting-document attachment corpus.",
            },
            {
                "path": "City Clerk Public Notices open data and background notice artifacts",
                "url": "https://open.toronto.ca/dataset/public-notices/",
                "status": "OPEN_REUSE_INGESTED",
                "result": f"{len(linked_notice_ids)} planning notices were linked to {len(linked_property_ids)} canonical properties through exact application numbers. Notice text is contextual evidence only.",
            },
            {
                "path": "Active and cleared building permits open data",
                "url": "https://open.toronto.ca/dataset/building-permits-active-permits/",
                "status": "OPEN_REUSE_METADATA_AVAILABLE",
                "result": "Permit records are a lawful addressable enrichment source, but they are not copies of AIC mechanical drawings, schedules, energy, planning, or acoustic reports.",
                "companion_url": "https://open.toronto.ca/dataset/building-permits-cleared-permits/",
            },
            {
                "path": "Council/committee planning repositories",
                "url": "https://secure.toronto.ca/council/#/committees",
                "status": "MANUAL_OR_TARGETED_REVIEW_ONLY",
                "result": "Meeting reports and attachments can support selected application review, but no complete deterministic AIC attachment mirror was identified.",
            },
            {
                "path": "Current AIC application search",
                "url": "https://www.toronto.ca/city-government/planning-development/application-information-centre/",
                "status": "MANUAL_REVIEW_ONLY_FOR_ATTACHMENTS",
                "result": "The current public application search remains usable by a reviewer; automated attachments remain reCAPTCHA-gated and were not bypassed.",
            },
        ],
        "public_notice_results": {
            **source_summary,
            "indexed_notice_documents": len(index_records),
            "records_with_target_mechanical_terms": signal_records,
            "records_with_explicit_cooling_tower_terms": tower_term_records,
        },
        "evidence_contract": "Public notices, permits, and meeting materials do not become confirmed cooling-tower evidence. No result here is represented as the unavailable AIC supporting-document corpus.",
    }
    write_json(MARKET / "aic_free_access_report.json", alternatives)
    write_json(MARKET / "aic_open_document_alternatives.json", {
        "schema_version": "toronto-aic-open-document-alternatives-1.0",
        "generated_at": utc_now(),
        "document_type": "CITY_CLERK_PUBLIC_NOTICE",
        "supporting_document_corpus": False,
        "records": index_records,
    })
    print(json.dumps(alternatives, indent=2))


if __name__ == "__main__":
    main()
