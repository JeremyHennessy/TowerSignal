import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.known_firms import build_known_firms


class KnownFirmsTests(unittest.TestCase):
    def fixtures(self):
        systems = {
            "metadata": {"generated_at": "2026-09-09T12:00:00Z"},
            "systems": [
                {
                    "system_id": "sys-1", "bin": "1000001", "bbl": "1000010001",
                    "address": "10 Main St", "borough": "Manhattan", "zip": "10001",
                    "latitude": 40.75, "longitude": -73.99,
                },
                {
                    "system_id": "sys-2", "bin": "1000001", "bbl": "1000010001",
                    "address": "10 Main St", "borough": "Manhattan", "zip": "10001",
                    "latitude": 40.7501, "longitude": -73.9901,
                },
                {
                    "system_id": "sys-3", "bin": "2000001", "bbl": "3000010001",
                    "address": "20 Water St", "borough": "Brooklyn", "zip": "11201",
                    "latitude": 40.69, "longitude": -73.99,
                },
            ],
        }
        companies = {
            "companies": [
                {
                    "company_id": "observed-company-alpha",
                    "canonical_name": "ALPHA WATER INC",
                    "identity_confidence": "STRONG",
                    "cross_source_resolution_method": "STRICT_VENDOR_KEY",
                    "aliases": [{"name": "Alpha Water, Inc.", "observation_count": 2}],
                    "observed_sources": ["NYC_CHECKBOOK_CITYWIDE"],
                    "observed_buyers": [{"buyer_name": "DCAS", "contract_count": 2}],
                    "service_categories": ["WATER_TREATMENT"],
                    "procurement_ids": ["p1", "p2"],
                    "metrics": {
                        "procurement_observation_count": 2,
                        "observed_contract_count": 2,
                        "active_contract_count": 1,
                        "observed_customer_count": 1,
                        "repeat_buyer_count": 1,
                        "observed_contract_value": 250000,
                        "first_seen": "2025-01-01",
                        "last_seen": "2026-08-01",
                    },
                    "value_semantics": "Observed public procurement values; not company revenue.",
                }
            ]
        }
        domestic = {
            "tank_inspections": [
                {
                    "inspection_id": "i1", "building_key": "NYC-BIN-1000001", "bin": "1000001", "bbl": "1000010001",
                    "address": "10 Main St", "borough": "Manhattan", "zip": "10001", "inspection_date": "2026-02-01",
                    "provider_raw": "Alpha Water, Inc.", "provider_data_quality": "VALID_NAME",
                    "lab_raw": "Alpha Water Inc", "laboratory_data_quality": "VALID_NAME",
                },
                {
                    "inspection_id": "i2", "building_key": "NYC-BIN-1000001", "bin": "1000001", "bbl": "1000010001",
                    "address": "10 Main St", "borough": "Manhattan", "zip": "10001", "inspection_date": "2026-07-01",
                    "provider_raw": "Alpha Water Inc", "provider_data_quality": "VALID_NAME",
                    "lab_raw": None, "laboratory_data_quality": "MISSING",
                },
                {
                    "inspection_id": "i3", "building_key": "NYC-BIN-2000001", "bin": "2000001", "bbl": "3000010001",
                    "address": "20 Water St", "borough": "Brooklyn", "zip": "11201", "inspection_date": "2026-06-15",
                    "provider_raw": "Beta Water LLC", "provider_data_quality": "VALID_NAME",
                    "lab_raw": None, "laboratory_data_quality": "MISSING",
                },
                {
                    "inspection_id": "i4", "building_key": "NYC-BIN-2000001", "bin": "2000001", "bbl": "3000010001",
                    "address": "20 Water St", "borough": "Brooklyn", "zip": "11201", "inspection_date": "2026-06-16",
                    "provider_raw": "Beta Water Inc", "provider_data_quality": "VALID_NAME",
                    "lab_raw": None, "laboratory_data_quality": "MISSING",
                },
            ],
            "dec_7g_businesses": [
                {
                    "qualification_id": "q1", "provider_name": "Beta Water LLC", "registration_number": "R-1",
                    "registration_effective_date": "2025-01-01", "registration_expiration_date": "2027-01-01",
                    "qualification_scope": "NYS DEC Category 7G Cooling Towers", "relationship_evidence": "QUALIFIED_PROVIDER",
                }
            ],
        }
        procurement = {
            "contracts": [
                {
                    "procurement_id": "p1", "source": "NYC_CHECKBOOK_CITYWIDE", "vendor_raw": "Alpha Water Inc",
                    "tower_account_system_ids": ["sys-1", "sys-2"], "tower_link_confidence": "CONFIRMED",
                    "award_date": "2026-01-15",
                }
            ]
        }
        shared_dob = {
            "job_filing_number": "DOB-1", "bbl": "1000010001", "activity_date": "2026-03-01",
            "applicant_business_name": "Engineering Group LLC", "owner_business_name": "Alpha Water, Inc.",
        }
        details = {
            "sys-1": {"dob_activity_history": [shared_dob], "legacy_dob_project_context": None},
            "sys-2": {"dob_activity_history": [shared_dob], "legacy_dob_project_context": None},
            "sys-3": {
                "dob_activity_history": [],
                "legacy_dob_project_context": None,
                "nyc_building_water_signals": {
                    "dob_water_permits": [
                        {
                            "activity_id": "water-permit-1",
                            "source_record_id": "DOB-WATER-1",
                            "job_filing_number": "B001",
                            "issued_date": "2026-04-15",
                            "approved_date": "2026-04-01",
                            "bbl": "3000010001",
                            "bin": "2000001",
                            "applicant_business_raw": "G.C. Environmental, Inc",
                        }
                    ]
                },
            },
        }
        return systems, companies, domestic, procurement, details

    def test_exact_procurement_alias_reuses_company_and_service_site_is_building_unique(self):
        systems, companies, domestic, procurement, details = self.fixtures()
        payload, firm_details = build_known_firms(
            systems_payload=systems,
            companies_payload=companies,
            domestic_payload=domestic,
            procurement_payloads=[procurement],
            details_by_system=details,
            generated_at="2026-09-09T12:00:00Z",
        )
        alpha = next(row for row in payload["firms"] if row["firm_id"] == "observed-company-alpha")
        self.assertEqual(alpha["serviced_site_count"], 1)
        self.assertEqual(alpha["contracted_site_count"], 1)
        self.assertEqual(alpha["tower_account_count"], 2)
        self.assertIn("DWT_INSPECTION_PROVIDER", alpha["roles"])
        self.assertIn("DWT_LABORATORY", alpha["roles"])
        self.assertIn("DOB_NOW_OWNER_BUSINESS", alpha["roles"])
        site = firm_details[alpha["firm_id"]]["site_relationships"][0]
        self.assertTrue(site["serviced"])
        self.assertTrue(site["contracted"])
        self.assertEqual(site["system_ids"], ["sys-1", "sys-2"])
        self.assertIn("DWT_INSPECTION_BY_FIRM_OBSERVED_SERVICE", site["evidence_classes"])
        self.assertIn("PROCUREMENT_TOWER_LINK_CONFIRMED", site["evidence_classes"])

    def test_project_role_does_not_inflate_serviced_site_count_and_duplicate_system_attachment_is_deduped(self):
        systems, companies, domestic, procurement, details = self.fixtures()
        payload, firm_details = build_known_firms(
            systems_payload=systems,
            companies_payload=companies,
            domestic_payload=domestic,
            procurement_payloads=[procurement],
            details_by_system=details,
            generated_at="2026-09-09T12:00:00Z",
        )
        engineering = next(row for row in payload["firms"] if row["canonical_name"] == "Engineering Group LLC")
        self.assertEqual(engineering["serviced_site_count"], 0)
        self.assertEqual(engineering["project_site_count"], 1)
        self.assertEqual(engineering["role_counts"]["DOB_NOW_APPLICANT_BUSINESS"], 1)
        detail = firm_details[engineering["firm_id"]]
        self.assertEqual(len(detail["site_relationships"]), 1)
        self.assertFalse(detail["site_relationships"][0]["serviced"])
        self.assertTrue(detail["site_relationships"][0]["project_role"])

    def test_attached_building_water_permit_applicant_is_included_as_project_role(self):
        systems, companies, domestic, procurement, details = self.fixtures()
        payload, firm_details = build_known_firms(
            systems_payload=systems,
            companies_payload=companies,
            domestic_payload=domestic,
            procurement_payloads=[procurement],
            details_by_system=details,
            generated_at="2026-09-09T12:00:00Z",
        )
        gce = next(row for row in payload["firms"] if row["canonical_name"] == "G.C. Environmental, Inc")
        self.assertEqual(gce["serviced_site_count"], 0)
        self.assertEqual(gce["project_site_count"], 1)
        self.assertEqual(gce["role_counts"]["DOB_NOW_APPLICANT_BUSINESS"], 1)
        self.assertIn("NYC_DOB_NOW_WATER_PERMITS", gce["source_classes"])
        site = firm_details[gce["firm_id"]]["site_relationships"][0]
        self.assertEqual(site["site_id"], "NYC-BIN-2000001")
        self.assertTrue(site["project_role"])
        self.assertFalse(site["serviced"])
        self.assertIn("DOB_NOW_APPLICANT_BUSINESS_BBL_EXACT", site["evidence_classes"])


    def test_legal_suffix_variants_remain_separate_known_firms(self):
        systems, companies, domestic, procurement, details = self.fixtures()
        payload, _ = build_known_firms(
            systems_payload=systems,
            companies_payload=companies,
            domestic_payload=domestic,
            procurement_payloads=[procurement],
            details_by_system=details,
            generated_at="2026-09-09T12:00:00Z",
        )
        beta = [row for row in payload["firms"] if row["normalized_name"] == "BETA WATER"]
        self.assertEqual(len(beta), 2)
        self.assertEqual({row["strict_name"] for row in beta}, {"BETA WATER LLC", "BETA WATER INC"})
        beta_llc = next(row for row in beta if row["strict_name"] == "BETA WATER LLC")
        self.assertEqual(beta_llc["qualification_count"], 1)
        self.assertEqual(beta_llc["serviced_site_count"], 1)

    def test_summary_distinguishes_unique_sites_from_firm_site_relationships(self):
        systems, companies, domestic, procurement, details = self.fixtures()
        payload, _ = build_known_firms(
            systems_payload=systems,
            companies_payload=companies,
            domestic_payload=domestic,
            procurement_payloads=[procurement],
            details_by_system=details,
            generated_at="2026-09-09T12:00:00Z",
        )
        summary = payload["summary"]
        self.assertEqual(summary["unique_serviced_site_count"], 2)
        self.assertGreater(summary["firm_serviced_site_relationship_count"], summary["unique_serviced_site_count"])
        self.assertGreaterEqual(summary["firms_with_dwt_service_evidence"], 3)


    def test_placeholder_bin_falls_back_to_valid_bbl_without_linking_unrelated_systems(self):
        systems = {
            "metadata": {"generated_at": "2026-09-09T12:00:00Z"},
            "systems": [
                {
                    "system_id": "sys-a", "bin": None, "bbl": "1005977503",
                    "address": "110 Charlton Street", "borough": "Manhattan", "zip": "10014",
                    "latitude": 40.727, "longitude": -74.007,
                },
                {
                    "system_id": "sys-b", "bin": None, "bbl": "1007290060",
                    "address": "395 9th Avenue", "borough": "Manhattan", "zip": "10001",
                    "latitude": 40.752, "longitude": -73.997,
                },
            ],
        }
        domestic = {
            "tank_inspections": [
                {
                    "inspection_id": "bad-bin-a", "building_key": "NYC-BIN-1000000",
                    "bin": "1000000", "bbl": "1005977503",
                    "address": "110 Charlton Street", "borough": "Manhattan", "zip": "10014",
                    "inspection_date": "2026-01-01",
                    "provider_raw": "EMSL Analytical", "provider_data_quality": "VALID_NAME",
                    "lab_raw": None, "laboratory_data_quality": "MISSING",
                },
                {
                    "inspection_id": "bad-bin-b", "building_key": "NYC-BIN-1000000",
                    "bin": "1000000", "bbl": "1007290060",
                    "address": "395 9th Avenue", "borough": "Manhattan", "zip": "10001",
                    "inspection_date": "2026-02-01",
                    "provider_raw": "EMSL Analytical", "provider_data_quality": "VALID_NAME",
                    "lab_raw": None, "laboratory_data_quality": "MISSING",
                },
            ],
            "dec_7g_businesses": [],
        }
        payload, firm_details = build_known_firms(
            systems_payload=systems,
            companies_payload={"companies": []},
            domestic_payload=domestic,
            procurement_payloads=[],
            details_by_system={},
            generated_at="2026-09-09T12:00:00Z",
        )
        emsl = next(row for row in payload["firms"] if row["canonical_name"] == "EMSL Analytical")
        sites = firm_details[emsl["firm_id"]]["site_relationships"]
        self.assertEqual({site["site_id"] for site in sites}, {"NYC-BBL-1005977503", "NYC-BBL-1007290060"})
        self.assertTrue(all(site["bin"] is None for site in sites))
        self.assertEqual({site["bbl"] for site in sites}, {"1005977503", "1007290060"})
        self.assertEqual({tuple(site["system_ids"]) for site in sites}, {("sys-a",), ("sys-b",)})


if __name__ == "__main__":
    unittest.main()
