import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from scripts.pull_ontario_open_building_environment import select_resources
from scripts.pull_toronto_history_notices import select_chemtrac_resources
from scripts.toronto_final_identity_cleanup import linked_range_parent


class TorontoSourceResourceSelectionTests(unittest.TestCase):
    def test_chemtrac_selects_latest_equivalent_annual_resource(self) -> None:
        selected, excluded = select_chemtrac_resources([
            {"id": "old", "name": "Chemtrac Data 2024", "format": "CSV", "last_modified": None},
            {"id": "current", "name": "Chemtrac Data 2024.csv", "format": "CSV", "last_modified": "2026-02-20T18:44:30"},
            {"id": "prior-year", "name": "Chemtrac Data 2023.csv", "format": "CSV", "last_modified": "2025-01-01T00:00:00"},
        ])
        self.assertEqual([item["id"] for item in selected], ["prior-year", "current"])
        self.assertEqual([item["id"] for item in excluded], ["old"])

    def test_environmental_selection_uses_one_english_xlsx_per_year_and_category(self) -> None:
        package = {"resources": [
            {"id": "csv-en", "name": "2024 air emissions", "format": "CSV", "language": "english", "url": "https://example/2024_air.csv"},
            {"id": "xlsx-en", "name": "2024 air emissions", "format": "XLSX", "language": "english", "url": "https://example/2024_air.xlsx"},
            {"id": "xlsx-fr", "name": "2024 air emissions", "format": "XLSX", "language": "french", "url": "https://example/2024_air_fr.xlsx"},
            {"id": "sewage", "name": "2024 industrial sewage", "format": "XLSX", "language": "english", "url": "https://example/2024_sewage.xlsx"},
        ]}
        selected = select_resources(package, "all_tabular")
        self.assertEqual([item["id"] for item in selected], ["xlsx-en", "sewage"])

    def test_range_resolves_only_when_both_endpoints_converge_on_city_parent(self) -> None:
        parent = {"address_point_id": "10", "address_point_id_link": ""}
        child = {"address_point_id": "20", "address_point_id_link": "10"}
        parent_result, endpoints = linked_range_parent("10-20 Bay St", {"10 BAY ST": [parent], "20 BAY ST": [child]}, {"10": parent, "20": child})
        self.assertEqual(parent_result, parent)
        self.assertEqual(endpoints, ["10", "20"])

        unresolved, _ = linked_range_parent("90-94 Adelaide St W", {"90 ADELAIDE ST W": [parent]}, {"10": parent})
        self.assertIsNone(unresolved)


if __name__ == "__main__":
    unittest.main()
