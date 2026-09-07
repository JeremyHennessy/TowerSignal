from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from attach_historical_311_context import attach
from towersignal.historical_311_context import build_historical_context, period_where
from validate_historical_311_context import validate


class Historical311ContextTests(unittest.TestCase):
    def test_period_where_is_bounded_and_exact_bbl(self):
        where = period_where(["1011210036", "2020200001"], "2020-01-01T00:00:00.000", "2025-01-01T00:00:00.000")
        self.assertIn("bbl in ('1011210036','2020200001')", where)
        self.assertIn("created_date >= '2020-01-01T00:00:00.000'", where)
        self.assertIn("created_date < '2025-01-01T00:00:00.000'", where)
        self.assertIn("agency='DEP'", where)

    @patch("towersignal.historical_311_context.fetch_snapshot")
    @patch("towersignal.historical_311_context.fetch_metadata")
    def test_build_collapses_raw_rows_to_historical_profile(self, metadata_mock, snapshot_mock):
        metadata_mock.return_value = {
            "fields": ["unique_key", "created_date", "agency", "complaint_type", "descriptor", "descriptor_2", "bbl", "borough"],
            "source_last_updated_at": "2026-09-07T00:00:00Z",
        }
        snapshot_mock.side_effect = [
            SimpleNamespace(rows=[
                {"unique_key": "1", "created_date": "2018-02-01T00:00:00.000", "agency": "DEP", "complaint_type": "Water Quality", "descriptor": "Dirty Water", "descriptor_2": "", "bbl": "1011210036", "borough": "MANHATTAN"},
                {"unique_key": "2", "created_date": "2019-03-01T00:00:00.000", "agency": "DEP", "complaint_type": "Hydrant", "descriptor": "Hydrant", "descriptor_2": "", "bbl": "1011210036", "borough": "MANHATTAN"},
            ]),
            SimpleNamespace(rows=[
                {"unique_key": "3", "created_date": "2024-04-01T00:00:00.000", "agency": "DEP", "complaint_type": "Water Leak", "descriptor": "Leak", "descriptor_2": "", "bbl": "1011210036", "borough": "MANHATTAN"},
                {"unique_key": "4", "created_date": "2024-05-01T00:00:00.000", "agency": "DEP", "complaint_type": "Water Quality", "descriptor": "Lead", "descriptor_2": "", "bbl": "1011210036", "borough": "MANHATTAN"},
            ]),
        ]
        payload = build_historical_context(["1011210036"], batch_size=200, page_size=5000)
        profile = payload["by_bbl"]["1011210036"]
        self.assertEqual(profile["request_count"], 3)
        self.assertEqual(profile["years"], ["2018", "2024"])
        self.assertTrue(profile["recurrent_history"])
        self.assertTrue(profile["has_2024_activity"])
        self.assertEqual(profile["first_reported_date"], "2018-02-01")
        self.assertEqual(profile["latest_reported_date"], "2024-05-01")
        self.assertNotIn("rows", profile)
        self.assertFalse(payload["governance"]["raw_historical_events_published"])

    def test_validator_and_attachment_keep_context_separate(self):
        payload = {
            "schema_version": "1.0",
            "domain": "NYC_HISTORICAL_BUILDING_WATER_CONTEXT",
            "generated_at": "2026-09-07T00:00:00Z",
            "query_boundaries": {"start": "2010-01-01", "end_exclusive": "2025-01-01", "property_match": "EXACT_BBL_ONLY"},
            "summary": {"requested_bbl_count": 1, "matched_bbl_count": 1, "source_row_count": 3, "building_water_request_count": 3, "recurrent_bbl_count": 1, "bbls_with_2024_activity": 1},
            "by_bbl": {
                "1011210036": {
                    "bbl": "1011210036", "request_count": 3,
                    "category_counts": {"BUILDING_WATER_QUALITY": 3}, "years": ["2018", "2024"], "year_count": 2,
                    "first_reported_date": "2018-02-01", "latest_reported_date": "2024-05-01",
                    "recurrent_history": True, "has_2024_activity": True,
                    "property_link_confidence": "CONFIRMED_SOURCE_BBL", "evidence_semantics": "REPORTED_SERVICE_REQUEST",
                }
            },
            "source_health": [{"dataset_id": "76ig-c548"}, {"dataset_id": "erm2-nwe9"}],
            "evidence_boundaries": {
                "historical_not_current": "Historical only", "property_link": "Exact BBL only",
                "raw_rows": "No raw rows", "provider": "No provider inference",
            },
            "governance": {
                "priority_score_1_0_changed": False, "current_trigger_created": False,
                "fuzzy_matching_used": False, "provider_or_incumbent_inference": False,
                "raw_historical_events_published": False,
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cache = base / "historical.json"
            cache.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(validate(cache)["matched_bbl_count"], 1)
            output = base / "data"
            detail_path = output / "details" / "20" / "2000015740.json"
            detail_path.parent.mkdir(parents=True)
            detail_path.write_text(json.dumps({"identity": {"system_id": "2000015740", "bbl": "1011210036"}, "nyc_building_water_signals": {"summary": {"record_count": 1}}}), encoding="utf-8")
            systems = {
                "metadata": {}, "summary": {},
                "systems": [{"system_id": "2000015740", "bbl": "1011210036"}],
            }
            (output / "systems.json").write_text(json.dumps(systems), encoding="utf-8")
            result = attach(output, cache)
            self.assertEqual(result["systems_attached"], 1)
            detail = json.loads(detail_path.read_text(encoding="utf-8"))
            self.assertEqual(detail["nyc_historical_water_context"]["summary"]["request_count"], 3)
            self.assertEqual(detail["nyc_building_water_signals"]["summary"]["record_count"], 1)


if __name__ == "__main__":
    unittest.main()
