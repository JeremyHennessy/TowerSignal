from __future__ import annotations

import unittest

from scripts.towersignal.source_health import SourceHealthError, health_entry, validate_source_health


class SourceHealthTests(unittest.TestCase):
    def test_healthy_entry_tracks_coverage_and_attachment(self) -> None:
        entry = health_entry(
            source_key="pluto",
            dataset_id="fixture",
            name="PLUTO",
            entity_unit="BBLs",
            retrieved_record_count=100,
            requested_entity_count=100,
            normalized_entity_count=95,
            matched_entity_count=95,
            attached_entity_count=110,
            displayed_entity_count=110,
            previous_coverage_percentage=94.0,
            coverage_note="fixture",
        )
        self.assertEqual(entry["status"], "HEALTHY")
        self.assertEqual(entry["coverage_percentage"], 95.0)
        self.assertEqual(entry["coverage_change_percentage_points"], 1.0)

    def test_matched_but_not_attached_fails(self) -> None:
        entry = health_entry(
            source_key="pluto",
            dataset_id="fixture",
            name="PLUTO",
            entity_unit="BBLs",
            retrieved_record_count=100,
            requested_entity_count=100,
            normalized_entity_count=90,
            matched_entity_count=90,
            attached_entity_count=0,
            displayed_entity_count=0,
            coverage_note="fixture",
        )
        self.assertEqual(entry["status"], "FAILED")
        with self.assertRaises(SourceHealthError):
            validate_source_health([entry])

    def test_catastrophic_coverage_drop_fails(self) -> None:
        entry = health_entry(
            source_key="oath",
            dataset_id="fixture",
            name="OATH",
            entity_unit="tickets",
            retrieved_record_count=40,
            requested_entity_count=100,
            normalized_entity_count=40,
            matched_entity_count=40,
            attached_entity_count=30,
            displayed_entity_count=30,
            previous_coverage_percentage=95.0,
            coverage_note="fixture",
        )
        self.assertEqual(entry["status"], "FAILED")

    def test_moderate_coverage_drop_warns_without_failing(self) -> None:
        entry = health_entry(
            source_key="hpd",
            dataset_id="fixture",
            name="HPD",
            entity_unit="BBLs",
            retrieved_record_count=70,
            requested_entity_count=100,
            normalized_entity_count=70,
            matched_entity_count=70,
            attached_entity_count=70,
            displayed_entity_count=70,
            previous_coverage_percentage=95.0,
            coverage_note="fixture",
        )
        self.assertEqual(entry["status"], "WARNING")
        validate_source_health([entry])


if __name__ == "__main__":
    unittest.main()
