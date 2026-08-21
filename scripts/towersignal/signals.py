from __future__ import annotations

from datetime import date
from typing import Any

from .normalize import parse_date


def _days_since(snapshot_date: date, iso_date: str | None) -> int | None:
    parsed = parse_date(iso_date)
    if parsed is None:
        return None
    return (snapshot_date - parsed).days


def _confirmed_violation_signal(inspections: list[dict[str, Any]], snapshot_date: date, recent_days: int) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for inspection in inspections:
        age = _days_since(snapshot_date, inspection.get("inspection_date"))
        if age is None or age < 0 or age > recent_days or not inspection.get("violations"):
            continue
        candidates.append(inspection)
    if not candidates:
        return None
    latest = sorted(candidates, key=lambda item: item.get("inspection_date") or "", reverse=True)[0]
    types = sorted({v.get("violation_type") for v in latest["violations"] if v.get("violation_type")})
    return {
        "type": "CONFIRMED_RECENT_VIOLATION",
        "title": "Confirmed violation",
        "evidence_confidence": "CONFIRMED",
        "fact_class": "CONFIRMED_FACT",
        "date": latest.get("inspection_date"),
        "reason": f"NYC Health inspection record contains {latest['violation_count']} violation(s) within the configured recent period.",
        "violation_types": types,
        "inspection_type": latest.get("inspection_type"),
    }


def build_signals(system: dict[str, Any], inspections: list[dict[str, Any]], rules: dict[str, Any], snapshot_date: date) -> dict[str, Any]:
    signals: list[dict[str, Any]] = []
    max_sample_days = int(rules["sampling"]["max_interval_days"])
    recent_violation_days = int(rules["signals"]["recent_violation_days"])
    recent_activity_days = int(rules["signals"]["recent_regulatory_activity_days"])

    confirmed = _confirmed_violation_signal(inspections, snapshot_date, recent_violation_days)
    if confirmed:
        signals.append(confirmed)

    days_since_sample = _days_since(snapshot_date, system.get("latest_sample_date"))
    if system.get("latest_sample_date") is None:
        signals.append(
            {
                "type": "NO_PUBLIC_SAMPLE_DATE",
                "title": "No public sample date",
                "evidence_confidence": "VERIFY",
                "fact_class": "COMMERCIAL_SIGNAL",
                "date": None,
                "reason": "The current public registration record does not include a usable reported sample date. Verify current operating and sampling status independently.",
            }
        )
    elif days_since_sample is not None and days_since_sample > max_sample_days:
        signals.append(
            {
                "type": "POTENTIAL_SAMPLING_GAP",
                "title": "Potential sampling gap",
                "evidence_confidence": "VERIFY",
                "fact_class": "COMMERCIAL_SIGNAL",
                "date": system.get("latest_sample_date"),
                "reason": (
                    f"The latest Legionella sample date appearing in NYC's public registration record is {days_since_sample} days old. "
                    f"NYC's {max_sample_days}-day sampling requirement applies while a system is operating. TowerSignal does not have enough public information to confirm continuous operating status, so this is a verification signal rather than a compliance determination."
                ),
            }
        )

    if int(system.get("active_equipment") or 0) > 1:
        signals.append(
            {
                "type": "MULTIPLE_ACTIVE_EQUIPMENT",
                "title": f"{system['active_equipment']} active tower units",
                "evidence_confidence": "STRONG_SIGNAL",
                "fact_class": "DERIVED_FACT",
                "date": None,
                "reason": "Multiple active pieces of cooling-tower equipment may indicate a higher-value service account. This is a commercial-value indicator, not a compliance signal.",
            }
        )

    latest_inspection = inspections[0] if inspections else None
    days_since_inspection = _days_since(snapshot_date, latest_inspection.get("inspection_date") if latest_inspection else None)
    if latest_inspection and days_since_inspection is not None and 0 <= days_since_inspection <= recent_activity_days:
        signals.append(
            {
                "type": "RECENT_NYC_HEALTH_INSPECTION",
                "title": "Recent NYC Health inspection",
                "evidence_confidence": "STRONG_SIGNAL",
                "fact_class": "CONFIRMED_FACT",
                "date": latest_inspection.get("inspection_date"),
                "reason": f"NYC Health recorded a {latest_inspection.get('inspection_type') or 'regulatory'} inspection {days_since_inspection} days ago.",
            }
        )

    any_confirmed_violation = any(inspection.get("violations") for inspection in inspections)
    violation_types = sorted(
        {
            violation.get("violation_type")
            for inspection in inspections
            for violation in inspection.get("violations", [])
            if violation.get("violation_type")
        }
    )
    return {
        "signals": signals,
        "days_since_latest_sample": days_since_sample,
        "latest_inspection": latest_inspection,
        "days_since_latest_inspection": days_since_inspection,
        "confirmed_violation": any_confirmed_violation,
        "recent_confirmed_violation": confirmed is not None,
        "violation_types": violation_types,
    }
