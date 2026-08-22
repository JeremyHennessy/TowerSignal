from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.history import HISTORY_SCHEMA_VERSION, build_history, build_observation, detect_changes  # noqa: E402


def full_observation(**overrides):
    system = {
        "system_id": "CT-100", "bin": "1000001", "bbl": "1000010001", "address": "100 EXAMPLE STREET",
        "borough": "Manhattan", "zip": "10001", "date_registered": "2026-01-01", "active_equipment": 2,
        "sample_dates": ["2026-08-01"], "latest_sample_date": "2026-08-01",
    }
    summary = {
        "primary_signal": "NO_CURRENT_SIGNAL", "signal_types": [], "priority_score": 40,
        "evidence_confidence": "STRONG_SIGNAL",
    }
    inspections = []
    oath_cases = []
    building_context = {"owner_name": "ABC LLC", "land_use": "05", "building_class": "O4", "year_built": 1980,
                        "building_area_sqft": 100000, "floors": 12, "total_units": 1}
    hpd_registration = {"registration_id": "R1", "last_registration_date": "2026-08-01", "contacts": []}
    for key, value in overrides.items():
        if key == "system": system.update(value)
        elif key == "summary": summary.update(value)
        elif key == "inspections": inspections = value
        elif key == "oath_cases": oath_cases = value
        elif key == "building_context": building_context = value
        elif key == "hpd_registration": hpd_registration = value
        else: system[key] = value
    return build_observation(system, summary, inspections, oath_cases, building_context, hpd_registration)


