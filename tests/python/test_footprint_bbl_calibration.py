from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from calibrate_footprint_bbl_semantics import build_calibration, classify_known_bbl  # noqa: E402


class FootprintBblCalibrationTests(unittest.TestCase):
    def system(self, **overrides):
        row = {
            "system_id": "1",
            "borough": "Manhattan",
            "bin": "1000001",
            "bbl": "1000010001",
        }
        row.update(overrides)
        return row

    def test_distinguishes_base_from_mappluto_agreement(self):
        row = classify_known_bbl(
            self.system(),
            [{"base_bbl": "1000010001", "mappluto_bbl": "1000017501"}],
        )
        self.assertEqual(row["status"], "REGISTRY_MATCHES_BASE_BBL_ONLY")

    def test_calibration_counts_fields_independently(self):
        systems = [
            self.system(system_id="base", bin="1000001", bbl="1000010001"),
            self.system(system_id="map", bin="1000002", bbl="1000027501"),
            self.system(system_id="both", bin="1000003", bbl="1000030001"),
        ]
        footprints = {
            "1000001": [{"base_bbl": "1000010001", "mappluto_bbl": "1000017501"}],
            "1000002": [{"base_bbl": "1000020001", "mappluto_bbl": "1000027501"}],
            "1000003": [{"base_bbl": "1000030001", "mappluto_bbl": "1000030001"}],
        }
        report = build_calibration(systems, footprints)
        self.assertEqual(report["base_bbl_matches_registry_count"], 2)
        self.assertEqual(report["mappluto_bbl_matches_registry_count"], 2)
        self.assertEqual(report["status_counts"]["REGISTRY_MATCHES_BASE_BBL_ONLY"], 1)
        self.assertEqual(report["status_counts"]["REGISTRY_MATCHES_MAPPLUTO_BBL_ONLY"], 1)
        self.assertTrue(report["decision_rule"]["does_not_modify_identity"])


if __name__ == "__main__":
    unittest.main()
