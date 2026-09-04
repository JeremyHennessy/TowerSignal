from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.domestic_water import (  # noqa: E402
    _laboratory_profiles,
    _property_profiles,
    _provider_profiles,
    normalize_bbl,
    normalize_company_key,
    normalize_compliance_activity,
    normalize_dec_applicator,
    normalize_dec_business,
    normalize_tank_inspection,
)


class DomesticWaterTests(unittest.TestCase):
    def test_provider_normalization_resolves_only_deterministic_legal_aliases(self) -> None:
        self.assertEqual(normalize_company_key("American Pipe & Tank, LLC"), "AMERICAN PIPE AND TANK")
        self.assertEqual(normalize_company_key("AMERICAN PIPE AND TANK INC."), "AMERICAN PIPE AND TANK")
        self.assertEqual(normalize_company_key("Rosenwach Tank Co. LLC"), "ROSENWACH TANK")
        self.assertEqual(normalize_company_key("Nalco Company"), "NALCO")
        self.assertNotEqual(normalize_company_key("EBS"), normalize_company_key("Environmental Building Solutions LLC"))

    def test_bbl_is_derived_only_from_valid_borough_block_and_lot(self) -> None:
        self.assertEqual(normalize_bbl("Manhattan", "00016", "0001"), "1000160001")
        self.assertEqual(normalize_bbl("Brooklyn", "123", "45"), "3001230045")
        self.assertIsNone(normalize_bbl("Unknown", "123", "45"))
        self.assertIsNone(normalize_bbl("Queens", "0", "45"))

    def test_tank_inspection_uses_actual_firm_field_and_preserves_yn_flag(self) -> None:
        row = {
            "bin": "1000001",
            "borough": "MANHATTAN",
            "block": "00016",
            "lot": "0001",
            "reporting_year": "2025",
            "tank_num": "1",
            "inspection_by_firm": "Rosenwach Tank Co. LLC",
            "inspection_performed": "Y",
            "inspection_date": "12/31/2025",
            "lab_name": "EMSL",
            "coliform": "A",
            "ecoli": "A",
        }
        normalized = normalize_tank_inspection(row)
        self.assertEqual(normalized["provider_key"], "ROSENWACH TANK")
        self.assertEqual(normalized["provider_source_field"], "inspection_by_firm")
        self.assertEqual(normalized["inspection_performed_flag"], "Y")
        self.assertEqual(normalized["lab_key"], "EMSL")
        self.assertEqual(normalized["inspection_date"], "2025-12-31")
        self.assertEqual(normalized["bbl"], "1000160001")
        self.assertEqual(normalized["provider_relationship_evidence"], "OBSERVED_SERVICE")
        self.assertEqual(normalized["provider_asset_link_confidence"], "CONFIRMED_ASSET")

        invalid = normalize_tank_inspection({**row, "inspection_by_firm": "2017"})
        self.assertIsNone(invalid["provider_id"])
        self.assertEqual(invalid["provider_data_quality"], "INVALID_OR_PLACEHOLDER")

    def test_provider_profiles_count_unique_buildings_tanks_and_aliases(self) -> None:
        rows = [
            normalize_tank_inspection(
                {
                    "bin": "1",
                    "borough": "MANHATTAN",
                    "block": "1",
                    "lot": "1",
                    "reporting_year": "2024",
                    "tank_num": "1",
                    "inspection_by_firm": "American Pipe & Tank",
                    "inspection_date": "01/10/2024",
                    "lab_name": "Lab A",
                }
            ),
            normalize_tank_inspection(
                {
                    "bin": "1",
                    "borough": "MANHATTAN",
                    "block": "1",
                    "lot": "1",
                    "reporting_year": "2025",
                    "tank_num": "1",
                    "inspection_by_firm": "AMERICAN PIPE AND TANK INC",
                    "inspection_date": "01/10/2025",
                    "lab_name": "Lab A",
                }
            ),
            normalize_tank_inspection(
                {
                    "bin": "2",
                    "borough": "MANHATTAN",
                    "block": "2",
                    "lot": "2",
                    "reporting_year": "2025",
                    "tank_num": "2",
                    "inspection_by_firm": "AMERICAN PIPE & TANK",
                    "inspection_date": "02/10/2025",
                    "lab_name": "Lab B",
                }
            ),
        ]
        providers = _provider_profiles(rows)
        self.assertEqual(len(providers), 1)
        provider = providers[0]
        self.assertEqual(provider["inspection_count"], 3)
        self.assertEqual(provider["observed_building_count"], 2)
        self.assertEqual(provider["observed_tank_count"], 2)
        self.assertEqual(len(provider["aliases"]), 3)
        self.assertEqual(provider["latest_observed_date"], "2025-02-10")

        labs = _laboratory_profiles(rows)
        self.assertEqual(len(labs), 2)

    def test_property_profile_exposes_latest_observed_provider_and_violation(self) -> None:
        inspections = [
            normalize_tank_inspection(
                {
                    "bin": "10",
                    "borough": "BRONX",
                    "block": "100",
                    "lot": "1",
                    "reporting_year": "2024",
                    "tank_num": "1",
                    "inspection_by_firm": "Old Tank Co",
                    "inspection_date": "05/01/2024",
                }
            ),
            normalize_tank_inspection(
                {
                    "bin": "10",
                    "borough": "BRONX",
                    "block": "100",
                    "lot": "1",
                    "reporting_year": "2025",
                    "tank_num": "1",
                    "inspection_by_firm": "New Tank Co",
                    "inspection_date": "05/01/2025",
                }
            ),
        ]
        compliance = [
            normalize_compliance_activity(
                {
                    "bin": "10",
                    "borough": "BRONX",
                    "activity_type": "Inspection",
                    "activity_year": "2025",
                    "violation_code": "DWT01",
                    "violation_text": "Example",
                    "date_of_occurrence": "2025-06-01T00:00:00.000",
                    "summons_number": "123",
                }
            )
        ]
        profile = _property_profiles(inspections, compliance)[0]
        self.assertEqual(profile["current_observed_provider_raw"], "New Tank Co")
        self.assertEqual(profile["latest_inspection_date"], "2025-05-01")
        self.assertEqual(profile["violation_count"], 1)
        self.assertEqual(profile["latest_violation_date"], "2025-06-01")

    def test_dec_7g_records_are_qualification_evidence_not_assignments(self) -> None:
        business = normalize_dec_business(
            {
                "business_agency_name": "Example Water LLC",
                "registration_number": "1234",
                "pesticide_category_code": "7g",
                "pesticide_category_desc": "Cooling Towers",
                "registration_expiration_date": "2027-01-01T00:00:00.000",
            }
        )
        applicator = normalize_dec_applicator(
            {
                "cert_number": "C2123456",
                "first_name": "Alex",
                "last_name": "Smith",
                "applicator_type": "Certified Commercial Pesticide Applicator",
                "category": "7g",
                "category_description": "Cooling Towers",
                "expiration_date": "2027-01-01T00:00:00.000",
            }
        )
        self.assertEqual(business["relationship_evidence"], "QUALIFIED_PROVIDER")
        self.assertEqual(applicator["relationship_evidence"], "QUALIFIED_PROVIDER")
        self.assertNotIn("building_key", business)
        self.assertNotIn("building_key", applicator)


if __name__ == "__main__":
    unittest.main()
