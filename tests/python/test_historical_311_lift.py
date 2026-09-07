from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.historical_311_lift import period_where, summarize_lift  # noqa: E402


class Historical311LiftTests(unittest.TestCase):
    def test_period_where_is_exact_bbl_and_bounded(self) -> None:
        where = period_where(["1011210036", "3001230045"], "2020-01-01T00:00:00.000", "2025-01-01T00:00:00.000")
        self.assertIn("bbl in ('1011210036','3001230045')", where)
        self.assertIn("created_date >= '2020-01-01T00:00:00.000'", where)
        self.assertIn("created_date < '2025-01-01T00:00:00.000'", where)
        self.assertIn("agency='DEP'", where)

    def test_summarize_counts_only_building_signals(self) -> None:
        historical = [
            {"request_id": "1", "bbl": "1011210036", "created_date": "2018-01-01", "category": "BUILDING_WATER_QUALITY", "is_building_water_signal": True},
            {"request_id": "2", "bbl": "1011210036", "created_date": "2022-04-02", "category": "BUILDING_WATER_LEAK", "is_building_water_signal": True},
            {"request_id": "3", "bbl": "1011210036", "created_date": "2024-06-03", "category": "BUILDING_WATER_QUALITY", "is_building_water_signal": True},
            {"request_id": "4", "bbl": "3001230045", "created_date": "2023-01-01", "category": "HYDRANT_CONTEXT", "is_building_water_signal": False},
            {"request_id": "5", "bbl": "4009990001", "created_date": "2020-01-01", "category": "BUILDING_NO_WATER_OR_PRESSURE", "is_building_water_signal": True},
        ]
        recent = [
            {"request_id": "6", "bbl": "4009990001", "created_date": "2026-02-01", "category": "BUILDING_WATER_QUALITY", "is_building_water_signal": True},
        ]
        result = summarize_lift(
            tower_bbls=["1011210036", "3001230045", "4009990001"],
            borough_by_bbl={"1011210036": "MANHATTAN", "3001230045": "BROOKLYN", "4009990001": "QUEENS"},
            historical_rows=historical,
            recent_rows=recent,
        )
        self.assertEqual(result["tower_bbls_with_historical_building_water_signal"], 2)
        self.assertEqual(result["historical_only_tower_bbl_count"], 1)
        self.assertEqual(result["recurring_historical_only_tower_bbl_count"], 1)
        self.assertEqual(result["historical_only_with_2024_activity_count"], 1)
        self.assertEqual(result["historical_only_by_borough"], {"MANHATTAN": 1})
        self.assertFalse(result["governance"]["historical_311_authorized_for_production"])
        self.assertFalse(result["governance"]["priority_score_1_0_changed"])

    def test_recent_signal_removes_historical_only_status(self) -> None:
        row = {"request_id": "1", "bbl": "1011210036", "created_date": "2024-05-01", "category": "BUILDING_WATER_QUALITY", "is_building_water_signal": True}
        recent = {"request_id": "2", "bbl": "1011210036", "created_date": "2025-05-01", "category": "BUILDING_WATER_QUALITY", "is_building_water_signal": True}
        result = summarize_lift(
            tower_bbls=["1011210036"],
            borough_by_bbl={"1011210036": "MANHATTAN"},
            historical_rows=[row],
            recent_rows=[recent],
        )
        self.assertEqual(result["historical_only_tower_bbl_count"], 0)
        self.assertEqual(result["tower_bbls_with_2025_plus_building_water_signal"], 1)


if __name__ == "__main__":
    unittest.main()
