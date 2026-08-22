from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

HISTORY_SCHEMA_VERSION = "1.0"
EVENT_RETENTION_DAYS = 400


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _event(
    event_type: str,
    current: dict[str, Any],
    detected_at: str,
    source: str,
    evidence_basis: str,
    previous_value: Any,
    new_value: Any,
    source_observation_date: str | None = None,
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "system_id": current["system_id"],
        "bbl": current.get("bbl"),
        "bin": current.get("bin"),
        "address": current.get("address"),
        "borough": current.get("borough"),
        "detected_at": detected_at,
        "source_observation_date": source_observation_date,
        "previous_value": previous_value,
        "new_value": new_value,
        "source": source,
        "evidence_basis": evidence_basis,
        "priority_score": current.get("priority_score"),
        "evidence_confidence": current.get("evidence_confidence"),
        "contact_available": bool(current.get("hpd_contacts")),
    }


def build_observation(
    system: dict[str, Any],
    summary_row: dict[str, Any],
    inspections: list[dict[str, Any]],
    oath_cases: list[dict[str, Any]],
    building_context: dict[str, Any] | None,
    hpd_registration: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "system_id": system["system_id"],
        "bin": system.get("bin"),
        "bbl": system.get("bbl"),
        "address": system.get("address"),
        "borough": system.get("borough"),
        "zip": system.get("zip"),
        "date_registered": system.get("date_registered"),
        "active_equipment": system.get("active_equipment", 0),
        "sample_dates": system.get("sample_dates", []),
        "latest_sample_date": system.get("latest_sample_date"),
        "primary_signal": summary_row.get("primary_signal"),
        "signal_types": summary_row.get("signal_types", []),
        "priority_score": summary_row.get("priority_score"),
        "evidence_confidence": summary_row.get("evidence_confidence"),
        "inspections": inspections,
        "oath_cases": oath_cases,
        "pluto_owner": (building_context or {}).get("owner_name"),
        "building_context": building_context,
        "hpd_registration_id": (hpd_registration or {}).get("registration_id"),
        "hpd_last_registration_date": (hpd_registration or {}).get("last_registration_date"),
        "hpd_contacts": (hpd_registration or {}).get("contacts", []),
    }


def _inspection_key(item: dict[str, Any]) -> str:
    return _canonical({
        "inspection_date": item.get("inspection_date"),
        "inspection_type": item.get("inspection_type"),
        "status": item.get("status"),
    })


def _violation_key(item: dict[str, Any]) -> str:
    return _canonical({
        "summons_number": item.get("summons_number"),
        "violation_code": item.get("violation_code"),
        "law_section": item.get("law_section"),
        "violation_type": item.get("violation_type"),
        "violation_text": item.get("violation_text"),
    })


def _contact_key(item: dict[str, Any]) -> str:
    return _canonical({
        "registration_contact_id": item.get("registration_contact_id"),
        "type": item.get("type"),
        "corporation_name": item.get("corporation_name"),
        "person_name": item.get("person_name"),
        "title": item.get("title"),
        "business_address": item.get("business_address"),
    })


def _oath_map(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("ticket_number")): item for item in items if item.get("ticket_number")}


def _managing_contacts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in items if "MANAG" in str(item.get("type") or "").upper() or "MANAG" in str(item.get("description") or "").upper()]


