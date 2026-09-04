from __future__ import annotations

import csv
import hashlib
import io
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from towersignal.procurement import (
    classify_procurement,
    normalize_company_name,
    normalize_space,
    parse_iso_date,
    parse_money,
    stable_id,
)

SCHEMA_VERSION = "1.0"
SOURCE_URL = "https://wwe2.osc.state.ny.us/transparency/contracts/contractresults.cfm"
SOURCE_PAGE = "https://wwe2.osc.state.ny.us/transparency/contracts/contractsearch.cfm"
USER_AGENT = "TowerSignal/1.0 (+https://github.com/JeremyHennessy/TowerSignal)"

HEADER_ALIASES = {
    "transaction_type": ("TRANSACTION TYPE", "TYPE"),
    "vendor": ("VENDOR NAME", "VENDOR"),
    "department": ("DEPARTMENT/FACILITY", "DEPARTMENT / FACILITY", "DEPARTMENT"),
    "contract": ("CONTRACT NUMBER", "CONTRACT"),
    "amount": ("TRANSACTION AMOUNT", "AMOUNT"),
    "start": ("START DATE", "CONTRACT START DATE"),
    "end": ("END DATE", "CONTRACT END DATE"),
    "description": ("CONTRACT DESCRIPTION", "DESCRIPTION"),
    "approved": (
        "TRANSACTION APPROVED/FILED DATE",
        "APPROVED/FILED DATE",
        "TRANSACTION APPROVED FILED DATE",
    ),
}

SUPPLEMENTAL_RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
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

