from __future__ import annotations

import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from towersignal.fetch import SourceFetchError, fetch_count, fetch_metadata, fetch_where
from towersignal.pluto import normalize_bbl

DOB_NOW_JOBS_DATASET_ID = "w9ak-ipjd"
DOB_NOW_JOBS_URL = "https://data.cityofnewyork.us/Housing-Development/DOB-NOW-Build-Job-Application-Filings/w9ak-ipjd"
DOB_NOW_JOBS_SELECT = ",".join((
    "job_filing_number",
    "filing_status",
    "bbl",
    "filing_date",
    "current_status_date",
    "first_permit_date",
    "approved_date",
    "signoff_date",
    "job_type",
    "job_description",
    "initial_cost",
    "mechanical_systems_work_type_",
    "boiler_equipment_work_type_",
    "owner_s_business_name",
    "applicant_business_name",
))
RECENT_ACTIVITY_DAYS = 365
_COOLING_TOWER_RE = re.compile(r"\bcooling\s+towers?\b", re.IGNORECASE)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _date(value: Any) -> str | None:
    text = _text(value)
    if text is None:
        return None
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        try:
            return date.fromisoformat(text[:10]).isoformat()
        except ValueError:
            pass
    for pattern in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _number(value: Any) -> float | None:
    text = _text(value)
    if text is None:
        return None
    cleaned = text.replace("$", "").replace(",", "")
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    if negative:
        cleaned = cleaned[1:-1]
    try:
        number = Decimal(cleaned)
    except InvalidOperation:
        return None
    if not number.is_finite():
        return None
    result = float(number)
    return -result if negative else result


def _flag(value: Any) -> bool:
    return str(value or "").strip().upper() in {"YES", "Y", "X", "TRUE", "1"}


def normalize_dob_job(row: dict[str, Any]) -> dict[str, Any]:
    description = _text(row.get("job_description"))
    filing_date = _date(row.get("filing_date"))
    current_status_date = _date(row.get("current_status_date"))
    first_permit_date = _date(row.get("first_permit_date"))
    approved_date = _date(row.get("approved_date"))
    signoff_date = _date(row.get("signoff_date"))
    lifecycle_dates = [value for value in (filing_date, current_status_date, first_permit_date, approved_date, signoff_date) if value]
    mechanical = _flag(row.get("mechanical_systems_work_type_"))
    boiler = _flag(row.get("boiler_equipment_work_type_"))
    explicit_cooling_tower = bool(description and _COOLING_TOWER_RE.search(description))
    if explicit_cooling_tower:
        relevance = "COOLING_TOWER_EXPLICIT"
    elif mechanical or boiler:
        relevance = "MECHANICAL_OR_BOILER"
    else:
        relevance = "PROPERTY_PROJECT"

    return {
        "job_filing_number": _text(row.get("job_filing_number")),
        "bbl": normalize_bbl(row.get("bbl")),
        "filing_status": _text(row.get("filing_status")),
        "job_type": _text(row.get("job_type")),
        "job_description": description,
        "initial_cost": _number(row.get("initial_cost")),
        "filing_date": filing_date,
        "current_status_date": current_status_date,
        "first_permit_date": first_permit_date,
        "approved_date": approved_date,
        "signoff_date": signoff_date,
        "activity_date": max(lifecycle_dates) if lifecycle_dates else None,
        "mechanical_systems": mechanical,
        "boiler_equipment": boiler,
        "explicit_cooling_tower_mention": explicit_cooling_tower,
        "commercial_relevance": relevance,
        "owner_business_name": _text(row.get("owner_s_business_name")),
        "applicant_business_name": _text(row.get("applicant_business_name")),
        "source": "NYC_DOB_NOW_JOB_APPLICATION_FILINGS",
        "match_basis": "BBL_EXACT",
    }


def summarize_dob_activity(records: list[dict[str, Any]], as_of: date, recent_days: int = RECENT_ACTIVITY_DAYS) -> dict[str, Any]:
    dated: list[tuple[date, dict[str, Any]]] = []
    for record in records:
        value = record.get("activity_date")
        if not value:
            continue
        try:
            dated.append((date.fromisoformat(str(value)), record))
        except ValueError:
            continue
    recent = [record for activity_date, record in dated if 0 <= (as_of - activity_date).days <= recent_days]
    return {
        "activity_count": len(records),
        "recent_activity_count": len(recent),
        "explicit_cooling_tower_count": sum(1 for record in records if record.get("explicit_cooling_tower_mention")),
        "mechanical_or_boiler_count": sum(1 for record in records if record.get("mechanical_systems") or record.get("boiler_equipment")),
        "latest_activity_date": max((activity_date.isoformat() for activity_date, _ in dated), default=None),
        "recent_window_days": recent_days,
    }


def fetch_dob_activity_by_bbl(bbl_values: set[str], chunk_size: int = 25) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    requested = sorted({bbl for value in bbl_values if (bbl := normalize_bbl(value)) is not None}, key=int)
    by_bbl: dict[str, dict[str, dict[str, Any]]] = {}

    for start in range(0, len(requested), chunk_size):
        chunk = requested[start : start + chunk_size]
        if not chunk:
            continue
        # Live contract check confirms DOB NOW exposes BBL as text, so exact values
        # are quoted. normalize_bbl constrains these values to positive digits.
        where = "bbl in (" + ",".join(f"'{bbl}'" for bbl in chunk) + ")"
        rows = fetch_where(
            DOB_NOW_JOBS_DATASET_ID,
            where=where,
            order_by="bbl,job_filing_number",
            select=DOB_NOW_JOBS_SELECT,
        )
        if len(rows) >= 50000:
            raise SourceFetchError(
                f"DOB NOW filtered query reached the 50,000-row fetch cap for {len(chunk)} BBLs. "
                "Refusing to publish potentially truncated project history."
            )
        for index, row in enumerate(rows):
            normalized = normalize_dob_job(row)
            bbl = normalized.get("bbl")
            if bbl is None or bbl not in requested:
                continue
            identity = normalized.get("job_filing_number") or f"missing-job-number-{start}-{index}"
            by_bbl.setdefault(bbl, {})[str(identity)] = normalized

    records: dict[str, list[dict[str, Any]]] = {}
    for bbl, keyed in by_bbl.items():
        records[bbl] = sorted(
            keyed.values(),
            key=lambda item: (item.get("activity_date") or "", item.get("job_filing_number") or ""),
            reverse=True,
        )

    metadata = fetch_metadata(DOB_NOW_JOBS_DATASET_ID)
    all_records = [record for values in records.values() for record in values]
    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return records, {
        "dataset_id": DOB_NOW_JOBS_DATASET_ID,
        "name": metadata["name"],
        "retrieved_at": retrieved_at,
        "source_record_count": fetch_count(DOB_NOW_JOBS_DATASET_ID),
        "source_query_scope": f"Exact BBL subsets for {len(requested):,} registered cooling-tower BBLs; all matching DOB NOW job filings retained",
        "source_last_updated_at": metadata.get("source_last_updated_at"),
        "url": DOB_NOW_JOBS_URL,
        "requested_bbl_count": len(requested),
        "matched_bbl_count": len(records),
        "matched_filing_count": len(all_records),
        "explicit_cooling_tower_filing_count": sum(1 for record in all_records if record.get("explicit_cooling_tower_mention")),
        "mechanical_or_boiler_filing_count": sum(1 for record in all_records if record.get("mechanical_systems") or record.get("boiler_equipment")),
    }
