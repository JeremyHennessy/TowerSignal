from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from diagnose_registration_bbl_quality import build_quality_report  # noqa: E402


class RegistrationBblQualityTests(unittest.TestCase):
    def test_reports_missing_and_cross_borough_bbls_without_repairing_them(self):
        systems = [
            {"system_id": "1", "borough": "Manhattan", "bbl": "1000010001", "bin": "1000001", "address": "1 A ST"},
            {"system_id": "2", "borough": "Brooklyn", "bbl": None, "bin": "3000001", "address": "2 B ST"},
            {"system_id": "3", "borough": "Queens", "bbl": "3000010001", "bin": "4000001", "address": "3 C ST"},
        ]
        report = build_quality_report(systems)
        self.assertEqual(report["system_count"], 3)
        self.assertEqual(report["valid_bbl_system_count"], 2)
        self.assertEqual(report["missing_or_invalid_bbl_system_count"], 1)
        self.assertEqual(report["published_borough_vs_bbl_prefix_mismatch_count"], 1)
        self.assertEqual(report["published_borough_breakdown"]["BROOKLYN"]["missing_or_invalid_bbl"], 1)
        self.assertEqual(report["published_borough_breakdown"]["QUEENS"]["published_borough_vs_bbl_prefix_mismatches"], 1)
        self.assertIn("do not authorize fuzzy property joins", report["evidence_boundary"])


if __name__ == "__main__":
    unittest.main()