class HistoryTests(unittest.TestCase):
    def test_compact_observation_excludes_full_source_payload(self):
        obs = full_observation(
            inspections=[{"inspection_date": "2026-08-20", "inspection_type": "Routine", "status": "Open",
                          "violations": [{"summons_number": "S1", "violation_code": "V1", "law_section": "X",
                                          "violation_type": "Violation", "violation_text": "x" * 5000}]}],
            oath_cases=[{"ticket_number": "T1", "hearing_status": "Pending", "hearing_result": None,
                         "penalty_imposed": 100, "balance_due": 100, "charges": [{"description": "raw" * 1000}]}],
        )
        self.assertNotIn("inspections", obs)
        self.assertEqual(len(obs["inspection_keys"]), 1)
        self.assertEqual(len(obs["violation_keys"]), 1)
        self.assertNotIn("charges", obs["oath_cases"][0])
        self.assertLessEqual(len(next(iter(obs["_violation_records"].values()))["description"]), 501)

    def test_initial_snapshot_creates_no_false_first_seen_events(self):
        snapshot, changes = build_history([full_observation()], "2026-08-22T01:00:00Z", None, [])
        self.assertTrue(changes["baseline_initialized"])
        self.assertEqual(changes["new_event_count"], 0)
        self.assertEqual(changes["events"], [])
        self.assertEqual(snapshot["history_schema_version"], HISTORY_SCHEMA_VERSION)
        self.assertNotIn("_inspection_records", snapshot["systems"][0])

    def test_schema_migration_emits_zero_synthetic_events(self):
        previous = {"history_schema_version": "1.0", "history_started_at": "2026-08-20T01:00:00Z",
                    "systems": [{"system_id": "CT-100", "active_equipment": 99}]}
        _, changes = build_history([full_observation()], "2026-08-22T01:00:00Z", previous, [])
        self.assertTrue(changes["schema_migrated"])
        self.assertTrue(changes["baseline_initialized"])
        self.assertEqual(changes["new_event_count"], 0)

    def test_compact_sample_violation_oath_owner_and_contact_changes_are_detected(self):
        previous = full_observation(
            summary={"signal_types": ["POTENTIAL_SAMPLING_GAP"]},
            inspections=[{"inspection_date": "2026-08-10", "inspection_type": "Routine", "status": "Closed", "violations": []}],
            oath_cases=[{"ticket_number": "T1", "hearing_status": "Pending", "hearing_result": None,
                         "penalty_imposed": 0, "balance_due": 0}],
        )
        current = full_observation(
            system={"active_equipment": 3, "sample_dates": ["2026-08-01", "2026-08-21"], "latest_sample_date": "2026-08-21"},
            inspections=[
                {"inspection_date": "2026-08-10", "inspection_type": "Routine", "status": "Closed", "violations": []},
                {"inspection_date": "2026-08-20", "inspection_type": "Routine", "status": "Open",
                 "violations": [{"summons_number": "S1", "violation_code": "V1", "law_section": "X",
                                  "violation_type": "Violation", "violation_text": "Test"}]},
            ],
            oath_cases=[{"ticket_number": "T1", "hearing_status": "Decided", "hearing_result": "In Violation",
                         "penalty_imposed": 500, "balance_due": 500, "decision_date": "2026-08-21"}],
            building_context={"owner_name": "XYZ HOLDINGS LLC"},
            hpd_registration={"registration_id": "R1", "last_registration_date": "2026-08-21",
                              "contacts": [{"registration_contact_id": "C1", "type": "Managing Agent",
                                            "description": "Managing Agent", "corporation_name": "XYZ MANAGEMENT INC",
                                            "person_name": None, "title": None, "business_address": "1 MAIN ST"}]},
        )
        event_types = {event["event_type"] for event in detect_changes(previous, current, "2026-08-22T01:00:00Z")}
        for expected in (
            "ACTIVE_EQUIPMENT_CHANGED", "SAMPLE_REPORTED", "LATEST_SAMPLE_CHANGED", "SAMPLING_GAP_RESOLVED",
            "INSPECTION_ADDED", "VIOLATION_ADDED", "OATH_STATUS_CHANGED", "OATH_DECISION_CHANGED",
            "OATH_PENALTY_CHANGED", "OATH_BALANCE_CHANGED", "PLUTO_OWNER_CHANGED", "HPD_REGISTRATION_CHANGED",
            "HPD_CONTACT_ADDED", "HPD_MANAGING_AGENT_CHANGED",
        ):
            self.assertIn(expected, event_types)

    def test_missing_current_enrichment_does_not_create_false_change_events(self):
        previous = full_observation(hpd_registration={"registration_id": "R1", "last_registration_date": "2026-08-01",
                                                      "contacts": [{"registration_contact_id": "C1", "type": "Managing Agent",
                                                                    "description": "Managing Agent", "corporation_name": "ABC MGMT"}]})
        current = full_observation(building_context=None, hpd_registration=None)
        event_types = {event["event_type"] for event in detect_changes(previous, current, "2026-08-22T01:00:00Z")}
        self.assertNotIn("PLUTO_OWNER_CHANGED", event_types)
        self.assertNotIn("HPD_REGISTRATION_CHANGED", event_types)
        self.assertNotIn("HPD_CONTACT_REMOVED", event_types)
        self.assertNotIn("HPD_MANAGING_AGENT_CHANGED", event_types)

    def test_removed_system_wording_is_snapshot_presence_not_decommissioning(self):
        previous_obs = full_observation()
        previous = {"history_schema_version": HISTORY_SCHEMA_VERSION, "history_started_at": "2026-08-20T01:00:00Z",
                    "systems": [previous_obs]}
        _, changes = build_history([], "2026-08-22T01:00:00Z", previous, [])
        self.assertEqual(changes["events"][0]["event_type"], "SYSTEM_NO_LONGER_PRESENT")
        self.assertEqual(changes["events"][0]["new_value"], {"present_in_snapshot": False})

    def test_new_system_after_baseline_is_first_seen(self):
        previous_obs = full_observation()
        previous = {"history_schema_version": HISTORY_SCHEMA_VERSION, "history_started_at": "2026-08-20T01:00:00Z",
                    "systems": [previous_obs]}
        second = full_observation(system={"system_id": "CT-200", "address": "200 EXAMPLE STREET"})
        _, changes = build_history([previous_obs, second], "2026-08-22T01:00:00Z", previous, [])
        first_seen = [event for event in changes["events"] if event["event_type"] == "SYSTEM_FIRST_SEEN"]
        self.assertEqual(len(first_seen), 1)
        self.assertEqual(first_seen[0]["system_id"], "CT-200")


if __name__ == "__main__":
    unittest.main()
