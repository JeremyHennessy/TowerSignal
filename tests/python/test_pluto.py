import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.pluto import normalize_bbl, normalize_pluto_record


class PlutoNormalizationTests(unittest.TestCase):
    def test_normalize_bbl_accepts_numeric_source_identity(self):
        self.assertEqual(normalize_bbl("1001230045"), "1001230045")
        self.assertEqual(normalize_bbl("1001230045.00000000"), "1001230045")
        self.assertEqual(normalize_bbl("1.001230045E9"), "1001230045")
        self.assertEqual(normalize_bbl("1-00123-0045"), "1001230045")
        self.assertIsNone(normalize_bbl("1001230045.5"))
        self.assertIsNone(normalize_bbl(""))
        self.assertIsNone(normalize_bbl(None))

    def test_normalize_pluto_record_preserves_commercial_context(self):
        record = normalize_pluto_record({
            "bbl": "1001230045.00000000",
            "ownername": "Example Owner LLC",
            "landuse": "5",
            "bldgclass": "O4",
            "lotarea": "12000",
            "bldgarea": "98000",
            "numfloors": "12",
            "unitsres": "0",
            "unitstotal": "24",
            "yearbuilt": "1968",
            "yearalter1": "2004",
            "yearalter2": "0",
        })
        self.assertEqual(record["bbl"], "1001230045")
        self.assertEqual(record["owner_name"], "Example Owner LLC")
        self.assertEqual(record["building_area_sqft"], 98000.0)
        self.assertEqual(record["floors"], 12.0)
        self.assertEqual(record["total_units"], 24)
        self.assertEqual(record["year_built"], 1968)
        self.assertEqual(record["source"], "NYC_DCP_PLUTO")


if __name__ == "__main__":
    unittest.main()
