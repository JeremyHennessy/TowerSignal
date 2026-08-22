from __future__ import annotations

import argparse
import json
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
        ))

    retain_seen_timestamps(observations, previous_snapshot, detected_at)
    previous_events_payload = load_json(previous_events_path, {"events": []})
    previous_events = previous_events_payload.get("events", []) if isinstance(previous_events_payload, dict) else []
    snapshot, changes = build_history(observations, detected_at, previous_snapshot, previous_events)
    write_history_outputs(output_dir, snapshot, changes)
    print(json.dumps({
        "history_started_at": changes["history_started_at"],
        "baseline_initialized": changes["baseline_initialized"],
        "current_system_count": len(observations),
        "new_event_count": changes["new_event_count"],
        "retained_event_count": len(changes["events"]),
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
