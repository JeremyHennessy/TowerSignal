from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.nys_history import (  # noqa: E402
    NYS_HISTORY_SCHEMA_VERSION,
    build_history,
    build_observation,
    detect_changes,
    retain_seen_timestamps,
)


def row(**overrides):
    value = {
        "system_id": "NYS-100",
        "source_equipment_id": "100",
        "address": "100 MAIN ST",
        "city": "Albany",
        "zip": "12207",
        "source_county": "Albany",
        "property_key": "100 main st|albany|12207",
        "property_equipment_count": 2,
        "regulation_compliance": "Compliant",
        "ct_status": "Legionella Sampled",
        "latest_sample_date": "2026-08-01",
        "latest_sample_result": "lt20",
        "operation_duration": "Year-round",
        "coordinate_status": "VALID",
        "latitude": 42.65,
        "longitude": -73.75,
        "last_update_days": 5,
        "last_sampled_days": 22,
    }
    value.update(overrides)
    return value


class NysHistoryTests(unittest.TestCase):
    def test_initial_baseline_emits_zero_synthetic_events(self) -> None:
        current = [build_observation(row())]
        retain_seen_timestamps(current, None, "2026-08-23T01:00:00Z")
        snapshot, changes = build_history(current, "2026-08-23T01:00:00Z", None, [])
        self.assertTrue(changes["baseline_initialized"])
        self.assertEqual(changes["new_event_count"], 0)
        self.assertEqual(changes["events"], [])
        self.assertEqual(snapshot["history_schema_version"], NYS_HISTORY_SCHEMA_VERSION)
        self.assertEqual(snapshot["systems"][0]["first_seen_at"], "2026-08-23T01:00:00Z")

    def test_source_native_status_and_sample_transitions_are_detected(self) -> None:
        previous = build_observation(row())
        current = build_observation(row(
            regulation_compliance="Non-compliant",
            ct_status="Disinfection Required",
            latest_sample_date="2026-08-20",
            latest_sample_result="gteq1000",
            operation_duration="Seasonal",
        ))
        events = detect_changes(previous, current, "2026-08-23T01:00:00Z")
        event_types = {event["event_type"] for event in events}
        self.assertEqual(event_types, {
            "NYS_REG_COMPLIANCE_CHANGED",
            "NYS_CT_STATUS_CHANGED",
            "NYS_SAMPLE_DATE_CHANGED",
            "NYS_SAMPLE_RESULT_CHANGED",
            "NYS_OPERATION_DURATION_CHANGED",
        })
        sample = next(event for event in events if event["event_type"] == "NYS_SAMPLE_RESULT_CHANGED")
        self.assertEqual(sample["source_observation_date"], "2026-08-20")
        self.assertEqual(sample["evidence_basis"], "EQUIPMENT_ID_EXACT")

    def test_relative_day_counters_do_not_create_history_events(self) -> None:
        previous = build_observation(row(last_update_days=5, last_sampled_days=22))
        current = build_observation(row(last_update_days=6, last_sampled_days=23))
        self.assertEqual(detect_changes(previous, current, "2026-08-23T01:00:00Z"), [])

    def test_new_and_missing_equipment_use_presence_wording(self) -> None:
        previous_obs = build_observation(row())
        previous_obs["first_seen_at"] = "2026-08-22T01:00:00Z"
        previous_obs["last_seen_at"] = "2026-08-22T01:00:00Z"
        previous = {
            "history_schema_version": NYS_HISTORY_SCHEMA_VERSION,
            "history_started_at": "2026-08-22T01:00:00Z",
            "systems": [previous_obs],
        }
        second = build_observation(row(system_id="NYS-200", source_equipment_id="200"))
        retain_seen_timestamps([previous_obs, second], previous, "2026-08-23T01:00:00Z")
        _, additions = build_history([previous_obs, second], "2026-08-23T01:00:00Z", previous, [])
        first_seen = [event for event in additions["events"] if event["event_type"] == "NYS_EQUIPMENT_FIRST_SEEN"]
        self.assertEqual(len(first_seen), 1)
        self.assertEqual(first_seen[0]["system_id"], "NYS-200")

        _, removals = build_history([], "2026-08-23T01:00:00Z", previous, [])
        self.assertEqual(removals["events"][0]["event_type"], "NYS_EQUIPMENT_NO_LONGER_PRESENT")
        self.assertEqual(removals["events"][0]["new_value"], {"present_in_snapshot": False})


if __name__ == "__main__":
    unittest.main()