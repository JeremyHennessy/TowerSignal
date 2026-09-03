from __future__ import annotations

import unittest

from scripts.toronto_app_sources import OFFICIAL_DATASET_URLS, normalize_source_link
from scripts.toronto_source_identity import find_source_record, stable_source_record_id


class TorontoBuildingPermitSourceTests(unittest.TestCase):
    def row(self) -> dict:
        return {
            "PERMIT_NUM": "24 123456 BLD 00 BA",
            "REVISION_NUM": "01",
            "STATUS": "Permit Issued",
            "ISSUED_DATE": "2026-08-01T00:00:00",
            "PERMIT_TYPE": "Mechanical",
            "STRUCTURE_TYPE": "Office",
            "WORK": "HVAC",
            "DESCRIPTION": "Replace existing rooftop chiller and cooling tower",
            "EST_CONST_COST": "125000",
            "BUILDER_NAME": "Example Builder",
            "_towersignal_source_lifecycle": "ACTIVE",
            "_towersignal_source_address": "100 Example St",
            "_towersignal_signals": ["chiller", "cooling_tower"],
            "_towersignal_cooling_tower_lifecycle": "REPLACE_COOLING_TOWER",
            "_towersignal_cooling_tower_lifecycle_reasons": ["EXPLICIT_EXISTING_TOWER", "REPLACEMENT_LANGUAGE"],
            "_towersignal_cooling_tower_current_interpretation": "ACTIVE_EXISTING_AND_REPLACEMENT_TOWER_SIGNAL",
        }

    def test_permit_identity_uses_complete_permit_and_revision(self) -> None:
        source = "toronto_building_permits_active_targeted"
        row = self.row()
        record_id = stable_source_record_id(source, row)
        self.assertEqual(record_id, f"{source}:id:24 123456 BLD 00 BA:revision:01")
        self.assertEqual(find_source_record(source, record_id, [row]), row)

    def test_app_projection_keeps_builder_as_source_detail_only(self) -> None:
        source = "toronto_building_permits_active_targeted"
        row = self.row()
        record_id = stable_source_record_id(source, row)
        normalized = normalize_source_link({
            "source_key": source,
            "source_record_id": record_id,
            "source_row_index": 0,
            "match_basis": "EXACT_UNIQUE_CIVIC_ADDRESS_TO_CURRENT_ADDRESS_POINT_ROOT",
            "source_address": "100 Example St",
        }, {source: [row]})
        self.assertEqual(normalized["record_title"], "24 123456 BLD 00 BA · revision 01")
        self.assertEqual(normalized["record_status"], "Permit Issued")
        self.assertIn({"label": "Builder name (publisher field)", "value": "Example Builder"}, normalized["record_details"])
        self.assertIn({"label": "Cooling tower lifecycle", "value": "REPLACE_COOLING_TOWER"}, normalized["record_details"])
        self.assertIsNone(normalized["record_url"])
        self.assertIn(source, OFFICIAL_DATASET_URLS)


if __name__ == "__main__":
    unittest.main()
