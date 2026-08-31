import json
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HISTORY = ROOT / "data/toronto/warehouse/current/open_licensed/chemtrac_history.json"
CURRENT = ROOT / "data/toronto/warehouse/current/open_licensed/chemtrac_2024.json"

def load_rows(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload, [row for row in payload.get("rows", []) if isinstance(row, dict)]

def clean(value):
    if value is None:
        return ""
    return str(value).strip()

def address(row):
    return clean(row.get("FA_ADDRESS_GIVEN") or row.get("FACILITY_ADDRESS") or row.get("ADDRESS")).upper()

class TorontoChemtracRegressionTests(unittest.TestCase):
    def test_history_has_one_source_row_per_year_and_row_id(self):
        _, rows = load_rows(HISTORY)
        keys = [(clean(row.get("_towersignal_reporting_year")), clean(row.get("_id"))) for row in rows]
        duplicates = [key for key, count in Counter(keys).items() if key != ("", "") and count > 1]
        self.assertEqual([], duplicates, f"duplicate annual ChemTRAC row identities: {duplicates[:20]}")

    def test_history_excludes_dedicated_2024_snapshot(self):
        payload, rows = load_rows(HISTORY)
        years = {clean(row.get("_towersignal_reporting_year")) for row in rows}
        self.assertNotIn("2024", years)
        excluded = payload.get("metadata", {}).get("excluded_dedicated_current_snapshot_resources") or []
        self.assertTrue(any(clean(item.get("year")) == "2024" for item in excluded))

    def test_ten_skagway_is_unique_across_history_and_current(self):
        _, historical = load_rows(HISTORY)
        _, current = load_rows(CURRENT)
        combined = []
        for row in historical:
            if "10 SKAGWAY" in address(row):
                combined.append((clean(row.get("FACILITY_ID")), clean(row.get("_towersignal_reporting_year")), clean(row.get("_id"))))
        for row in current:
            if "10 SKAGWAY" in address(row):
                combined.append((clean(row.get("FACILITY_ID")), "2024", clean(row.get("_id"))))
        self.assertGreater(len(combined), 0, "10 Skagway regression fixture disappeared")
        duplicates = [key for key, count in Counter(combined).items() if count > 1]
        self.assertEqual([], duplicates, f"10 Skagway duplicate ChemTRAC records returned: {duplicates}")

if __name__ == "__main__":
    unittest.main()
