import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECONCILIATION = ROOT / "data/toronto/market/current/reconciliation_details.json"

class TorontoIdentityExceptionTests(unittest.TestCase):
    def test_current_unresolved_identity_contract(self):
        payload = json.loads(RECONCILIATION.read_text(encoding="utf-8"))
        records = {row.get("property_key"): row for row in payload.get("records", []) if isinstance(row, dict)}
        expected = {
            "toronto-geoid:8127974": ("89 HUMBER COLLEGE BLVD", "NO_CURRENT_ADDRESS_POINT_MATCH"),
            "toronto-geoid:12763885": ("90-94 ADELAIDE ST W", "MULTI_ADDRESS_RANGE_REVIEW_REQUIRED"),
        }
        for key, (address, status) in expected.items():
            self.assertIn(key, records)
            row = records[key]
            self.assertEqual(address, row.get("input_address"))
            self.assertEqual(status, row.get("resolution_status"))
            self.assertFalse(row.get("resolved"))
            self.assertFalse(row.get("candidate_address_point_ids") or [])
        unresolved = {key for key, row in records.items() if row.get("resolved") is False}
        self.assertEqual(set(expected), unresolved)

if __name__ == "__main__":
    unittest.main()
