from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.nys_history import (  # noqa: E402
    build_history,
    build_observation,
    load_json,
    retain_seen_timestamps,
    write_history_outputs,
)


def build(output_dir: Path, previous_snapshot_path: Path | None, previous_events_path: Path | None) -> dict:
    systems_path = output_dir / "nys-systems.json"
    if not systems_path.exists():
        raise RuntimeError(f"Generated NYS systems payload does not exist: {systems_path}")
    payload = json.loads(systems_path.read_text(encoding="utf-8"))
    detected_at = payload.get("metadata", {}).get("generated_at") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    observations = [build_observation(row) for row in payload.get("systems", [])]
    previous_snapshot = load_json(previous_snapshot_path, None)
    retain_seen_timestamps(observations, previous_snapshot, detected_at)
    previous_events_payload = load_json(previous_events_path, {"events": []})
    previous_events = previous_events_payload.get("events", []) if isinstance(previous_events_payload, dict) else []
    snapshot, changes = build_history(observations, detected_at, previous_snapshot, previous_events)
    write_history_outputs(output_dir, snapshot, changes)
    print(json.dumps({
        "history_started_at": changes["history_started_at"],
        "baseline_initialized": changes["baseline_initialized"],
        "current_equipment_count": len(observations),
        "new_event_count": changes["new_event_count"],
        "retained_event_count": len(changes["events"]),
    }, indent=2))
    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description="Build TowerSignal NYS deterministic history")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data")
    parser.add_argument("--previous-snapshot", type=Path)
    parser.add_argument("--previous-events", type=Path)
    args = parser.parse_args()
    build(args.output, args.previous_snapshot, args.previous_events)


if __name__ == "__main__":
    main()