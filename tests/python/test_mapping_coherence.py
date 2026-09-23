from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_mapping_coherence import validate


class MappingCoherenceTests(unittest.TestCase):
    def _fixture(self) -> tuple[tempfile.TemporaryDirectory, Path]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / "details" / "20").mkdir(parents=True)
        metadata = {
            "snapshot_date": "2026-09-23",
            "pluto_requested_bbl_count": 1,
            "hpd_requested_bbl_count": 1,
            "dob_requested_bbl_count": 2,
            "hpd_violation_requested_bbl_count": 2,
            "legacy_dob_project_requested_bbl_count": 2,
            "nyc_water_signal_requested_bbl_count": 2,
            "cms_institutional_requested_bbl_count": 2,
            "nyc_lead_service_line_requested_bbl_count": 2,
            "nyc_historical_311_requested_bbl_count": 2,
            "dob_match_basis": "BBL_ALIAS_EXACT",
            "hpd_violation_match_basis": "BBL_ALIAS_EXACT",
            "legacy_dob_project_match_basis": "BBL_ALIAS_EXACT",
            "nyc_water_signal_match_basis": "EXACT_SOURCE_BBL_ALIAS_OR_BIN",
            "cms_institutional_match_basis": "PAD_EXACT_ADDRESS_BBL_ALIAS",
            "nyc_lead_service_line_match_basis": "BBL_ALIAS_EXACT",
            "nyc_historical_311_match_basis": "BBL_ALIAS_EXACT",
        }
        system = {
            "system_id": "2000014227",
            "address": "400 West 61st Street",
            "bbl": "1011717513",
            "registry_bbl": "1011710154",
            "property_bbl": "1011717513",
            "bbl_aliases": ["1011710154", "1011717513"],
            "pluto_match": True,
            "pluto_owner_name": "RCB1 NOMINEE LLC",
            "pluto_building_area_sqft": 846331.0,
            "hpd_contact_count": 1,
            "dob_activity_count": 0,
            "dob_recent_activity_count": 0,
            "dob_explicit_cooling_tower_count": 0,
            "dob_mechanical_or_boiler_count": 0,
            "latest_dob_activity_date": None,
        }
        detail = {
            "identity": {"system_id": "2000014227"},
            "building_context": {"owner_name": "RCB1 NOMINEE LLC", "building_area_sqft": 846331.0},
            "hpd_registration": {"contacts": [{"person_name": "Example"}]},
            "dob_activity_history": [],
        }
        (root / "systems.json").write_text(json.dumps({"metadata": metadata, "systems": [system]}))
        (root / "details" / "20" / "2000014227.json").write_text(json.dumps(detail))
        return temp, root

    def test_accepts_aligned_summary_and_alias_layers(self):
        temp, root = self._fixture()
        try:
            result = validate(root)
            self.assertEqual(result["canonical_bbl_count"], 1)
            self.assertEqual(result["exact_bbl_alias_count"], 2)
            self.assertEqual(result["summary_detail_mismatch_count"], 0)
        finally:
            temp.cleanup()

    def test_rejects_stale_summary_fields(self):
        temp, root = self._fixture()
        try:
            payload = json.loads((root / "systems.json").read_text())
            payload["systems"][0]["hpd_contact_count"] = 0
            (root / "systems.json").write_text(json.dumps(payload))
            with self.assertRaisesRegex(RuntimeError, "Summary/detail mapping coherence failed"):
                validate(root)
        finally:
            temp.cleanup()

    def test_rejects_old_alias_universe(self):
        temp, root = self._fixture()
        try:
            payload = json.loads((root / "systems.json").read_text())
            payload["metadata"]["legacy_dob_project_requested_bbl_count"] = 1
            (root / "systems.json").write_text(json.dumps(payload))
            with self.assertRaisesRegex(RuntimeError, "legacy DOB/BIS was built against 1 BBLs"):
                validate(root)
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
