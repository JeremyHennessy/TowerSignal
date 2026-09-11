from __future__ import annotations

import io
import json
import threading
import time
from contextlib import redirect_stderr, redirect_stdout
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from scripts import build_legacy_dob_project_cache as builder

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

    def test_build_uses_max_four_concurrent_exact_queries_and_deterministic_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            bbls = [f"3{lot:05d}0001" for lot in range(1, 122)]
            source = {"metadata": {"snapshot_date": "2026-09-11"},
                      "systems": [{"bbl": bbl} for bbl in reversed(bbls)]}
            (output / "systems.json").write_text(json.dumps(source))
            requested = sorted(bbls, key=int)
            chunks = [requested[i:i + builder.QUERY_CHUNK_SIZE] for i in range(0, len(requested), builder.QUERY_CHUNK_SIZE)]
            where_to_index = {builder._exact_where(chunk): index for index, chunk in enumerate(chunks, 1)}
            calls = []
            lock = threading.Lock()
            active = 0
            peak = 0

            def fake_fetch(dataset_id, **kwargs):
                nonlocal active, peak
                self.assertEqual(dataset_id, builder.DATASET_ID)
                index = where_to_index[kwargs["where"]]
                with lock:
                    calls.append((index, kwargs.copy()))
                    active += 1
                    peak = max(peak, active)
                try:
                    time.sleep(0.01 * (6 - index))
                    borough, block, lot = builder._bbl_components(chunks[index - 1][0])
                    return [self.base_row(
                        job_s1_no=f"row-{index}",
                        borough=borough,
                        block=block,
                        lot=str(int(lot)).zfill(5),
                        job_description=f"Replace cooling tower batch {index}",
                    )]
                finally:
                    with lock:
                        active -= 1

            stderr = io.StringIO()
            with patch.object(builder, "fetch_where", side_effect=fake_fetch), \
                 patch.object(builder, "fetch_metadata", return_value={"name": "DOB", "source_last_updated_at": "2026-09-10T00:00:00Z"}), \
                 patch.object(builder, "fetch_count", return_value=2700000), \
                 redirect_stderr(stderr), redirect_stdout(io.StringIO()):
                result = builder.build(output)

            self.assertEqual(builder.MAX_CONCURRENT_REQUESTS, 4)
            self.assertLessEqual(peak, 4)
            self.assertGreaterEqual(peak, 2)
            self.assertEqual(len(calls), len(chunks))
            self.assertEqual({index for index, _ in calls}, set(range(1, len(chunks) + 1)))
            for index, kwargs in calls:
                self.assertEqual(kwargs, {
                    "where": builder._exact_where(chunks[index - 1]),
                    "order_by": "borough,block,lot,job_s1_no",
                    "select": builder.SELECT,
                    "limit": builder.FETCH_CAP,
                    "request_timeout": 120,
                })
            expected_bbl_order = [builder.normalize_bbl(chunk[0]) for chunk in chunks]
            self.assertEqual(list(result["by_bbl"]), expected_bbl_order)
            self.assertEqual(result["summary"]["exact_bbl_job_count"], len(chunks))
            self.assertEqual(result["summary"]["retained_record_count"], len(chunks))
            self.assertIn("at most 4 concurrent requests", stderr.getvalue())
            self.assertIn("merging", stderr.getvalue())
            self.assertEqual(json.loads((output / "legacy-dob-projects.json").read_text()), result)

    def test_capped_concurrent_query_fails_without_replacing_existing_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output / "systems.json").write_text(json.dumps({"systems": [{"bbl": "3000010001"}]}))
            cache = output / "legacy-dob-projects.json"
            cache.write_bytes(b"previous verified cache")
            with patch.object(builder, "fetch_where", return_value=[self.base_row()] * builder.FETCH_CAP), \
                 redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()), \
                 self.assertRaisesRegex(builder.SourceFetchError, "refusing possibly truncated evidence"):
                builder.build(output)
            self.assertEqual(cache.read_bytes(), b"previous verified cache")

    def test_concurrent_source_error_propagates_and_does_not_publish_partial_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            bbls = [f"3{lot:05d}0001" for lot in range(1, 32)]
            (output / "systems.json").write_text(json.dumps({"systems": [{"bbl": b} for b in bbls]}))
            calls = 0
            lock = threading.Lock()

            def fake_fetch(*args, **kwargs):
                nonlocal calls
                with lock:
                    calls += 1
                    current = calls
                if current == 1:
                    raise builder.SourceFetchError("source timeout")
                return []

            with patch.object(builder, "fetch_where", side_effect=fake_fetch), \
                 redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()), \
                 self.assertRaisesRegex(builder.SourceFetchError, "source timeout"):
                builder.build(output)
            self.assertFalse((output / "legacy-dob-projects.json").exists())

    def test_count_failure_after_concurrent_collection_prevents_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output / "systems.json").write_text(json.dumps({"systems": [{"bbl": "3000010001"}]}))
            with patch.object(builder, "fetch_where", return_value=[self.base_row()]), \
                 patch.object(builder, "fetch_metadata", return_value={"name": "DOB"}), \
                 patch.object(builder, "fetch_count", side_effect=builder.SourceFetchError("count unavailable")), \
                 redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()), \
                 self.assertRaisesRegex(builder.SourceFetchError, "count unavailable"):
                builder.build(output)
            self.assertFalse((output / "legacy-dob-projects.json").exists())


if __name__ == "__main__":
    unittest.main()
