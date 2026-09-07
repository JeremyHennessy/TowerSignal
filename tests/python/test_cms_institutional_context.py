from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from attach_cms_institutional_context import attach
from towersignal.cms_institutional import build_cms_institutional_context, is_nyc_zip, reconcile_geosearch
from validate_cms_institutional_context import validate


class CmsInstitutionalContextTests(unittest.TestCase):
    def test_nyc_zip_boundary_excludes_nassau(self):
        self.assertTrue(is_nyc_zip("11432"))
        self.assertTrue(is_nyc_zip("11694"))
        self.assertFalse(is_nyc_zip("11501"))

    def test_reconcile_requires_exact_house_street_zip_and_one_bbl(self):
        facility = {"address": "123 MAIN ST", "zip": "10001"}
        payload = {"features": [{"properties": {
            "housenumber": "123", "street": "MAIN ST", "postalcode": "10001",
            "addendum": {"pad": {"bbl": "1000010001", "bin": "1000001"}},
        }}]}
        result = reconcile_geosearch(facility, payload)
        self.assertEqual(result["status"], "RESOLVED_UNIQUE_PAD_EXACT_ADDRESS")
        self.assertEqual(result["bbl"], "1000010001")
        mismatch = reconcile_geosearch({"address": "124 MAIN ST", "zip": "10001"}, payload)
        self.assertEqual(mismatch["status"], "UNRESOLVED_NO_EXACT_PAD_RESULT")

    @patch("towersignal.cms_institutional.resolve_facility")
    @patch("towersignal.cms_institutional.fetch_cms_dataset")
    def test_build_retains_only_current_tower_overlap(self, fetch_mock, resolve_mock):
        hospital = {"facility_id": "H1", "facility_name": "Hospital A", "address": "123 MAIN ST", "citytown": "NEW YORK", "state": "NY", "zip_code": "10001", "hospital_type": "Acute Care", "hospital_ownership": "Voluntary"}
        nursing = {"cms_certification_number_ccn": "N1", "provider_name": "Nursing A", "provider_address": "200 BROADWAY", "provider_city": "NEW YORK", "provider_state": "NY", "provider_zip_code": "10007", "ownership_type": "For profit", "chain_name": "Chain A"}
        fetch_mock.side_effect = [([hospital], 5419), ([nursing], 14690)]

        def resolve(row):
            bbl = "1000010001" if row["source_kind"] == "HOSPITAL" else "1000020002"
            return {**row, "property_resolution": {"status": "RESOLVED_UNIQUE_PAD_EXACT_ADDRESS", "bbl": bbl, "bin": "1000001", "candidate_count": 1}}

        resolve_mock.side_effect = resolve
        payload = build_cms_institutional_context(["1000010001"], geosearch_workers=1)
        self.assertEqual(payload["summary"]["tower_overlap_facility_count"], 1)
        self.assertEqual(payload["summary"]["resolved_non_tower_bbl_count"], 1)
        self.assertEqual(payload["by_bbl"]["1000010001"][0]["source_facility_id"], "H1")
        self.assertNotIn("1000020002", payload["by_bbl"])
        self.assertFalse(payload["governance"]["cms_only_properties_promoted_to_tower_universe"])

    def test_validator_and_attachment_preserve_exact_context(self):
        cache_payload = {
            "schema_version": "1.0", "domain": "CMS_NYC_INSTITUTIONAL_CONTEXT", "generated_at": "2026-09-07T00:00:00Z",
            "summary": {"hospital_source_rows": 5419, "nursing_home_source_rows": 14690, "nyc_candidate_facility_count": 210, "exact_resolved_facility_count": 116, "tower_overlap_facility_count": 1, "tower_overlap_bbl_count": 1, "resolved_non_tower_bbl_count": 70},
            "by_bbl": {"1011210036": [{"source_dataset_id": "xubh-q36u", "source_facility_id": "H1", "source_kind": "HOSPITAL", "facility_name": "Hospital A", "facility_type": "Acute Care", "ownership_type": "Voluntary", "chain_name": None, "bbl": "1011210036", "bin": "1079280", "property_link_confidence": "CONFIRMED_PAD_EXACT_ADDRESS_BBL"}]},
            "source": {"datasets": [], "property_resolution": "exact"},
            "evidence_boundaries": {"property_link": "Exact PAD", "facility": "Context only", "non_tower": "Not promoted", "provider": "No incumbent"},
            "governance": {"priority_score_1_0_changed": False, "current_trigger_created": False, "fuzzy_matching_used": False, "provider_or_incumbent_inference": False, "cms_only_properties_promoted_to_tower_universe": False, "raw_cms_rows_published": False},
        }
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cache = base / "cms.json"
            cache.write_text(json.dumps(cache_payload), encoding="utf-8")
            self.assertEqual(validate(cache)["tower_overlap_facility_count"], 1)
            output = base / "data"
            detail_path = output / "details" / "20" / "2000015740.json"
            detail_path.parent.mkdir(parents=True)
            detail_path.write_text(json.dumps({"identity": {"system_id": "2000015740"}}), encoding="utf-8")
            (output / "systems.json").write_text(json.dumps({"metadata": {}, "summary": {}, "systems": [{"system_id": "2000015740", "bbl": "1011210036", "priority_score": 50}]}), encoding="utf-8")
            result = attach(output, cache)
            self.assertEqual(result["facilities_attached"], 1)
            systems = json.loads((output / "systems.json").read_text())
            self.assertEqual(systems["systems"][0]["priority_score"], 50)
            detail = json.loads(detail_path.read_text())
            self.assertEqual(detail["cms_institutional_context"]["facilities"][0]["source_facility_id"], "H1")


if __name__ == "__main__":
    unittest.main()
