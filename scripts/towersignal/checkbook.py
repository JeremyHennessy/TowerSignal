from __future__ import annotations

import json
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .fetch import USER_AGENT
from .procurement import (
    CompanyResolution,
    classify_procurement,
    normalize_company_name,
    normalize_contract,
    normalize_space,
    procurement_source_health,
    stable_id,
    utc_now,
)

API_URL = "https://www.checkbooknyc.com/api"
CONTRACT_API_URL = "https://www.checkbooknyc.com/contract-api"
PAGE_SIZE = 20000
MIN_REQUEST_INTERVAL_SECONDS = 1.2
MAX_RETRIES = 3

CITYWIDE_SOURCE = "NYC_CHECKBOOK_CITYWIDE"
EDC_SOURCE = "NYC_CHECKBOOK_EDC"

CITYWIDE_COLUMNS = (
    "prime_contract_id",
    "prime_vendor",
    "prime_contract_purpose",
    "prime_contract_original_amount",
    "prime_contract_current_amount",
    "prime_vendor_spent_to_date",
    "prime_contract_start_date",
    "prime_contract_end_date",
    "prime_contracting_agency",
    "prime_contract_version",
    "parent_contract_id",
    "prime_contract_type",
    "prime_contract_award_method",
    "prime_contract_expense_category",
    "prime_contract_industry",
    "prime_contract_pin",
)

CITYWIDE_SUBVENDOR_COLUMNS = (
    "prime_contract_id",
    "prime_contracting_agency",
    "sub_vendor",
    "sub_vendor_mwbe_category",
    "sub_contract_purpose",
    "sub_contract_status",
    "sub_contract_original_amount",
    "sub_contract_current_amount",
    "sub_vendor_paid_to_date",
    "sub_contract_industry",
    "sub_contract_start_date",
    "sub_contract_end_date",
    "sub_contract_reference_id",
    "sub_woman_owned_business",
    "sub_emerging_business",
)

# The live API currently rejects these documented response fields in the all-years
# registered-expense query. Keep them explicit so a future source-contract change
# is deliberate and testable rather than silently reintroduced.
CITYWIDE_EXCLUDED_COLUMNS = (
    "year",
    "prime_contract_registration_date",
    "sub_contract_registration_date",
)

EDC_COLUMNS = (
    "contract_id",
    "prime_vendor",
    "purpose",
    "other_government_entities",
    "version",
    "parent_contract_id",
    "original_amount",
    "current_amount",
    "spent_to_date",
    "contract_type",
    "award_method",
    "expense_category",
    "start_date",
    "end_date",
    "pin",
    "document_code",
    "contract_industry",
    "budget_name",
    "entity_contract_number",
    "commodity_line",
)

RequestXml = Callable[[bytes], bytes | str]


class CheckbookSourceError(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


_request_lock = threading.Lock()
_last_request_at = 0.0


def _pace_request() -> None:
    global _last_request_at
    with _request_lock:
        now = time.monotonic()
        wait = MIN_REQUEST_INTERVAL_SECONDS - (now - _last_request_at)
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.monotonic()


def _default_request_xml(payload: bytes) -> bytes:
    opener = build_opener(_NoRedirect())
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        _pace_request()
        request = Request(
            API_URL,
            data=payload,
            method="POST",
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/xml, text/xml",
                "Content-Type": "application/xml; charset=utf-8",
            },
        )
        try:
            with opener.open(request, timeout=120) as response:
                code = getattr(response, "status", response.getcode())
                if 300 <= int(code) < 400:
                    raise CheckbookSourceError(f"Checkbook NYC returned redirect HTTP {code}; redirects are not followed")
                return response.read()
        except HTTPError as exc:
            if 300 <= exc.code < 500:
                raise CheckbookSourceError(f"Checkbook NYC request failed with non-retryable HTTP {exc.code}") from exc
            last_error = exc
        except (URLError, TimeoutError, OSError) as exc:
            last_error = exc

        if attempt + 1 < MAX_RETRIES:
            time.sleep(2**attempt)

    raise CheckbookSourceError(f"Checkbook NYC request failed after {MAX_RETRIES} attempts: {last_error}")


@dataclass(frozen=True)
class ScopeSpec:
    name: str
    source: str
    type_of_data: str
    criteria: tuple[tuple[str, str, str], ...]
    columns: tuple[str, ...]
    identity_field: str


