from __future__ import annotations

import json
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from towersignal.procurement import classify_procurement, normalize_space, parse_iso_date, parse_money, stable_id

API_ROOT = "https://data.ny.gov"
USER_AGENT = "TowerSignal/1.0 (+https://github.com/JeremyHennessy/TowerSignal)"
SCHEMA_VERSION = "1.0"

DATASETS: tuple[tuple[str, str, str], ...] = (
    ("NYS_ABO_STATE_AUTHORITIES", "ehig-g5x3", "Procurement Report for State Authorities"),
    ("NYS_ABO_LOCAL_AUTHORITIES", "8w5p-k45m", "Procurement Report for Local Authorities"),
    ("NYS_ABO_LOCAL_DEVELOPMENT_CORPORATIONS", "d84c-dk28", "Procurement Report for Local Development Corporations"),
    ("NYS_ABO_INDUSTRIAL_DEVELOPMENT_AGENCIES", "p3p6-xqr5", "Procurement Report for Industrial Development Agencies"),
)

# These are retrieval terms, not a model. The existing deterministic procurement
# classifier remains the authority on whether a retrieved row is relevant.
RETRIEVAL_TERMS: tuple[str, ...] = (
    "cooling tower",
    "water treatment",
    "cooling water",
    "condenser water",
    "boiler water",
    "legionella",
    "disinfection",
    "water management",
    "water quality",
    "biocide",
    "chiller",
    "hvac maintenance",
    "mechanical maintenance",
    "laboratory testing",
    "chemical treatment",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _request_json(url: str, *, retries: int = 4, timeout: int = 90) -> Any:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(2**attempt)
    raise RuntimeError(f"Failed to retrieve NY Open Data source after {retries} attempts: {url}: {last_error}")


def _query(dataset_id: str, params: Mapping[str, Any]) -> list[dict[str, Any]]:
    payload = _request_json(f"{API_ROOT}/resource/{dataset_id}.json?{urlencode(params)}")
    if not isinstance(payload, list):
        raise RuntimeError(f"NYS dataset {dataset_id} returned a non-list payload")
    return [row for row in payload if isinstance(row, dict)]


def _fetch_count(dataset_id: str) -> int:
    rows = _query(dataset_id, {"$select": "count(*) as count"})
    if not rows or "count" not in rows[0]:
        raise RuntimeError(f"NYS dataset {dataset_id} count query returned an unexpected payload")
    return int(rows[0]["count"])


def _fetch_metadata(dataset_id: str) -> dict[str, Any]:
    payload = _request_json(f"{API_ROOT}/api/views/{dataset_id}")
    if not isinstance(payload, dict):
        raise RuntimeError(f"NYS dataset {dataset_id} metadata returned a non-object payload")
    return payload


def _fetch_search(dataset_id: str, term: str, *, page_size: int = 50000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = _query(dataset_id, {"$limit": page_size, "$offset": offset, "$q": term})
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def _first(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _address(row: Mapping[str, Any]) -> str | None:
    parts = [
        _first(row, "vendor_address_1", "address_1", "vendor_address"),
        _first(row, "vendor_address_2", "address_2"),
        _first(row, "vendor_city", "city"),
        _first(row, "vendor_state", "state"),
        _first(row, "vendor_postal_code", "zip", "postal_code"),
        _first(row, "vendor_country", "country"),
    ]
    value = normalize_space(" ".join(str(part) for part in parts if part not in (None, "")))
    return value or None


def _source_row_fingerprint(dataset_id: str, row: Mapping[str, Any]) -> str:
    material = [
        dataset_id,
        _first(row, "authority_name"),
        _first(row, "fiscal_year_end_date"),
        _first(row, "vendor_name"),
        _first(row, "procurement_description"),
        _first(row, "award_date"),
        _first(row, "contract_begin_date", "contract_start_date", "begin_date", "start_date"),
        _first(row, "contract_end_date", "end_date"),
        _first(row, "contract_amount", "amount", "procurement_amount"),
        _first(row, "procurement_number", "contract_number", "contract_id"),
    ]
    return stable_id("nys-abo-row", *material)


def normalize_row(source: str, dataset_id: str, row: Mapping[str, Any], *, retrieved_at: str) -> dict[str, Any] | None:
    vendor = normalize_space(str(_first(row, "vendor_name", "vendor") or "")) or None
    description = normalize_space(str(_first(row, "procurement_description", "description") or ""))
    procurement_type = normalize_space(str(_first(row, "type_of_procurement", "procurement_type") or ""))
    award_process = normalize_space(str(_first(row, "award_process", "award_method") or ""))
    authority = normalize_space(str(_first(row, "authority_name", "agency_name", "buyer_name") or "")) or None
    classification = classify_procurement(description, procurement_type, award_process)
    if classification.service_category == "UNRELATED":
        return None

    source_record_id = _source_row_fingerprint(dataset_id, row)
    contract_number = normalize_space(str(_first(row, "procurement_number", "contract_number", "contract_id") or "")) or None
    fiscal_year = parse_iso_date(_first(row, "fiscal_year_end_date"))
    award_date = parse_iso_date(_first(row, "award_date"))
    start_date = parse_iso_date(_first(row, "contract_begin_date", "contract_start_date", "begin_date", "start_date"))
    end_date = parse_iso_date(_first(row, "contract_end_date", "end_date"))
    amount = parse_money(_first(row, "contract_amount", "amount", "procurement_amount", "total_amount"))
    expended = parse_money(_first(row, "amount_expended", "amount_spent", "expenditures", "spend_to_date"))

    return {
        "schema_version": SCHEMA_VERSION,
        "procurement_id": stable_id("procurement", source, source_record_id),
        "source": source,
        "source_record_id": source_record_id,
        "source_contract_id": contract_number,
        "vendor_raw": vendor,
        "vendor_address": _address(row),
        "vendor_role": "REPORTED_VENDOR",
        "company_id": None,
        "company_match_confidence": "UNRESOLVED" if vendor else None,
        "company_resolution_method": "NYS_ABO_REPORTED_VENDOR_NAME",
        "buyer_name": authority,
        "agency": authority,
        "title": description or procurement_type or "NYS authority procurement",
        "description": description or None,
        "procurement_text": normalize_space(" ".join(value for value in (description, procurement_type, award_process) if value)),
        "service_category": classification.service_category,
        "service_confidence": classification.confidence,
        "classification_terms": list(classification.matched_terms),
        "classification_reason": classification.reason,
        "original_amount": amount,
        "current_amount": amount,
        "spend_to_date": expended,
        "amount": amount,
        "amount_evidence": "Authority-reported procurement/contract amount; not company revenue." if amount is not None else None,
        "observed_value_evidence": "Public authority annual procurement report; values are source-reported procurement values, not vendor revenue.",
        "start_date": start_date,
        "end_date": end_date,
        "award_date": award_date,
        "due_date": None,
        "notice_start_date": None,
        "notice_end_date": None,
        "status": "HISTORICAL_REPORTING_OBSERVATION",
        "notice_type": "PROCUREMENT_CONTRACT_REPORT",
        "procurement_category": procurement_type or None,
        "selection_method": award_process or None,
        "pin": None,
        "scope": "NYS public authority annual procurement reporting",
        "source_url": f"https://data.ny.gov/d/{dataset_id}",
        "retrieved_at": retrieved_at,
        "source_updated_at": fiscal_year,
        "facility_id": None,
        "facility_match_confidence": "UNLINKED",
        "tower_account_system_ids": [],
        "tower_link_confidence": "UNLINKED",
        "source_dataset_id": dataset_id,
        "source_fiscal_year_end": fiscal_year,
    }


def build_payload(*, cohort_aliases: Sequence[str] = (), retrieval_terms: Sequence[str] = RETRIEVAL_TERMS) -> dict[str, Any]:
    generated_at = utc_now()
    contracts: list[dict[str, Any]] = []
    dataset_health: list[dict[str, Any]] = []
    seen_procurement_ids: set[str] = set()

    search_terms = list(dict.fromkeys([*retrieval_terms, *[normalize_space(alias) for alias in cohort_aliases if normalize_space(alias)]]))
    for source, dataset_id, name in DATASETS:
        metadata = _fetch_metadata(dataset_id)
        source_count = _fetch_count(dataset_id)
        unique_rows: dict[str, dict[str, Any]] = {}
        term_counts: Counter[str] = Counter()
        for term in search_terms:
            for row in _fetch_search(dataset_id, term):
                fingerprint = _source_row_fingerprint(dataset_id, row)
                unique_rows[fingerprint] = row
                term_counts[term] += 1

        normalized_count = 0
        vendor_count = 0
        for row in unique_rows.values():
            normalized = normalize_row(source, dataset_id, row, retrieved_at=generated_at)
            if normalized is None:
                continue
            procurement_id = normalized["procurement_id"]
            if procurement_id in seen_procurement_ids:
                continue
            seen_procurement_ids.add(procurement_id)
            contracts.append(normalized)
            normalized_count += 1
            if normalized.get("vendor_raw"):
                vendor_count += 1

        rows_updated_at = metadata.get("rowsUpdatedAt") or metadata.get("dataUpdatedAt")
        dataset_health.append({
            "source": source,
            "dataset_id": dataset_id,
            "dataset_name": name,
            "status": "HEALTHY",
            "record_count": source_count,
            "retrieved_candidate_count": len(unique_rows),
            "relevant_record_count": normalized_count,
            "vendor_record_count": vendor_count,
            "pagination_complete": True,
            "schema_valid": True,
            "source_last_updated_epoch": rows_updated_at,
            "retrieved_at": generated_at,
            "retrieval_term_match_counts": dict(sorted(term_counts.items())),
            "coverage_note": "Server-side full-text retrieval over specialized service terms plus curated cohort aliases; deterministic classifier decides publication relevance.",
        })

    contracts.sort(key=lambda row: (str(row.get("award_date") or row.get("start_date") or ""), str(row.get("source")), str(row.get("procurement_id"))), reverse=True)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "source": {
            "name": "New York State Authorities Budget Office procurement reports",
            "api_root": API_ROOT,
            "dataset_ids": [dataset_id for _, dataset_id, _ in DATASETS],
            "coverage": "Statewide public-authority procurement reports covering the eight most recent completed fiscal years published by ABO.",
            "value_semantics": "Source-reported procurement/contract values are observed public contract values, not vendor revenue.",
        },
        "summary": {
            "source_dataset_count": len(DATASETS),
            "source_record_count": sum(int(item["record_count"]) for item in dataset_health),
            "retrieved_candidate_count": sum(int(item["retrieved_candidate_count"]) for item in dataset_health),
            "relevant_contract_count": len(contracts),
            "vendor_record_count": sum(1 for row in contracts if row.get("vendor_raw")),
            "classification_counts": dict(sorted(Counter(str(row.get("service_category")) for row in contracts).items())),
            "value_semantics": "Observed public procurement values; not company revenue.",
        },
        "source_health": dataset_health,
        "contracts": contracts,
    }