def detect_changes(previous: dict[str, Any], current: dict[str, Any], detected_at: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    if previous.get("active_equipment") != current.get("active_equipment"):
        events.append(_event("ACTIVE_EQUIPMENT_CHANGED", current, detected_at, "NYC_COOLING_TOWER_REGISTRATIONS", "SYSTEM_ID_EXACT", previous.get("active_equipment"), current.get("active_equipment")))

    previous_samples = set(previous.get("sample_dates") or [])
    current_samples = set(current.get("sample_dates") or [])
    for sample_date in sorted(current_samples - previous_samples):
        events.append(_event("SAMPLE_REPORTED", current, detected_at, "NYC_COOLING_TOWER_REGISTRATIONS", "SYSTEM_ID_EXACT", None, sample_date, sample_date))
    if previous.get("latest_sample_date") != current.get("latest_sample_date"):
        events.append(_event("LATEST_SAMPLE_CHANGED", current, detected_at, "NYC_COOLING_TOWER_REGISTRATIONS", "SYSTEM_ID_EXACT", previous.get("latest_sample_date"), current.get("latest_sample_date"), current.get("latest_sample_date")))

    previous_signals = set(previous.get("signal_types") or [])
    current_signals = set(current.get("signal_types") or [])
    if "POTENTIAL_SAMPLING_GAP" not in previous_signals and "POTENTIAL_SAMPLING_GAP" in current_signals:
        events.append(_event("SAMPLING_GAP_ENTERED", current, detected_at, "TOWERSIGNAL_DERIVED", "DETERMINISTIC_RULE_CHANGE", False, True, current.get("latest_sample_date")))
    if "POTENTIAL_SAMPLING_GAP" in previous_signals and "POTENTIAL_SAMPLING_GAP" not in current_signals:
        events.append(_event("SAMPLING_GAP_RESOLVED", current, detected_at, "TOWERSIGNAL_DERIVED", "DETERMINISTIC_RULE_CHANGE", True, False, current.get("latest_sample_date")))

    previous_inspections = {_inspection_key(item): item for item in previous.get("inspections") or []}
    current_inspections = {_inspection_key(item): item for item in current.get("inspections") or []}
    for key, inspection in current_inspections.items():
        if key not in previous_inspections:
            events.append(_event("INSPECTION_ADDED", current, detected_at, "NYC_COOLING_TOWER_INSPECTIONS", "SYSTEM_ID_EXACT", None, {"inspection_date": inspection.get("inspection_date"), "inspection_type": inspection.get("inspection_type"), "status": inspection.get("status")}, inspection.get("inspection_date")))

    previous_violations = {}
    for inspection in previous.get("inspections") or []:
        for violation in inspection.get("violations") or []:
            previous_violations[_violation_key(violation)] = (inspection, violation)
    for inspection in current.get("inspections") or []:
        for violation in inspection.get("violations") or []:
            key = _violation_key(violation)
            if key not in previous_violations:
                events.append(_event("VIOLATION_ADDED", current, detected_at, "NYC_COOLING_TOWER_INSPECTIONS", "SYSTEM_ID_EXACT", None, violation, inspection.get("inspection_date")))

    previous_oath = _oath_map(previous.get("oath_cases") or [])
    current_oath = _oath_map(current.get("oath_cases") or [])
    for ticket, case in current_oath.items():
        old = previous_oath.get(ticket)
        if old is None:
            events.append(_event("OATH_CASE_ADDED", current, detected_at, "NYC_OATH_HEARINGS_DIVISION_CASE_STATUS", "SUMMONS_TICKET_EXACT", None, {"ticket_number": ticket, "hearing_status": case.get("hearing_status"), "hearing_result": case.get("hearing_result")}, case.get("decision_date") or case.get("hearing_date") or case.get("violation_date")))
            continue
        for event_type, field in (("OATH_STATUS_CHANGED", "hearing_status"), ("OATH_DECISION_CHANGED", "hearing_result"), ("OATH_PENALTY_CHANGED", "penalty_imposed"), ("OATH_BALANCE_CHANGED", "balance_due")):
            if old.get(field) != case.get(field):
                events.append(_event(event_type, current, detected_at, "NYC_OATH_HEARINGS_DIVISION_CASE_STATUS", "SUMMONS_TICKET_EXACT", {"ticket_number": ticket, field: old.get(field)}, {"ticket_number": ticket, field: case.get(field)}, case.get("decision_date") or case.get("hearing_date")))

    if previous.get("pluto_owner") != current.get("pluto_owner"):
        events.append(_event("PLUTO_OWNER_CHANGED", current, detected_at, "NYC_DCP_PLUTO", "BBL_EXACT", previous.get("pluto_owner"), current.get("pluto_owner")))

    registration_fields = ("hpd_registration_id", "hpd_last_registration_date")
    if any(previous.get(field) != current.get(field) for field in registration_fields):
        events.append(_event("HPD_REGISTRATION_CHANGED", current, detected_at, "NYC_HPD_MULTIPLE_DWELLING_REGISTRATION", "BBL_EXACT", {field: previous.get(field) for field in registration_fields}, {field: current.get(field) for field in registration_fields}, current.get("hpd_last_registration_date")))

    previous_contacts = {_contact_key(item): item for item in previous.get("hpd_contacts") or []}
    current_contacts = {_contact_key(item): item for item in current.get("hpd_contacts") or []}
    for key, contact in current_contacts.items():
        if key not in previous_contacts:
            events.append(_event("HPD_CONTACT_ADDED", current, detected_at, "NYC_HPD_REGISTRATION_CONTACTS", "REGISTRATION_ID_EXACT", None, contact, current.get("hpd_last_registration_date")))
    for key, contact in previous_contacts.items():
        if key not in current_contacts:
            events.append(_event("HPD_CONTACT_REMOVED", current, detected_at, "NYC_HPD_REGISTRATION_CONTACTS", "REGISTRATION_ID_EXACT", contact, None, current.get("hpd_last_registration_date")))

    old_managers = [_contact_key(item) for item in _managing_contacts(previous.get("hpd_contacts") or [])]
    new_managers = [_contact_key(item) for item in _managing_contacts(current.get("hpd_contacts") or [])]
    if old_managers != new_managers:
        events.append(_event("HPD_MANAGING_AGENT_CHANGED", current, detected_at, "NYC_HPD_REGISTRATION_CONTACTS", "REGISTRATION_ID_EXACT", _managing_contacts(previous.get("hpd_contacts") or []), _managing_contacts(current.get("hpd_contacts") or []), current.get("hpd_last_registration_date")))

    return events


def build_history(
    current_observations: list[dict[str, Any]],
    detected_at: str,
    previous_snapshot: dict[str, Any] | None,
    previous_events: list[dict[str, Any]] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    current_by_id = {item["system_id"]: item for item in current_observations}
    previous_by_id = {item["system_id"]: item for item in (previous_snapshot or {}).get("systems", [])}
    history_started_at = (previous_snapshot or {}).get("history_started_at") or detected_at
    baseline_initialized = not bool(previous_snapshot and previous_by_id)
    new_events: list[dict[str, Any]] = []

    if not baseline_initialized:
        for system_id, current in current_by_id.items():
            previous = previous_by_id.get(system_id)
            if previous is None:
                new_events.append(_event("SYSTEM_FIRST_SEEN", current, detected_at, "NYC_COOLING_TOWER_REGISTRATIONS", "SYSTEM_ID_EXACT", None, {"present_in_snapshot": True}, current.get("date_registered")))
            else:
                new_events.extend(detect_changes(previous, current, detected_at))
        for system_id, previous in previous_by_id.items():
            if system_id not in current_by_id:
                missing = dict(previous)
                new_events.append(_event("SYSTEM_NO_LONGER_PRESENT", missing, detected_at, "NYC_COOLING_TOWER_REGISTRATIONS", "SYSTEM_ID_EXACT", {"present_in_snapshot": True}, {"present_in_snapshot": False}))

    cutoff = datetime.fromisoformat(detected_at.replace("Z", "+00:00")) - timedelta(days=EVENT_RETENTION_DAYS)
    retained = []
    for event in (previous_events or []) + new_events:
        try:
            event_dt = datetime.fromisoformat(str(event.get("detected_at", "")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if event_dt >= cutoff:
            retained.append(event)
    retained.sort(key=lambda item: (item.get("detected_at") or "", item.get("system_id") or "", item.get("event_type") or ""), reverse=True)

    snapshot = {
        "history_schema_version": HISTORY_SCHEMA_VERSION,
        "history_started_at": history_started_at,
        "observed_at": detected_at,
        "systems": sorted(current_observations, key=lambda item: item["system_id"]),
    }
    changes = {
        "history_schema_version": HISTORY_SCHEMA_VERSION,
        "history_started_at": history_started_at,
        "observed_at": detected_at,
        "baseline_initialized": baseline_initialized,
        "new_event_count": len(new_events),
        "events": retained,
    }
    return snapshot, changes


def load_json(path: Path | None, default: Any) -> Any:
    if path is None or not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_history_outputs(output_dir: Path, snapshot: dict[str, Any], changes: dict[str, Any]) -> None:
    history_dir = output_dir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    (history_dir / "latest.json").write_text(json.dumps(snapshot, separators=(",", ":")), encoding="utf-8")
    (history_dir / "events.json").write_text(json.dumps({"events": changes["events"]}, separators=(",", ":")), encoding="utf-8")
    (output_dir / "changes.json").write_text(json.dumps(changes, separators=(",", ":")), encoding="utf-8")

    by_system: dict[str, list[dict[str, Any]]] = {}
    for event in changes["events"]:
        by_system.setdefault(event["system_id"], []).append(event)
    detail_root = output_dir / "history" / "systems"
    for system_id, events in by_system.items():
        safe = "".join(ch for ch in system_id if ch.isalnum() or ch in ("-", "_"))
        prefix = (safe[:2] or "xx").lower()
        target = detail_root / prefix / f"{safe}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"history_started_at": changes["history_started_at"], "events": events}, separators=(",", ":")), encoding="utf-8")
