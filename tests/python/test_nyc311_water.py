from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.nyc311_water import classify_request, normalize_bbl, normalize_request  # noqa: E402


class Nyc311WaterTests(unittest.TestCase):
    def test_bbl_validation_accepts_only_exact_nyc_bbl(self) -> None:
        self.assertEqual(normalize_bbl("1000160001"), "1000160001")
        self.assertEqual(normalize_bbl("1-00016-0001"), "1000160001")
        self.assertIsNone(normalize_bbl("9000160001"))
        self.assertIsNone(normalize_bbl("100016001"))

    def test_lead_kit_is_activity_not_condition_confirmation(self) -> None:
        result = classify_request("Lead", "Lead Kit")
        self.assertEqual(result.category, "LEAD_TEST_KIT_ACTIVITY")
        self.assertEqual(result.asset_scope, "BUILDING_WATER_ACTIVITY")
        self.assertIn("does not prove", result.reason)

    def test_dirty_water_is_quality_signal(self) -> None:
        result = classify_request("Water Quality", "Dirty Water")
        self.assertEqual(result.category, "DRINKING_WATER_QUALITY")
        self.assertEqual(result.asset_scope, "BUILDING_OR_DISTRIBUTION_SIGNAL")

    def test_low_pressure_is_supply_signal(self) -> None:
        result = classify_request("Water System", "Low Pressure")
        self.assertEqual(result.category, "WATER_SUPPLY_PRESSURE")
        self.assertEqual(result.asset_scope, "BUILDING_OR_DISTRIBUTION_SIGNAL")

    def test_hydrant_and_main_break_are_public_infrastructure(self) -> None:
        hydrant = classify_request("Water Maintenance", "Fire Hydrant Defective")
        main = classify_request("Water Maintenance", "Water Main Break")
        self.assertEqual(hydrant.category, "PUBLIC_WATER_INFRASTRUCTURE")
        self.assertEqual(main.category, "PUBLIC_WATER_INFRASTRUCTURE")
        self.assertEqual(hydrant.asset_scope, "PUBLIC_INFRASTRUCTURE")

    def test_generic_leak_remains_mixed_location(self) -> None:
        result = classify_request("Water Maintenance", "Leak")
        self.assertEqual(result.category, "WATER_LEAK_REPORTED")
        self.assertEqual(result.asset_scope, "MIXED_LOCATION_SIGNAL")

    def test_normalized_request_preserves_reported_evidence_boundary(self) -> None:
        row = normalize_request(
            "NYC_311_2020_PRESENT",
            "erm2-nwe9",
            {
                "unique_key": "123",
                "created_date": "2026-09-01T10:00:00.000",
                "agency": "DEP",
                "complaint_type": "Water Quality",
                "descriptor": "Dirty Water",
                "status": "Closed",
                "borough": "MANHATTAN",
                "bbl": "1000160001",
                "incident_address": "1 EXAMPLE ST",
            },
        )
        self.assertEqual(normalized := row["evidence_type"], "REPORTED_SERVICE_REQUEST")
        self.assertEqual(row["condition_confirmation"], "UNVERIFIED_REPORTED_CONDITION")
        self.assertEqual(row["property_link_confidence"], "CONFIRMED_LOCATION_IDENTIFIER")
        self.assertEqual(row["bbl"], "1000160001")
        self.assertEqual(row["source_dataset_id"], "erm2-nwe9")
        self.assertEqual(normalized, "REPORTED_SERVICE_REQUEST")


if __name__ == "__main__":
    unittest.main()
