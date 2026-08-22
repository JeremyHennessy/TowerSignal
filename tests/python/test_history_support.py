from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from scripts.build_history import suppress_pluto_attachment_recovery_events, suppress_unsupported_disappearance_events  # noqa: E402


class EnrichmentSupportTests(unittest.TestCase):
    def test_lost_pluto_match_does_not_become_owner_change(self):
        detected = "2026-08-22T01:00:00Z"
        changes = {"new_event_count": 1, "events": [{"event_type": "PLUTO_OWNER_CHANGED", "system_id": "CT-1", "detected_at": detected}]}
        current = [{"system_id": "CT-1", "pluto_owner": None, "hpd_registration_id": None}]
        previous = {"systems": [{"system_id": "CT-1", "pluto_owner": "ABC LLC"}]}
        suppress_unsupported_disappearance_events(changes, current, previous, detected)
        self.assertEqual(changes["events"], [])
        self.assertEqual(changes["new_event_count"], 0)
        self.assertEqual(changes["suppressed_unsupported_event_count"], 1)

    def test_valid_current_pluto_owner_change_is_retained(self):
        detected = "2026-08-22T01:00:00Z"
        event = {"event_type": "PLUTO_OWNER_CHANGED", "system_id": "CT-1", "detected_at": detected}
        changes = {"new_event_count": 1, "events": [event]}
        current = [{"system_id": "CT-1", "pluto_owner": "XYZ LLC", "hpd_registration_id": None}]
        previous = {"systems": [{"system_id": "CT-1", "pluto_owner": "ABC LLC"}]}
        suppress_unsupported_disappearance_events(changes, current, previous, detected)
        self.assertEqual(changes["events"], [event])
        self.assertEqual(changes["new_event_count"], 1)

    def test_contact_removal_requires_same_current_registration(self):
        detected = "2026-08-22T01:00:00Z"
        event = {"event_type": "HPD_CONTACT_REMOVED", "system_id": "CT-1", "detected_at": detected}
        changes = {"new_event_count": 1, "events": [event]}
        current = [{"system_id": "CT-1", "hpd_registration_id": "R2"}]
        previous = {"systems": [{"system_id": "CT-1", "hpd_registration_id": "R1"}]}
        suppress_unsupported_disappearance_events(changes, current, previous, detected)
        self.assertEqual(changes["events"], [])

    def test_bulk_pluto_restoration_is_baselined_not_called_owner_change(self):
        detected = "2026-08-22T02:00:00Z"
        current = [
            {"system_id": "CT-1", "pluto_owner": "A LLC"},
            {"system_id": "CT-2", "pluto_owner": "B LLC"},
            {"system_id": "CT-3", "pluto_owner": "C LLC"},
            {"system_id": "CT-4", "pluto_owner": None},
        ]
        previous = {"systems": [
            {"system_id": "CT-1", "pluto_owner": None},
            {"system_id": "CT-2", "pluto_owner": None},
            {"system_id": "CT-3", "pluto_owner": None},
            {"system_id": "CT-4", "pluto_owner": None},
        ]}
        events = [
            {"event_type": "PLUTO_OWNER_CHANGED", "system_id": "CT-1", "detected_at": detected},
            {"event_type": "PLUTO_OWNER_CHANGED", "system_id": "CT-2", "detected_at": detected},
            {"event_type": "PLUTO_OWNER_CHANGED", "system_id": "CT-3", "detected_at": detected},
            {"event_type": "SAMPLE_REPORTED", "system_id": "CT-1", "detected_at": detected},
        ]
        changes = {"new_event_count": 4, "events": events}
        suppress_pluto_attachment_recovery_events(changes, current, previous, detected)
        self.assertEqual([event["event_type"] for event in changes["events"]], ["SAMPLE_REPORTED"])
        self.assertEqual(changes["new_event_count"], 1)
        self.assertEqual(changes["suppressed_data_repair_event_count"], 3)
        self.assertTrue(changes["pluto_attachment_recovery_baselined"])

    def test_normal_non_null_owner_transition_is_not_suppressed(self):
        detected = "2026-08-22T02:00:00Z"
        event = {"event_type": "PLUTO_OWNER_CHANGED", "system_id": "CT-1", "detected_at": detected}
        current = [{"system_id": "CT-1", "pluto_owner": "NEW LLC"}, {"system_id": "CT-2", "pluto_owner": "B LLC"}, {"system_id": "CT-3", "pluto_owner": "C LLC"}]
        previous = {"systems": [{"system_id": "CT-1", "pluto_owner": "OLD LLC"}, {"system_id": "CT-2", "pluto_owner": None}, {"system_id": "CT-3", "pluto_owner": None}]}
        changes = {"new_event_count": 1, "events": [event]}
        suppress_pluto_attachment_recovery_events(changes, current, previous, detected)
        self.assertEqual(changes["events"], [event])
        self.assertEqual(changes["suppressed_data_repair_event_count"], 0)


if __name__ == "__main__":
    unittest.main()
