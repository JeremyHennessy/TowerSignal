from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.history import build_history, detect_changes  # noqa: E402


def observation(**overrides):
    base = {
        "system_id": "CT-100",
        "bin": "1000001",
        "bbl": "1000010001",
        "address": "100 EXAMPLE STREET",
        "borough": "Manhattan",
        "active_equipment": 2,
        "sample_dates": ["2026-08-01"],
        "latest_sample_date": "2026-08-01",
        "signal_types": [],
        "primary_signal": "NO_CURRENT_SIGNAL",
        "priority_score": 40,
        "evidence_confidence": "STRONG_SIGNAL",
        "inspections": [],
        "oath_cases": [],
        "pluto_owner": "ABC LLC",
        "hpd_registration_id": "R1",
        "hpd_last_registration_date": "2026-08-01",
        "hpd_contacts": [],
    }
    base.update(overrides)
    return base


class HistoryTests(unittest.TestCase):
    def test_initial_snapshot_creates_no_false_first_seen_events(self):
        snapshot, changes = build_history([observation()], "2026-08-22T01:00:00Z", None, [])
        self.assertTrue(changes["baseline_initialized"])
        self.assertEqual(changes["new_event_count"], 0)
        self.assertEqual(changes["events"], [])
        self.assertEqual(snapshot["systems"][0]["system_id"], "CT-100")

    def test_sample_violation_oath_owner_and_contact_changes_are_detected(self):
        previous = observation(
            signal_types=["POTENTIAL_SAMPLING_GAP"],
            inspections=[{"inspection_date": "2026-08-10", "inspection_type": "Routine", "status": "Closed", "violations": []}],
            oath_cases=[{"ticket_number": "T1", "hearing_status": "Pending", "hearing_result": None, "penalty_imposed": 0, "balance_due": 0}],
        )
        current = observation(
            active_equipment=3,
            sample_dates=["2026-08-01", "2026-08-21"],
            latest_sample_date="2026-08-21",
            signal_types=[],
            inspections=[
                {"inspection_date": "2026-08-10", "inspection_type": "Routine", "status": "Closed", "violations": []},
                {"inspection_date": "2026-08-20", "inspection_type": "Routine", "status": "Open", "violations": [{"summons_number": "S1", "violation_code": "V1", "law_section": "X", "violation_type": "Violation", "violation_text": "Test"}]},
            ],
            oath_cases=[{"ticket_number": "T1", "hearing_status": "Decided", "hearing_result": "In Violation", "penalty_imposed": 500, "balance_due": 500, "decision_date": "2026-08-21"}],
            pluto_owner="XYZ HOLDINGS LLC",
            hpd_contacts=[{"registration_contact_id": "C1", "type": "Managing Agent", "description": "Managing Agent", "corporation_name": "XYZ MANAGEMENT INC", "person_name": None, "title": None, "business_address": "1 MAIN ST"}],
        )
        events = detect_changes(previous, current, "2026-08-22T01:00:00Z")
        event_types = {event["event_type"] for event in events}
        self.assertIn("ACTIVE_EQUIPMENT_CHANGED", event_types)
        self.assertIn("SAMPLE_REPORTED", event_types)
        self.assertIn("LATEST_SAMPLE_CHANGED", event_types)
        self.assertIn("SAMPLING_GAP_RESOLVED", event_types)
        self.assertIn("INSPECTION_ADDED", event_types)
        self.assertIn("VIOLATION_ADDED", event_types)
        self.assertIn("OATH_STATUS_CHANGED", event_types)
        self.assertIn("OATH_DECISION_CHANGED", event_types)
        self.assertIn("OATH_PENALTY_CHANGED", event_types)
        self.assertIn("OATH_BALANCE_CHANGED", event_types)
        self.assertIn("PLUTO_OWNER_CHANGED", event_types)
        self.assertIn("HPD_CONTACT_ADDED", event_types)
        self.assertIn("HPD_MANAGING_AGENT_CHANGED", event_types)

    def test_removed_system_wording_is_snapshot_presence_not_decommissioning(self):
        previous_snapshot = {
            "history_started_at": "2026-08-20T01:00:00Z",
            "systems": [observation()],
        }
        _, changes = build_history([], "2026-08-22T01:00:00Z", previous_snapshot, [])
        self.assertEqual(changes["new_event_count"], 1)
        event = changes["events"][0]
        self.assertEqual(event["event_type"], "SYSTEM_NO_LONGER_PRESENT")
        self.assertEqual(event["new_value"], {"present_in_snapshot": False})

    def test_new_system_after_baseline_is_first_seen(self):
        previous_snapshot = {
            "history_started_at": "2026-08-20T01:00:00Z",
            "systems": [observation()],
        }
        current = [observation(), observation(system_id="CT-200", address="200 EXAMPLE STREET")]
        _, changes = build_history(current, "2026-08-22T01:00:00Z", previous_snapshot, [])
        first_seen = [event for event in changes["events"] if event["event_type"] == "SYSTEM_FIRST_SEEN"]
        self.assertEqual(len(first_seen), 1)
        self.assertEqual(first_seen[0]["system_id"], "CT-200")


if __name__ == "__main__":
    unittest.main()
