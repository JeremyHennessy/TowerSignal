from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.nyc_distribution_water import normalize_sample, parse_measurement  # noqa: E402


class NycDistributionWaterTests(unittest.TestCase):
    def test_less_than_measurement_preserves_qualifier(self) -> None:
        value = parse_measurement("<1")
        self.assertEqual(value["raw"], "<1")
        self.assertEqual(value["numeric"], 1.0)
        self.assertEqual(value["qualifier"], "LT")

    def test_non_detect_is_not_converted_to_zero(self) -> None:
        value = parse_measurement("ND")
        self.assertIsNone(value["numeric"])
        self.assertEqual(value["qualifier"], "ND")

    def test_numeric_measurement_is_exact(self) -> None:
        value = parse_measurement("0.42")
        self.assertEqual(value["numeric"], 0.42)
        self.assertEqual(value["qualifier"], "EQ")

    def test_sample_site_remains_unlinked_to_property(self) -> None:
        sample = normalize_sample({
            "sample_number": "123",
            "sample_date": "2026-08-01T00:00:00.000",
            "sample_time": "10:00 AM",
            "sample_site": "1S03",
            "sample_class": "Routine",
            "residual_free_chlorine_mg_l": "0.42",
            "turbidity_ntu": "0.08",
            "fluoride_mg_l": "0.7",
            "coliform_quanti_tray_mpn_100ml": "<1",
            "e_coli_quanti_tray_mpn_100ml": "ND",
        })
        self.assertEqual(sample["sample_date"], "2026-08-01")
        self.assertEqual(sample["sample_site"], "1S03")
        self.assertEqual(sample["property_link_confidence"], "UNLINKED_SAMPLE_SITE")
        self.assertEqual(sample["measurements"]["coliform"]["qualifier"], "LT")

    def test_missing_sample_number_fails_closed(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "sample_number"):
            normalize_sample({})


if __name__ == "__main__":
    unittest.main()
