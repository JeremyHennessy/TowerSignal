from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.dob_activity import fetch_dob_activity_by_bbl  # noqa: E402
from towersignal.fetch import SourceFetchError, fetch_count, fetch_dataset, fetch_metadata, fetch_where  # noqa: E402
from towersignal.normalize import normalize_registrations  # noqa: E402
from towersignal.pluto import normalize_bbl  # noqa: E402

REGISTRATION_DATASET_ID = "y4fw-iqfr"
REGISTRATION_URL = "https://data.cityofnewyork.us/Health/NYC-Cooling-Tower-Registrations/y4fw-iqfr"
LEGACY_JOBS_DATASET_ID = "ic3t-wcy2"
LEGACY_JOBS_URL = "https://data.cityofnewyork.us/Housing-Development/DOB-Job-Application-Filings/ic3t-wcy2"
LEGACY_SOURCE = "NYC_DOB_BIS_JOB_APPLICATION_FILINGS"
SCHEMA_VERSION = "1.0"
QUERY_CHUNK_SIZE = 30
RECENT_DAYS = 365
ACTIONABLE_DAYS = 1095
FETCH_CAP = 50000
COOLING_TOWER_RE = re.compile(r"\bcooling\s+towers?\b", re.IGNORECASE)
BOROUGH_NAMES = {
    "1": "MANHATTAN",
    "2": "BRONX",
    "3": "BROOKLYN",
    "4": "QUEENS",
    "5": "STATEN ISLAND",
}
BOROUGH_CODES = {name: code for code, name in BOROUGH_NAMES.items()}
LEGACY_SELECT = ",".join((
    "job_s1_no",
    "job__",
    "doc__",
    "borough",
    "block",
    "lot",
    "bin__",
    "job_type",
    "job_status",
    "job_status_descrp",
    "latest_action_date",
    "plumbing",
    "mechanical",
    "boiler",
    "equipment",
    "other",
    "other_description",
    "applicant_s_first_name",
    "applicant_s_last_name",
    "applicant_professional_title",
    "applicant_license__",
    "pre__filing_date",
    "approved",
    "fully_permitted",
    "signoff_date",
    "initial_cost",
    "owner_s_business_name",
    "job_description",
))


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _flag(value: Any) -> bool:
    return str(value or "").strip().upper() in {"X", "Y", "YES", "TRUE", "1"}


