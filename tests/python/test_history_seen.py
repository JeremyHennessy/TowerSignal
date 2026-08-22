from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from scripts.build_history import retain_seen_timestamps  # noqa: E402


class SeenTimestampTests(unittest.TestCase):
    def test_initial_observation_sets_first_and_last_seen(self):
        observations = [{"system_id": "CT-1"}]
        retain_seen_timestamps(observations, None, "2026-08-22T01:00:00Z")
        self.assertEqual(observations[0]["first_seen_at"], "2026-08-22T01:00:00Z")
        self.assertEqual(observations[0]["last_seen_at"], "2026-08-22T01:00:00Z")

    def test_existing_system_preserves_first_seen_and_advances_last_seen(self):
        previous = {"systems": [{"system_id": "CT-1", "first_seen_at": "2026-08-20T01:00:00Z", "last_seen_at": "2026-08-21T01:00:00Z"}]}
        observations = [{"system_id": "CT-1"}]
        retain_seen_timestamps(observations, previous, "2026-08-22T01:00:00Z")
        self.assertEqual(observations[0]["first_seen_at"], "2026-08-20T01:00:00Z")
        self.assertEqual(observations[0]["last_seen_at"], "2026-08-22T01:00:00Z")


if __name__ == "__main__":
    unittest.main()
