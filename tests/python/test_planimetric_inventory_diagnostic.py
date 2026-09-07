from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from diagnose_planimetric_inventory import build_diagnostic  # noqa: E402
from towersignal.fetch import SourceFetchError  # noqa: E402


class PlanimetricInventoryDiagnosticTests(unittest.TestCase):
    def source(self, dataset_id: str) -> dict:
        return {
            "dataset_id": dataset_id,
            "name": dataset_id,
            "url": f"https://example.test/{dataset_id}",
            "source_record_count": 10,
            "source_last_updated_at": "2026-09-01T00:00:00Z",
            "retrieved_at": "2026-09-07T00:00:00Z",
        }

    def test_exact_bin_reconciliation_reports_both_mismatch_directions(self):
        systems = [
            {"system_id": "CT-1", "bin": "1000001"},
            {"system_id": "CT-2", "bin": "1000001"},
            {"system_id": "CT-3", "bin": "2000002"},
            {"system_id": "CT-4", "bin": None},
        ]
        physical = [
            {"globalid": "g-1", "bin": "1000001", "sub_featur": "212000", "status": "Unchanged"},
            {"globalid": "g-2", "bin": "1000001", "sub_featur": "212010", "status": "Unchanged"},
            {"globalid": "g-3", "bin": "3000003", "sub_featur": "212000", "status": "Unchanged"},
            {"globalid": "g-4", "bin": "0", "sub_featur": "212000", "status": "Unchanged"},
        ]

        report = build_diagnostic(
            systems,
            physical,
            registration_source=self.source("y4fw-iqfr"),
            planimetric_source=self.source("x748-37q7"),
        )
        summary = report["summary"]
        self.assertEqual(summary["regulatory_system_count"], 4)
        self.assertEqual(summary["regulatory_systems_without_valid_bin"], 1)
        self.assertEqual(summary["regulatory_unique_bin_count"], 2)
        self.assertEqual(summary["physical_feature_count"], 4)
        self.assertEqual(summary["physical_features_without_valid_bin"], 1)
        self.assertEqual(summary["physical_unique_bin_count"], 2)
        self.assertEqual(summary["matched_exact_bin_count"], 1)
        self.assertEqual(summary["matched_regulatory_system_count"], 2)
        self.assertEqual(summary["matched_physical_feature_count"], 2)
        self.assertEqual(summary["regulatory_bins_without_physical_match"], 1)
        self.assertEqual(summary["regulatory_systems_without_physical_match"], 1)
        self.assertEqual(summary["physical_bins_without_regulatory_match"], 1)
        self.assertEqual(summary["physical_features_without_regulatory_match"], 1)
        self.assertEqual(summary["physical_bins_with_multiple_features"], 1)

        self.assertEqual(report["borough_breakdown"]["matched_bins"], {"Manhattan": 1})
        self.assertEqual(report["borough_breakdown"]["regulatory_only_bins"], {"Bronx": 1})
        self.assertEqual(report["borough_breakdown"]["physical_only_bins"], {"Brooklyn": 1})
        self.assertEqual(report["mismatch_examples"]["regulatory_only_bins"], ["2000002"])
        self.assertEqual(report["mismatch_examples"]["physical_only_bins"], ["3000003"])
        self.assertNotIn("0", report["mismatch_examples"]["physical_only_bins"])

    def test_diagnostic_preserves_non_scoring_evidence_boundaries(self):
        report = build_diagnostic(
            [{"system_id": "CT-1", "bin": "1000001"}],
            [{"globalid": "g-1", "bin": "1000001", "sub_featur": "212000", "status": "Unchanged"}],
            registration_source=self.source("y4fw-iqfr"),
            planimetric_source=self.source("x748-37q7"),
        )
        contract = report["identity_contract"]
        recommendation = report["recommendation"]
        self.assertEqual(contract["property_reconciliation_key"], "BIN_EXACT")
        self.assertFalse(contract["address_matching_used"])
        self.assertFalse(contract["fuzzy_matching_used"])
        self.assertFalse(recommendation["priority_score_change"])
        self.assertFalse(recommendation["production_ui_change"])
        self.assertFalse(recommendation["durable_history_change"])
        boundaries = " ".join(report["evidence_boundaries"]).lower()
        self.assertIn("not evidence of an illegal", boundaries)
        self.assertIn("not evidence that the tower does not physically exist", boundaries)
        self.assertIn("2022", boundaries)

    def test_duplicate_physical_global_id_fails_closed(self):
        with self.assertRaises(SourceFetchError):
            build_diagnostic(
                [{"system_id": "CT-1", "bin": "1000001"}],
                [
                    {"globalid": "g-1", "bin": "1000001", "sub_featur": "212000", "status": "Unchanged"},
                    {"globalid": "g-1", "bin": "3000003", "sub_featur": "212000", "status": "Unchanged"},
                ],
                registration_source=self.source("y4fw-iqfr"),
                planimetric_source=self.source("x748-37q7"),
            )


if __name__ == "__main__":
    unittest.main()
