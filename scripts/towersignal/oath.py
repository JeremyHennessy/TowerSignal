from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from towersignal.fetch import fetch_count, fetch_metadata, fetch_where

OATH_DATASET_ID = "jz4z-kudi"
OATH_SOURCE_URL = "https://data.cityofnewyork.us/City-Government/OATH-Hearings-Division-Case-Status/jz4z-kudi"
MATCH_BASIS = "SUMMONS_NUMBER_EXACT"


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
        charges.append(
            {
                "code": code or None,
                "code_section": section or None,
                "description": description or None,
                "infraction_amount": _number(amount),
            }
        )
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


def fetch_oath_cases(ticket_numbers: Iterable[str], batch_size: int = 100) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    requested = sorted({ticket for value in ticket_numbers if (ticket := normalize_ticket_number(value))})
    cases: dict[str, dict[str, Any]] = {}

    for start in range(0, len(requested), batch_size):
        batch = requested[start : start + batch_size]
        quoted = ",".join("'" + ticket.replace("'", "''") + "'" for ticket in batch)
        rows = fetch_where(OATH_DATASET_ID, f"ticket_number in ({quoted})", order_by="ticket_number")
        expected = set(batch)
        for row in rows:
            case = normalize_case(row)
            if not case:
                continue
            ticket = case["ticket_number"]
            if ticket not in expected:
                raise RuntimeError(f"OATH query returned unexpected ticket {ticket}")
            existing = cases.get(ticket)
            if existing is None or _completeness(case) > _completeness(existing):
                cases[ticket] = case

    metadata = fetch_metadata(OATH_DATASET_ID)
    source_count = fetch_count(OATH_DATASET_ID)
    matched = set(cases)
    return cases, {
        "dataset_id": OATH_DATASET_ID,
        "name": metadata["name"],
        "source_record_count": source_count,
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
