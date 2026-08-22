from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from scripts.build_history import suppress_unsupported_disappearance_events  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