def _date(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        try:
            return date.fromisoformat(text[:10]).isoformat()
        except ValueError:
            return None
    return None


def _bbl_components(value: Any) -> tuple[str, str, str] | None:
    bbl = normalize_bbl(value)
    if not bbl:
        return None
    padded = bbl.zfill(10)
    if len(padded) != 10 or padded[0] not in BOROUGH_NAMES:
        return None
    return BOROUGH_NAMES[padded[0]], padded[1:6], padded[6:10]


def _source_bbl(row: dict[str, Any]) -> str | None:
    borough_raw = str(row.get("borough") or "").strip().upper()
    borough = BOROUGH_CODES.get(borough_raw)
    if borough is None and borough_raw in BOROUGH_NAMES:
        borough = borough_raw
    block_digits = "".join(ch for ch in str(row.get("block") or "") if ch.isdigit())
    lot_digits = "".join(ch for ch in str(row.get("lot") or "") if ch.isdigit())
    if borough not in BOROUGH_NAMES or not block_digits or not lot_digits:
        return None
    block_number = int(block_digits)
    lot_number = int(lot_digits)
    if block_number <= 0 or lot_number <= 0 or block_number > 99999 or lot_number > 9999:
        return None
    block = str(block_number).zfill(5)
    lot = str(lot_number).zfill(4)
    return normalize_bbl(f"{borough}{block}{lot}")


def _applicant(row: dict[str, Any]) -> str | None:
    parts = [_text(row.get("applicant_s_first_name")), _text(row.get("applicant_s_last_name"))]
    name = " ".join(part for part in parts if part)
    return name or None


def normalize_legacy_job(row: dict[str, Any]) -> dict[str, Any]:
    bbl = _source_bbl(row)
    job_description = _text(row.get("job_description"))
    other_description = _text(row.get("other_description"))
    explicit_text = " ".join(value for value in (job_description, other_description) if value)
    explicit_cooling_tower = bool(explicit_text and COOLING_TOWER_RE.search(explicit_text))
    mechanical = _flag(row.get("mechanical"))
    boiler = _flag(row.get("boiler"))
    plumbing = _flag(row.get("plumbing"))
    equipment = _flag(row.get("equipment"))
    lifecycle = [
        value for value in (
            _date(row.get("pre__filing_date")),
            _date(row.get("approved")),
            _date(row.get("fully_permitted")),
            _date(row.get("signoff_date")),
            _date(row.get("latest_action_date")),
        ) if value
    ]
    if explicit_cooling_tower:
        relevance = "COOLING_TOWER_EXPLICIT"
    elif mechanical or boiler or plumbing or equipment:
        relevance = "MECHANICAL_BOILER_PLUMBING_OR_EQUIPMENT"
    else:
        relevance = "PROPERTY_PROJECT_HISTORY"
    return {
        "source_row_id": _text(row.get("job_s1_no")),
        "job_number": _text(row.get("job__")),
        "document_number": _text(row.get("doc__")),
        "bbl": bbl,
        "bin": _text(row.get("bin__")),
        "job_type": _text(row.get("job_type")),
        "job_status": _text(row.get("job_status")),
        "job_status_description": _text(row.get("job_status_descrp")),
        "latest_action_date": _date(row.get("latest_action_date")),
        "prefiling_date": _date(row.get("pre__filing_date")),
        "approved_date": _date(row.get("approved")),
        "fully_permitted_date": _date(row.get("fully_permitted")),
        "signoff_date": _date(row.get("signoff_date")),
        "activity_date": max(lifecycle) if lifecycle else None,
        "plumbing": plumbing,
        "mechanical": mechanical,
        "boiler": boiler,
        "equipment": equipment,
        "other_work": _flag(row.get("other")),
        "other_description": other_description,
        "job_description": job_description,
        "explicit_cooling_tower_mention": explicit_cooling_tower,
        "commercial_relevance": relevance,
        "applicant_name": _applicant(row),
        "applicant_professional_title": _text(row.get("applicant_professional_title")),
        "applicant_license_number": _text(row.get("applicant_license__")),
        "owner_business_name": _text(row.get("owner_s_business_name")),
        "initial_cost_raw": _text(row.get("initial_cost")),
        "source": LEGACY_SOURCE,
        "match_basis": "BOROUGH_BLOCK_LOT_TO_BBL_EXACT",
        "relationship_boundary": "RECORDED_DOB_APPLICANT_NOT_PROOF_OF_SERVICE_CONTRACT",
    }


def _exact_where(chunk: list[str]) -> str:
    clauses = []
    for bbl in chunk:
        components = _bbl_components(bbl)
        if not components:
            continue
        borough, block, lot = components
        source_lot = str(int(lot)).zfill(5)
        clauses.append(f"(borough='{borough}' AND block='{block}' AND lot='{source_lot}')")
    if not clauses:
        raise ValueError("No valid BBLs for legacy DOB query")
    return " OR ".join(clauses)


def fetch_legacy_jobs_by_bbl(bbl_values: set[str], chunk_size: int = QUERY_CHUNK_SIZE) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    requested = sorted({bbl for raw in bbl_values if (bbl := normalize_bbl(raw)) and _bbl_components(bbl)}, key=int)
    requested_set = set(requested)
    by_bbl: dict[str, dict[str, dict[str, Any]]] = {}
    started = time.monotonic()
    for start in range(0, len(requested), chunk_size):
        chunk = requested[start:start + chunk_size]
        rows = fetch_where(
            LEGACY_JOBS_DATASET_ID,
            where=_exact_where(chunk),
            order_by="borough,block,lot,job_s1_no",
            select=LEGACY_SELECT,
            limit=FETCH_CAP,
            request_timeout=120,
        )
        if len(rows) >= FETCH_CAP:
            raise SourceFetchError(
                f"Legacy DOB exact-property query reached the {FETCH_CAP:,}-row cap for {len(chunk)} BBLs; refusing a possibly truncated diagnostic"
            )
        for row in rows:
            normalized = normalize_legacy_job(row)
            bbl = normalized.get("bbl")
            if bbl not in requested_set:
                continue
            identity = normalized.get("source_row_id") or f"{normalized.get('job_number')}:{normalized.get('document_number')}"
            if not identity or identity == "None:None":
                raise SourceFetchError(f"Legacy DOB row on BBL {bbl} lacks a stable job identity")
            by_bbl.setdefault(str(bbl), {})[str(identity)] = normalized
    records = {
        bbl: sorted(values.values(), key=lambda row: (row.get("activity_date") or "", row.get("source_row_id") or ""), reverse=True)
        for bbl, values in by_bbl.items()
    }
    metadata = fetch_metadata(LEGACY_JOBS_DATASET_ID)
    return records, {
        "dataset_id": LEGACY_JOBS_DATASET_ID,
        "name": metadata.get("name") or "DOB Job Application Filings",
        "url": LEGACY_JOBS_URL,
        "source_record_count": fetch_count(LEGACY_JOBS_DATASET_ID),
        "source_last_updated_at": metadata.get("source_last_updated_at"),
        "requested_bbl_count": len(requested),
        "matched_bbl_count": len(records),
        "matched_job_count": sum(len(rows) for rows in records.values()),
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "source_scope": "Legacy BIS/eFiling/HUB jobs with Latest Action Date since 2000; DOB NOW jobs are excluded by authoritative source contract",
    }


def _is_recent(value: str | None, as_of: date, days: int) -> bool:
    if not value:
        return False
    try:
        age = (as_of - date.fromisoformat(value)).days
    except ValueError:
        return False
    return 0 <= age <= days


def _compact_bytes(value: Any) -> int:
    return len(json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def build_diagnostic(
    systems: list[dict[str, Any]],
    legacy_by_bbl: dict[str, list[dict[str, Any]]],
    dob_now_by_bbl: dict[str, list[dict[str, Any]]],
    *,
    registration_source: dict[str, Any],
    legacy_source: dict[str, Any],
    dob_now_source: dict[str, Any],
    as_of: date,
) -> dict[str, Any]:
    system_bbls = [normalize_bbl(row.get("bbl")) for row in systems]
    valid_bbls = {bbl for bbl in system_bbls if bbl}
    legacy_bbls = set(legacy_by_bbl) & valid_bbls
    now_bbls = set(dob_now_by_bbl) & valid_bbls
    both = legacy_bbls & now_bbls
    legacy_only = legacy_bbls - now_bbls
    now_only = now_bbls - legacy_bbls

    legacy_records = [record for bbl in sorted(legacy_bbls) for record in legacy_by_bbl[bbl]]
    now_records = [record for bbl in sorted(now_bbls) for record in dob_now_by_bbl[bbl]]
    recent_legacy = [record for record in legacy_records if _is_recent(record.get("activity_date"), as_of, RECENT_DAYS)]
    actionable_legacy = [record for record in legacy_records if _is_recent(record.get("activity_date"), as_of, ACTIONABLE_DAYS)]
    recent_now_bbls = {
        bbl for bbl, records in dob_now_by_bbl.items()
        if any(_is_recent(record.get("activity_date"), as_of, ACTIONABLE_DAYS) for record in records)
    }
    actionable_legacy_bbls = {
        str(record["bbl"]) for record in actionable_legacy if record.get("bbl")
    }
    incremental_actionable_bbls = actionable_legacy_bbls - recent_now_bbls
    explicit_legacy_bbls = {
        str(record["bbl"]) for record in legacy_records if record.get("explicit_cooling_tower_mention") and record.get("bbl")
    }
    explicit_now_bbls = {
        bbl for bbl, records in dob_now_by_bbl.items()
        if any(record.get("explicit_cooling_tower_mention") for record in records)
    }
    incremental_explicit_bbls = explicit_legacy_bbls - explicit_now_bbls
    mechanical_legacy = [
        record for record in legacy_records
        if record.get("mechanical") or record.get("boiler") or record.get("plumbing") or record.get("equipment")
    ]
    applicants = Counter(record["applicant_name"] for record in legacy_records if record.get("applicant_name"))
    owners = Counter(record["owner_business_name"] for record in legacy_records if record.get("owner_business_name"))

    by_borough = Counter()
    for bbl in legacy_bbls:
        code = bbl.zfill(10)[0]
        by_borough[BOROUGH_NAMES.get(code, "UNKNOWN").title()] += 1

    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "as_of": as_of.isoformat(),
        "sources": {
            "regulatory": registration_source,
            "legacy_dob_bis": legacy_source,
            "dob_now": dob_now_source,
        },
        "identity_contract": {
            "tower_property_key": "BBL_EXACT",
            "legacy_source_key": "borough + block + lot -> 10-digit BBL exact",
            "address_matching_used": False,
            "fuzzy_matching_used": False,
            "legacy_source_excludes_dob_now": True,
            "cooling_tower_classification": "EXPLICIT_PUBLISHED_JOB_TEXT_ONLY",
            "applicant_semantics": "RECORDED_DOB_APPLICANT_NOT_PROOF_OF_SERVICE_CONTRACT",
        },
        "summary": {
            "regulatory_system_count": len(systems),
            "regulatory_systems_without_valid_bbl": sum(1 for bbl in system_bbls if not bbl),
            "regulatory_unique_bbl_count": len(valid_bbls),
            "legacy_matched_bbl_count": len(legacy_bbls),
            "dob_now_matched_bbl_count": len(now_bbls),
            "bbls_with_both_legacy_and_dob_now": len(both),
            "bbls_with_legacy_but_no_dob_now": len(legacy_only),
            "bbls_with_dob_now_but_no_legacy": len(now_only),
            "legacy_job_count": len(legacy_records),
            "dob_now_job_count": len(now_records),
            "legacy_jobs_with_action_last_365_days": len(recent_legacy),
            "legacy_jobs_with_action_last_3_years": len(actionable_legacy),
            "legacy_bbls_with_action_last_3_years": len(actionable_legacy_bbls),
            "incremental_legacy_actionable_bbls_without_recent_dob_now": len(incremental_actionable_bbls),
            "legacy_explicit_cooling_tower_job_count": sum(1 for row in legacy_records if row.get("explicit_cooling_tower_mention")),
            "legacy_explicit_cooling_tower_bbl_count": len(explicit_legacy_bbls),
            "incremental_legacy_explicit_cooling_tower_bbls_not_in_dob_now": len(incremental_explicit_bbls),
            "legacy_mechanical_boiler_plumbing_equipment_job_count": len(mechanical_legacy),
            "distinct_recorded_legacy_applicants": len(applicants),
            "distinct_recorded_legacy_owner_business_names": len(owners),
        },
        "borough_breakdown": dict(sorted(by_borough.items())),
        "incremental_examples": {
            "actionable_legacy_bbls_without_recent_dob_now": sorted(incremental_actionable_bbls)[:50],
            "legacy_explicit_cooling_tower_bbls_not_in_dob_now": sorted(incremental_explicit_bbls)[:50],
            "legacy_only_bbls": sorted(legacy_only)[:50],
        },
        "recorded_identity_examples": {
            "applicants": [{"name": name, "job_observations": count} for name, count in applicants.most_common(25)],
            "owner_business_names": [{"name": name, "job_observations": count} for name, count in owners.most_common(25)],
        },
        "storage_diagnostic": {
            "normalized_legacy_records_json_bytes": _compact_bytes(legacy_records),
            "normalized_dob_now_records_json_bytes": _compact_bytes(now_records),
            "automatic_durable_history_inclusion": False,
        },
        "evidence_boundaries": [
            "The legacy source explicitly excludes DOB NOW submissions, so it is complementary historical project evidence rather than a second copy of DOB NOW.",
            "A legacy DOB/BIS job on an exact BBL is project-history evidence only; it does not prove a current contractor, maintenance provider, owner, or service relationship.",
            "Cooling-tower relevance is asserted only when source-published job/other-description text explicitly says cooling tower; mechanical, boiler, plumbing, and equipment flags remain broader context.",
            "A recently updated old BIS job can be commercially timely context, but Latest Action Date is a source lifecycle date and not proof that field work occurred on that date.",
        ],
        "recommendation": {
            "priority_score_change": False,
            "production_ui_change": False,
            "durable_history_change": False,
            "production_ingestion_authorized": False,
            "decision_rule": "Production ingestion should be considered only if exact-BBL legacy history materially increases recent/actionable or explicit cooling-tower coverage beyond DOB NOW at acceptable runtime/storage cost.",
        },
    }
    return report


def run(output: Path, as_of: date) -> dict[str, Any]:
    registration_snapshot = fetch_dataset(REGISTRATION_DATASET_ID, "system_id")
    systems, _ = normalize_registrations(registration_snapshot.rows)
    bbls = {str(row["bbl"]) for row in systems if row.get("bbl")}
    legacy_by_bbl, legacy_meta = fetch_legacy_jobs_by_bbl(bbls)
    dob_now_by_bbl, dob_now_meta = fetch_dob_activity_by_bbl(bbls)
    report = build_diagnostic(
        systems,
        legacy_by_bbl,
        dob_now_by_bbl,
        registration_source={
            "dataset_id": registration_snapshot.dataset_id,
            "name": registration_snapshot.name,
            "url": REGISTRATION_URL,
            "source_record_count": registration_snapshot.source_record_count,
            "source_last_updated_at": registration_snapshot.source_last_updated_at,
            "retrieved_at": registration_snapshot.retrieved_at,
        },
        legacy_source=legacy_meta,
        dob_now_source=dob_now_meta,
        as_of=as_of,
    )
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose incremental legacy DOB/BIS history for TowerSignal NYC BBLs")
    parser.add_argument("--output", type=Path, default=Path("legacy-dob-bis-diagnostic.json"))
    parser.add_argument("--as-of", default=date.today().isoformat())
    args = parser.parse_args()
    run(args.output, date.fromisoformat(args.as_of))


if __name__ == "__main__":
    main()
