from __future__ import annotations

import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import build_lead_service_line_cache as lead_cache  # noqa: E402
from attach_nyc_service_lines import attach  # noqa: E402


class LeadServiceLineCacheTests(unittest.TestCase):
    def test_normalize_row_preserves_property_material_and_excludes_geometry(self) -> None:
        row = lead_cache.normalize_row(
            {
                "objectid": "10",
                "tbbl": "1000160001",
                "address": "1 EXAMPLE STREET",
                "material": "Lead",
                "record_ty": "Service Line",
                "city_owned": "No",
                "the_geom": {"type": "MultiPolygon", "coordinates": []},
            }
        )
        self.assertEqual(row["record_id"], "10")
        self.assertEqual(row["bbl"], "1000160001")
        self.assertEqual(row["material"], "Lead")
        self.assertEqual(row["source_dataset_id"], "jqfp-uff7")
        self.assertNotIn("the_geom", row)

    def test_geometry_is_not_requested(self) -> None:
        self.assertNotIn("the_geom", lead_cache.SELECT.split(","))
        self.assertEqual(set(lead_cache.SELECT.split(",")), lead_cache.REQUIRED_FIELDS)


    def test_attach_merges_service_line_records_from_preserved_base_bbl_alias(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "data"
            detail = output / "details" / "20"
            detail.mkdir(parents=True)
            systems = {
                "metadata": {},
                "summary": {},
                "systems": [{
                    "system_id": "2000014227",
                    "bbl": "1011717513",
                    "property_bbl": "1011717513",
                    "registry_bbl": "1011710154",
                    "bbl_aliases": ["1011710154", "1011717513"],
                }],
            }
            (output / "systems.json").write_text(json.dumps(systems))
            (detail / "2000014227.json").write_text(json.dumps({"identity": {"system_id": "2000014227"}}))
            data_path = Path(directory) / "service-lines.jsonl.gz"
            with gzip.open(data_path, "wt", encoding="utf-8") as handle:
                handle.write(json.dumps({
                    "record_id": "SL1",
                    "bbl": "1011710154",
                    "material": "Lead",
                    "record_type": "Service Line",
                    "city_owned": "No",
                }) + "\n")
            summary_path = Path(directory) / "summary.json"
            summary_path.write_text(json.dumps({
                "schema_version": "1.0",
                "generated_at": "2026-09-22T00:00:00Z",
                "source": {"source_record_count": 1},
            }))
            report = attach(output, data_path, summary_path)
            updated = json.loads((detail / "2000014227.json").read_text())
            self.assertEqual(report["systems_attached"], 1)
            self.assertEqual(updated["nyc_lead_service_lines"]["summary"]["record_count"], 1)
            self.assertEqual(updated["nyc_lead_service_lines"]["matched_bbl_aliases"], ["1011710154"])
            self.assertEqual(updated["nyc_lead_service_lines"]["match_basis"], "BBL_ALIAS_EXACT")



if __name__ == "__main__":
    unittest.main()
