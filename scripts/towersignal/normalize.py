from __future__ import annotations

from datetime import date, datetime
from typing import Any

DATE_FORMATS = ("%m/%d/%Y", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d")


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _float(value: Any) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def parse_date(value: Any) -> date | None:
    text = _clean(value)
    if not text:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_sample_dates(raw: Any) -> dict[str, Any]:
    original = "" if raw is None else str(raw)
    valid: set[date] = set()
    malformed: list[str] = []
    for token in original.split(","):
        text = token.strip()
        if not text:
            continue
        parsed = parse_date(text)
        if parsed is None:
            malformed.append(text)
        else:
            valid.add(parsed)
    dates = sorted(valid)
    intervals = [(dates[index] - dates[index - 1]).days for index in range(1, len(dates))]
    return {
        "raw": original,
        "dates": [item.isoformat() for item in dates],
        "malformed": malformed,
        "latest": dates[-1].isoformat() if dates else None,
        "previous": dates[-2].isoformat() if len(dates) > 1 else None,
        "latest_interval_days": intervals[-1] if intervals else None,
        "intervals": intervals,
        "count": len(dates),
    }


def registration_completeness(record: dict[str, Any]) -> tuple[int, int, str]:
    keys = (
        "bin",
        "system_id",
        "date_registered",
        "number",
        "street",
        "borough",
        "zip",
        "sampledates",
        "activeequipment",
        "bbl",
        "latitude",
        "longitude",
    )
    nonblank = sum(1 for key in keys if _clean(record.get(key)))
    samples = parse_sample_dates(record.get("sampledates"))["count"]
    return nonblank, samples, str(record)


def normalize_registrations(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    best: dict[str, dict[str, Any]] = {}
    duplicate_rows = 0
    missing_system_id = 0

    for row in rows:
        system_id = _clean(row.get("system_id"))
        if not system_id:
            missing_system_id += 1
            continue
        existing = best.get(system_id)
        if existing is None:
            best[system_id] = row
        else:
            duplicate_rows += 1
            if registration_completeness(row) > registration_completeness(existing):
                best[system_id] = row

    normalized: list[dict[str, Any]] = []
    for system_id, row in best.items():
        sample = parse_sample_dates(row.get("sampledates"))
        number = _clean(row.get("number"))
        street = _clean(row.get("street"))
        address = " ".join(part for part in (number, street) if part) or None
        normalized.append(
            {
                "system_id": system_id,
                "bin": _clean(row.get("bin")),
                "bbl": _clean(row.get("bbl")),
                "date_registered": _clean(row.get("date_registered")),
                "address": address,
                "number": number,
                "street": street,
                "borough": _clean(row.get("borough")),
                "zip": _clean(row.get("zip")),
                "active_equipment": _int(row.get("activeequipment"), 0),
                "latitude": _float(row.get("latitude")),
                "longitude": _float(row.get("longitude")),
                "community_board": _clean(row.get("community_board")),
                "council_district": _clean(row.get("council_district")),
                "census_tract": _clean(row.get("census_tract")),
                "ntacode": _clean(row.get("ntacode")),
                "sampledates_raw": sample["raw"],
                "sample_dates": sample["dates"],
                "malformed_sample_values": sample["malformed"],
                "latest_sample_date": sample["latest"],
                "previous_sample_date": sample["previous"],
                "latest_sample_interval_days": sample["latest_interval_days"],
                "sample_intervals_days": sample["intervals"],
                "sample_count": sample["count"],
            }
        )

    normalized.sort(key=lambda item: item["system_id"])
    return normalized, {
        "source_duplicate_rows": duplicate_rows,
        "source_missing_system_id_rows": missing_system_id,
        "normalized_system_count": len(normalized),
    }
