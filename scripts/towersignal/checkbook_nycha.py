from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping, Sequence

from .checkbook import (
    API_URL,
    CONTRACT_API_URL,
    PAGE_SIZE,
    CheckbookSourceError,
    ScopeSpec,
    _default_request_xml,
    build_request_xml,
)
from .checkbook_recent import recent_nyc_fiscal_years
from .procurement import (
    classify_procurement,
    normalize_company_name,
    normalize_space,
    parse_iso_date,
    parse_money,
    stable_id,
    utc_now,
)

SCHEMA_VERSION = "1.0"
SOURCE = "NYC_CHECKBOOK_NYCHA"
DEFAULT_FISCAL_YEAR_COUNT = 5

NYCHA_COLUMNS = (
    "year",
    "contract_id",
    "purchase_order_type",
    "record_type",
    "number_of_releases",
    "quantity_ordered",
    "release_number",
    "item_description",
    "item_category",
    "shipment_number",
    "start_date",
    "end_date",
    "approved_date",
    "line_current_amount",
    "line_number",
    "line_original_amount",
    "line_invoiced_amount",
    "release_current_amount",
    "release_original_amount",
    "release_invoiced_amount",
    "contract_current_amount",
    "contract_original_amount",
    "contract_invoiced_amount",
    "purpose",
    "vendor",
    "location",
    "contract_type",
    "award_method",
    "grant_name",
    "expenditure_type",
    "industry",
    "funding_source",
    "responsibility_center",
    "pin",
    "program",
    "project",
)

NYCHA_SCOPE = ScopeSpec(
    name="NYCHA_CONTRACT_RELEASE_LINES",
    source=SOURCE,
    type_of_data="Contracts_NYCHA",
    criteria=(),
    columns=NYCHA_COLUMNS,
    identity_field="contract_id",
)

DOMESTIC_RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("DOMESTIC_WATER_TANK", "STRONG", (
        "drinking water tank", "domestic water tank", "potable water tank",
        "roof water tank", "rooftop water tank", "water storage tank",
    )),
    ("BACKFLOW_CROSS_CONNECTION", "STRONG", (
        "backflow preventer", "backflow prevention", "cross connection",
        "cross-connection", "rpz",
    )),
    ("WATER_DISINFECTION", "CONFIRMED", (
        "monochloramine", "supplemental chlorination", "hyperchlorination",
    )),
    ("WATER_SAMPLING", "STRONG", (
        "potable water sampling", "drinking water sampling", "water sampling",
    )),
    ("DOMESTIC_WATER", "STRONG", (
        "domestic water", "potable water", "drinking water",
    )),
    ("DOMESTIC_WATER_PUMP", "STRONG", (
        "domestic water pump", "potable water pump", "booster pump", "water booster",
    )),
    ("DOMESTIC_PLUMBING", "VERIFY", (
        "plumbing service", "plumbing maintenance", "plumbing repair",
    )),
)

NEGATIVE_CONTEXTS = (
    "bottled water",
    "drinking water delivery",
    "wastewater",
    "stormwater",
    "water main",
    "hydrant",
    "swimming pool",
    "pool maintenance",
    "fire sprinkler",
    "fire suppression",
)

PROTECTED_MARKERS = (
    "cooling tower",
    "legionella",
    "condenser water",
    "boiler water",
    "water management plan",
    "water management program",
    "ashrae 188",
)

PURPOSE_QUERY_TERMS = (
    "water",
    "cooling",
    "legionella",
    "chlorination",
    "backflow",
    "plumbing",
    "tank",
    "pump",
    "booster",
    "potable",
    "domestic",
)


@dataclass(frozen=True)
class NychaPartition:
    fiscal_year: int
    purpose_query: str | None
    expected_count: int
    rows: tuple[dict[str, str], ...]
    pagination_complete: bool


def _text(node: ET.Element | None) -> str | None:
    if node is None or node.text is None:
        return None
    value = normalize_space(node.text)
    return value or None


