import unittest

from scripts.toronto_app_sources import _rows, normalize_source_link
from scripts.toronto_source_identity import stable_source_record_id


class TorontoBpsAppSourceTests(unittest.TestCase):
    def test_rows_recognizes_persisted_toronto_candidates(self) -> None:
        row = {"Address": "30 Bond St", "Organization": "Unity Health Toronto"}
        self.assertEqual(_rows({"toronto_candidates": [row]}), [row])

    def test_bps_source_is_dataset_fallback_with_narrow_role_context(self) -> None:
        source = "ontario_bps_energy_2024"
        row = {
            "Year": 2024,
            "Organization": "Unity Health Toronto",
            "Property Name": "St. Michael's Hospital",
            "Sector": "Public Hospital",
            "Subsector": "Chronic",
            "Address": "30 Bond St.",
            "Year Ending": "2024-12-31T00:00:00",
            "Primary Property Type - Self Selected": "Hospital (General Medical & Surgical)",
        }
        record_id = stable_source_record_id(source, row)
        normalized = normalize_source_link(
            {
                "source_key": source,
                "source_record_id": record_id,
                "source_row_index": 0,
                "match_basis": "EXACT_CORRECTED_CANONICAL_PROPERTY_ADDRESS_TO_ADDRESS_POINT_SPINE",
                "source_address": "30 Bond St.",
            },
            {source: [row]},
        )
        self.assertEqual(normalized["record_title"], "St. Michael's Hospital")
        self.assertEqual(normalized["record_status"], "Published BPS energy report")
        self.assertIsNone(normalized["record_url"])
        self.assertEqual(normalized["dataset_url"], "https://data.ontario.ca/dataset/energy-use-and-greenhouse-gas-emissions-for-the-broader-public-sector")
        self.assertIn({"label": "Organization", "value": "Unity Health Toronto"}, normalized["record_details"])


if __name__ == "__main__":
    unittest.main()
