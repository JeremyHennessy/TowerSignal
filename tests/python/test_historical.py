from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.historical import build_historical_profile


class HistoricalProfileTests(unittest.TestCase):
    def test_builds_descriptive_history_without_compliance_inference(self) -> None:
        system = {
            "date_registered": "01/15/2020",
            "sample_dates": ["2026-05-01", "2026-05-31", "2026-07-05"],
            "sample_intervals_days": [30, 35],
        }
        inspections = [
            {"inspection_date": "2024-01-10", "violation_count": 0},
            {"inspection_date": "2025-04-12", "violation_count": 2},
            {"inspection_date": "2026-03-20", "violation_count": 1},
        ]
        oath_cases = [
            {"penalty_imposed": 1000, "paid_amount": 500, "balance_due": 500},
            {"penalty_imposed": "250", "paid_amount": "250", "balance_due": 0},
        ]

        profile = build_historical_profile(system, inspections, oath_cases, date(2026, 8, 22))

        self.assertEqual(profile["registration_date"], "2020-01-15")
        self.assertEqual(profile["first_public_evidence_date"], "2020-01-15")
        self.assertEqual(profile["sample"]["reported_sample_count"], 3)
        self.assertEqual(profile["sample"]["average_interval_days"], 32.5)
        self.assertEqual(profile["sample"]["longest_interval_days"], 35)
        self.assertEqual(profile["inspection"]["inspection_count"], 3)
        self.assertEqual(profile["inspection"]["inspections_with_violations"], 2)
        self.assertEqual(profile["inspection"]["violation_citation_count"], 3)
        self.assertEqual(profile["inspection"]["latest_violation_date"], "2026-03-20")
        self.assertEqual(profile["oath"]["penalty_imposed_total"], 1250.0)
        self.assertEqual(profile["oath"]["paid_amount_total"], 750.0)
        self.assertEqual(profile["oath"]["balance_due_total"], 500.0)

    def test_handles_missing_history(self) -> None:
        profile = build_historical_profile({}, [], [], date(2026, 8, 22))
        self.assertIsNone(profile["registration_date"])
        self.assertIsNone(profile["first_public_evidence_date"])
        self.assertEqual(profile["sample"]["reported_sample_count"], 0)
        self.assertEqual(profile["inspection"]["inspection_count"], 0)
        self.assertEqual(profile["oath"]["case_count"], 0)
        self.assertEqual(profile["oath"]["balance_due_total"], 0.0)


if __name__ == "__main__":
    unittest.main()
