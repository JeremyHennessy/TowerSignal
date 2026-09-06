from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import build_lead_service_line_cache as lead_cache  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