@dataclass(frozen=True)
class ScopeResult:
    spec: ScopeSpec
    expected_count: int
    rows: tuple[dict[str, str], ...]
    pagination_complete: bool


CITYWIDE_SCOPE = ScopeSpec(
    name="CITYWIDE_REGISTERED_EXPENSE",
    source=CITYWIDE_SOURCE,
    type_of_data="Contracts",
    criteria=(("status", "value", "registered"), ("category", "value", "expense")),
    columns=CITYWIDE_COLUMNS,
    identity_field="prime_contract_id",
)

CITYWIDE_SUBVENDOR_SCOPE = ScopeSpec(
    name="CITYWIDE_REGISTERED_EXPENSE_SUBVENDORS",
    source=CITYWIDE_SOURCE,
    type_of_data="Contracts",
    criteria=(
        ("status", "value", "registered"),
        ("category", "value", "expense"),
        ("contract_includes_sub_vendors", "value", "1"),
    ),
    columns=CITYWIDE_SUBVENDOR_COLUMNS,
    identity_field="prime_contract_id",
)

EDC_SCOPE = ScopeSpec(
    name="NYCEDC_REGISTERED_EXPENSE",
    source=EDC_SOURCE,
    type_of_data="Contracts_OGE",
    criteria=(
        ("status", "value", "registered"),
        ("category", "value", "expense"),
        ("other_government_entities_code", "value", "z81"),
    ),
    columns=EDC_COLUMNS,
    identity_field="contract_id",
)


def build_request_xml(
    spec: ScopeSpec,
    *,
    records_from: int,
    max_records: int,
    extra_criteria: Sequence[tuple[str, str, str]] = (),
) -> bytes:
    if records_from <= 0:
        raise ValueError("records_from must be 1-based and positive")
    if max_records <= 0 or max_records > PAGE_SIZE:
        raise ValueError(f"max_records must be between 1 and {PAGE_SIZE}")

    root = ET.Element("request")
    ET.SubElement(root, "type_of_data").text = spec.type_of_data
    ET.SubElement(root, "records_from").text = str(records_from)
    ET.SubElement(root, "max_records").text = str(max_records)
    criteria_node = ET.SubElement(root, "search_criteria")
    for name, kind, value in (*spec.criteria, *extra_criteria):
        criteria = ET.SubElement(criteria_node, "criteria")
        ET.SubElement(criteria, "name").text = name
        ET.SubElement(criteria, "type").text = kind
        ET.SubElement(criteria, "value").text = value

    response_columns = ET.SubElement(root, "response_columns")
    for column in spec.columns:
        ET.SubElement(response_columns, "column").text = column
    return ET.tostring(root, encoding="utf-8", xml_declaration=False)


def _text(node: ET.Element | None) -> str | None:
    if node is None or node.text is None:
        return None
    value = normalize_space(node.text)
    return value or None


def parse_response_xml(payload: bytes | str, *, identity_field: str) -> tuple[int, tuple[dict[str, str], ...]]:
    try:
        root = ET.fromstring(payload)
    except (ET.ParseError, TypeError) as exc:
        raise CheckbookSourceError(f"Checkbook NYC returned malformed XML: {exc}") from exc

    result = (_text(root.find("./status/result")) or "").lower()
    if result != "success":
        messages = [
            normalize_space(" ".join(part for part in (_text(node.find("code")), _text(node.find("description"))) if part))
            for node in root.findall("./status/messages/message")
        ]
        message = "; ".join(value for value in messages if value) or "no source message"
        raise CheckbookSourceError(f"Checkbook NYC API reported {result or 'unknown'}: {message}")

    count_text = _text(root.find("./result_records/record_count"))
    try:
        record_count = int(count_text or "")
    except ValueError as exc:
        raise CheckbookSourceError(f"Checkbook NYC response has invalid record_count: {count_text!r}") from exc
    if record_count < 0:
        raise CheckbookSourceError("Checkbook NYC response has negative record_count")

    transactions = root.findall("./result_records/contract_transactions/transaction")
    rows: list[dict[str, str]] = []
    for transaction in transactions:
        row = {child.tag: normalize_space(child.text or "") for child in list(transaction)}
        if not normalize_space(row.get(identity_field)):
            raise CheckbookSourceError(f"Checkbook NYC transaction is missing required identity {identity_field}")
        rows.append(row)
    return record_count, tuple(rows)


