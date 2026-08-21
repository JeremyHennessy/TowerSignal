import json
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.inspections import aggregate_inspections
from towersignal.normalize import normalize_registrations, parse_sample_dates
from towersignal.scoring import priority_score
from towersignal.signals import build_signals


class SampleParserTests(unittest.TestCase):
    def test_parses_one_date(self):
        parsed = parse_sample_dates("08/10/2026")
        self.assertEqual(parsed["dates"], ["2026-08-10"])
        self.assertEqual(parsed["latest"], "2026-08-10")

    def test_many_dates_sorted_deduplicated(self):
        parsed = parse_sample_dates("08/10/2026, 07/13/2026, 08/10/2026, 06/29/2026")
        self.assertEqual(parsed["dates"], ["2026-06-29", "2026-07-13", "2026-08-10"])
        self.assertEqual(parsed["latest"], "2026-08-10")
        self.assertEqual(parsed["previous"], "2026-07-13")
        self.assertEqual(parsed["latest_interval_days"], 28)

    def test_blank_and_malformed(self):
        self.assertEqual(parse_sample_dates("   ")["dates"], [])
        parsed = parse_sample_dates("bad, 08/01/2026")
        self.assertEqual(parsed["dates"], ["2026-08-01"])
        self.assertEqual(parsed["malformed"], ["bad"])


class NormalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registrations = json.loads((ROOT / "data/fixtures/registrations.json").read_text())
        cls.inspection_rows = json.loads((ROOT / "data/fixtures/inspections.json").read_text())
        cls.rules = json.loads((ROOT / "config/rules/nyc.json").read_text())

    def test_registration_deduplicates_and_preserves_best_record(self):
        normalized, meta = normalize_registrations(self.registrations)
        self.assertEqual(len(normalized), 5)
        self.assertEqual(meta["source_duplicate_rows"], 1)
        duplicate = next(item for item in normalized if item["system_id"] == "SYS-DUPE")
        self.assertEqual(duplicate["sample_count"], 2)
        self.assertEqual(duplicate["active_equipment"], 3)
        self.assertEqual(duplicate["coordinate_status"], "VALID")

    def test_invalid_source_coordinates_are_quarantined_not_mapped(self):
        source = dict(self.registrations[0])
        source.update({"system_id": "SYS-BAD-COORD", "latitude": "0.0", "longitude": "0.0"})
        normalized, meta = normalize_registrations([source])
        system = normalized[0]
        self.assertEqual(system["coordinate_status"], "INVALID_SOURCE")
        self.assertIsNone(system["latitude"])
        self.assertIsNone(system["longitude"])
        self.assertEqual(system["source_latitude_raw"], "0.0")
        self.assertEqual(system["source_longitude_raw"], "0.0")
        self.assertEqual(meta["invalid_coordinate_system_count"], 1)

    def test_inspection_aggregation_groups_violation_rows(self):
        grouped = aggregate_inspections(self.inspection_rows)
        inspections = grouped["SYS-GAP"]
        self.assertEqual(len(inspections), 2)
        self.assertEqual(inspections[0]["violation_count"], 2)
        self.assertEqual({v["violation_code"] for v in inspections[0]["violations"]}, {"CT01", "CT02"})
        self.assertEqual(inspections[1]["violation_count"], 0)

    def test_signal_semantics_and_scoring(self):
        normalized, _ = normalize_registrations(self.registrations)
        gap = next(item for item in normalized if item["system_id"] == "SYS-GAP")
        inspections = aggregate_inspections(self.inspection_rows)["SYS-GAP"]
        state = build_signals(gap, inspections, self.rules, date(2026, 8, 21))
        types = {item["type"] for item in state["signals"]}
        self.assertIn("POTENTIAL_SAMPLING_GAP", types)
        self.assertIn("CONFIRMED_RECENT_VIOLATION", types)
        gap_signal = next(item for item in state["signals"] if item["type"] == "POTENTIAL_SAMPLING_GAP")
        self.assertEqual(gap_signal["evidence_confidence"], "VERIFY")
        self.assertNotIn("noncompliant", gap_signal["reason"].lower())

        score_a = priority_score(gap, state)
        score_b = priority_score(gap, state)
        self.assertEqual(score_a, score_b)
        self.assertGreaterEqual(score_a["score"], 0)
        self.assertLessEqual(score_a["score"], 100)
        self.assertTrue(score_a["components"])

    def test_no_public_sample_does_not_create_confirmed_violation(self):
        normalized, _ = normalize_registrations(self.registrations)
        no_sample = next(item for item in normalized if item["system_id"] == "SYS-NONE")
        state = build_signals(no_sample, [], self.rules, date(2026, 8, 21))
        self.assertFalse(state["confirmed_violation"])
        self.assertEqual(state["signals"][0]["type"], "NO_PUBLIC_SAMPLE_DATE")
        self.assertEqual(state["signals"][0]["evidence_confidence"], "VERIFY")


if __name__ == "__main__":
    unittest.main()
