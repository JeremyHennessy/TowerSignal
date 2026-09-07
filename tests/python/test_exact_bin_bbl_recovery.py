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

    def test_unambiguous_exact_bin_candidate_is_recoverable(self):
        row = classify_recovery(
            self.system(),
            [{"base_bbl": "3000010044", "mappluto_bbl": "3000010044"}],
        )
        self.assertEqual(row["status"], "UNAMBIGUOUS_EXACT_BIN_RECOVERY")
        self.assertEqual(row["candidate_bbls"], ["3000010044"])

    def test_conflicting_published_bbls_remain_unresolved(self):
        row = classify_recovery(
            self.system(),
            [
                {"base_bbl": "3000010044", "mappluto_bbl": "3000010044"},
                {"base_bbl": "3000010045", "mappluto_bbl": "3000010045"},
            ],
        )
        self.assertEqual(row["status"], "CONFLICTING_FOOTPRINT_BBLS")

    def test_cross_borough_candidate_remains_unresolved(self):
        row = classify_recovery(
            self.system(borough="Queens", bin="4000001"),
            [{"base_bbl": "3000010044", "mappluto_bbl": "3000010044"}],
        )
        self.assertEqual(row["status"], "BOROUGH_PREFIX_CONFLICT")

    def test_report_does_not_modify_existing_valid_bbl_systems(self):
        systems = [
            self.system(system_id="missing"),
            self.system(system_id="existing", bbl="3000020001", bin="3000002"),
        ]
        report = build_report(
            systems,
            {"3000001": [{"base_bbl": "3000010044", "mappluto_bbl": "3000010044"}]},
        )
        self.assertEqual(report["missing_registry_bbl_system_count"], 1)
        self.assertEqual(report["unambiguous_exact_bin_recovery_count"], 1)
        self.assertFalse(report["identity_contract"]["fuzzy_matching_used"])
        self.assertFalse(report["recommendation"]["priority_score_change"])


if __name__ == "__main__":
    unittest.main()