def fetch_scope(
    spec: ScopeSpec,
    *,
    request_xml: RequestXml = _default_request_xml,
    page_size: int = PAGE_SIZE,
    extra_criteria: Sequence[tuple[str, str, str]] = (),
) -> ScopeResult:
    if page_size <= 0 or page_size > PAGE_SIZE:
        raise ValueError(f"page_size must be between 1 and {PAGE_SIZE}")

    rows: list[dict[str, str]] = []
    expected_count: int | None = None
    records_from = 1

    while expected_count is None or len(rows) < expected_count:
        payload = request_xml(
            build_request_xml(
                spec,
                records_from=records_from,
                max_records=page_size,
                extra_criteria=extra_criteria,
            )
        )
        page_count, page_rows = parse_response_xml(payload, identity_field=spec.identity_field)
        if expected_count is None:
            expected_count = page_count
        elif page_count != expected_count:
            raise CheckbookSourceError(
                f"Checkbook NYC {spec.name} record_count changed during pagination: {expected_count} -> {page_count}"
            )

        if not page_rows:
            if len(rows) < expected_count:
                raise CheckbookSourceError(
                    f"Checkbook NYC {spec.name} pagination ended early at {len(rows)} of {expected_count}"
                )
            break

        rows.extend(dict(row) for row in page_rows)
        records_from += len(page_rows)

    expected = expected_count or 0
    if len(rows) != expected:
        raise CheckbookSourceError(
            f"Checkbook NYC {spec.name} pagination incomplete: expected {expected}, retrieved {len(rows)}"
        )
    return ScopeResult(spec=spec, expected_count=expected, rows=tuple(rows), pagination_complete=True)


def _material_key(row: Mapping[str, str], fields: Iterable[str]) -> tuple[str, ...]:
    return tuple(normalize_space(row.get(field)) for field in fields)


CITYWIDE_PRIME_MATERIAL_FIELDS = (
    "prime_vendor",
    "prime_contract_purpose",
    "prime_contract_original_amount",
    "prime_contract_current_amount",
    "prime_vendor_spent_to_date",
    "prime_contract_start_date",
    "prime_contract_end_date",
    "prime_contracting_agency",
    "prime_contract_version",
    "parent_contract_id",
    "prime_contract_type",
    "prime_contract_award_method",
    "prime_contract_expense_category",
)

EDC_MATERIAL_FIELDS = (
    "prime_vendor",
    "purpose",
    "original_amount",
    "current_amount",
    "spent_to_date",
    "other_government_entities",
    "version",
    "parent_contract_id",
    "contract_type",
    "award_method",
    "expense_category",
    "start_date",
    "end_date",
)


def _collapse_rows(
    rows: Sequence[Mapping[str, str]],
    *,
    identity_field: str,
    material_fields: Sequence[str],
) -> tuple[dict[str, str], ...]:
    grouped: dict[str, list[Mapping[str, str]]] = {}
    for row in rows:
        identity = normalize_space(row.get(identity_field))
        if not identity:
            raise CheckbookSourceError(f"Source row missing identity {identity_field}")
        grouped.setdefault(identity, []).append(row)

    collapsed: list[dict[str, str]] = []
    for identity in sorted(grouped):
        candidates = grouped[identity]
        signatures = {_material_key(row, material_fields) for row in candidates}
        if len(signatures) > 1:
            raise CheckbookSourceError(
                f"Checkbook NYC returned conflicting material fields for {identity_field}={identity}"
            )
        collapsed.append(dict(candidates[0]))
    return tuple(collapsed)


def _unresolved(vendor: str | None) -> CompanyResolution:
    normalized = normalize_space(vendor)
    return CompanyResolution(
        company_id=None,
        canonical_name=None,
        confidence="UNRESOLVED",
        resolution_method="NO_SAFE_MATCH",
        normalized_vendor_name=normalize_company_name(normalized),
    )


