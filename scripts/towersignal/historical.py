from __future__ import annotations

from datetime import date
from statistics import mean
from typing import Any

from .normalize import parse_date


def _iso_date(value: Any) -> str | None:
    parsed = parse_date(value)
    return parsed.isoformat() if parsed else None


def _sum_money(rows: list[dict[str, Any]], key: str) -> float:
    total = 0.0
    for row in rows:
        value = row.get(key)
        if value is None:
            continue
        try:
            total += float(value)
        except (TypeError, ValueError):
            continue
    return round(total, 2)


def build_historical_profile(
    system: dict[str, Any],
    inspections: list[dict[str, Any]],
    oath_cases: list[dict[str, Any]],
    snapshot_date: date,
) -> dict[str, Any]:
    registration_date = _iso_date(system.get("date_registered"))
    registration_age_days = None
    if registration_date:
        registration_age_days = max(0, (snapshot_date - date.fromisoformat(registration_date)).days)

    sample_dates = [value for value in system.get("sample_dates", []) if value]
    sample_intervals = [int(value) for value in system.get("sample_intervals_days", [])]

    inspection_dates = sorted(
        value
        for value in (_iso_date(item.get("inspection_date")) for item in inspections)
        if value
    )
    violation_inspections = [item for item in inspections if int(item.get("violation_count") or 0) > 0]
    violation_dates = sorted(
        value
        for value in (_iso_date(item.get("inspection_date")) for item in violation_inspections)
        if value
    )
    violation_citation_count = sum(int(item.get("violation_count") or 0) for item in inspections)

    evidence_dates = [
        value
        for value in (
            registration_date,
            sample_dates[0] if sample_dates else None,
            inspection_dates[0] if inspection_dates else None,
        )
        if value
    ]

    return {
        "registration_date": registration_date,
        "registration_age_days": registration_age_days,
        "first_public_evidence_date": min(evidence_dates) if evidence_dates else None,
        "sample": {
            "first_reported_date": sample_dates[0] if sample_dates else None,
            "latest_reported_date": sample_dates[-1] if sample_dates else None,
            "reported_sample_count": len(sample_dates),
            "average_interval_days": round(mean(sample_intervals), 1) if sample_intervals else None,
            "longest_interval_days": max(sample_intervals) if sample_intervals else None,
        },
        "inspection": {
            "first_inspection_date": inspection_dates[0] if inspection_dates else None,
            "latest_inspection_date": inspection_dates[-1] if inspection_dates else None,
            "inspection_count": len(inspections),
            "inspections_with_violations": len(violation_inspections),
            "violation_citation_count": violation_citation_count,
            "first_violation_date": violation_dates[0] if violation_dates else None,
            "latest_violation_date": violation_dates[-1] if violation_dates else None,
        },
        "oath": {
            "case_count": len(oath_cases),
            "penalty_imposed_total": _sum_money(oath_cases, "penalty_imposed"),
            "paid_amount_total": _sum_money(oath_cases, "paid_amount"),
            "balance_due_total": _sum_money(oath_cases, "balance_due"),
        },
    }
