from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

NYS_HISTORY_SCHEMA_VERSION = "1.0"
NYS_EVENT_RETENTION_DAYS = 400
NYS_SOURCE = "NYS_COOLING_TOWER_REGISTRY_WEEKLY_EXTRACT"
NYS_EVIDENCE_BASIS = "EQUIPMENT_ID_EXACT"


def build_observation(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "system_id": row["system_id"],
        "source_equipment_id": row.get("source_equipment_id"),
        "address": row.get("address"),
        "city": row.get("city"),
        "zip": row.get("zip"),
        "source_county": row.get("source_county"),
        "property_key": row.get("property_key"),
        "property_equipment_count": row.get("property_equipment_count"),
        "regulation_compliance": row.get("regulation_compliance"),
        "ct_status": row.get("ct_status"),
        "latest_sample_date": row.get("latest_sample_date"),
        "latest_sample_result": row.get("latest_sample_result"),
        "operation_duration": row.get("operation_duration"),
        "coordinate_status": row.get("coordinate_status"),
        "latitude": row.get("latitude"),
        "longitude": row.get("longitude"),
    }


def _event(event_type: str, current: dict[str, Any], detected_at: str, previous_value: Any, new_value: Any,
           source_observation_date: str | None = None) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "system_id": current["system_id"],
        "source_equipment_id": current.get("source_equipment_id"),
        "address": current.get("address"),
        "city": current.get("city"),
        "zip": current.get("zip"),
        "source_county": current.get("source_county"),
        "detected_at": detected_at,
        "source_observation_date": source_observation_date,
        "previous_value": previous_value,
        "new_value": new_value,
        "source": NYS_SOURCE,
        "evidence_basis": NYS_EVIDENCE_BASIS,
    }


def detect_changes(previous: dict[str, Any], current: dict[str, Any], detected_at: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    fields = (
        ("NYS_REG_COMPLIANCE_CHANGED", "regulation_compliance", None),
        ("NYS_CT_STATUS_CHANGED", "ct_status", None),
        ("NYS_SAMPLE_DATE_CHANGED", "latest_sample_date", "latest_sample_date"),
        ("NYS_SAMPLE_RESULT_CHANGED", "latest_sample_result", "latest_sample_date"),
        ("NYS_OPERATION_DURATION_CHANGED", "operation_duration", None),
    )
    for event_type, field, source_date_field in fields:
        if previous.get(field) != current.get(field):
            events.append(_event(
                event_type,
                current,
                detected_at,
                previous.get(field),
                current.get(field),
                current.get(source_date_field) if source_date_field else None,
            ))
    return events


def retain_seen_timestamps(observations: list[dict[str, Any]], previous_snapshot: dict[str, Any] | None,
                           detected_at: str) -> list[dict[str, Any]]:
    previous_by_id = {item["system_id"]: item for item in (previous_snapshot or {}).get("systems", [])}
    for observation in observations:
        previous = previous_by_id.get(observation["system_id"])
        observation["first_seen_at"] = previous.get("first_seen_at") if previous and previous.get("first_seen_at") else detected_at
        observation["last_seen_at"] = detected_at
    return observations


def build_history(current_observations: list[dict[str, Any]], detected_at: str,
                  previous_snapshot: dict[str, Any] | None,
                  previous_events: list[dict[str, Any]] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    current_by_id = {item["system_id"]: item for item in current_observations}
    previous_by_id = {item["system_id"]: item for item in (previous_snapshot or {}).get("systems", [])}
    history_started_at = (previous_snapshot or {}).get("history_started_at") or detected_at
    schema_changed = bool(previous_snapshot) and previous_snapshot.get("history_schema_version") != NYS_HISTORY_SCHEMA_VERSION
    baseline_initialized = not bool(previous_snapshot and previous_by_id) or schema_changed
    new_events: list[dict[str, Any]] = []

    if not baseline_initialized:
        for system_id, current in current_by_id.items():
            previous = previous_by_id.get(system_id)
            if previous is None:
                new_events.append(_event(
                    "NYS_EQUIPMENT_FIRST_SEEN", current, detected_at, None,
                    {"present_in_snapshot": True}, current.get("latest_sample_date"),
                ))
            else:
                new_events.extend(detect_changes(previous, current, detected_at))
        for system_id, previous in previous_by_id.items():
            if system_id not in current_by_id:
                new_events.append(_event(
                    "NYS_EQUIPMENT_NO_LONGER_PRESENT", dict(previous), detected_at,
                    {"present_in_snapshot": True}, {"present_in_snapshot": False}, None,
                ))

    cutoff = datetime.fromisoformat(detected_at.replace("Z", "+00:00")) - timedelta(days=NYS_EVENT_RETENTION_DAYS)
    retained: list[dict[str, Any]] = []
    for event in (previous_events or []) + new_events:
        try:
            event_dt = datetime.fromisoformat(str(event.get("detected_at", "")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if event_dt >= cutoff:
            retained.append(event)
    retained.sort(key=lambda item: (
        item.get("detected_at") or "",
        item.get("system_id") or "",
        item.get("event_type") or "",
    ), reverse=True)

    snapshot = {
        "history_schema_version": NYS_HISTORY_SCHEMA_VERSION,
        "history_started_at": history_started_at,
        "observed_at": detected_at,
        "systems": sorted(current_observations, key=lambda item: item["system_id"]),
    }
    changes = {
        "history_schema_version": NYS_HISTORY_SCHEMA_VERSION,
        "history_started_at": history_started_at,
        "observed_at": detected_at,
        "baseline_initialized": baseline_initialized,
        "schema_migrated": schema_changed,
        "new_event_count": len(new_events),
        "events": retained,
    }
    return snapshot, changes


def load_json(path: Path | None, default: Any) -> Any:
    if path is None or not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_history_outputs(output_dir: Path, snapshot: dict[str, Any], changes: dict[str, Any]) -> None:
    history_dir = output_dir / "history" / "nys"
    history_dir.mkdir(parents=True, exist_ok=True)
    (history_dir / "latest.json").write_text(json.dumps(snapshot, separators=(",", ":")), encoding="utf-8")
    (history_dir / "events.json").write_text(json.dumps({"events": changes["events"]}, separators=(",", ":")), encoding="utf-8")
    (output_dir / "nys-changes.json").write_text(json.dumps(changes, separators=(",", ":")), encoding="utf-8")