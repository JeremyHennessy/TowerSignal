from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.history import build_history, build_observation, load_json, write_history_outputs  # noqa: E402


def safe_detail_path(base: Path, system_id: str) -> Path:
    safe = "".join(ch for ch in system_id if ch.isalnum() or ch in ("-", "_"))
    prefix = (safe[:2] or "xx").lower()
    return base / "details" / prefix / f"{safe}.json"


def retain_seen_timestamps(observations: list[dict[str, Any]], previous_snapshot: dict[str, Any] | None, detected_at: str) -> list[dict[str, Any]]:
    previous_by_id = {item["system_id"]: item for item in (previous_snapshot or {}).get("systems", [])}
    for observation in observations:
        previous = previous_by_id.get(observation["system_id"])
        observation["first_seen_at"] = previous.get("first_seen_at") if previous and previous.get("first_seen_at") else detected_at
        observation["last_seen_at"] = detected_at
    return observations


def suppress_unsupported_disappearance_events(
    changes: dict[str, Any],
    observations: list[dict[str, Any]],
    previous_snapshot: dict[str, Any] | None,
    detected_at: str,
) -> dict[str, Any]:
    """Do not convert a lost enrichment match into a commercial change signal."""
    current_by_id = {item["system_id"]: item for item in observations}
    previous_by_id = {item["system_id"]: item for item in (previous_snapshot or {}).get("systems", [])}
    retained_events = []
    suppressed_new = 0
    for event in changes.get("events", []):
        if event.get("detected_at") != detected_at:
            retained_events.append(event)
            continue
        current = current_by_id.get(event.get("system_id"))
        previous = previous_by_id.get(event.get("system_id"))
        event_type = event.get("event_type")
        unsupported = False
        if current is not None and event_type == "PLUTO_OWNER_CHANGED" and not current.get("pluto_owner"):
            unsupported = True
        elif current is not None and event_type == "HPD_REGISTRATION_CHANGED" and not current.get("hpd_registration_id"):
            unsupported = True
        elif current is not None and event_type == "HPD_CONTACT_REMOVED":
            unsupported = not current.get("hpd_registration_id") or not previous or current.get("hpd_registration_id") != previous.get("hpd_registration_id")
        elif current is not None and event_type == "HPD_MANAGING_AGENT_CHANGED" and not current.get("hpd_registration_id"):
            unsupported = True
        if unsupported:
            suppressed_new += 1
        else:
            retained_events.append(event)
    changes["events"] = retained_events
    changes["new_event_count"] = max(0, int(changes.get("new_event_count", 0)) - suppressed_new)
    changes["suppressed_unsupported_event_count"] = suppressed_new
    return changes


def suppress_pluto_attachment_recovery_events(
    changes: dict[str, Any],
    observations: list[dict[str, Any]],
    previous_snapshot: dict[str, Any] | None,
    detected_at: str,
) -> dict[str, Any]:
    """Baseline a bulk PLUTO attachment restoration without inventing owner-change events.

    A source/join repair can restore context that was absent from the previous
    observation. If the previous snapshot had no PLUTO owners at all and the
    current snapshot suddenly has broad PLUTO coverage, null -> owner is an
    enrichment restoration, not evidence that ownership changed in the real
    world. Existing non-null -> different non-null owner transitions remain
    eligible as genuine deterministic change events.
    """
    previous_systems = (previous_snapshot or {}).get("systems", [])
    if not previous_systems or not observations:
        changes["suppressed_data_repair_event_count"] = 0
        return changes

    previous_owner_count = sum(1 for item in previous_systems if item.get("pluto_owner"))
    current_owner_count = sum(1 for item in observations if item.get("pluto_owner"))
    broad_recovery_floor = max(3, math.ceil(len(observations) * 0.25))
    is_attachment_recovery = previous_owner_count == 0 and current_owner_count >= broad_recovery_floor
    if not is_attachment_recovery:
        changes["suppressed_data_repair_event_count"] = 0
        return changes

    previous_by_id = {item["system_id"]: item for item in previous_systems}
    retained_events = []
    suppressed_new = 0
    for event in changes.get("events", []):
        if event.get("detected_at") != detected_at or event.get("event_type") != "PLUTO_OWNER_CHANGED":
            retained_events.append(event)
            continue
        previous = previous_by_id.get(event.get("system_id"))
        if previous is not None and not previous.get("pluto_owner"):
            suppressed_new += 1
        else:
            retained_events.append(event)

    changes["events"] = retained_events
    changes["new_event_count"] = max(0, int(changes.get("new_event_count", 0)) - suppressed_new)
    changes["suppressed_data_repair_event_count"] = suppressed_new
    changes["pluto_attachment_recovery_baselined"] = True
    return changes


def build(output_dir: Path, previous_snapshot_path: Path | None, previous_events_path: Path | None) -> dict:
    systems_path = output_dir / "systems.json"
    if not systems_path.exists():
        raise RuntimeError(f"Generated systems payload does not exist: {systems_path}")
    payload = json.loads(systems_path.read_text(encoding="utf-8"))
    detected_at = payload.get("metadata", {}).get("generated_at") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    previous_snapshot = load_json(previous_snapshot_path, None)

    observations = []
    for row in payload.get("systems", []):
        detail_path = safe_detail_path(output_dir, row["system_id"])
        if not detail_path.exists():
            raise RuntimeError(f"Missing detail payload for historical observation: {row['system_id']}")
        detail = json.loads(detail_path.read_text(encoding="utf-8"))
        identity = detail["identity"]
        system = {
            **identity,
            "date_registered": None,
            "sample_dates": detail.get("sample_history", {}).get("dates", []),
            "latest_sample_date": detail.get("sample_history", {}).get("latest_sample_date"),
        }
        observations.append(build_observation(
            system,
            row,
            detail.get("inspection_history", []),
            detail.get("oath_case_history", []),
            detail.get("building_context"),
            detail.get("hpd_registration"),
            detail.get("dob_activity_history", []),
        ))

    retain_seen_timestamps(observations, previous_snapshot, detected_at)
    previous_events_payload = load_json(previous_events_path, {"events": []})
    previous_events = previous_events_payload.get("events", []) if isinstance(previous_events_payload, dict) else []
    snapshot, changes = build_history(observations, detected_at, previous_snapshot, previous_events)
    snapshot["source_health"] = payload.get("metadata", {}).get("source_health", [])
    suppress_unsupported_disappearance_events(changes, observations, previous_snapshot, detected_at)
    suppress_pluto_attachment_recovery_events(changes, observations, previous_snapshot, detected_at)
    write_history_outputs(output_dir, snapshot, changes)
    print(json.dumps({
        "history_started_at": changes["history_started_at"],
        "baseline_initialized": changes["baseline_initialized"],
        "current_system_count": len(observations),
        "new_event_count": changes["new_event_count"],
        "retained_event_count": len(changes["events"]),
        "suppressed_unsupported_event_count": changes.get("suppressed_unsupported_event_count", 0),
        "suppressed_data_repair_event_count": changes.get("suppressed_data_repair_event_count", 0),
        "pluto_attachment_recovery_baselined": changes.get("pluto_attachment_recovery_baselined", False),
        "source_health_count": len(snapshot.get("source_health", [])),
    }, indent=2))
    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description="Build TowerSignal deterministic historical change outputs")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data")
    parser.add_argument("--previous-snapshot", type=Path)
    parser.add_argument("--previous-events", type=Path)
    args = parser.parse_args()
    build(args.output, args.previous_snapshot, args.previous_events)


if __name__ == "__main__":
    main()