def _normalize_citywide_prime(row: Mapping[str, str], *, retrieved_at: str) -> dict[str, Any]:
    contract_id = normalize_space(row.get("prime_contract_id"))
    vendor = normalize_space(row.get("prime_vendor")) or None
    contract = normalize_contract(
        source=CITYWIDE_SOURCE,
        source_record_id=contract_id,
        source_contract_id=contract_id,
        vendor_raw=vendor,
        buyer_name=normalize_space(row.get("prime_contracting_agency")) or None,
        agency=normalize_space(row.get("prime_contracting_agency")) or None,
        title=normalize_space(row.get("prime_contract_purpose")) or None,
        description=normalize_space(row.get("prime_contract_purpose")) or None,
        retrieved_at=retrieved_at,
        raw=row,
        company_resolution=_unresolved(vendor),
        original_amount=row.get("prime_contract_original_amount"),
        current_amount=row.get("prime_contract_current_amount"),
        spend_to_date=row.get("prime_vendor_spent_to_date"),
        start_date=row.get("prime_contract_start_date"),
        end_date=row.get("prime_contract_end_date"),
        award_method=normalize_space(row.get("prime_contract_award_method")) or None,
        contract_type=normalize_space(row.get("prime_contract_type")) or None,
        status="REGISTERED",
        source_url=CONTRACT_API_URL,
    )
    contract.update(
        {
            "vendor_role": "PRIME",
            "parent_contract_id": normalize_space(row.get("parent_contract_id")) or None,
            "expense_category": normalize_space(row.get("prime_contract_expense_category")) or None,
            "industry": normalize_space(row.get("prime_contract_industry")) or None,
            "pin": normalize_space(row.get("prime_contract_pin")) or None,
            "contract_version": normalize_space(row.get("prime_contract_version")) or None,
            "observed_value_evidence": "SOURCE_REPORTED_PUBLIC_CONTRACT",
        }
    )
    return contract


def _normalize_citywide_subcontract(row: Mapping[str, str], *, retrieved_at: str) -> dict[str, Any] | None:
    prime_contract_id = normalize_space(row.get("prime_contract_id"))
    vendor = normalize_space(row.get("sub_vendor")) or None
    purpose = normalize_space(row.get("sub_contract_purpose")) or None
    if not vendor and not purpose:
        return None
    classified = classify_procurement(purpose)
    if classified.service_category == "UNRELATED":
        return None

    reference_id = normalize_space(row.get("sub_contract_reference_id"))
    source_record_id = stable_id(
        "checkbook-sub",
        prime_contract_id,
        reference_id,
        vendor,
        purpose,
        row.get("sub_contract_start_date"),
        row.get("sub_contract_end_date"),
        row.get("sub_contract_original_amount"),
        row.get("sub_contract_current_amount"),
    )
    contract = normalize_contract(
        source=CITYWIDE_SOURCE,
        source_record_id=source_record_id,
        source_contract_id=reference_id or None,
        vendor_raw=vendor,
        buyer_name=normalize_space(row.get("prime_contracting_agency")) or None,
        agency=normalize_space(row.get("prime_contracting_agency")) or None,
        title=purpose,
        description=purpose,
        retrieved_at=retrieved_at,
        raw=row,
        company_resolution=_unresolved(vendor),
        original_amount=row.get("sub_contract_original_amount"),
        current_amount=row.get("sub_contract_current_amount"),
        spend_to_date=row.get("sub_vendor_paid_to_date"),
        start_date=row.get("sub_contract_start_date"),
        end_date=row.get("sub_contract_end_date"),
        status=normalize_space(row.get("sub_contract_status")) or "REGISTERED",
        source_url=CONTRACT_API_URL,
    )
    contract.update(
        {
            "vendor_role": "SUBCONTRACTOR",
            "parent_contract_id": prime_contract_id or None,
            "industry": normalize_space(row.get("sub_contract_industry")) or None,
            "sub_contract_reference_id": reference_id or None,
            "observed_value_evidence": "SOURCE_REPORTED_PUBLIC_SUBCONTRACT",
        }
    )
    return contract


