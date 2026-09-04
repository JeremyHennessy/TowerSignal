from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.ll84_water import extract_bbls, extract_bins, latest_by_property, normalize_row, parse_number  # noqa: E402


class Ll84WaterTests(unittest.TestCase):
    def test_identifier_parsing_preserves_multiple_exact_values(self) -> None:
        self.assertEqual(extract_bbls("1000160001; 1000160002 / invalid"), ["1000160001", "1000160002"])
        self.assertEqual(extract_bins("1000001, 1000002; 9000000"), ["1000001", "1000002"])
        self.assertEqual(extract_bbls("9999999999"), [])
        self.assertEqual(extract_bins("9999999"), [])

    def test_number_parser_keeps_missing_values_null(self) -> None:
        self.assertEqual(parse_number("1,234.5"), 1234.5)
        self.assertIsNone(parse_number("Not Available"))
        self.assertIsNone(parse_number(""))

    def test_normalization_does_not_collapse_multi_asset_property(self) -> None:
        row = normalize_row(
            {
                "report_year": "2024",
                "property_id": "123",
                "property_name": "Example Portfolio",
                "nyc_borough_block_and_lot": "1000160001;1000160002",
                "nyc_building_identification": "1000001;1000002",
                "address_1": "1 Example St",
                "borough": "Manhattan",
                "primary_property_type_self": "Office",
                "property_gfa_calculated_1": "100000",
                "municipally_supplied_potable_1": "2,500.5",
                "water_use_all_water_sources": "2600",
                "last_modified_date_water": "11/20/2025",
            }
        )
        self.assertEqual(row["bbls"], ["1000160001", "1000160002"])
        self.assertEqual(row["bins"], ["1000001", "1000002"])
        self.assertEqual(row["effective_municipal_potable_kgal"], 2500.5)
        self.assertEqual(row["property_link_confidence"], "CONFIRMED_IDENTIFIER")
        self.assertEqual(row["water_meter_last_modified_date"], "2025-11-20")

    def test_total_potable_precedes_mixed_and_mixed_is_fallback(self) -> None:
        base = {
            "report_year": "2024",
            "property_id": "123",
            "nyc_borough_block_and_lot": "1000160001",
            "nyc_building_identification": "1000001",
        }
        total = normalize_row({**base, "municipally_supplied_potable": "200", "municipally_supplied_potable_1": "250"})
        fallback = normalize_row({**base, "property_id": "124", "municipally_supplied_potable": "200"})
        self.assertEqual(total["effective_municipal_potable_kgal"], 250.0)
        self.assertEqual(fallback["effective_municipal_potable_kgal"], 200.0)

    def test_latest_profile_calculates_year_over_year_only_for_same_epa_property(self) -> None:
        rows = [
            normalize_row(
                {
                    "report_year": "2023",
                    "property_id": "123",
                    "nyc_borough_block_and_lot": "1000160001",
                    "municipally_supplied_potable_1": "100",
                }
            ),
            normalize_row(
                {
                    "report_year": "2024",
                    "property_id": "123",
                    "nyc_borough_block_and_lot": "1000160001",
                    "municipally_supplied_potable_1": "125",
                }
            ),
            normalize_row(
                {
                    "report_year": "2024",
                    "property_id": "999",
                    "nyc_borough_block_and_lot": "1000990001",
                    "municipally_supplied_potable_1": "50",
                }
            ),
        ]
        profiles = {row["epa_property_id"]: row for row in latest_by_property(rows)}
        self.assertEqual(profiles["123"]["latest_report_year"], "2024")
        self.assertEqual(profiles["123"]["year_over_year_delta_kgal"], 25.0)
        self.assertEqual(profiles["123"]["year_over_year_delta_pct"], 25.0)
        self.assertIsNone(profiles["999"]["year_over_year_delta_kgal"])


if __name__ == "__main__":
    unittest.main()
