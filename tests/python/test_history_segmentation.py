from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.history import HISTORY_SCHEMA_VERSION, build_history  # noqa: E402
from towersignal.history_store import (  # noqa: E402
    HISTORY_STORAGE_VERSION,
    load_history_snapshot,
    reconstruct_segmented_snapshot,
    write_segmented_snapshot,
)
from validate_history_store import validate_history_size  # noqa: E402


def system(system_id: str = "CT-1") -> dict:
    return {
        "system_id": system_id,
        "bin": "1000001",
        "bbl": "1000010001",
        "address": "1 TEST ST",
        "borough": "Manhattan",
        "zip": "10001",
        "date_registered": "2026-01-01",
        "active_equipment": 1,
        "sample_dates": ["2026-09-01"],
        "latest_sample_date": "2026-09-01",
        "primary_signal": "NO_CURRENT_SIGNAL",
        "signal_types": [],
        "priority_score": 10,
        "evidence_confidence": "STRONG_SIGNAL",
        "first_seen_at": "2026-08-20T00:00:00Z",
        "last_seen_at": "2026-09-07T00:00:00Z",
        "inspection_keys": ["i1"],
        "violation_keys": ["v1"],
        "oath_cases": [{"ticket_number": "T1", "hearing_status": "Closed"}],
        "pluto_owner": "OWNER LLC",
        "building_context": {"owner_name": "OWNER LLC", "year_built": 1980},
        "hpd_registration_id": "R1",
        "hpd_last_registration_date": "2026-08-01",
        "hpd_contacts": [{"registration_contact_id": "C1", "type": "Managing Agent"}],
    }


def snapshot() -> dict:
    return {
        "history_schema_version": HISTORY_SCHEMA_VERSION,
        "history_started_at": "2026-08-20T00:00:00Z",
        "observed_at": "2026-09-07T00:00:00Z",
        "dob_history_initialized": True,
        "dob_by_bbl": {"1000010001": {"M1": ["Filed", 1]}},
        "systems": [system()],
        "source_health": [{"source_key": "registrations", "coverage_percentage": 100.0}],
    }


class HistorySegmentationTests(unittest.TestCase):
    def test_segmented_snapshot_round_trips_to_identical_logical_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_dir = Path(tmp) / "history"
            original = snapshot()
            manifest = write_segmented_snapshot(history_dir, original)
            self.assertEqual(manifest["history_storage_version"], HISTORY_STORAGE_VERSION)
            self.assertLess((history_dir / "latest.json").stat().st_size, 20_000)
            reconstructed = load_history_snapshot(history_dir / "latest.json")
            self.assertEqual(reconstructed, original)
            validation = validate_history_size(history_dir / "latest.json")
            self.assertEqual(validation["storage_version"], HISTORY_STORAGE_VERSION)
            self.assertEqual(validation["system_count"], 1)
            self.assertGreaterEqual(validation["segment_count"], 7)

    def test_old_monolith_remains_readable_for_first_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "latest.json"
            original = snapshot()
            path.write_text(json.dumps(original), encoding="utf-8")
            self.assertEqual(load_history_snapshot(path), original)

    def test_storage_migration_does_not_trigger_history_schema_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_dir = Path(tmp) / "history"
            previous = snapshot()
            write_segmented_snapshot(history_dir, previous)
            reconstructed = load_history_snapshot(history_dir / "latest.json")
            current = dict(system())
            # build_history expects transient DOB/inspection records only when detecting
            # new source events; unchanged durable state is sufficient for this migration proof.
            current["_dob_jobs"] = {"M1": ["Filed", 1]}
            current["_dob_records"] = {}
            current["_inspection_records"] = {}
            current["_violation_records"] = {}
            _, changes = build_history([current], "2026-09-08T00:00:00Z", reconstructed, [])
            self.assertFalse(changes["schema_migrated"])
            self.assertFalse(changes["baseline_initialized"])
            self.assertEqual(changes["new_event_count"], 0)

    def test_unknown_durable_field_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = snapshot()
            original["systems"][0]["future_unowned_field"] = "must not disappear"
            with self.assertRaisesRegex(RuntimeError, "future_unowned_field"):
                write_segmented_snapshot(Path(tmp) / "history", original)

    def test_tampered_segment_fails_checksum_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_dir = Path(tmp) / "history"
            manifest = write_segmented_snapshot(history_dir, snapshot())
            core = history_dir / manifest["segments"]["core"]["path"]
            core.write_text(core.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "size mismatch|checksum mismatch"):
                reconstruct_segmented_snapshot(history_dir, manifest)


if __name__ == "__main__":
    unittest.main()
