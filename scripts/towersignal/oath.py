from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Iterable
import time

from towersignal.fetch import SourceFetchError, fetch_metadata, fetch_where

OATH_DATASET_ID = "jz4z-kudi"
OATH_SOURCE_URL = "https://data.cityofnewyork.us/City-Government/OATH-Hearings-Division-Case-Status/jz4z-kudi"
MATCH_BASIS = "SUMMONS_NUMBER_EXACT"
MIN_EXPECTED_MATCH_RATIO = 0.90
DEFAULT_BATCH_SIZE = 250
DEFAULT_MAX_WORKERS = 2
OATH_RATE_LIMIT_RETRIES = 4
OATH_TIMEOUT_SPLIT_AFTER_ATTEMPTS = 2
OATH_MIN_SPLIT_BATCH_SIZE = 25
OATH_REQUEST_RETRIES = 1
OATH_REQUEST_TIMEOUT_SECONDS = 30
OATH_AGENCY_SLICE_MIN_REQUESTED = 1000
OATH_AGENCY_PAGE_SIZE = 10000
OATH_AGENCY_MIN_PAGE_SIZE = 500
OATH_AGENCY_PAGE_RETRIES = 3
OATH_AGENCY_PAGE_REQUEST_RETRIES = 1
OATH_AGENCY_PAGE_TIMEOUT_SECONDS = 20
OATH_AGENCY_SNAPSHOT_ATTEMPTS = 2
OATH_COOLING_TOWER_AGENCY = "COOLING TOWERS - DOHMH"

OATH_SELECT = ",".join([
    "ticket_number", "issuing_agency", "violation_date",
    "violation_location_borough", "violation_location_block_no", "violation_location_lot_no",
    "violation_location_house", "violation_location_street_name", "violation_location_zip_code",
    "hearing_status", "hearing_result", "hearing_date", "decision_date", "compliance_status",
    "violation_description", "violation_details", "penalty_imposed", "paid_amount",
    "additional_penalties_or_late_fees", "balance_due", "total_violation_amount", "date_judgment_docketed",
    *[field for index in range(1, 11) for field in (
        f"charge_{index}_code", f"charge_{index}_code_section",
        f"charge_{index}_code_description", f"charge_{index}_infraction_amount",
    )],
])


def normalize_ticket_number(value: Any) -> str | None:
    if value is None:
        return None
    text = "".join(ch for ch in str(value).strip().upper() if ch.isalnum())
    return text or None