def _normalize_edc_contract(row: Mapping[str, str], *, retrieved_at: str) -> dict[str, Any]:
    contract_id = normalize_space(row.get("contract_id"))
    vendor = normalize_space(row.get("prime_vendor")) or None
    purpose = normalize_space(row.get("purpose")) or None
    buyer = normalize_space(row.get("other_government_entities")) or "NYCEDC"
    contract = normalize_contract(
        source=EDC_SOURCE,
        source_record_id=contract_id,
        source_contract_id=contract_id,
        vendor_raw=vendor,
        buyer_name=buyer,
        agency=buyer,
        title=purpose,
        description=purpose,
        retrieved_at=retrieved_at,
        raw=row,
        company_resolution=_unresolved(vendor),
        original_amount=row.get("original_amount"),
        current_amount=row.get("current_amount"),
        spend_to_date=row.get("spent_to_date"),
        start_date=row.get("start_date"),
        end_date=row.get("end_date"),
        award_method=normalize_space(row.get("award_method")) or None,
        contract_type=normalize_space(row.get("contract_type")) or None,
        status="REGISTERED",
        source_url=CONTRACT_API_URL,
    )
    contract.update(
        {
            "vendor_role": "PRIME",
            "parent_contract_id": normalize_space(row.get("parent_contract_id")) or None,
            "expense_category": normalize_space(row.get("expense_category")) or None,
            "industry": normalize_space(row.get("contract_industry")) or None,
            "pin": normalize_space(row.get("pin")) or None,
            "contract_version": normalize_space(row.get("version")) or None,
            "document_code": normalize_space(row.get("document_code")) or None,
            "budget_name": normalize_space(row.get("budget_name")) or None,
            "commodity_line": normalize_space(row.get("commodity_line")) or None,
            "entity_contract_number": normalize_space(row.get("entity_contract_number")) or None,
            "observed_value_evidence": "SOURCE_REPORTED_PUBLIC_CONTRACT",
        }
    )
    return contract


