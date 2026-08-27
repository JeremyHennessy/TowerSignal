import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.company_intelligence import build_company_intelligence, strict_vendor_key


def contract(vendor, *, source="NYC_CHECKBOOK_CITYWIDE", procurement_id=None, buyer="DCAS", amount=100000, category="WATER_TREATMENT"):
    return {
        "procurement_id": procurement_id or f"p-{vendor}-{source}",
        "source": source,
        "vendor_raw": vendor,
        "buyer_name": buyer,
        "agency": buyer,
        "service_category": category,
        "current_amount": amount,
        "spend_to_date": amount / 2,
        "start_date": "2026-01-01",
        "end_date": "2027-01-01",
        "retrieved_at": "2026-08-27T00:00:00Z",
    }


class CompanyIntelligenceTests(unittest.TestCase):
    def test_strict_vendor_key_preserves_legal_suffixes(self):
        self.assertEqual(strict_vendor_key("Alpha Water LLC"), "ALPHA WATER LLC")
        self.assertEqual(strict_vendor_key("Alpha Water, Inc."), "ALPHA WATER INC")
        self.assertNotEqual(strict_vendor_key("Alpha Water LLC"), strict_vendor_key("Alpha Water Inc"))

    def test_exact_source_label_variants_collapse_without_suffix_loss(self):
        payload = build_company_intelligence([
            contract("BARCLAY WATER MGMT INC", procurement_id="p1"),
            contract("Barclay Water Mgmt, Inc.", procurement_id="p2", buyer="NYCHA", amount=200000),
        ], generated_at="2026-08-27T00:00:00Z", as_of=date(2026, 8, 27))
        self.assertEqual(payload["summary"]["observed_vendor_company_count"], 1)
        company = payload["companies"][0]
        self.assertEqual(company["identity_confidence"], "STRONG")
        self.assertEqual(company["strict_vendor_key"], "BARCLAY WATER MGMT INC")
        self.assertEqual(company["metrics"]["observed_contract_count"], 2)
        self.assertEqual(company["metrics"]["observed_customer_count"], 2)
        self.assertEqual(company["metrics"]["observed_contract_value"], 300000.0)
        self.assertIn("not company revenue", company["value_semantics"])

    def test_suffix_variants_are_review_candidates_not_silently_merged(self):
        payload = build_company_intelligence([
            contract("ALPHA WATER LLC", procurement_id="p1"),
            contract("ALPHA WATER INC", procurement_id="p2", source="NYC_CITY_RECORD"),
        ], generated_at="2026-08-27T00:00:00Z", as_of=date(2026, 8, 27))
        self.assertEqual(payload["summary"]["observed_vendor_company_count"], 2)
        self.assertEqual(payload["summary"]["companies_requiring_resolution_review"], 2)
        self.assertEqual(payload["summary"]["unresolved_observation_count"], 2)
        for company in payload["companies"]:
            self.assertEqual(company["cross_source_resolution_confidence"], "VERIFY")
            self.assertEqual(len(company["candidate_related_company_ids"]), 1)

    def test_short_generic_alias_like_rmc_is_observed_but_not_promoted_to_parent_relationship(self):
        payload = build_company_intelligence([
            contract("RMC", procurement_id="p1"),
        ], generated_at="2026-08-27T00:00:00Z", as_of=date(2026, 8, 27))
        company = payload["companies"][0]
        self.assertEqual(company["canonical_name"], "RMC")
        self.assertEqual(company["identity_scope"], "OBSERVED_PUBLIC_PROCUREMENT_VENDOR_LABEL")
        self.assertIsNone(company["current_parent_company_id"])
        self.assertIsNone(company["current_sponsor_company_id"])


if __name__ == "__main__":
    unittest.main()
