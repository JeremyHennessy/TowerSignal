from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts.attach_legacy_dob_project_context import attach
from scripts.build_legacy_dob_project_cache import normalize_job


class LegacyDobProjectCacheTests(unittest.TestCase):
    def base_row(self, **overrides):
        row = {
            "job_s1_no": "300000000",
            "job__": "123456789",
            "doc__": "01",
            "borough": "BROOKLYN",
            "block": "00001",
            "lot": "00001",
            "bin__": "3000001",
            "job_type": "A2",
            "job_status": "X",
            "job_status_descrp": "SIGNED OFF",
            "latest_action_date": "09/01/2026",
            "mechanical": "X",
            "plumbing": "",
            "boiler": "",
            "equipment": "",
            "other": "",
            "other_description": "",
            "job_description": "Mechanical work",
            "applicant_s_first_name": "Jane",
            "applicant_s_last_name": "Engineer",
            "applicant_professional_title": "PE",
            "applicant_license__": "12345",
            "owner_s_business_name": "OWNER LLC",
            "pre__filing_date": "08/01/2026",
            "approved": "08/15/2026",
            "fully_permitted": "08/20/2026",
            "signoff_date": "",
            "initial_cost": "$10000",
        }
        row.update(overrides)
        return row

    def test_old_explicit_cooling_tower_record_is_retained(self):
        record = normalize_job(
            self.base_row(
                latest_action_date="01/10/2015",
                mechanical="",
                job_description="Replace existing cooling tower at roof",
            ),
            as_of=date(2026, 9, 7),
        )
        self.assertIsNotNone(record)
        self.assertTrue(record["explicit_cooling_tower_mention"])
        self.assertFalse(record["recent_relevant_project"])
        self.assertEqual(record["commercial_relevance"], "COOLING_TOWER_EXPLICIT")
        self.assertEqual(record["bbl"], "3000010001")
        self.assertEqual(record["match_basis"], "BOROUGH_BLOCK_LOT_TO_BBL_EXACT")

    def test_recent_mechanical_record_is_retained_without_cooling_tower_claim(self):
        record = normalize_job(self.base_row(), as_of=date(2026, 9, 7))
        self.assertIsNotNone(record)
        self.assertFalse(record["explicit_cooling_tower_mention"])
        self.assertTrue(record["recent_relevant_project"])
        self.assertEqual(record["commercial_relevance"], "RECENT_MECHANICAL_BOILER_PLUMBING_OR_EQUIPMENT")

    def test_old_generic_property_record_is_not_retained(self):
        record = normalize_job(
            self.base_row(
                latest_action_date="01/10/2015",
                mechanical="",
                job_description="Interior renovation",
            ),
            as_of=date(2026, 9, 7),
        )
        self.assertIsNone(record)

    def test_attach_preserves_priority_and_adds_exact_bbl_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            detail_dir = output / "details" / "20"
            detail_dir.mkdir(parents=True)
            systems = {
                "metadata": {"sources": []},
                "summary": {"registered_systems": 1},
                "systems": [{
                    "system_id": "200001",
                    "bbl": "3000010001",
                    "priority_score": 77,
                }],
            }
            (output / "systems.json").write_text(json.dumps(systems), encoding="utf-8")
            (output / "metadata.json").write_text(json.dumps(systems["metadata"]), encoding="utf-8")
            (detail_dir / "200001.json").write_text(json.dumps({"identity": {"system_id": "200001", "bbl": "3000010001"}}), encoding="utf-8")
            record = normalize_job(self.base_row(), as_of=date(2026, 9, 7))
            cache = {
                "domain": "NYC_LEGACY_DOB_PROJECT_CONTEXT",
                "generated_at": "2026-09-07T17:00:00Z",
                "as_of": "2026-09-07",
                "source": {
                    "dataset_id": "ic3t-wcy2",
                    "name": "DOB Job Application Filings",
                    "source_record_count": 2700000,
                    "source_last_updated_at": "2026-09-04T20:00:00Z",
                    "url": "https://data.cityofnewyork.us/",
                    "requested_bbl_count": 1,
                    "source_matched_bbl_count": 1,
                    "exact_bbl_job_count": 25,
                },
                "summary": {
                    "retained_bbl_count": 1,
                    "retained_record_count": 1,
                },
                "evidence_semantics": {"scoring": "unchanged"},
                "by_bbl": {
                    "3000010001": {
                        "summary": {
                            "record_count": 1,
                            "explicit_cooling_tower_count": 0,
                            "recent_relevant_project_count": 1,
                            "latest_activity_date": "2026-09-01",
                        },
                        "records": [record],
                    }
                },
            }
            cache_path = output / "legacy-dob-projects.json"
            cache_path.write_text(json.dumps(cache), encoding="utf-8")
            result = attach(output, cache_path)
            updated = json.loads((output / "systems.json").read_text(encoding="utf-8"))
            detail = json.loads((detail_dir / "200001.json").read_text(encoding="utf-8"))
            self.assertEqual(updated["systems"][0]["priority_score"], 77)
            self.assertEqual(updated["systems"][0]["legacy_dob_project_record_count"], 1)
            self.assertEqual(result["attached_systems"], 1)
            self.assertEqual(detail["legacy_dob_project_context"]["records"][0]["applicant_name"], "Jane Engineer")
            self.assertEqual(detail["legacy_dob_project_context"]["records"][0]["relationship_boundary"], "RECORDED_DOB_APPLICANT_NOT_PROOF_OF_SERVICE_CONTRACT")


if __name__ == "__main__":
    unittest.main()
