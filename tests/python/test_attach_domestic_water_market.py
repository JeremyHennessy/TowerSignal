from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from attach_domestic_water_market import attach  # noqa: E402


class AttachDomesticWaterMarketTests(unittest.TestCase):
    def test_attaches_provider_evidence_only_by_exact_bin(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            output = root / "public" / "data"
            detail_dir = output / "details" / "sy"
            detail_dir.mkdir(parents=True)
            payload = {
                "metadata": {"generated_at": "2026-09-06T00:00:00Z"},
                "summary": {},
                "systems": [
                    {"system_id": "SYS-1", "bin": "1000001", "bbl": "1000010001", "address": "10 Alpha St"},
                    {"system_id": "SYS-2", "bin": "2000002", "bbl": "2000020002", "address": "10 Alpha St"},
                ],
            }
            (output / "systems.json").write_text(json.dumps(payload), encoding="utf-8")
            (output / "metadata.json").write_text(json.dumps(payload["metadata"]), encoding="utf-8")
            for system_id in ("SYS-1", "SYS-2"):
                (detail_dir / f"{system_id}.json").write_text(
                    json.dumps({"identity": {"system_id": system_id}}),
                    encoding="utf-8",
                )

            cache = root / "domestic-water-market.json"
            cache.write_text(json.dumps({
                "schema_version": "1.0",
                "generated_at": "2026-09-06T00:00:00Z",
                "domain": "NY_DOMESTIC_WATER_PROVIDER_INTELLIGENCE",
                "properties": [
                    {
                        "building_key": "NYC-BIN-1000001",
                        "bin": "1000001",
                        "bbl": "1000010001",
                        "address": "10 Alpha St",
                        "borough": "MANHATTAN",
                        "zip": "10001",
                        "inspection_count": 4,
                        "observed_tank_count": 2,
                        "observed_provider_ids": ["provider-a", "provider-b"],
                        "observed_lab_ids": ["lab-a"],
                        "latest_inspection_date": "2026-03-15",
                        "latest_reporting_year": "2026",
                        "current_observed_provider_id": "provider-a",
                        "current_observed_provider_raw": "Example Water Service LLC",
                        "current_observed_lab_id": "lab-a",
                        "current_observed_lab_raw": "Example Lab",
                        "compliance_activity_count": 3,
                        "violation_count": 1,
                        "latest_violation_date": "2025-12-01",
                    },
                    {
                        "building_key": "NYC-BBL-2000020002",
                        "bin": "2000002",
                        "bbl": "2000020002",
                        "address": "10 Alpha St",
                        "inspection_count": 5,
                        "observed_provider_ids": ["provider-wrong"],
                        "observed_lab_ids": [],
                        "current_observed_provider_id": "provider-wrong",
                        "current_observed_provider_raw": "Must Not Attach",
                        "compliance_activity_count": 0,
                        "violation_count": 0,
                    },
                ],
            }), encoding="utf-8")

            report = attach(output, cache)
            self.assertEqual(report["systems_attached"], 1)
            self.assertEqual(report["systems_with_current_observed_provider"], 1)
            self.assertEqual(report["match_basis"], "BIN_EXACT")

            systems = json.loads((output / "systems.json").read_text(encoding="utf-8"))["systems"]
            first, second = systems
            self.assertTrue(first["dwt_market_exact_bin_match"])
            self.assertEqual(first["dwt_market_current_provider_raw"], "Example Water Service LLC")
            self.assertEqual(first["dwt_market_latest_inspection_date"], "2026-03-15")
            self.assertEqual(first["dwt_market_observed_provider_count"], 2)
            self.assertFalse(second["dwt_market_exact_bin_match"])
            self.assertIsNone(second["dwt_market_current_provider_raw"])

            first_detail = json.loads((detail_dir / "SYS-1.json").read_text(encoding="utf-8"))
            second_detail = json.loads((detail_dir / "SYS-2.json").read_text(encoding="utf-8"))
            self.assertEqual(first_detail["domestic_water_market"]["match_basis"], "BIN_EXACT")
            self.assertIn("not proof of a current cooling-tower incumbent", first_detail["domestic_water_market"]["evidence_boundaries"]["provider"])
            self.assertIsNone(second_detail["domestic_water_market"])

    def test_rejects_duplicate_exact_bin_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            output = root / "public" / "data"
            output.mkdir(parents=True)
            (output / "systems.json").write_text(json.dumps({"metadata": {}, "summary": {}, "systems": []}), encoding="utf-8")
            cache = root / "domestic-water-market.json"
            cache.write_text(json.dumps({
                "domain": "NY_DOMESTIC_WATER_PROVIDER_INTELLIGENCE",
                "properties": [
                    {"building_key": "NYC-BIN-1000001", "bin": "1000001"},
                    {"building_key": "NYC-BIN-1000001", "bin": "1000001"},
                ],
            }), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "duplicate exact-BIN"):
                attach(output, cache)


if __name__ == "__main__":
    unittest.main()
