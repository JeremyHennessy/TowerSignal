from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.domestic_water_market import normalize_dec_applicator


class DomesticWaterMarketNormalizationTests(unittest.TestCase):
    def test_dec_applicator_preserves_official_region_field(self):
        record = normalize_dec_applicator({
            "cert_number": "C1234567",
            "first_name": "Example",
            "last_name": "Applicator",
            "region": "2",
            "renewal_date": "2026-01-15",
            "expiration_date": "2027-01-15",
            "applicator_type": "Commercial",
            "category": "7G",
            "category_description": "Cooling Towers",
        })
        self.assertEqual(record["cert_number"], "C1234567")
        self.assertEqual(record["dec_region"], "2")
        self.assertEqual(record["category"], "7G")
        self.assertEqual(record["relationship_evidence"], "QUALIFIED_PROVIDER")


if __name__ == "__main__":
    unittest.main()
