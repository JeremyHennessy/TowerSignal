from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from diagnose_cms_nyc_facilities import (  # noqa: E402
    is_nyc_zip,
    normalize_cms_facility,
    reconcile_geosearch,
)


class CmsNycFacilityDiagnosticTests(unittest.TestCase):
    def test_nyc_zip_filter_includes_all_borough_patterns_without_nassau_spillover(self) -> None:
        for postal in ("10023", "10301", "10467", "11004", "11101", "11215", "11375", "11691"):
            self.assertTrue(is_nyc_zip(postal), postal)
        for postal in ("11003", "11010", "11501", "11743", "12207"):
            self.assertFalse(is_nyc_zip(postal), postal)

    def test_hospital_identity_preserves_source_facility_id(self) -> None:
        facility = normalize_cms_facility(
            "HOSPITAL",
            {
                "facility_id": "330001",
                "facility_name": "EXAMPLE HOSPITAL",
                "address": "88 CENTRAL PARK WEST",
                "citytown": "NEW YORK",
                "state": "NY",
                "zip_code": "10023",
                "hospital_type": "Acute Care Hospitals",
                "hospital_ownership": "Voluntary non-profit - Private",
            },
        )
        self.assertIsNotNone(facility)
        assert facility is not None
        self.assertEqual(facility["source_facility_id"], "330001")
        self.assertEqual(facility["source_dataset_id"], "xubh-q36u")
        self.assertEqual(facility["zip"], "10023")

    def test_non_nyc_cms_row_is_not_candidate(self) -> None:
        facility = normalize_cms_facility(
            "HOSPITAL",
            {
                "facility_id": "330999",
                "facility_name": "LONG ISLAND HOSPITAL",
                "address": "1 MAIN STREET",
                "citytown": "MINEOLA",
                "state": "NY",
                "zip_code": "11501",
            },
        )
        self.assertIsNone(facility)

    def test_unique_pad_bbl_requires_exact_house_street_and_zip(self) -> None:
        facility = {
            "address": "88 CENTRAL PARK WEST",
            "zip": "10023",
        }
        payload = {
            "features": [
                {
                    "properties": {
                        "housenumber": "88",
                        "street": "CENTRAL PARK WEST",
                        "postalcode": "10023",
                        "label": "88 Central Park West, Manhattan, NY, 10023",
                        "confidence": 1,
                        "addendum": {"pad": {"bbl": "1011210036", "bin": "1079280"}},
                    }
                }
            ]
        }
        result = reconcile_geosearch(facility, payload)
        self.assertEqual(result["status"], "RESOLVED_UNIQUE_PAD_EXACT_ADDRESS")
        self.assertEqual(result["bbl"], "1011210036")
        self.assertEqual(result["bin"], "1079280")

    def test_street_mismatch_stays_unresolved_even_with_pad_id(self) -> None:
        facility = {"address": "88 CENTRAL PARK WEST", "zip": "10023"}
        payload = {
            "features": [
                {
                    "properties": {
                        "housenumber": "88",
                        "street": "COLUMBUS AVENUE",
                        "postalcode": "10023",
                        "addendum": {"pad": {"bbl": "1011210036", "bin": "1079280"}},
                    }
                }
            ]
        }
        result = reconcile_geosearch(facility, payload)
        self.assertEqual(result["status"], "UNRESOLVED_NO_EXACT_PAD_RESULT")
        self.assertIsNone(result["bbl"])

    def test_multiple_exact_pad_properties_remain_unresolved(self) -> None:
        facility = {"address": "1 COMPLEX PLAZA", "zip": "10001"}
        payload = {
            "features": [
                {
                    "properties": {
                        "housenumber": "1",
                        "street": "COMPLEX PLAZA",
                        "postalcode": "10001",
                        "addendum": {"pad": {"bbl": "1000010001", "bin": "1000001"}},
                    }
                },
                {
                    "properties": {
                        "housenumber": "1",
                        "street": "COMPLEX PLAZA",
                        "postalcode": "10001",
                        "addendum": {"pad": {"bbl": "1000010002", "bin": "1000002"}},
                    }
                },
            ]
        }
        result = reconcile_geosearch(facility, payload)
        self.assertEqual(result["status"], "UNRESOLVED_MULTIPLE_PAD_PROPERTIES")
        self.assertIsNone(result["bbl"])


if __name__ == "__main__":
    unittest.main()