def _date_only(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return text


def _number(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _charges(row: dict[str, Any]) -> list[dict[str, Any]]:
    charges: list[dict[str, Any]] = []
    for index in range(1, 11):
        code = row.get(f"charge_{index}_code")
        section = row.get(f"charge_{index}_code_section")
        description = row.get(f"charge_{index}_code_description")
        amount = row.get(f"charge_{index}_infraction_amount")
        if not any(value not in (None, "") for value in (code, section, description, amount)):
            continue
        charges.append({"code": code or None, "code_section": section or None, "description": description or None, "infraction_amount": _number(amount)})
    return charges


def normalize_case(row: dict[str, Any]) -> dict[str, Any] | None:
    ticket_number = normalize_ticket_number(row.get("ticket_number"))
    if not ticket_number:
        return None
    return {
        "ticket_number": ticket_number,
        "ticket_number_source_raw": row.get("ticket_number"),
        "match_basis": MATCH_BASIS,
        "issuing_agency": row.get("issuing_agency") or None,
        "violation_date": _date_only(row.get("violation_date")),
        "violation_location": {
            "borough": row.get("violation_location_borough") or None,
            "block": row.get("violation_location_block_no") or None,
            "lot": row.get("violation_location_lot_no") or None,
            "house": row.get("violation_location_house") or None,
            "street_name": row.get("violation_location_street_name") or None,
            "zip": row.get("violation_location_zip_code") or None,
        },
        "hearing_status": row.get("hearing_status") or None,
        "hearing_result": row.get("hearing_result") or None,
        "hearing_date": _date_only(row.get("hearing_date")),
        "decision_date": _date_only(row.get("decision_date")),
        "compliance_status": row.get("compliance_status") or None,
        "violation_description": row.get("violation_description") or row.get("violation_details") or None,
        "penalty_imposed": _number(row.get("penalty_imposed")),
        "paid_amount": _number(row.get("paid_amount")),
        "additional_penalties_or_late_fees": _number(row.get("additional_penalties_or_late_fees")),
        "balance_due": _number(row.get("balance_due")),
        "total_violation_amount": _number(row.get("total_violation_amount")),
        "date_judgment_docketed": _date_only(row.get("date_judgment_docketed")),
        "charges": _charges(row),
    }


def _completeness(case: dict[str, Any]) -> int:
    score = 0
    for key, value in case.items():
        if key in {"ticket_number_source_raw", "match_basis"}:
            continue
        if isinstance(value, dict):
            score += sum(1 for item in value.values() if item not in (None, "", []))
        elif isinstance(value, list):
            score += len(value)
        elif value not in (None, ""):
            score += 1
    return score


def validate_match_coverage(requested_count: int, matched_count: int, minimum_ratio: float = MIN_EXPECTED_MATCH_RATIO) -> None:
    if requested_count < 100:
        return
    ratio = matched_count / requested_count if requested_count else 1.0
    if ratio < minimum_ratio:
        raise SourceFetchError(
            f"OATH exact-ticket match coverage collapsed to {matched_count:,}/{requested_count:,} ({ratio:.1%}); "
            f"expected at least {minimum_ratio:.0%}. Refusing to publish a potentially incomplete lifecycle snapshot."
        )


def _is_transient_oath_error(exc: SourceFetchError) -> bool:
    message = str(exc).lower()
    return "429" in message or "too many requests" in message or "timeout" in message or "timed out" in message


def _is_timeout_oath_error(exc: SourceFetchError) -> bool:
    message = str(exc).lower()
    return "timeout" in message or "timed out" in message


def _fetch_exact_ticket_batch(batch: list[str]) -> tuple[list[str], list[dict[str, Any]]]:
    quoted = ",".join("\'" + ticket.replace("\'", "\'\'") + "\'" for ticket in batch)
    where = f"ticket_number in ({quoted})"
    last_error: SourceFetchError | None = None
    for attempt in range(OATH_RATE_LIMIT_RETRIES):
        try:
            rows = fetch_where(
                OATH_DATASET_ID,
                where,
                select=OATH_SELECT,
                request_retries=OATH_REQUEST_RETRIES,
                request_timeout=OATH_REQUEST_TIMEOUT_SECONDS,
            )
            return batch, rows
        except SourceFetchError as exc:
            last_error = exc
            if not _is_transient_oath_error(exc):
                raise
            if (
                _is_timeout_oath_error(exc)
                and len(batch) > OATH_MIN_SPLIT_BATCH_SIZE
                and attempt + 1 >= OATH_TIMEOUT_SPLIT_AFTER_ATTEMPTS
            ):
                raise
            if attempt + 1 >= OATH_RATE_LIMIT_RETRIES:
                raise
            delay = 10 * (attempt + 1)
            print(
                f"[oath] Transient OATH source error while fetching {len(batch):,} exact tickets; "
                f"retrying in {delay}s",
                flush=True,
            )
            time.sleep(delay)
    raise last_error or SourceFetchError("OATH exact-ticket batch failed")


def _fetch_exact_ticket_batch_resilient(batch: list[str]) -> tuple[list[str], list[dict[str, Any]]]:
    try:
        return _fetch_exact_ticket_batch(batch)
    except SourceFetchError as exc:
        if not _is_timeout_oath_error(exc) or len(batch) <= OATH_MIN_SPLIT_BATCH_SIZE:
            raise
        midpoint = len(batch) // 2
        left = batch[:midpoint]
        right = batch[midpoint:]
        if not left or not right:
            raise
        print(
            f"[oath] Exact-ticket query for {len(batch):,} tickets timed out repeatedly; "
            f"splitting into {len(left):,} + {len(right):,} tickets",
            flush=True,
        )
        _, left_rows = _fetch_exact_ticket_batch_resilient(left)
        _, right_rows = _fetch_exact_ticket_batch_resilient(right)
        return batch, [*left_rows, *right_rows]

def _merge_exact_ticket_batch(cases: dict[str, dict[str, Any]], batch: list[str], rows: list[dict[str, Any]]) -> None:
    expected = set(batch)
    for row in rows:
        case = normalize_case(row)
        if not case:
            continue
        ticket = case["ticket_number"]
        if ticket not in expected:
            raise SourceFetchError(f"OATH query returned unexpected ticket {ticket}")
        existing = cases.get(ticket)
        if existing is None or _completeness(case) > _completeness(existing):
            cases[ticket] = case


def _cooling_tower_agency_where() -> str:
    agency = OATH_COOLING_TOWER_AGENCY.replace("'", "''")
    return f"issuing_agency='{agency}'"


def _fetch_agency_count(where: str) -> int:
    count_rows = fetch_where(
        OATH_DATASET_ID,
        where,
        select="count(*) as count",
        request_retries=OATH_RATE_LIMIT_RETRIES,
        request_timeout=OATH_REQUEST_TIMEOUT_SECONDS,
        limit=1,
    )
    try:
        return int(count_rows[0]["count"])
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        raise SourceFetchError("OATH cooling-tower agency count returned an unexpected payload") from exc


def _fetch_agency_seek_page(page_where: str, page_size: int) -> tuple[list[dict[str, Any]], int]:
    current_size = max(OATH_AGENCY_MIN_PAGE_SIZE, min(page_size, OATH_AGENCY_PAGE_SIZE))
    transient_attempt = 0
    while True:
        try:
            rows = fetch_where(
                OATH_DATASET_ID,
                page_where,
                order_by="ticket_number",
                select=OATH_SELECT,
                request_retries=OATH_AGENCY_PAGE_REQUEST_RETRIES,
                request_timeout=OATH_AGENCY_PAGE_TIMEOUT_SECONDS,
                limit=current_size,
            )
            return rows, current_size
        except SourceFetchError as exc:
            if not _is_transient_oath_error(exc):
                raise
            if _is_timeout_oath_error(exc) and current_size > OATH_AGENCY_MIN_PAGE_SIZE:
                next_size = max(OATH_AGENCY_MIN_PAGE_SIZE, current_size // 2)
                print(
                    f"[oath] OATH agency seek page timed out at {current_size:,} rows; "
                    f"retrying the same cursor at {next_size:,} rows",
                    flush=True,
                )
                current_size = next_size
                transient_attempt = 0
                continue
            transient_attempt += 1
            if transient_attempt >= OATH_AGENCY_PAGE_RETRIES:
                raise
            delay = 5 * transient_attempt
            print(
                f"[oath] Transient OATH agency-page error at {current_size:,} rows; "
                f"retrying the same cursor in {delay}s",
                flush=True,
            )
            time.sleep(delay)


def _fetch_exact_ticket_fallback(
    requested: set[str],
    *,
    seed_cases: dict[str, dict[str, Any]] | None = None,
    seed_query_row_count: int = 0,
) -> tuple[dict[str, dict[str, Any]], int]:
    requested_list = sorted(requested)
    cases: dict[str, dict[str, Any]] = dict(seed_cases or {})
    unresolved = [ticket for ticket in requested_list if ticket not in cases]
    batches = [
        unresolved[start : start + DEFAULT_BATCH_SIZE]
        for start in range(0, len(unresolved), DEFAULT_BATCH_SIZE)
    ]
    query_row_count = seed_query_row_count
    worker_count = max(1, min(DEFAULT_MAX_WORKERS, len(batches))) if batches else 1
    print(
        f"[oath] Falling back to {len(batches):,} exact-ticket batches for {len(unresolved):,} unresolved "
        f"tickets with {worker_count} worker(s) after the agency-slice scan could not produce a stable complete snapshot",
        flush=True,
    )
    if batches:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [executor.submit(_fetch_exact_ticket_batch_resilient, batch) for batch in batches]
            for completed_count, future in enumerate(as_completed(futures), start=1):
                batch, rows = future.result()
                query_row_count += len(rows)
                _merge_exact_ticket_batch(cases, batch, rows)
                if completed_count % 25 == 0 or completed_count == len(batches):
                    print(
                        f"[oath] Exact-ticket fallback completed {completed_count:,}/{len(batches):,} batches; "
                        f"matched {len(cases):,}/{len(requested_list):,} tickets",
                        flush=True,
                    )
    validate_match_coverage(len(requested_list), len(cases))
    return cases, query_row_count


def _fetch_cooling_tower_agency_cases(requested: set[str]) -> tuple[dict[str, dict[str, Any]], int, bool]:
    where = _cooling_tower_agency_where()
    last_counts: tuple[int, int, int] | None = None

    for snapshot_attempt in range(1, OATH_AGENCY_SNAPSHOT_ATTEMPTS + 1):
        try:
            expected_count = _fetch_agency_count(where)
        except SourceFetchError as exc:
            if not _is_transient_oath_error(exc):
                raise
            print(
                f"[oath] Transient OATH agency-count failure ({exc}); "
                "using exact-ticket fallback instead of abandoning the lifecycle build",
                flush=True,
            )
            cases, query_row_count = _fetch_exact_ticket_fallback(requested)
            return cases, query_row_count, True
        print(
            f"[oath] Fetching {expected_count:,} {OATH_COOLING_TOWER_AGENCY} cases "
            f"(snapshot attempt {snapshot_attempt}/{OATH_AGENCY_SNAPSHOT_ATTEMPTS}) with seek pagination; "
            f"intersecting with {len(requested):,} exact summons tickets",
            flush=True,
        )
        cases: dict[str, dict[str, Any]] = {}
        fetched_count = 0
        cursor: str | None = None
        page_size = OATH_AGENCY_PAGE_SIZE
        while True:
            page_where = where
            if cursor is not None:
                escaped_cursor = cursor.replace("'", "''")
                page_where = f"{where} AND ticket_number > '{escaped_cursor}'"
            try:
                rows, page_size = _fetch_agency_seek_page(page_where, page_size)
            except SourceFetchError as exc:
                if not _is_transient_oath_error(exc):
                    raise
                print(
                    f"[oath] OATH agency seek page still failed at the minimum adaptive page size ({exc}); "
                    "using exact-ticket fallback instead of abandoning the lifecycle build",
                    flush=True,
                )
                fallback_cases, query_row_count = _fetch_exact_ticket_fallback(
                    requested,
                    seed_cases=cases,
                    seed_query_row_count=fetched_count,
                )
                return fallback_cases, query_row_count, True
            if not rows:
                break
            raw_tickets = [str(row.get("ticket_number") or "").strip() for row in rows]
            if any(not ticket for ticket in raw_tickets):
                raise SourceFetchError("OATH agency seek page returned a row without ticket_number")
            if raw_tickets != sorted(raw_tickets):
                raise SourceFetchError("OATH agency seek page violated ticket_number ordering")
            if cursor is not None and raw_tickets[0] <= cursor:
                raise SourceFetchError(
                    f"OATH agency seek pagination did not advance beyond ticket_number {cursor}"
                )
            next_cursor = raw_tickets[-1]
            if cursor is not None and next_cursor <= cursor:
                raise SourceFetchError(
                    f"OATH agency seek cursor did not advance: {cursor} -> {next_cursor}"
                )
            fetched_count += len(rows)
            for row in rows:
                case = normalize_case(row)
                if not case:
                    continue
                ticket = case["ticket_number"]
                if ticket not in requested:
                    continue
                existing = cases.get(ticket)
                if existing is None or _completeness(case) > _completeness(existing):
                    cases[ticket] = case
            cursor = next_cursor
            print(
                f"[oath] Read {fetched_count:,}/{expected_count:,} agency-slice cases; "
                f"matched {len(cases):,}/{len(requested):,} requested tickets; cursor={cursor}",
                flush=True,
            )
            if len(rows) < page_size:
                break

        try:
            final_count = _fetch_agency_count(where)
        except SourceFetchError as exc:
            if not _is_transient_oath_error(exc):
                raise
            print(
                f"[oath] Transient OATH agency-final-count failure ({exc}); "
                "using exact-ticket fallback instead of publishing an unverifiable agency snapshot",
                flush=True,
            )
            fallback_cases, query_row_count = _fetch_exact_ticket_fallback(requested)
            return fallback_cases, query_row_count, True
        last_counts = (expected_count, fetched_count, final_count)
        if expected_count == fetched_count == final_count:
            return cases, fetched_count, False

        if snapshot_attempt < OATH_AGENCY_SNAPSHOT_ATTEMPTS:
            print(
                f"[oath] OATH agency slice changed during seek pagination: start count {expected_count:,}, "
                f"fetched {fetched_count:,}, end count {final_count:,}; restarting from the first key",
                flush=True,
            )

    start_count, fetched_count, end_count = last_counts or (0, 0, 0)
    print(
        f"[oath] OATH agency slice did not stabilize after {OATH_AGENCY_SNAPSHOT_ATTEMPTS} seek attempts: "
        f"start count {start_count:,}, fetched {fetched_count:,}, end count {end_count:,}. "
        "Using exact-ticket fallback rather than publishing a mixed agency snapshot.",
        flush=True,
    )
    cases, query_row_count = _fetch_exact_ticket_fallback(requested)
    return cases, query_row_count, True


def fetch_oath_cases(
    ticket_numbers: Iterable[str],
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    requested = sorted({ticket for value in ticket_numbers if (ticket := normalize_ticket_number(value))})
    cases: dict[str, dict[str, Any]] = {}
    query_row_count = 0
    query_scope = "Exact ticket_number queries for summonses present in NYC Cooling Tower System Inspection Results"

    if len(requested) >= OATH_AGENCY_SLICE_MIN_REQUESTED:
        cases, query_row_count, used_exact_fallback = _fetch_cooling_tower_agency_cases(set(requested))
        query_scope = (
            f"OATH issuing_agency='{OATH_COOLING_TOWER_AGENCY}' rows intersected by exact "
            "NYC Health summons_number values"
        )
        if used_exact_fallback:
            query_scope += "; unstable agency snapshot fell back to exact ticket_number batches"
    else:
        batches = [requested[start : start + batch_size] for start in range(0, len(requested), batch_size)]
        worker_count = max(1, min(max_workers, len(batches))) if batches else 1

        if batches:
            print(
                f"[oath] Fetching {len(requested):,} exact tickets in {len(batches):,} batches with {worker_count} worker(s)",
                flush=True,
            )
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = [executor.submit(_fetch_exact_ticket_batch_resilient, batch) for batch in batches]
                for completed_count, future in enumerate(as_completed(futures), start=1):
                    batch, rows = future.result()
                    query_row_count += len(rows)
                    _merge_exact_ticket_batch(cases, batch, rows)
                    if completed_count % 10 == 0 or completed_count == len(batches):
                        print(
                            f"[oath] Completed {completed_count:,}/{len(batches):,} exact-ticket batches; "
                            f"matched {len(cases):,}/{len(requested):,} tickets so far",
                            flush=True,
                        )

    metadata = fetch_metadata(OATH_DATASET_ID)
    matched = set(cases)
    validate_match_coverage(len(requested), len(matched))
    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return cases, {
        "dataset_id": OATH_DATASET_ID,
        "name": metadata["name"],
        "retrieved_at": retrieved_at,
        "source_record_count": query_row_count,
        "source_query_scope": query_scope,
        "source_last_updated_at": metadata.get("source_last_updated_at"),
        "url": OATH_SOURCE_URL,
        "requested_ticket_count": len(requested),
        "matched_ticket_count": len(matched),
        "unmatched_ticket_count": len(set(requested) - matched),
        "matched_case_count": len(cases),
    }


def summons_numbers_from_inspections(inspections_by_system: dict[str, list[dict[str, Any]]]) -> set[str]:
    values: set[str] = set()
    for inspections in inspections_by_system.values():
        for inspection in inspections:
            for violation in inspection.get("violations", []):
                ticket = normalize_ticket_number(violation.get("summons_number"))
                if ticket:
                    values.add(ticket)
    return values


def cases_for_system(inspections: list[dict[str, Any]], cases_by_ticket: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    tickets: set[str] = set()
    for inspection in inspections:
        for violation in inspection.get("violations", []):
            ticket = normalize_ticket_number(violation.get("summons_number"))
            if ticket:
                tickets.add(ticket)
    cases = [cases_by_ticket[ticket] for ticket in tickets if ticket in cases_by_ticket]
    return sorted(cases, key=lambda item: (item.get("violation_date") or "", item["ticket_number"]), reverse=True)
