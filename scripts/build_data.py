from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal import PRIORITY_MODEL_VERSION, SCHEMA_VERSION  # noqa: E402
from towersignal.building_footprints import fetch_building_footprints_by_bin  # noqa: E402
from towersignal.dob_activity import fetch_dob_activity_by_bbl, summarize_dob_activity  # noqa: E402
from towersignal.fetch import fetch_dataset  # noqa: E402
from towersignal.historical import build_historical_profile  # noqa: E402
from towersignal.hpd import fetch_hpd_contacts_by_bbl  # noqa: E402
from towersignal.inspections import aggregate_inspections  # noqa: E402
from towersignal.normalize import normalize_registrations  # noqa: E402
from towersignal.oath import cases_for_system, fetch_oath_cases, summons_numbers_from_inspections  # noqa: E402
from towersignal.planimetrics import fetch_planimetric_towers_by_bin, normalize_bin as normalize_planimetric_bin  # noqa: E402
from towersignal.pluto import fetch_pluto_by_bbl, normalize_bbl  # noqa: E402
from towersignal.scoring import priority_score  # noqa: E402
from towersignal.signals import build_signals  # noqa: E402
from towersignal.validate import validate_generated, validate_normalized, validate_sources  # noqa: E402

REGISTRATION_ID = "y4fw-iqfr"
INSPECTION_ID = "f9wb-g8mb"


def load_rules() -> dict:
    return json.loads((ROOT / "config/rules/nyc.json").read_text(encoding="utf-8"))


