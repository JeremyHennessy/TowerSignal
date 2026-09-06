from __future__ import annotations

import gzip
import json
import tempfile
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from attach_nyc_service_lines import attach  # noqa: E402


class AttachNycServiceLinesTests(unittest.TestCase):
    def test_attaches_only_exact_bbl_rows_to_account_detail(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            output = root / "public" / "data"
            detail_dir = output / "details" / "sy"
            detail_dir.mkdir(parents=True)
            payload = {
                "metadata": {"generated_at": "2026-09-05T00:00:00Z"},
                "summary": {},
                "systems": [
                    {"system_id": "SYS-1", "bbl": "1000010001"},
                    {"system_id": "SYS-2", "bbl": "2000020002"},
                ],
            }
            (output / "systems.json").write_text(json.dumps(payload), encoding="utf-8")
            for system_id in ("SYS-1", "SYS-2"):
                (detail_dir / f"{system_id}.json").write_text(
                    json.dumps({"identity": {"system_id": system_id}}),
                    encoding="utf-8",
                )

            data = root / "service-lines.jsonl.gz"
            with gzip.open(data, "wt", encoding="utf-8") as handle:
                handle.write(json.dumps({
                    "record_id": "1",
                    "bbl": "1000010001",
                    "address": "10 Alpha St",
                    "material": "Lead",
                    "record_type": "Private",
                    "city_owned": "No",
                    "source_dataset_id": "jqfp-uff7",
                }) + "\n")
                handle.write(json.dumps({
                    "record_id": "2",
                    "bbl": "9999999999",
                    "address": "10 Alpha St",
                    "material": "Copper",
                    "record_type": "Private",
                    "city_owned": "No",
                    "source_dataset_id": "jqfp-uff7",
                }) + "\n")
            summary = root / "service-line-summary.json"
            summary.write_text(json.dumps({
                "schema_version": "1.0",
                "generated_at": "2026-09-05T00:00:00Z",
                "source": {
                    "name": "Lead Service Lines",
                    "url": "https://data.cityofnewyork.us/d/jqfp-uff7",
                    "source_record_count": 2,
                    "source_last_updated_at": None,
                },
            }), encoding="utf-8")

            report = attach(output, data, summary)
            self.assertEqual(report["matched_bbl_count"], 1)
            self.assertEqual(report["matched_record_count"], 1)
            first_detail = json.loads((detail_dir / "SYS-1.json").read_text(encoding="utf-8"))
            second_detail = json.loads((detail_dir / "SYS-2.json").read_text(encoding="utf-8"))
            self.assertEqual(first_detail["nyc_lead_service_lines"]["summary"]["record_count"], 1)
            self.assertIsNone(second_detail["nyc_lead_service_lines"])


if __name__ == "__main__":
    unittest.main()