def parse_nycha_response(payload: bytes | str) -> tuple[int, tuple[dict[str, str], ...]]:
    try:
        root = ET.fromstring(payload)
    except (ET.ParseError, TypeError) as exc:
        raise CheckbookSourceError(f"Checkbook NYCHA returned malformed XML: {exc}") from exc

    result = (_text(root.find("./status/result")) or "").lower()
    if result != "success":
        messages = []
        for node in root.findall("./status/messages/message"):
            message = normalize_space(
                " ".join(
                    part
                    for part in (_text(node.find("code")), _text(node.find("description")))
                    if part
                )
            )
            if message:
                messages.append(message)
        raise CheckbookSourceError(
            f"Checkbook NYCHA API reported {result or 'unknown'}: "
            f"{'; '.join(messages) or 'no source message'}"
        )

    count_text = _text(root.find("./result_records/record_count"))
    try:
        record_count = int(count_text or "")
    except ValueError as exc:
        raise CheckbookSourceError(
            f"Checkbook NYCHA response has invalid record_count: {count_text!r}"
        ) from exc

    result_records = root.find("./result_records")
    if result_records is None:
        if record_count == 0:
            return 0, ()
        raise CheckbookSourceError("Checkbook NYCHA response missing result_records")

    containers = [child for child in list(result_records) if child.tag != "record_count"]
    transaction_nodes: list[ET.Element] = []
    for container in containers:
        transaction_nodes.extend(container.findall("./transaction"))

    rows: list[dict[str, str]] = []
    for transaction in transaction_nodes:
        row = {child.tag: normalize_space(child.text or "") for child in list(transaction)}
        if not normalize_space(row.get("contract_id")):
            raise CheckbookSourceError("Checkbook NYCHA row missing contract_id")
        rows.append(row)
    return record_count, tuple(rows)


def fetch_partition(
    fiscal_year: int,
    *,
    purpose_query: str | None = None,
    page_size: int = PAGE_SIZE,
    request_xml=_default_request_xml,
) -> NychaPartition:
    if page_size <= 0 or page_size > PAGE_SIZE:
        raise ValueError(f"page_size must be between 1 and {PAGE_SIZE}")

    rows: list[dict[str, str]] = []
    expected_count: int | None = None
    records_from = 1
    criteria: tuple[tuple[str, str, str], ...] = (("fiscal_year", "value", str(fiscal_year)),)
    if purpose_query:
        criteria = (*criteria, ("purpose", "value", purpose_query))
    while expected_count is None or len(rows) < expected_count:
        request = build_request_xml(
            NYCHA_SCOPE,
            records_from=records_from,
            max_records=page_size,
            extra_criteria=criteria,
        )
        try:
            page_count, page_rows = parse_nycha_response(request_xml(request))
        except CheckbookSourceError as exc:
            raise CheckbookSourceError(
                f"Checkbook NYCHA FY{fiscal_year} {purpose_query or 'all'} "
                f"records_from={records_from} max_records={page_size}: {exc}"
            ) from exc
        if expected_count is None:
            expected_count = page_count
        elif page_count != expected_count:
            raise CheckbookSourceError(
                f"Checkbook NYCHA FY{fiscal_year} {purpose_query or 'all'} count changed during pagination: "
                f"{expected_count} -> {page_count}"
            )
        if not page_rows:
            if len(rows) < (expected_count or 0):
                raise CheckbookSourceError(
                    f"Checkbook NYCHA FY{fiscal_year} {purpose_query or 'all'} ended early at "
                    f"{len(rows)} of {expected_count}"
                )
            break
        rows.extend(dict(row) for row in page_rows)
        records_from += len(page_rows)

    expected = expected_count or 0
    if len(rows) != expected:
        raise CheckbookSourceError(
            f"Checkbook NYCHA FY{fiscal_year} {purpose_query or 'all'} incomplete: "
            f"expected {expected}, retrieved {len(rows)}"
        )
    return NychaPartition(fiscal_year, purpose_query, expected, tuple(rows), True)


def classify_nycha_water(*values: Any) -> dict[str, Any]:
    source_text = normalize_space(" ".join(str(value or "") for value in values))
    lowered = source_text.lower()
    negatives = [term for term in NEGATIVE_CONTEXTS if term in lowered]
    protected = [term for term in PROTECTED_MARKERS if term in lowered]
    if negatives and not protected:
        return {
            "service_category": "UNRELATED",
            "confidence": "STRONG",
            "matched_terms": negatives,
            "reason": "Explicit non-building-water context excluded",
            "classification_layer": "NYCHA_CONTEXT_GUARD",
        }

    primary = classify_procurement(source_text)
    if primary.service_category != "UNRELATED":
        return {
            "service_category": primary.service_category,
            "confidence": primary.confidence,
            "matched_terms": list(primary.matched_terms),
            "reason": primary.reason,
            "classification_layer": "TOWERSIGNAL_PROCUREMENT",
        }

    for category, confidence, terms in DOMESTIC_RULES:
        matched = [term for term in terms if term in lowered]
        if matched:
            return {
                "service_category": category,
                "confidence": confidence,
                "matched_terms": matched,
                "reason": "Explicit NYCHA domestic/building-water wording",
                "classification_layer": "NYCHA_DOMESTIC_WATER",
            }
    return {
        "service_category": "UNRELATED",
        "confidence": "CONFIRMED",
        "matched_terms": [],
        "reason": "No supported cooling/building-water service language",
        "classification_layer": "NYCHA_DOMESTIC_WATER",
    }


