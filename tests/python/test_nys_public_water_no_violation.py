from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import build_nys_public_water_cache as build_cache  # noqa: E402


class NysPublicWaterNoViolationTests(unittest.TestCase):
    def test_explicit_no_violation_page_returns_empty_rows(self) -> None:
        html = """
        <html><h1>New York City Compliance Report 2025</h1>
        <h2>There are no violations entered in SDWIS/State for 2025</h2></html>
        """
        rows = build_cache.parse_violation_page_allow_explicit_empty(
            html,
            source_url="https://example.test/new_york_city_compliance_report.htm",
        )
        self.assertEqual(rows, [])

    def test_unexpected_missing_table_still_fails_closed(self) -> None:
        html = "<html><h1>County Compliance Report 2025</h1><p>Unexpected format</p></html>"
        with self.assertRaises(build_cache.nys_public_water.NysPublicWaterSourceError):
            build_cache.parse_violation_page_allow_explicit_empty(
                html,
                source_url="https://example.test/broken_county_compliance_report.htm",
            )

    def test_duplicate_looking_source_rows_receive_distinct_stable_ids(self) -> None:
        row = {
            "violation_id": "old-id",
            "calendar_year": 2025,
            "pws_id": "NY1400411",
            "pws_name": "ANGOLA VILLAGE",
            "system_type": "C-Community water system",
            "violation_type": "4G - LSL REPORTING-INITIAL",
            "contaminants": None,
            "months_covered": "October 2024 to August 2025",
            "status": "No longer in violation",
            "source_url": "https://example.test/erie_county_compliance_report.htm",
        }
        result = build_cache._rekey_violation_rows(
            [row, dict(row)],
            source_url="https://example.test/erie_county_compliance_report.htm",
        )
        self.assertEqual(len(result), 2)
        self.assertNotEqual(result[0]["violation_id"], result[1]["violation_id"])
        self.assertEqual(result[0]["source_row_ordinal"], 0)
        self.assertEqual(result[1]["source_row_ordinal"], 1)


if __name__ == "__main__":
    unittest.main()
