from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.nys_registry import normalize_nys_coordinates, normalize_nys_registry  # noqa: E402


class NysRegistryTests(unittest.TestCase):
    def test_coordinate_validation_retains_missing_and_quarantines_invalid(self) -> None:
        valid = normalize_nys_coordinates("43.0", "-75.0")
        self.assertEqual(valid["coordinate_status"], "VALID")
        self.assertEqual(valid["latitude"], 43.0)

        missing = normalize_nys_coordinates(None, None)
        self.assertEqual(missing["coordinate_status"], "MISSING")
        self.assertIsNone(missing["latitude"])

        invalid = normalize_nys_coordinates("0", "0")
        self.assertEqual(invalid["coordinate_status"], "INVALID_SOURCE")
        self.assertIsNone(invalid["latitude"])
        self.assertEqual(invalid["source_latitude_raw"], "0")

    def test_normalization_preserves_source_status_and_groups_only_exact_address_key(self) -> None:
        rows = [
            {
                "equipment_id": "100",
                "county": "New York",
                "reg_comp": "Non-compliant",
                "ct_status": "Sample_Required",
                "lastupdate": "8",
                "last_sampled_days": "99",
                "equipment_street_address": "252 Genesee St",
                "equipment_location_city": "Oneida",
                "equipment_location_zip": "13421",
                "equipment_last_legionellla_sample_collection_date": "2026-05-11",
                "equipment_last_legionella_test_result": "lt20",
                "equipment_tower_operation_duration": "Year-round",
                "latitude": "43.078739",
                "longitude": "-75.6493",
            },
            {
                "equipment_id": "101",
                "county": "Madison",
                "reg_comp": "Compliant",
                "ct_status": "Legionella Sampled",
                "equipment_street_address": "252 Genesee St",
                "equipment_location_city": "Oneida",
                "equipment_location_zip": "13421",
                "equipment_last_legionellla_sample_collection_date": "2026-07-20",
                "equipment_last_legionella_test_result": "gteq20butlt100",
                "equipment_tower_operation_duration": "Seasonal",
                "latitude": "43.078739",
                "longitude": "-75.6493",
            },
            {
                "equipment_id": "102",
                "county": "Madison",
                "reg_comp": "Compliant",
                "ct_status": "Legionella Sampled",
                "equipment_street_address": "253 Genesee St",
                "equipment_location_city": "Oneida",
                "equipment_location_zip": "13421",
                "latitude": "43.07",
                "longitude": "-75.64",
            },
        ]
        systems, meta = normalize_nys_registry(rows)
        self.assertEqual(len(systems), 3)
        first = next(row for row in systems if row["source_equipment_id"] == "100")
        second = next(row for row in systems if row["source_equipment_id"] == "101")
        third = next(row for row in systems if row["source_equipment_id"] == "102")
        self.assertEqual(first["system_id"], "NYS-100")
        self.assertEqual(first["source_county"], "New York")
        self.assertEqual(first["regulation_compliance"], "Non-compliant")
        self.assertEqual(first["ct_status"], "Sample_Required")
        self.assertEqual(first["latest_sample_date"], "2026-05-11")
        self.assertEqual(first["latest_sample_result"], "lt20")
        self.assertEqual(first["property_equipment_count"], 2)
        self.assertEqual(second["property_equipment_count"], 2)
        self.assertEqual(third["property_equipment_count"], 1)
        self.assertEqual(meta["multi_equipment_property_count"], 1)
        self.assertEqual(meta["equipment_at_multi_equipment_properties"], 2)

    def test_duplicate_equipment_id_does_not_multiply_inventory(self) -> None:
        rows = [
            {"equipment_id": "10", "equipment_street_address": "A", "latitude": "43", "longitude": "-75"},
            {"equipment_id": "10", "equipment_street_address": "B", "latitude": "43", "longitude": "-75"},
        ]
        systems, meta = normalize_nys_registry(rows)
        self.assertEqual(len(systems), 1)
        self.assertEqual(meta["source_duplicate_equipment_rows"], 1)


if __name__ == "__main__":
    unittest.main()