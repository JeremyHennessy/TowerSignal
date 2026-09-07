from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from diagnose_legacy_dob_history import (  # noqa: E402
    _exact_where,
    _source_bbl,
    build_diagnostic,
    normalize_legacy_job,
)


class LegacyDobBisDiagnosticTests(unittest.TestCase):
    def source(self, dataset_id: str) -> dict:
        return {"dataset_id": dataset_id, "source_record_count": 1, "source_last_updated_at": "2026-09-07T00:00:00Z"}

    def test_bis_five_character_lot_reconstructs_exact_bbl(self):
        row = {"borough": "MANHATTAN", "block": "00817", "lot": "00044"}
        self.assertEqual(_source_bbl(row), "1008170044")
        where = _exact_where(["1008170044"])
        self.assertEqual(where, "(borough='MANHATTAN' AND block='00817' AND lot='00044')")

    def test_invalid_or_zero_property_components_do_not_join(self):
        self.assertIsNone(_source_bbl({"borough": "MANHATTAN", "block": "00000", "lot": "00044"}))
        self.assertIsNone(_source_bbl({"borough": "MANHATTAN", "block": "00817", "lot": "00000"}))
        self.assertIsNone(_source_bbl({"borough": "UNKNOWN", "block": "00817", "lot": "00044"}))

    def test_explicit_cooling_tower_requires_source_text(self):
        explicit = normalize_legacy_job({
            "job_s1_no": "1", "borough": "MANHATTAN", "block": "00817", "lot": "00044",
            "job_description": "Replace existing cooling tower and associated piping", "mechanical": "X",
        })
        generic = normalize_legacy_job({
            "job_s1_no": "2", "borough": "MANHATTAN", "block": "00817", "lot": "00044",
            "job_description": "Replace mechanical equipment and piping", "mechanical": "X",
        })
        other = normalize_legacy_job({
            "job_s1_no": "3", "borough": "MANHATTAN", "block": "00817", "lot": "00044",
            "other_description": "COOLING TOWER SUPPORT WORK", "other": "X",
        })
        self.assertTrue(explicit["explicit_cooling_tower_mention"])
        self.assertFalse(generic["explicit_cooling_tower_mention"])
        self.assertTrue(other["explicit_cooling_tower_mention"])
        self.assertEqual(generic["commercial_relevance"], "MECHANICAL_BOILER_PLUMBING_OR_EQUIPMENT")
        self.assertEqual(explicit["relationship_boundary"], "RECORDED_DOB_APPLICANT_NOT_PROOF_OF_SERVICE_CONTRACT")

    def test_incremental_metrics_are_property_level_and_non_scoring(self):
        systems = [
            {"system_id": "CT-1", "bbl": "1008170044"},
            {"system_id": "CT-2", "bbl": "2001000001"},
            {"system_id": "CT-3", "bbl": "3002000002"},
        ]
        legacy = {
            "1008170044": [{
                "bbl": "1008170044", "activity_date": "2026-08-01", "explicit_cooling_tower_mention": True,
                "mechanical": True, "boiler": False, "plumbing": False, "equipment": False,
                "applicant_name": "TEST ENGINEER", "owner_business_name": "OWNER A",
            }],
            "2001000001": [{
                "bbl": "2001000001", "activity_date": "2025-05-01", "explicit_cooling_tower_mention": False,
                "mechanical": False, "boiler": True, "plumbing": False, "equipment": False,
                "applicant_name": "OTHER ENGINEER", "owner_business_name": "OWNER B",
            }],
        }
        dob_now = {
            "1008170044": [{"bbl": "1008170044", "activity_date": "2026-07-01", "explicit_cooling_tower_mention": True}],
            "3002000002": [{"bbl": "3002000002", "activity_date": "2026-06-01", "explicit_cooling_tower_mention": False}],
        }
        report = build_diagnostic(
            systems,
            legacy,
            dob_now,
            registration_source=self.source("y4fw-iqfr"),
            legacy_source=self.source("ic3t-wcy2"),
            dob_now_source=self.source("w9ak-ipjd"),
            as_of=date(2026, 9, 7),
        )
        summary = report["summary"]
        self.assertEqual(summary["legacy_matched_bbl_count"], 2)
        self.assertEqual(summary["dob_now_matched_bbl_count"], 2)
        self.assertEqual(summary["bbls_with_both_legacy_and_dob_now"], 1)
        self.assertEqual(summary["bbls_with_legacy_but_no_dob_now"], 1)
        self.assertEqual(summary["incremental_legacy_actionable_bbls_without_recent_dob_now"], 1)
        self.assertEqual(summary["incremental_legacy_explicit_cooling_tower_bbls_not_in_dob_now"], 0)
        self.assertFalse(report["identity_contract"]["fuzzy_matching_used"])
        self.assertFalse(report["recommendation"]["priority_score_change"])
        self.assertFalse(report["recommendation"]["production_ingestion_authorized"])


if __name__ == "__main__":
    unittest.main()