def _source_record_id(row: Mapping[str, str], fiscal_year: int) -> str:
    return stable_id(
        "nycha-line",
        fiscal_year,
        row.get("contract_id"),
        row.get("release_number"),
        row.get("line_number"),
        row.get("shipment_number"),
        row.get("approved_date"),
        row.get("item_description"),
        row.get("line_current_amount"),
    )


def normalize_row(row: Mapping[str, str], *, fiscal_year: int, retrieved_at: str) -> dict[str, Any] | None:
    classification = classify_nycha_water(row.get("purpose"), row.get("item_description"))
    if classification["service_category"] == "UNRELATED":
        return None

    vendor = normalize_space(row.get("vendor")) or None
    source_record_id = _source_record_id(row, fiscal_year)
    line_current_amount = parse_money(row.get("line_current_amount"))
    return {
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "procurement_id": stable_id("nycha-procurement", source_record_id),
        "source_record_id": source_record_id,
        "source_contract_id": normalize_space(row.get("contract_id")) or None,
        "fiscal_year": fiscal_year,
        "contract_id": normalize_space(row.get("contract_id")) or None,
        "release_number": normalize_space(row.get("release_number")) or None,
        "line_number": normalize_space(row.get("line_number")) or None,
        "shipment_number": normalize_space(row.get("shipment_number")) or None,
        "record_type": normalize_space(row.get("record_type")) or None,
        "purchase_order_type": normalize_space(row.get("purchase_order_type")) or None,
        "number_of_releases": normalize_space(row.get("number_of_releases")) or None,
        "quantity_ordered": normalize_space(row.get("quantity_ordered")) or None,
        "purpose": normalize_space(row.get("purpose")) or None,
        "item_description": normalize_space(row.get("item_description")) or None,
        "item_category": normalize_space(row.get("item_category")) or None,
        "vendor_raw": vendor,
        "vendor_key": normalize_company_name(vendor) if vendor else None,
        "company_id": None,
        "company_match_confidence": "UNRESOLVED" if vendor else None,
        "company_resolution_method": "NO_SAFE_MATCH" if vendor else None,
        "vendor_role": "VENDOR" if vendor else None,
        "buyer_name": "New York City Housing Authority",
        "agency": "NYCHA",
        "title": normalize_space(row.get("purpose")) or normalize_space(row.get("item_description")) or None,
        "description": normalize_space(row.get("item_description")) or normalize_space(row.get("purpose")) or None,
        "location": normalize_space(row.get("location")) or None,
        "location_link_confidence": "NYCHA_SOURCE_CONTEXT" if normalize_space(row.get("location")) else "UNLINKED",
        "facility_raw": normalize_space(row.get("location")) or None,
        "facility_match_confidence": "CONTEXT" if normalize_space(row.get("location")) else "UNLINKED",
        "tower_link_confidence": "UNLINKED",
        "tower_account_system_ids": [],
        "responsibility_center": normalize_space(row.get("responsibility_center")) or None,
        "funding_source": normalize_space(row.get("funding_source")) or None,
        "program": normalize_space(row.get("program")) or None,
        "project": normalize_space(row.get("project")) or None,
        "grant_name": normalize_space(row.get("grant_name")) or None,
        "expenditure_type": normalize_space(row.get("expenditure_type")) or None,
        "industry": normalize_space(row.get("industry")) or None,
        "pin": normalize_space(row.get("pin")) or None,
        "contract_type": normalize_space(row.get("contract_type")) or None,
        "award_method": normalize_space(row.get("award_method")) or None,
        "start_date": parse_iso_date(row.get("start_date")),
        "end_date": parse_iso_date(row.get("end_date")),
        "approved_date": parse_iso_date(row.get("approved_date")),
        "line_original_amount": parse_money(row.get("line_original_amount")),
        "line_current_amount": line_current_amount,
        "current_amount": line_current_amount,
        "line_invoiced_amount": parse_money(row.get("line_invoiced_amount")),
        "release_original_amount": parse_money(row.get("release_original_amount")),
        "release_current_amount": parse_money(row.get("release_current_amount")),
        "release_invoiced_amount": parse_money(row.get("release_invoiced_amount")),
        "contract_original_amount": parse_money(row.get("contract_original_amount")),
        "contract_current_amount": parse_money(row.get("contract_current_amount")),
        "contract_invoiced_amount": parse_money(row.get("contract_invoiced_amount")),
        "amount_evidence": (
            "NYCHA source line/release/contract amounts are preserved at their source granularity; "
            "repeated contract-level amounts are not summed across line rows."
        ),
        "service_category": classification["service_category"],
        "service_confidence": classification["confidence"],
        "classification_terms": classification["matched_terms"],
        "classification_reason": classification["reason"],
        "classification_layer": classification["classification_layer"],
        "source_dataset_id": "NYC_CHECKBOOK_CONTRACTS_NYCHA",
        "source_url": CONTRACT_API_URL,
        "retrieved_at": retrieved_at,
        "raw": dict(row),
    }