def safe_detail_path(base: Path, system_id: str) -> Path:
    safe = "".join(ch for ch in system_id if ch.isalnum() or ch in ("-", "_"))
    prefix = (safe[:2] or "xx").lower()
    target = base / prefix / f"{safe}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def build(output_dir: Path) -> dict:
    rules = load_rules()
    registration_snapshot = fetch_dataset(REGISTRATION_ID, "system_id")
    inspection_snapshot = fetch_dataset(INSPECTION_ID, "system_id,inspection_date")
    validate_sources(registration_snapshot.rows, inspection_snapshot.rows)

    systems, dedupe_meta = normalize_registrations(registration_snapshot.rows)
    snapshot_date = datetime.now(ZoneInfo("America/New_York")).date()
    validate_normalized(systems, snapshot_date)
    inspections_by_system = aggregate_inspections(inspection_snapshot.rows)

    bbl_values = {system["bbl"] for system in systems if system.get("bbl")}
    bin_values = {system["bin"] for system in systems if system.get("bin")}
    oath_ticket_numbers = summons_numbers_from_inspections(inspections_by_system)
    oath_cases_by_ticket, oath_meta = fetch_oath_cases(oath_ticket_numbers)
    pluto_by_bbl, pluto_meta = fetch_pluto_by_bbl(bbl_values)
    dob_by_bbl, dob_meta = fetch_dob_activity_by_bbl(bbl_values)
    hpd_by_bbl, hpd_meta = fetch_hpd_contacts_by_bbl(bbl_values)
    planimetric_by_bin, planimetric_meta = fetch_planimetric_towers_by_bin(bin_values)
    building_footprints_by_bin, building_footprint_meta = fetch_building_footprints_by_bin(bin_values)

    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    sources = [
        {
            "dataset_id": registration_snapshot.dataset_id,
            "name": registration_snapshot.name,
            "retrieved_at": registration_snapshot.retrieved_at,
            "source_record_count": registration_snapshot.source_record_count,
            "source_last_updated_at": registration_snapshot.source_last_updated_at,
            "url": "https://data.cityofnewyork.us/Health/NYC-Cooling-Tower-Registrations/y4fw-iqfr",
        },
        {
            "dataset_id": inspection_snapshot.dataset_id,
            "name": inspection_snapshot.name,
            "retrieved_at": inspection_snapshot.retrieved_at,
            "source_record_count": inspection_snapshot.source_record_count,
            "source_last_updated_at": inspection_snapshot.source_last_updated_at,
            "url": "https://data.cityofnewyork.us/Health/NYC-Cooling-Tower-System-Inspection-Results/f9wb-g8mb",
        },
        {
            "dataset_id": oath_meta["dataset_id"],
            "name": oath_meta["name"],
            "retrieved_at": oath_meta["retrieved_at"],
            "source_record_count": oath_meta["source_record_count"],
            "source_query_scope": oath_meta["source_query_scope"],
            "source_last_updated_at": oath_meta["source_last_updated_at"],
            "url": oath_meta["url"],
            "matched_record_count": oath_meta["matched_case_count"],
        },
        {
            "dataset_id": pluto_meta["dataset_id"],
            "name": pluto_meta["name"],
            "retrieved_at": pluto_meta["retrieved_at"],
            "source_record_count": pluto_meta["source_record_count"],
            "source_query_scope": pluto_meta["source_query_scope"],
            "source_last_updated_at": pluto_meta["source_last_updated_at"],
            "url": pluto_meta["url"],
            "matched_record_count": pluto_meta["matched_bbl_count"],
        },
        {
            "dataset_id": dob_meta["dataset_id"],
            "name": dob_meta["name"],
            "retrieved_at": dob_meta["retrieved_at"],
            "source_record_count": dob_meta["source_record_count"],
            "source_query_scope": dob_meta["source_query_scope"],
            "source_last_updated_at": dob_meta["source_last_updated_at"],
            "url": dob_meta["url"],
            "matched_record_count": dob_meta["matched_filing_count"],
        },
        {
            "dataset_id": hpd_meta["registration_dataset_id"],
            "name": hpd_meta["registration_name"],
            "retrieved_at": hpd_meta["retrieved_at"],
            "source_record_count": hpd_meta["registration_source_record_count"],
            "source_query_scope": hpd_meta["source_query_scope"],
            "source_last_updated_at": hpd_meta["registration_source_last_updated_at"],
            "url": hpd_meta["registration_url"],
            "matched_record_count": hpd_meta["matched_registration_bbl_count"],
        },
        {
            "dataset_id": hpd_meta["contacts_dataset_id"],
            "name": hpd_meta["contacts_name"],
            "retrieved_at": hpd_meta["retrieved_at"],
            "source_record_count": hpd_meta["contacts_source_record_count"],
            "source_query_scope": "Exact registration_id contacts for HPD registrations matched to cooling-tower BBLs",
            "source_last_updated_at": hpd_meta["contacts_source_last_updated_at"],
            "url": hpd_meta["contacts_url"],
            "matched_record_count": hpd_meta["matched_contact_record_count"],
        },
        {
            "dataset_id": planimetric_meta["dataset_id"],
            "name": planimetric_meta["name"],
            "retrieved_at": planimetric_meta["retrieved_at"],
            "source_record_count": planimetric_meta["source_record_count"],
            "source_query_scope": planimetric_meta["source_query_scope"],
            "source_last_updated_at": planimetric_meta["source_last_updated_at"],
            "url": planimetric_meta["url"],
            "matched_record_count": planimetric_meta["matched_feature_count"],
        },
        {
            "dataset_id": building_footprint_meta["dataset_id"],
            "name": building_footprint_meta["name"],
            "retrieved_at": building_footprint_meta["retrieved_at"],
            "source_record_count": building_footprint_meta["source_record_count"],
            "source_query_scope": building_footprint_meta["source_query_scope"],
            "source_last_updated_at": building_footprint_meta["source_last_updated_at"],
            "url": building_footprint_meta["url"],
            "matched_record_count": building_footprint_meta["matched_feature_count"],
        },
    ]
    metadata = {
        "generated_at": generated_at,
        "snapshot_date": snapshot_date.isoformat(),
        "sources": sources,
        "normalized_system_count": len(systems),
        "source_duplicate_registration_rows": dedupe_meta["source_duplicate_rows"],
        "source_missing_registration_system_id_rows": dedupe_meta["source_missing_system_id_rows"],
        "invalid_coordinate_system_count": dedupe_meta["invalid_coordinate_system_count"],
        "oath_requested_ticket_count": oath_meta["requested_ticket_count"],
        "oath_matched_ticket_count": oath_meta["matched_ticket_count"],
        "oath_unmatched_ticket_count": oath_meta["unmatched_ticket_count"],
        "oath_match_basis": "SUMMONS_NUMBER_EXACT",
        "pluto_requested_bbl_count": pluto_meta["requested_bbl_count"],
        "pluto_matched_bbl_count": pluto_meta["matched_bbl_count"],
        "dob_requested_bbl_count": dob_meta["requested_bbl_count"],
        "dob_matched_bbl_count": dob_meta["matched_bbl_count"],
        "dob_matched_filing_count": dob_meta["matched_filing_count"],
        "dob_explicit_cooling_tower_filing_count": dob_meta["explicit_cooling_tower_filing_count"],
        "dob_mechanical_or_boiler_filing_count": dob_meta["mechanical_or_boiler_filing_count"],
        "hpd_requested_bbl_count": hpd_meta["requested_bbl_count"],
        "hpd_matched_registration_bbl_count": hpd_meta["matched_registration_bbl_count"],
        "hpd_matched_contact_bbl_count": hpd_meta["matched_contact_bbl_count"],
        "planimetric_requested_bin_count": planimetric_meta["requested_bin_count"],
        "planimetric_matched_bin_count": planimetric_meta["matched_bin_count"],
        "planimetric_matched_feature_count": planimetric_meta["matched_feature_count"],
        "planimetric_match_basis": planimetric_meta["match_basis"],
        "planimetric_feature_identity_basis": planimetric_meta["feature_identity_basis"],
        "planimetric_imagery_year": planimetric_meta["imagery_year"],
        "building_footprint_requested_bin_count": building_footprint_meta["requested_bin_count"],
        "building_footprint_matched_bin_count": building_footprint_meta["matched_bin_count"],
        "building_footprint_matched_feature_count": building_footprint_meta["matched_feature_count"],
        "building_footprint_match_basis": building_footprint_meta["match_basis"],
        "rules_version": rules["rules_version"],
        "priority_model_version": PRIORITY_MODEL_VERSION,
    }

    summary_rows = []
    detail_dir = output_dir / "details"
    if detail_dir.exists():
        for old in detail_dir.rglob("*.json"):
            old.unlink()
    detail_dir.mkdir(parents=True, exist_ok=True)

    gap_count = 0
    recent_violation_count = 0
    active_equipment_total = 0
    systems_with_oath_cases = 0
    systems_with_pluto_context = 0
    systems_with_dob_activity = 0
    systems_with_recent_dob_activity = 0
    systems_with_explicit_cooling_tower_dob_activity = 0
    systems_with_hpd_registration = 0
    systems_with_hpd_contacts = 0
    systems_with_planimetric_bin_match = 0
    systems_with_building_footprint_match = 0

    for system in systems:
        inspections = inspections_by_system.get(system["system_id"], [])
        oath_cases = cases_for_system(inspections, oath_cases_by_ticket)
        historical_profile = build_historical_profile(system, inspections, oath_cases, snapshot_date)
        if oath_cases:
            systems_with_oath_cases += 1
        bbl_key = normalize_bbl(system.get("bbl"))
        bin_key = normalize_planimetric_bin(system.get("bin"))
        building_context = pluto_by_bbl.get(bbl_key) if bbl_key else None
        dob_activity = dob_by_bbl.get(bbl_key, []) if bbl_key else []
        dob_summary = summarize_dob_activity(dob_activity, snapshot_date)
        hpd_registration = hpd_by_bbl.get(bbl_key) if bbl_key else None
        planimetric_building_tower_features = planimetric_by_bin.get(bin_key, []) if bin_key else []
        building_footprints = building_footprints_by_bin.get(bin_key, []) if bin_key else []
        if building_context:
            systems_with_pluto_context += 1
        if dob_summary["activity_count"]:
            systems_with_dob_activity += 1
        if dob_summary["recent_activity_count"]:
            systems_with_recent_dob_activity += 1
        if dob_summary["explicit_cooling_tower_count"]:
            systems_with_explicit_cooling_tower_dob_activity += 1
        if hpd_registration:
            systems_with_hpd_registration += 1
        hpd_contact_count = len(hpd_registration["contacts"]) if hpd_registration else 0
        if hpd_contact_count:
            systems_with_hpd_contacts += 1
        if planimetric_building_tower_features:
            systems_with_planimetric_bin_match += 1
        if building_footprints:
            systems_with_building_footprint_match += 1
        signal_state = build_signals(system, inspections, rules, snapshot_date)
        scoring = priority_score(system, signal_state)
        signals = signal_state["signals"]
        signal_types = [signal["type"] for signal in signals]
        if "POTENTIAL_SAMPLING_GAP" in signal_types:
            gap_count += 1
        if signal_state["recent_confirmed_violation"]:
            recent_violation_count += 1
        active_equipment_total += int(system.get("active_equipment") or 0)

        primary = next(
            (candidate for candidate in (
                "CONFIRMED_RECENT_VIOLATION",
                "POTENTIAL_SAMPLING_GAP",
                "NO_PUBLIC_SAMPLE_DATE",
                "MULTIPLE_ACTIVE_EQUIPMENT",
                "RECENT_NYC_HEALTH_INSPECTION",
            ) if candidate in signal_types),
            "NO_CURRENT_SIGNAL",
        )
        if primary == "CONFIRMED_RECENT_VIOLATION":
            evidence_confidence = "CONFIRMED"
        elif primary in {"POTENTIAL_SAMPLING_GAP", "NO_PUBLIC_SAMPLE_DATE"}:
            evidence_confidence = "VERIFY"
        else:
            evidence_confidence = "STRONG_SIGNAL"

        latest_inspection = signal_state["latest_inspection"]
        row = {
            "system_id": system["system_id"],
            "bin": system["bin"],
            "bbl": system["bbl"],
            "address": system["address"],
            "borough": system["borough"],
            "zip": system["zip"],
            "active_equipment": system["active_equipment"],
            "latitude": system["latitude"],
            "longitude": system["longitude"],
            "coordinate_status": system["coordinate_status"],
            "registration_date": historical_profile["registration_date"],
            "sample_count": historical_profile["sample"]["reported_sample_count"],
            "inspection_count": historical_profile["inspection"]["inspection_count"],
            "violation_citation_count": historical_profile["inspection"]["violation_citation_count"],
            "latest_violation_date": historical_profile["inspection"]["latest_violation_date"],
            "oath_balance_due_total": historical_profile["oath"]["balance_due_total"],
            "latest_sample_date": system["latest_sample_date"],
            "days_since_latest_sample": signal_state["days_since_latest_sample"],
            "latest_inspection_date": latest_inspection.get("inspection_date") if latest_inspection else None,
            "latest_inspection_type": latest_inspection.get("inspection_type") if latest_inspection else None,
            "confirmed_violation": signal_state["confirmed_violation"],
            "recent_confirmed_violation": signal_state["recent_confirmed_violation"],
            "violation_types": signal_state["violation_types"],
            "signal_types": signal_types,
            "primary_signal": primary,
            "evidence_confidence": evidence_confidence,
            "priority_score": scoring["score"],
            "score_components": scoring["components"],
            "oath_case_count": len(oath_cases),
            "pluto_match": building_context is not None,
            "pluto_owner_name": building_context.get("owner_name") if building_context else None,
            "pluto_building_area_sqft": building_context.get("building_area_sqft") if building_context else None,
            "dob_activity_count": dob_summary["activity_count"],
            "dob_recent_activity_count": dob_summary["recent_activity_count"],
            "dob_explicit_cooling_tower_count": dob_summary["explicit_cooling_tower_count"],
            "dob_mechanical_or_boiler_count": dob_summary["mechanical_or_boiler_count"],
            "latest_dob_activity_date": dob_summary["latest_activity_date"],
            "hpd_contact_count": hpd_contact_count,
            "planimetric_bin_match": bool(planimetric_building_tower_features),
            "planimetric_building_tower_count": len(planimetric_building_tower_features),
            "building_footprint_bin_match": bool(building_footprints),
            "building_footprint_count": len(building_footprints),
        }
        summary_rows.append(row)

        detail = {
            "schema_version": SCHEMA_VERSION,
            "metadata": metadata,
            "identity": {
                "system_id": system["system_id"],
                "bin": system["bin"],
                "bbl": system["bbl"],
                "address": system["address"],
                "borough": system["borough"],
                "zip": system["zip"],
                "active_equipment": system["active_equipment"],
                "latitude": system["latitude"],
                "longitude": system["longitude"],
                "coordinate_status": system["coordinate_status"],
                "source_latitude_raw": system["source_latitude_raw"],
                "source_longitude_raw": system["source_longitude_raw"],
            },
            "historical_profile": historical_profile,
            "building_context": building_context,
            "dob_activity_history": dob_activity,
            "hpd_registration": hpd_registration,
            "planimetric_building_tower_features": planimetric_building_tower_features,
            "building_footprints": building_footprints,
            "sample_history": {
                "source_raw": system["sampledates_raw"],
                "dates": system["sample_dates"],
                "malformed_values": system["malformed_sample_values"],
                "latest_sample_date": system["latest_sample_date"],
                "previous_sample_date": system["previous_sample_date"],
                "latest_sample_interval_days": system["latest_sample_interval_days"],
                "intervals_days": system["sample_intervals_days"],
                "sample_count": system["sample_count"],
            },
            "signals": signals,
            "inspection_history": inspections,
            "oath_case_history": oath_cases,
            "scoring": scoring,
        }
        safe_detail_path(detail_dir, system["system_id"]).write_text(json.dumps(detail, separators=(",", ":")), encoding="utf-8")

    summary_rows.sort(key=lambda item: (-item["priority_score"], item.get("borough") or "", item.get("address") or ""))
    payload = {
        "schema_version": SCHEMA_VERSION,
        "metadata": metadata,
        "summary": {
            "registered_systems": len(summary_rows),
            "active_equipment": active_equipment_total,
            "potential_sampling_gaps": gap_count,
            "recent_confirmed_violations": recent_violation_count,
            "systems_with_oath_cases": systems_with_oath_cases,
            "systems_with_pluto_context": systems_with_pluto_context,
            "systems_with_dob_activity": systems_with_dob_activity,
            "systems_with_recent_dob_activity": systems_with_recent_dob_activity,
            "systems_with_explicit_cooling_tower_dob_activity": systems_with_explicit_cooling_tower_dob_activity,
            "systems_with_hpd_registration": systems_with_hpd_registration,
            "systems_with_hpd_contacts": systems_with_hpd_contacts,
            "systems_with_planimetric_bin_match": systems_with_planimetric_bin_match,
            "systems_with_building_footprint_match": systems_with_building_footprint_match,
        },
        "systems": summary_rows,
    }
    validate_generated(payload)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "systems.json").write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    print(f"OATH exact ticket matches: {oath_meta['matched_ticket_count']:,}/{oath_meta['requested_ticket_count']:,}")
    print(f"PLUTO exact BBL matches: {pluto_meta['matched_bbl_count']:,}/{pluto_meta['requested_bbl_count']:,}")
    print(f"DOB NOW exact BBL matches: {dob_meta['matched_bbl_count']:,}/{dob_meta['requested_bbl_count']:,}; {dob_meta['matched_filing_count']:,} job filings")
    print(f"HPD exact BBL registrations: {hpd_meta['matched_registration_bbl_count']:,}/{hpd_meta['requested_bbl_count']:,}; contacts on {hpd_meta['matched_contact_bbl_count']:,} BBLs")
    print(f"Planimetric exact BIN matches: {planimetric_meta['matched_bin_count']:,}/{planimetric_meta['requested_bin_count']:,}; {planimetric_meta['matched_feature_count']:,} physical tower features")
    print(f"Building-footprint exact BIN matches: {building_footprint_meta['matched_bin_count']:,}/{building_footprint_meta['requested_bin_count']:,}; {building_footprint_meta['matched_feature_count']:,} footprint features")
    print(f"Generated {len(summary_rows):,} systems at {generated_at}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build TowerSignal static NYC data")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data")
    args = parser.parse_args()
    build(args.output)


if __name__ == "__main__":
    main()