SUPPLEMENTAL_NEGATIVES = (
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


class OpenBookSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class FetchResult:
    payload: bytes
    retrieved_at: str
    content_type: str | None
    content_length: int | None
    last_modified: str | None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def export_params(as_of: date) -> dict[str, str]:
    return {
        "DocType": "csv",
        "ac": "",
        "v": "",
        "vo": "B",
        "cn": "",
        "selOrigDateChoiceOperator": "Before",
        "txtOrigFromDate": as_of.strftime("%m/%d/%Y"),
        "txtOrigToDate": "",
        "selCTDateChoice": "0",
        "selCTDateChoiceOperator": "0",
        "txtCTFromDate": "",
        "txtCTToDate": "",
        "selContractAmountChoice": "0",
        "txtContractAmount1": "",
        "txtContractAmount2": "",
        "b": "Search",
        "order": "VENDOR_NAME",
        "sort": "ASC",
    }


def build_export_url(as_of: date) -> str:
    return f"{SOURCE_URL}?{urlencode(export_params(as_of))}"


def fetch_export(as_of: date, *, retries: int = 4, timeout: int = 180) -> FetchResult:
    url = build_export_url(as_of)
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/csv,text/plain,application/octet-stream,*/*",
                },
            )
            with urlopen(request, timeout=timeout) as response:
                payload = response.read()
                headers = response.headers
            if len(payload) < 1000:
                raise OpenBookSourceError(f"Open Book export unexpectedly small: {len(payload)} bytes")
            return FetchResult(
                payload=payload,
                retrieved_at=utc_now(),
                content_type=headers.get("Content-Type"),
                content_length=(
                    int(headers.get("Content-Length"))
                    if str(headers.get("Content-Length") or "").isdigit()
                    else None
                ),
                last_modified=headers.get("Last-Modified"),
            )
        except (HTTPError, URLError, TimeoutError, OpenBookSourceError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(2**attempt)
    raise OpenBookSourceError(
        f"Failed to retrieve Open Book CSV export after {retries} attempts: {last_error}"
    )


def _decode(payload: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise OpenBookSourceError("Open Book CSV export could not be decoded")


def _header_key(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", normalize_space(value).upper()).strip()


def _resolve_headers(headers: Sequence[str]) -> dict[str, int]:
    normalized = [_header_key(value) for value in headers]
    resolved: dict[str, int] = {}
    for canonical, aliases in HEADER_ALIASES.items():
        candidates = {_header_key(alias) for alias in aliases}
        for index, header in enumerate(normalized):
            if header in candidates:
                resolved[canonical] = index
                break
    missing = sorted(set(HEADER_ALIASES) - set(resolved))
    if missing:
        raise OpenBookSourceError(
            f"Open Book CSV missing required columns: {', '.join(missing)}"
        )
    return resolved


def parse_export(payload: bytes) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    text = _decode(payload).replace("\x00", "")
    all_rows = list(csv.reader(io.StringIO(text)))
    if not all_rows:
        raise OpenBookSourceError("Open Book CSV export is empty")

    header_index: int | None = None
    header_map: dict[str, int] | None = None
    for index, row in enumerate(all_rows[:10]):
        try:
            candidate = _resolve_headers(row)
        except OpenBookSourceError:
            continue
        header_index = index
        header_map = candidate
        break
    if header_index is None or header_map is None:
        raise OpenBookSourceError(
            "Open Book CSV header row was not found in the first 10 rows"
        )

    headers = all_rows[header_index]
    records: list[dict[str, Any]] = []
    skipped_blank_rows = 0
    for source_row_number, row in enumerate(
        all_rows[header_index + 1 :], start=header_index + 2
    ):
        if not any(normalize_space(value) for value in row):
            skipped_blank_rows += 1
            continue
        if len(row) < len(headers):
            row = [*row, *([""] * (len(headers) - len(row)))]

        def value(name: str) -> str:
            column = header_map[name]
            return normalize_space(row[column] if column < len(row) else "")

        vendor = value("vendor")
        department = value("department")
        contract_number = value("contract")
        if not vendor or not department or not contract_number:
            raise OpenBookSourceError(
                f"Open Book row {source_row_number} missing vendor/department/contract identity"
            )
        records.append(
            {
                "source_row_number": source_row_number,
                "transaction_type": value("transaction_type") or None,
                "vendor_raw": vendor,
                "vendor_key": normalize_company_name(vendor),
                "department_facility": department,
                "contract_number": contract_number,
                "transaction_amount": parse_money(value("amount")),
                "start_date": parse_iso_date(value("start")),
                "end_date": parse_iso_date(value("end")),
                "description": value("description") or None,
                "approved_filed_date": parse_iso_date(value("approved")),
                "raw": {
                    headers[i]: row[i] if i < len(row) else ""
                    for i in range(len(headers))
                },
            }
        )
    if not records:
        raise OpenBookSourceError(
            "Open Book CSV contained no contract transaction records"
        )
    return records, {
        "header_row_number": header_index + 1,
        "headers": headers,
        "skipped_blank_row_count": skipped_blank_rows,
    }


def classify_water_contract(text: str) -> dict[str, Any]:
    source_text = normalize_space(text)
    primary = classify_procurement(source_text)
    if primary.service_category != "UNRELATED":
        return {
            "service_category": primary.service_category,
            "confidence": primary.confidence,
            "matched_terms": list(primary.matched_terms),
            "reason": primary.reason,
            "classification_layer": "TOWERSIGNAL_PROCUREMENT",
        }

    lowered = source_text.lower()
    if any(term in lowered for term in SUPPLEMENTAL_NEGATIVES):
        return {
            "service_category": "UNRELATED",
            "confidence": "STRONG",
            "matched_terms": [
                term for term in SUPPLEMENTAL_NEGATIVES if term in lowered
            ],
            "reason": (
                "Supplemental domestic-water classifier excluded a "
                "non-building-water context"
            ),
            "classification_layer": "OPENBOOK_DOMESTIC_WATER",
        }

    for category, confidence, terms in SUPPLEMENTAL_RULES:
        matched = [term for term in terms if term in lowered]
        if matched:
            return {
                "service_category": category,
                "confidence": confidence,
                "matched_terms": matched,
                "reason": (
                    "Explicit domestic/building-water wording in Open Book contract text"
                ),
                "classification_layer": "OPENBOOK_DOMESTIC_WATER",
            }
    return {
        "service_category": "UNRELATED",
        "confidence": "CONFIRMED",
        "matched_terms": [],
        "reason": "No supported cooling/building-water service language",
        "classification_layer": "OPENBOOK_DOMESTIC_WATER",
    }


def _contract_status(
    start_date: str | None, end_date: str | None, as_of: date
) -> str:
    start = date.fromisoformat(start_date) if start_date else None
    end = date.fromisoformat(end_date) if end_date else None
    if start and start > as_of:
        return "FUTURE_BY_SOURCE_DATES"
    if end and end < as_of:
        return "ENDED_BY_SOURCE_DATE"
    if (not start or start <= as_of) and (not end or end >= as_of):
        return "ACTIVE_OR_OPEN_BY_SOURCE_DATES"
    return "UNKNOWN"


def _contract_key(row: Mapping[str, Any]) -> str:
    return stable_id(
        "openbook-contract",
        row.get("vendor_key"),
        row.get("department_facility"),
        row.get("contract_number"),
    )


def build_payload(*, as_of: date | None = None) -> dict[str, Any]:
    as_of = as_of or date.today()
    fetched = fetch_export(as_of)
    rows, csv_meta = parse_export(fetched.payload)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_contract_key(row)].append(row)

    relevant_contracts: list[dict[str, Any]] = []
    relevant_transaction_count = 0
    classification_counts: Counter[str] = Counter()
    relevant_vendors: set[str] = set()

    for contract_id, transactions in grouped.items():
        descriptions = list(
            dict.fromkeys(
                normalize_space(row.get("description"))
                for row in transactions
                if normalize_space(row.get("description"))
            )
        )
        classification = classify_water_contract(" | ".join(descriptions))
        if classification["service_category"] == "UNRELATED":
            continue

        relevant_transaction_count += len(transactions)
        classification_counts[str(classification["service_category"])] += 1
        relevant_vendors.add(str(transactions[0]["vendor_key"]))

        amounts = [
            row["transaction_amount"]
            for row in transactions
            if row.get("transaction_amount") is not None
        ]
        starts = sorted(
            {str(row["start_date"]) for row in transactions if row.get("start_date")}
        )
        ends = sorted(
            {str(row["end_date"]) for row in transactions if row.get("end_date")}
        )
        approved = sorted(
            {
                str(row["approved_filed_date"])
                for row in transactions
                if row.get("approved_filed_date")
            }
        )
        original_amounts = [
            row["transaction_amount"]
            for row in transactions
            if row.get("transaction_amount") is not None
            and str(row.get("transaction_type") or "")
            .upper()
            .startswith("ORIGINAL")
        ]

        source_transactions: list[dict[str, Any]] = []
        for row in transactions:
            source_transactions.append(
                {
                    **row,
                    "transaction_id": stable_id(
                        "openbook-transaction",
                        contract_id,
                        row["source_row_number"],
                        row.get("transaction_type"),
                        row.get("approved_filed_date"),
                        row.get("transaction_amount"),
                    ),
                }
            )

        start_date = starts[0] if starts else None
        end_date = ends[-1] if ends else None
        relevant_contracts.append(
            {
                "schema_version": SCHEMA_VERSION,
                "contract_id": contract_id,
                "source": "NYS_OPEN_BOOK",
                "source_contract_number": transactions[0]["contract_number"],
                "vendor_raw": transactions[0]["vendor_raw"],
                "vendor_key": transactions[0]["vendor_key"],
                "company_id": None,
                "company_match_confidence": "UNRESOLVED",
                "department_facility": transactions[0]["department_facility"],
                "service_category": classification["service_category"],
                "service_confidence": classification["confidence"],
                "classification_terms": classification["matched_terms"],
                "classification_reason": classification["reason"],
                "classification_layer": classification["classification_layer"],
                "descriptions": descriptions,
                "transaction_count": len(transactions),
                "original_transaction_amount_total": (
                    round(sum(original_amounts), 2) if original_amounts else None
                ),
                "net_transaction_amount": (
                    round(sum(amounts), 2) if amounts else None
                ),
                "amount_evidence": (
                    "Net/source transaction amounts from Open Book contract and "
                    "amendment history; not company revenue and not labeled as "
                    "spending-to-date."
                ),
                "start_date": start_date,
                "end_date": end_date,
                "latest_approved_filed_date": approved[-1] if approved else None,
                "source_date_status": _contract_status(
                    start_date, end_date, as_of
                ),
                "source_url": SOURCE_PAGE,
                "transactions": source_transactions,
            }
        )

    relevant_contracts.sort(
        key=lambda row: (
            str(row.get("latest_approved_filed_date") or ""),
            str(row.get("vendor_key") or ""),
            str(row.get("contract_id") or ""),
        ),
        reverse=True,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": fetched.retrieved_at,
        "as_of_date": as_of.isoformat(),
        "domain": "NYS_OPEN_BOOK_WATER_CONTRACT_TRANSACTIONS",
        "source": {
            "name": "Open Book New York - Office of the State Comptroller",
            "search_page": SOURCE_PAGE,
            "export_url": build_export_url(as_of),
            "content_type": fetched.content_type,
            "content_length": fetched.content_length,
            "last_modified": fetched.last_modified,
            "sha256": hashlib.sha256(fetched.payload).hexdigest(),
            "header_row_number": csv_meta["header_row_number"],
            "headers": csv_meta["headers"],
            "skipped_blank_row_count": csv_meta["skipped_blank_row_count"],
            "transport_complete": True,
            "schema_valid": True,
        },
        "evidence_semantics": {
            "transaction_amount": (
                "Open Book transaction amount for an original contract or amendment. "
                "It is public contract evidence, not vendor revenue."
            ),
            "net_transaction_amount": (
                "TowerSignal sum of source transaction amounts for the contract identity; "
                "it is not represented as spending-to-date."
            ),
            "vendor_identity": (
                "Open Book vendor string is preserved; no fuzzy company merge is applied."
            ),
            "facility_identity": (
                "Department/Facility is source-reported contracting context and is not "
                "automatically an exact building/tower/property link."
            ),
        },
        "summary": {
            "source_transaction_count": len(rows),
            "source_contract_count": len(grouped),
            "relevant_contract_count": len(relevant_contracts),
            "relevant_transaction_count": relevant_transaction_count,
            "relevant_vendor_count": len(relevant_vendors),
            "classification_counts": dict(sorted(classification_counts.items())),
        },
        "contracts": relevant_contracts,
    }
