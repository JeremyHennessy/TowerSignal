from __future__ import annotations

import unittest

from scripts.pull_ontario_open_building_environment import resource_year


class OntarioOpenBuildingEnvironmentTests(unittest.TestCase):
    def test_resource_name_year_wins_over_later_metadata_year(self) -> None:
        resource = {
            "name": "2022",
            "description": "Updated publication prepared in 2023",
            "url": "https://example.invalid/energy_large_building_energy_water_ghgs_2022.xlsx",
        }
        self.assertEqual(resource_year(resource), 2022)

    def test_url_year_is_fallback_when_name_has_no_year(self) -> None:
        resource = {
            "name": "Annual report",
            "description": "Published in 2025",
            "url": "https://example.invalid/compliance-2024.csv",
        }
        self.assertEqual(resource_year(resource), 2024)

    def test_description_year_is_last_fallback(self) -> None:
        self.assertEqual(resource_year({"name": "Dataset", "url": "", "description": "Reporting year 2021"}), 2021)


if __name__ == "__main__":
    unittest.main()
