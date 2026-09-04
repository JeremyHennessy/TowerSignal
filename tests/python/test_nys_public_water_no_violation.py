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


if __name__ == "__main__":
    unittest.main()
