from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from diagnose_exact_bin_bbl_recovery import build_report, classify_recovery  # noqa: E402


class ExactBinBblRecoveryTests(unittest.TestCase):
    def system(self, **overrides):
        row = {
            "system_id": "2001",
            "borough": "Brooklyn",
            "bin": "3000001",
            "bbl": None,
            "address": "1 TEST ST",
        }
        row.update(overrides)
        return row

    def test_unique_mappluto_candidate_is_recoverable_even_when_base_differs(self):
        row = classify_recovery(
            self.system(),
            [{"base_bbl": "3000010044", "mappluto_bbl": "3000017501"}],
        )
        self.assertEqual(row["status"], "UNAMBIGUOUS_EXACT_BIN_MAPPLUTO_RECOVERY")
        self.assertEqual(row["recovery_bbl"], "3000017501")
        self.assertEqual(row["mappluto_bbl_candidates"], ["3000017501"])
        self.assertEqual(row["base_bbl_context"], ["3000010044"])

    def test_multiple_mappluto_candidates_remain_unresolved(self):
        row = classify_recovery(
            self.system(),
            [
                {"base_bbl": "3000010044", "mappluto_bbl": "3000017501"},
                {"base_bbl": "3000010045", "mappluto_bbl": "3000017502"},
            ],
        )
        self.assertEqual(row["status"], "CONFLICTING_MAPPLUTO_BBLS")
        self.assertIsNone(row["recovery_bbl"])

    def test_mappluto_cross_borough_candidate_remains_unresolved(self):
        row = classify_recovery(
            self.system(borough="Queens", bin="4000001"),
            [{"base_bbl": "4000010044", "mappluto_bbl": "3000017501"}],
        )
        self.assertEqual(row["status"], "MAPPLUTO_BOROUGH_PREFIX_CONFLICT")
        self.assertIsNone(row["recovery_bbl"])

    def test_base_only_candidate_remains_review_only(self):
        row = classify_recovery(
            self.system(),
            [{"base_bbl": "3000010044", "mappluto_bbl": None}],
        )
        self.assertEqual(row["status"], "BASE_BBL_ONLY_REVIEW")
        self.assertIsNone(row["recovery_bbl"])

    def test_report_does_not_modify_existing_valid_bbl_systems(self):
        systems = [
            self.system(system_id="missing"),
            self.system(system_id="existing", bbl="3000027501", bin="3000002"),
        ]
        report = build_report(
            systems,
            {"3000001": [{"base_bbl": "3000010044", "mappluto_bbl": "3000017501"}]},
        )
        self.assertEqual(report["missing_registry_bbl_system_count"], 1)
        self.assertEqual(report["unambiguous_exact_bin_mappluto_recovery_count"], 1)
        self.assertEqual(report["identity_contract"]["recovery_value"], "UNIQUE_PUBLISHED_BUILDING_FOOTPRINT_MAPPLUTO_BBL")
        self.assertFalse(report["identity_contract"]["fuzzy_matching_used"])
        self.assertFalse(report["recommendation"]["priority_score_change"])


if __name__ == "__main__":
    unittest.main()
