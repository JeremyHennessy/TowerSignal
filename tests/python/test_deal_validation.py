import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.deal_validation import build_deal_validation, relationship_metrics, strict_vendor_key


def contract(vendor, procurement_id, buyer, start, end, category="WATER_TREATMENT"):
    return {
        "procurement_id": procurement_id,
        "source": "NYC_CHECKBOOK_CITYWIDE",
        "vendor_raw": vendor,
        "buyer_name": buyer,
        "agency": buyer,
        "service_category": category,
        "start_date": start,
        "end_date": end,
        "current_amount": 999999999,
        "retrieved_at": "2026-08-27T00:00:00Z",
    }


def cohort():
    return {
        "curated_as_of": "2026-08-27",
        "validation_gate": {"min_observed_outcome_targets": 3, "min_screened_outcome_targets": 2},
        "screen_experiment": {"anchor_target_id": "barclay", "cutoff_date": "2024-11-01"},
        "targets": [
            {
                "id": "barclay", "canonical_name": "Barclay Water Management",
                "aliases": ["BARCLAY WATER MGMT INC"], "outcome_date": "2024-11-01",
                "acquirer": "Ecolab", "outcome_type": "STRATEGIC_ACQUISITION",
                "primary_source_url": "https://example.test/barclay", "source_scope_relation": "NYC_CORE",
            },
            {
                "id": "rmc", "canonical_name": "Rochester Midland Corporation",
                "aliases": ["RMC", "ROCHESTER MIDLAND CORPORATION"], "outcome_date": "2023-08-04",
                "acquirer": "Peak Rock", "outcome_type": "PLATFORM_ACQUISITION",
                "primary_source_url": "https://example.test/rmc", "source_scope_relation": "NEW_YORK_STATE_OUTSIDE_NYC_PROCUREMENT_SCOPE",
            },
            {
                "id": "tower", "canonical_name": "Tower Water",
                "aliases": ["TOWER WATER", "TOWER CLEANING PLUS INC"], "outcome_date": "2026-06-10",
                "acquirer": "Sylmar Group", "outcome_type": "PLATFORM_ADD_ON_ACQUISITION",
                "primary_source_url": "https://example.test/tower", "source_scope_relation": "NYC_CORE",
            },
        ],
    }


class DealValidationTests(unittest.TestCase):
    def test_exact_alias_preserves_suffix_and_does_not_fuzzy_match(self):
        self.assertEqual(strict_vendor_key("Barclay Water Mgmt, Inc."), "BARCLAY WATER MGMT INC")
        self.assertNotEqual(strict_vendor_key("Industrial Water Technologies Inc"), strict_vendor_key("Industrial Water Management Inc"))

    def test_relationship_screen_uses_relationship_density_not_money(self):
        rows = [
            contract("BARCLAY WATER MGMT INC", "p1", "Police", "2022-09-01", "2023-06-30", "COOLING_TOWER_CLEANING"),
            contract("BARCLAY WATER MGMT INC", "p2", "Police", "2023-11-02", "2024-06-30"),
            contract("BARCLAY WATER MGMT INC", "p3", "DCAS", "2022-09-01", "2022-09-30", "COOLING_TOWER_MAINTENANCE"),
        ]
        metrics = relationship_metrics(rows, cutoff=__import__("datetime").date(2024, 11, 1))
        self.assertTrue(metrics["relationship_density_screen_pass"])
        self.assertEqual(metrics["public_buyer_count"], 2)
        self.assertEqual(metrics["repeat_buyer_count"], 1)
        self.assertEqual(metrics["specialized_service_observation_count"], 3)
        self.assertNotIn("current_amount", metrics)

    def test_low_source_coverage_fails_gate_even_when_barclay_passes_screen(self):
        rows = [
            contract("BARCLAY WATER MGMT INC", "p1", "Police", "2022-09-01", "2023-06-30", "COOLING_TOWER_CLEANING"),
            contract("BARCLAY WATER MGMT INC", "p2", "Police", "2023-11-02", "2024-06-30"),
            contract("BARCLAY WATER MGMT INC", "p3", "DCAS", "2022-09-01", "2022-09-30", "COOLING_TOWER_MAINTENANCE"),
            contract("INDUSTRIAL WATER MANAGEMENT INC", "p4", "DCAS", "2024-01-01", "2025-01-01", "BOILER_WATER_TREATMENT"),
        ]
        report = build_deal_validation(rows, cohort(), generated_at="2026-08-27T00:00:00Z")
        self.assertEqual(report["summary"]["exact_observed_outcome_count"], 1)
        self.assertEqual(report["summary"]["observed_outcomes_passing_screen"], 1)
        self.assertFalse(report["validation_gate"]["passed"])
        self.assertFalse(report["validation_gate"]["opportunity_score_2_allowed"])
        self.assertFalse(report["validation_gate"]["home_deal_model_allowed"])
        self.assertEqual(report["validation_gate"]["recommended_next_step"], "EXPAND_PROCUREMENT_SOURCE_COVERAGE_BEFORE_SCORING")
        rmc = next(target for target in report["targets"] if target["id"] == "rmc")
        self.assertEqual(rmc["coverage_status"], "OUTSIDE_CURRENT_NYC_PROCUREMENT_SCOPE")
        tower = next(target for target in report["targets"] if target["id"] == "tower")
        self.assertEqual(tower["coverage_status"], "IN_MARKET_NOT_OBSERVED")

    def test_screen_comparison_is_not_labeled_non_acquired(self):
        rows = [
            contract("OTHER WATER CO INC", "p1", "Buyer A", "2023-01-01", "2025-01-01", "WATER_TREATMENT"),
            contract("OTHER WATER CO INC", "p2", "Buyer A", "2023-02-01", "2025-02-01", "WATER_TREATMENT"),
            contract("OTHER WATER CO INC", "p3", "Buyer B", "2023-03-01", "2025-03-01", "COOLING_TOWER_MAINTENANCE"),
        ]
        report = build_deal_validation(rows, cohort(), generated_at="2026-08-27T00:00:00Z")
        hit = report["screen_experiment"]["hits"][0]
        self.assertEqual(hit["classification"], "NO_CURATED_OUTCOME_COMPARISON")
        self.assertIsNone(hit["curated_acquisition_target_id"])


if __name__ == "__main__":
    unittest.main()
