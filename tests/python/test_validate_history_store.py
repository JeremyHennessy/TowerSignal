from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_history_store import HARD_MAX_BYTES, validate_history_size  # noqa: E402


class HistorySizeGateTests(unittest.TestCase):
    def test_accepts_compact_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            current = Path(tmp) / "latest.json"
            current.write_bytes(b"x" * 1024)
            result = validate_history_size(current)
            self.assertEqual(result["current_bytes"], 1024)

    def test_rejects_hard_ceiling_breach(self):
        with tempfile.TemporaryDirectory() as tmp:
            current = Path(tmp) / "latest.json"
            with current.open("wb") as handle:
                handle.truncate(HARD_MAX_BYTES + 1)
            with self.assertRaises(RuntimeError):
                validate_history_size(current)

    def test_rejects_large_growth_after_compact_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous = Path(tmp) / "previous.json"
            current = Path(tmp) / "current.json"
            previous.write_bytes(b"x" * (2 * 1024 * 1024))
            current.write_bytes(b"x" * (6 * 1024 * 1024))
            with self.assertRaises(RuntimeError):
                validate_history_size(current, previous)

    def test_allows_migration_from_oversized_old_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous = Path(tmp) / "previous.json"
            current = Path(tmp) / "current.json"
            with previous.open("wb") as handle:
                handle.truncate(HARD_MAX_BYTES + 10 * 1024 * 1024)
            current.write_bytes(b"x" * (3 * 1024 * 1024))
            result = validate_history_size(current, previous)
            self.assertEqual(result["current_bytes"], 3 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