def build_payload(
    *,
    as_of: date | None = None,
    fiscal_year_count: int = DEFAULT_FISCAL_YEAR_COUNT,
    purpose_query_terms: Sequence[str] = PURPOSE_QUERY_TERMS,
    page_size: int = PAGE_SIZE,
    request_xml=_default_request_xml,
) -> dict[str, Any]:
    as_of = as_of or date.today()
    fiscal_years = recent_nyc_fiscal_years(as_of, fiscal_year_count)
    purpose_query_terms = tuple(normalize_space(term).lower() for term in purpose_query_terms if normalize_space(term))
    if not purpose_query_terms:
        raise ValueError("purpose_query_terms must contain at least one NYCHA purpose search term")
    generated_at = utc_now()
    partitions = [
        fetch_partition(year, purpose_query=term, page_size=page_size, request_xml=request_xml)
        for year in fiscal_years
        for term in purpose_query_terms
    ]

    relevant_rows: list[dict[str, Any]] = []
    seen_record_ids: set[str] = set()
    scanned_record_ids: set[str] = set()
    for partition in partitions:
        for row in partition.rows:
            scanned_record_ids.add(_source_record_id(row, partition.fiscal_year))
            normalized = normalize_row(
                row,
                fiscal_year=partition.fiscal_year,
                retrieved_at=generated_at,
            )
            if normalized is None:
                continue
            record_id = str(normalized["source_record_id"])
            if record_id in seen_record_ids:
                continue
            seen_record_ids.add(record_id)
            relevant_rows.append(normalized)

    contract_ids = {str(row["contract_id"]) for row in relevant_rows if row.get("contract_id")}
    vendor_keys = {str(row["vendor_key"]) for row in relevant_rows if row.get("vendor_key")}
    locations = {str(row["location"]) for row in relevant_rows if row.get("location")}
    categories = Counter(str(row["service_category"]) for row in relevant_rows)
    relevant_rows.sort(
        key=lambda row: (
            str(row.get("approved_date") or ""),
            str(row.get("contract_id") or ""),
            str(row.get("release_number") or ""),
            str(row.get("line_number") or ""),
        ),
        reverse=True,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "as_of_date": as_of.isoformat(),
        "domain": "NYCHA_WATER_CONTRACT_RELEASE_LINES",
        "source": {
            "name": "Checkbook NYC - NYCHA Contracts",
            "api_url": API_URL,
            "contract_api_url": CONTRACT_API_URL,
            "type_of_data": "Contracts_NYCHA",
            "fiscal_years": list(fiscal_years),
            "purpose_query_terms": list(purpose_query_terms),
            "source_scope": "Bounded live Checkbook NYCHA purpose=value keyword partitions; item_description is retrieved and preserved but is not an accepted source-side search criterion.",
            "granularity": "release/line-item",
        },
        "evidence_semantics": {
            "vendor": "Source-reported NYCHA contract vendor; no fuzzy company merge is applied.",
            "location": "NYCHA source location context; not automatically an exact building/tower/property link.",
            "amounts": "Line, release and contract amount fields are preserved separately and are not multiplied across repeated rows.",
            "invoiced": "Source-reported invoiced amounts are not represented as company revenue.",
        },
        "summary": {
            "fiscal_year_count": len(fiscal_years),
            "purpose_query_term_count": len(purpose_query_terms),
            "source_record_count": sum(partition.expected_count for partition in partitions),
            "fetched_record_count": sum(len(partition.rows) for partition in partitions),
            "unique_scanned_release_line_count": len(scanned_record_ids),
            "relevant_release_line_count": len(relevant_rows),
            "relevant_contract_count": len(contract_ids),
            "relevant_vendor_count": len(vendor_keys),
            "relevant_location_count": len(locations),
            "classification_counts": dict(sorted(categories.items())),
        },
        "source_health": [
            {
                "source": SOURCE,
                "fiscal_year": partition.fiscal_year,
                "purpose_query": partition.purpose_query,
                "status": "HEALTHY",
                "source_record_count": partition.expected_count,
                "fetched_record_count": len(partition.rows),
                "pagination_complete": partition.pagination_complete,
                "schema_valid": True,
            }
            for partition in partitions
        ],
        "records": relevant_rows,
    }
