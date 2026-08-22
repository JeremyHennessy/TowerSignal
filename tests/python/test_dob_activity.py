import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.dob_activity import normalize_dob_job, summarize_dob_activity


class DobActivityTests(unittest.TestCase):
    def test_explicit_cooling_tower_description_is_distinguished_from_mechanical_context(self):
        record = normalize_dob_job({
            "job_filing_number": "M12345678-I1",
            "bbl": "1002360038",
            "filing_status": "Approved",
            "job_type": "Alteration",
            "job_description": "Replace two existing cooling towers and associated piping.",
            "mechanical_systems_work_type_": "YES",
            "boiler_equipment_work_type_": "NO",
            "filing_date": "2026-01-12T00:00:00.000",
            "current_status_date": "2026-08-20T09:30:00.000",
            "initial_cost": "$1,250,000",
            "owner_s_business_name": "Example Owner LLC",
            "applicant_business_name": "Example Engineering PC",
        })
        self.assertEqual(record["bbl"], "1002360038")
        self.assertTrue(record["explicit_cooling_tower_mention"])
        self.assertTrue(record["mechanical_systems"])
        self.assertEqual(record["commercial_relevance"], "COOLING_TOWER_EXPLICIT")
        self.assertEqual(record["activity_date"], "2026-08-20")
        self.assertEqual(record["initial_cost"], 1250000.0)

    def test_mechanical_flag_does_not_become_explicit_cooling_tower_claim(self):
        record = normalize_dob_job({
            "job_filing_number": "M12345679-I1",
            "bbl": "1002360038",
            "job_description": "Modify HVAC distribution and controls.",
            "mechanical_systems_work_type_": "YES",
            "boiler_equipment_work_type_": "NO",
            "filing_date": "2026-06-01T00:00:00.000",
        })
        self.assertFalse(record["explicit_cooling_tower_mention"])
        self.assertEqual(record["commercial_relevance"], "MECHANICAL_OR_BOILER")

    def test_general_project_remains_property_context_only(self):
        record = normalize_dob_job({
            "job_filing_number": "M12345680-I1",
            "bbl": "1002360038",
            "job_description": "Interior partition modifications.",
            "mechanical_systems_work_type_": "NO",
            "boiler_equipment_work_type_": "NO",
            "filing_date": "2025-01-01T00:00:00.000",
        })
        self.assertEqual(record["commercial_relevance"], "PROPERTY_PROJECT")

    def test_activity_date_uses_latest_available_lifecycle_date(self):
        record = normalize_dob_job({
            "job_filing_number": "M12345681-I1",
            "bbl": "1002360038",
            "filing_date": "2022-03-31T00:00:00.000",
            "first_permit_date": "2022-06-01T00:00:00.000",
            "approved_date": "2022-05-01T00:00:00.000",
            "current_status_date": "2026-08-21T04:31:00.000",
            "signoff_date": None,
        })
        self.assertEqual(record["activity_date"], "2026-08-21")

    def test_summary_counts_recent_and_relevance_without_scoring(self):
        records = [
            normalize_dob_job({
                "job_filing_number": "A",
                "bbl": "1002360038",
                "job_description": "Cooling tower replacement.",
                "mechanical_systems_work_type_": "YES",
                "current_status_date": "2026-08-20T00:00:00.000",
            }),
            normalize_dob_job({
                "job_filing_number": "B",
                "bbl": "1002360038",
                "job_description": "Boiler replacement.",
                "boiler_equipment_work_type_": "YES",
                "current_status_date": "2025-01-01T00:00:00.000",
            }),
            normalize_dob_job({
                "job_filing_number": "C",
                "bbl": "1002360038",
                "job_description": "Interior work.",
            }),
        ]
        summary = summarize_dob_activity(records, date(2026, 8, 22))
        self.assertEqual(summary["activity_count"], 3)
        self.assertEqual(summary["recent_activity_count"], 1)
        self.assertEqual(summary["explicit_cooling_tower_count"], 1)
        self.assertEqual(summary["mechanical_or_boiler_count"], 2)
        self.assertEqual(summary["latest_activity_date"], "2026-08-20")
        self.assertEqual(summary["recent_window_days"], 365)


if __name__ == "__main__":
    unittest.main()
