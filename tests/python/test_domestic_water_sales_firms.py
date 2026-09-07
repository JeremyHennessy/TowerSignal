import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.domestic_water import normalize_self_report_row


class DomesticWaterSalesFirmTests(unittest.TestCase):
    def test_self_report_retains_source_named_inspection_firm_and_laboratory(self):
        record = normalize_self_report_row({
            "bin": "1089811",
            "reporting_year": "2026",
            "tank_num": "1",
            "inspection_by_firm": "Example Water Services LLC",
            "lab_name": "Example Environmental Lab",
            "inspection_date": "2026-06-15",
        })

        self.assertEqual(record["inspection_by_firm"], "Example Water Services LLC")
        self.assertEqual(record["lab_name"], "Example Environmental Lab")
        self.assertEqual(record["inspection_date"], "2026-06-15")
        self.assertEqual(record["match_basis"], "BIN_EXACT")


if __name__ == "__main__":
    unittest.main()
