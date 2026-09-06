from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from attach_nyc_water_signals import attach  # noqa: E402


class AttachNycWaterSignalsTests(unittest.TestCase):
    def test_attaches_only_exact_property_signal_rows_to_account_detail(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            output = root / "public" / "data"
            detail_dir = output / "details" / "sy"
            detail_dir.mkdir(parents=True)
            payload = {
                "metadata": {"generated_at": "2026-09-05T00:00:00Z"},
                "summary": {},
                "systems": [
                    {"system_id": "SYS-1", "bbl": "1000010001", "bin": "1000001", "address": "10 Alpha St"},
                    {"system_id": "SYS-2", "bbl": "2000020002", "bin": "2000002", "address": "10 Alpha St"},
                ],
            }
            (output / "systems.json").write_text(json.dumps(payload), encoding="utf-8")
            for system_id in ("SYS-1", "SYS-2"):
                (detail_dir / f"{system_id}.json").write_text(
                    json.dumps({"identity": {"system_id": system_id}}),
                    encoding="utf-8",
                )

            cache = root / "nyc-water-signals.json"
            cache.write_text(json.dumps({
                "schema_version": "1.0",
                "generated_at": "2026-09-05T00:00:00Z",
                "domain": "NYC_BUILDING_WATER_SIGNALS",
                "query_boundaries": {},
                "source_health": [
                    {"dataset_id": "erm2-nwe9", "source_record_count": 2},
                    {"dataset_id": "wvxf-dwi5", "source_record_count": 1},
                    {"dataset_id": "w9ak-ipjd", "source_record_count": 1},
                    {"dataset_id": "rbx6-tga4", "source_record_count": 0},
                    {"dataset_id": "5zyy-y8am", "source_record_count": 2},
                ],
                "water_311_requests": [
                    {
                        "request_id": "311-1",
                        "created_date": "2026-01-01",
                        "category": "BUILDING_WATER_QUALITY",
                        "bbl": "1000010001",
                        "property_link_confidence": "CONFIRMED_SOURCE_BBL",
                        "is_building_water_signal": True,
                        "raw": {"discard": True},
                    },
                    {
                        "request_id": "311-2",
                        "created_date": "2026-01-02",
                        "category": "STREET_WATER_MAIN_CONTEXT",
                        "bbl": "1000010001",
                        "property_link_confidence": "CONTEXT_ONLY",
                        "is_building_water_signal": False,
                    },
                ],
                "hpd_open_water_violations": [
                    {
                        "violation_id": "hpd-1",
                        "inspection_date": "2026-02-01",
                        "category": "HOT_WATER",
                        "bbl": None,
                        "bin": "1000001",
                        "property_link_confidence": "CONFIRMED_SOURCE_BIN",
                    }
                ],
                "dob_water_job_filings": [
                    {
                        "activity_id": "dob-1",
                        "filing_date": "2026-03-01",
                        "category": "DOMESTIC_WATER_SYSTEM",
                        "bbl": "1000010001",
                        "bin": "1000001",
                        "property_link_confidence": "CONFIRMED_SOURCE_BBL",
                        "applicant_business_key": "EXAMPLE PLUMBING",
                    }
                ],
                "dob_water_permits": [],
                "ll84_water_benchmarks": [
                    {
                        "benchmark_id": "ll84-1",
                        "report_year": "2025",
                        "bbls": ["1000010001"],
                        "bins": [],
                        "property_link_confidence": "EXACT_SINGLE_BBL",
                    },
                    {
                        "benchmark_id": "ll84-2",
                        "report_year": "2025",
                        "bbls": ["1000010001", "2000020002"],
                        "bins": ["1000001", "2000002"],
                        "property_link_confidence": "MULTI_IDENTIFIER_CONTEXT",
                    },
                ],
            }), encoding="utf-8")

            report = attach(output, cache)
            self.assertEqual(report["systems_attached"], 1)
            self.assertEqual(report["attached_record_count"], 4)
            first_detail = json.loads((detail_dir / "SYS-1.json").read_text(encoding="utf-8"))
            second_detail = json.loads((detail_dir / "SYS-2.json").read_text(encoding="utf-8"))
            context = first_detail["nyc_building_water_signals"]
            self.assertEqual(context["summary"]["record_count"], 4)
            self.assertEqual(context["summary"]["dob_applicant_business_count"], 1)
            self.assertEqual(context["summary"]["category_counts"]["BUILDING_WATER_QUALITY"], 1)
            self.assertNotIn("raw", context["water_311_requests"][0])
            self.assertIsNone(second_detail["nyc_building_water_signals"])


if __name__ == "__main__":
    unittest.main()