def _dedupe_contracts(contracts: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for contract in contracts:
        procurement_id = str(contract["procurement_id"])
        previous = by_id.get(procurement_id)
        if previous is not None and previous != contract:
            raise CheckbookSourceError(f"Normalized Checkbook procurement ID collision: {procurement_id}")
        by_id[procurement_id] = contract
    return [by_id[key] for key in sorted(by_id)]


def _source_health_for_scope(
    scope: ScopeResult,
    contracts: Sequence[Mapping[str, Any]],
    *,
    retrieved_at: str,
) -> dict[str, Any]:
    unresolved = sum(1 for row in contracts if row.get("vendor_raw") and not row.get("company_id"))
    return procurement_source_health(
        source=scope.spec.source,
        last_success=retrieved_at,
        last_attempt=retrieved_at,
        record_count=scope.expected_count,
        relevant_record_count=len(contracts),
        normalized_contract_count=len(contracts),
        normalized_notice_count=0,
        resolved_company_count=0,
        unresolved_vendor_count=unresolved,
        facility_link_count=0,
        exact_tower_link_count=0,
        pagination_complete=scope.pagination_complete,
        schema_valid=True,
        freshness="CURRENT",
    )


def build_checkbook_cache(
    *,
    request_xml: RequestXml = _default_request_xml,
    retrieved_at: str | None = None,
    page_size: int = PAGE_SIZE,
) -> dict[str, Any]:
    retrieved_at = retrieved_at or utc_now()
    citywide_scope = fetch_scope(CITYWIDE_SCOPE, request_xml=request_xml, page_size=page_size)
    citywide_subvendor_scope = fetch_scope(
        CITYWIDE_SUBVENDOR_SCOPE,
        request_xml=request_xml,
        page_size=page_size,
    )
    edc_scope = fetch_scope(EDC_SCOPE, request_xml=request_xml, page_size=page_size)

    citywide_primes = _collapse_rows(
        citywide_scope.rows,
        identity_field="prime_contract_id",
        material_fields=CITYWIDE_PRIME_MATERIAL_FIELDS,
    )
    edc_primes = _collapse_rows(
        edc_scope.rows,
        identity_field="contract_id",
        material_fields=EDC_MATERIAL_FIELDS,
    )

    citywide_contracts: list[dict[str, Any]] = []
    for row in citywide_primes:
        contract = _normalize_citywide_prime(row, retrieved_at=retrieved_at)
        if contract["service_category"] != "UNRELATED":
            citywide_contracts.append(contract)
    for row in citywide_subvendor_scope.rows:
        subcontract = _normalize_citywide_subcontract(row, retrieved_at=retrieved_at)
        if subcontract is not None:
            citywide_contracts.append(subcontract)
    citywide_contracts = _dedupe_contracts(citywide_contracts)

    edc_contracts = [
        contract
        for row in edc_primes
        if (contract := _normalize_edc_contract(row, retrieved_at=retrieved_at))["service_category"] != "UNRELATED"
    ]
    edc_contracts = _dedupe_contracts(edc_contracts)

    all_contracts = _dedupe_contracts([*citywide_contracts, *edc_contracts])
    citywide_health = _source_health_for_scope(citywide_scope, citywide_contracts, retrieved_at=retrieved_at)
    citywide_health.update(
        {
            "subvendor_record_count": citywide_subvendor_scope.expected_count,
            "subvendor_pagination_complete": citywide_subvendor_scope.pagination_complete,
        }
    )
    source_health = {
        CITYWIDE_SOURCE: citywide_health,
        EDC_SOURCE: _source_health_for_scope(edc_scope, edc_contracts, retrieved_at=retrieved_at),
    }

    classification_counts: dict[str, int] = {}
    for contract in all_contracts:
        category = str(contract.get("service_category") or "UNRELATED")
        classification_counts[category] = classification_counts.get(category, 0) + 1

    return {
        "schema_version": "1.0",
        "generated_at": retrieved_at,
        "source": {
            "name": "Checkbook NYC Contracts API",
            "api_url": API_URL,
            "documentation_url": CONTRACT_API_URL,
            "retrieved_at": retrieved_at,
            "page_size": page_size,
            "request_rate_floor_seconds": MIN_REQUEST_INTERVAL_SECONDS,
            "scopes": [
                {
                    "name": citywide_scope.spec.name,
                    "source": citywide_scope.spec.source,
                    "record_count": citywide_scope.expected_count,
                    "pagination_complete": citywide_scope.pagination_complete,
                },
                {
                    "name": citywide_subvendor_scope.spec.name,
                    "source": citywide_subvendor_scope.spec.source,
                    "record_count": citywide_subvendor_scope.expected_count,
                    "pagination_complete": citywide_subvendor_scope.pagination_complete,
                },
                {
                    "name": edc_scope.spec.name,
                    "source": edc_scope.spec.source,
                    "record_count": edc_scope.expected_count,
                    "pagination_complete": edc_scope.pagination_complete,
                },
            ],
            "deferred_scopes": [
                {
                    "name": "NYCHA",
                    "type_of_data": "Contracts_NYCHA",
                    "status": "DEFERRED_SEPARATE_ADAPTER",
                    "reason": "NYCHA contract data uses release and line-item granularity and requires a separate normalization contract.",
                }
            ],
        },
        "summary": {
            "citywide_source_transaction_count": citywide_scope.expected_count,
            "citywide_subvendor_source_transaction_count": citywide_subvendor_scope.expected_count,
            "citywide_unique_prime_contract_count": len(citywide_primes),
            "citywide_relevant_contract_count": len(citywide_contracts),
            "edc_source_transaction_count": edc_scope.expected_count,
            "edc_unique_prime_contract_count": len(edc_primes),
            "edc_relevant_contract_count": len(edc_contracts),
            "relevant_contract_count": len(all_contracts),
            "unresolved_vendor_count": sum(1 for row in all_contracts if row.get("vendor_raw") and not row.get("company_id")),
            "classification_counts": dict(sorted(classification_counts.items())),
            "value_semantics": "Observed source-reported public contract/subcontract values and spend-to-date; not company revenue or a complete customer book.",
        },
        "source_health": source_health,
        "contracts": all_contracts,
    }


def fetch_contract_by_id(
    source: str,
    contract_id: str,
    *,
    request_xml: RequestXml = _default_request_xml,
) -> tuple[dict[str, str], ...]:
    contract_id = normalize_space(contract_id)
    if not contract_id:
        raise ValueError("contract_id is required")
    spec = CITYWIDE_SCOPE if source == CITYWIDE_SOURCE else EDC_SCOPE if source == EDC_SOURCE else None
    if spec is None:
        raise ValueError(f"Unsupported Checkbook source: {source}")
    result = fetch_scope(
        spec,
        request_xml=request_xml,
        page_size=min(100, PAGE_SIZE),
        extra_criteria=(("contract_id", "value", contract_id),),
    )
    return result.rows


def compact_cache_summary(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        {
            "generated_at": payload.get("generated_at"),
            "summary": payload.get("summary"),
            "source_health": payload.get("source_health"),
        },
        indent=2,
        sort_keys=True,
    )
