from __future__ import annotations

import csv
import io
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.openbook_water import build_export_url, parse_export  # noqa: E402
from towersignal.openbook_water_guard import classify_water_contract  # noqa: E402


class OpenBookWaterTests(unittest.TestCase):
    def _csv(self, rows: list[list[str]]) -> bytes:
        handle = io.StringIO()
        writer = csv.writer(handle)
        writer.writerows(rows)
        return handle.getvalue().encode("utf-8")

    def test_export_url_requests_official_csv(self) -> None:
        url = build_export_url(date(2026, 9, 4))
        self.assertIn("DocType=csv", url)
        self.assertIn("txtOrigFromDate=09%2F04%2F2026", url)
        self.assertIn("order=VENDOR_NAME", url)

    def test_parse_export_discovers_header_after_report_line(self) -> None:
        payload = self._csv([
            ["Open Book New York export"],
            [
                "TRANSACTION TYPE", "VENDOR NAME", "DEPARTMENT/FACILITY",
                "CONTRACT NUMBER", "TRANSACTION AMOUNT", "START DATE", "END DATE",
                "CONTRACT DESCRIPTION", "TRANSACTION APPROVED/FILED DATE",
            ],
            [
                "Original Contract", "CHEMTREAT INC", "SUNY at Stony Brook",
                "T081022", "43101", "07/01/2022", "06/30/2026",
                "COOLING TOWERS WATER TREATMENT", "08/29/2022",
            ],
        ])
        records, meta = parse_export(payload)
        self.assertEqual(meta["header_row_number"], 2)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["vendor_key"], "CHEMTREAT")
        self.assertEqual(records[0]["transaction_amount"], 43101.0)

    def test_domestic_water_terms_are_published(self) -> None:
        result = classify_water_contract("Replace domestic water tank and backflow preventer")
        self.assertIn(
            result["service_category"],
            {"DOMESTIC_WATER_TANK", "BACKFLOW_CROSS_CONNECTION"},
        )
        self.assertNotEqual(result["service_category"], "UNRELATED")

    def test_wastewater_does_not_become_domestic_water(self) -> None:
        result = classify_water_contract("Wastewater treatment plant pump replacement")
        self.assertEqual(result["service_category"], "UNRELATED")
        self.assertEqual(result["classification_layer"], "OPENBOOK_CONTEXT_GUARD")

    def test_explicit_cooling_tower_survives_unrelated_site_context(self) -> None:
        result = classify_water_contract("Cooling tower maintenance at wastewater treatment facility")
        self.assertEqual(result["service_category"], "COOLING_TOWER_MAINTENANCE")

    def test_plumbing_remains_review_level(self) -> None:
        result = classify_water_contract("Annual plumbing maintenance and repair")
        self.assertEqual(result["service_category"], "DOMESTIC_PLUMBING")
        self.assertEqual(result["confidence"], "VERIFY")


if __name__ == "__main__":
    unittest.main()
