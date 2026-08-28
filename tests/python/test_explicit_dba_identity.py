import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.company_identity import explicit_dba_aliases, source_identity_keys
from towersignal.company_intelligence import build_company_intelligence
from towersignal.deal_validation import build_deal_validation


def contract(vendor, *, procurement_id="p1", buyer="Governors Island Corporation", category="WATER_TREATMENT"):
    return {
        "procurement_id": procurement_id,
        "source": "NYS_ABO_LOCAL_DEVELOPMENT_CORPORATIONS",
        "vendor_raw": vendor,
        "buyer_name": buyer,
        "agency": buyer,
        "service_category": category,
        "current_amount": 20330.49,
        "spend_to_date": 20330.49,
        "start_date": "2023-08-02",
        "end_date": "2024-08-02",
        "award_date": "2023-08-02",
        "retrieved_at": "2026-08-28T00:00:00Z",
    }


def tower_water_cohort():
    return {
        "curated_as_of": "2026-08-28",
        "validation_gate": {"min_observed_outcome_targets": 2, "min_screened_outcome_targets": 1},
        "screen_experiment": {"anchor_target_id": "tower", "cutoff_date": "2024-11-01"},
        "targets": [
            {
                "id": "tower",
                "canonical_name": "Tower Water",
                "aliases": ["TOWER WATER", "TOWER CLEANING PLUS INC"],
                "outcome_date": "2026-06-10",
                "acquirer": "Sylmar Group",
                "outcome_type": "PLATFORM_ADD_ON_ACQUISITION",
                "primary_source_url": "https://example.test/tower-water",
                "source_scope_relation": "NYC_CORE",
            }
        ],
    }


class ExplicitDbaIdentityTests(unittest.TestCase):
    def test_parser_accepts_only_explicit_dba_syntax(self):
        self.assertEqual(
            explicit_dba_aliases("Tower Cleaning Plus D/B/A Tower Water"),
            ("Tower Cleaning Plus", "Tower Water"),
        )
        self.assertEqual(
            explicit_dba_aliases("Tower Cleaning Plus D/B/A/ Tower Water"),
            ("Tower Cleaning Plus", "Tower Water"),
        )
        self.assertEqual(
            explicit_dba_aliases("Tower Cleaning Plus dba Tower Water"),
            ("Tower Cleaning Plus", "Tower Water"),
        )
        self.assertEqual(explicit_dba_aliases("Tower Water Solutions Inc"), ())
        self.assertEqual(explicit_dba_aliases("Tower Cleaning Plus / Tower Water"), ())

    def test_source_identity_keys_preserve_full_label_and_declared_components(self):
        keys = source_identity_keys("Tower Cleaning Plus D/B/A Tower Water")
        self.assertIn("TOWER CLEANING PLUS D B A TOWER WATER", keys)
        self.assertIn("TOWER CLEANING PLUS", keys)
        self.assertIn("TOWER WATER", keys)
        self.assertNotIn("TOWER WATER SOLUTIONS", keys)

    def test_company_intelligence_exposes_dba_components_without_merging_raw_company(self):
        payload = build_company_intelligence(
            [contract("Tower Cleaning Plus D/B/A Tower Water")],
            generated_at="2026-08-28T00:00:00Z",
            as_of=date(2026, 8, 28),
        )
        self.assertEqual(payload["summary"]["observed_vendor_company_count"], 1)
        self.assertEqual(payload["summary"]["explicit_dba_alias_count"], 2)
        company = payload["companies"][0]
        self.assertEqual(company["strict_vendor_key"], "TOWER CLEANING PLUS D B A TOWER WATER")
        aliases = {row["alias"]: row for row in company["aliases"]}
        self.assertIn("Tower Cleaning Plus D/B/A Tower Water", aliases)
        self.assertIn("Tower Cleaning Plus", aliases)
        self.assertIn("Tower Water", aliases)
        self.assertEqual(aliases["Tower Water"]["confidence"], "CONFIRMED")
        self.assertEqual(aliases["Tower Water"]["resolution_method"], "EXPLICIT_SOURCE_DBA_ALIAS")
        self.assertIsNone(company["current_parent_company_id"])
        self.assertIsNone(company["current_sponsor_company_id"])

    def test_deal_validation_recognizes_exact_declared_dba_alias_without_fuzzy_matching(self):
        report = build_deal_validation(
            [contract("Tower Cleaning Plus D/B/A Tower Water")],
            tower_water_cohort(),
            generated_at="2026-08-28T00:00:00Z",
        )
        target = report["targets"][0]
        self.assertEqual(target["coverage_status"], "OBSERVED_IN_CURRENT_SOURCES")
        self.assertEqual(target["matched_alias_keys"], ["TOWER WATER"])
        self.assertEqual(target["identity_match_methods"], ["EXPLICIT_SOURCE_DBA_ALIAS"])
        self.assertEqual(target["matched_source_vendor_labels"], ["Tower Cleaning Plus D/B/A Tower Water"])
        self.assertEqual(target["exact_source_observation_count"], 1)
        self.assertEqual(target["public_buyer_count"], 1)
        self.assertFalse(target["relationship_density_screen_pass"])
        self.assertFalse(report["validation_gate"]["passed"])
        self.assertFalse(report["validation_gate"]["opportunity_score_2_allowed"])

    def test_similar_vendor_without_explicit_dba_does_not_match(self):
        report = build_deal_validation(
            [contract("Tower Water Solutions Inc")],
            tower_water_cohort(),
            generated_at="2026-08-28T00:00:00Z",
        )
        target = report["targets"][0]
        self.assertEqual(target["coverage_status"], "IN_MARKET_NOT_OBSERVED")
        self.assertEqual(target["matched_alias_keys"], [])
        self.assertEqual(target["exact_source_observation_count"], 0)


if __name__ == "__main__":
    unittest.main()
