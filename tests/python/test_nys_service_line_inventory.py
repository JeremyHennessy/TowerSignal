from __future__ import annotations

import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.nys_service_line_inventory import (  # noqa: E402
    SOURCE_FIELDS,
    NysServiceLineSourceError,
    _authoritative_metadata_fields,
    _bulk_csv_url,
    normalize_category,
    normalize_material,
    normalize_method,
    normalize_row,
    parse_location,
    service_address_id,
)


class NysServiceLineInventoryTests(unittest.TestCase):
    def test_known_material_variants_normalize_conservatively(self) -> None:
        self.assertEqual(normalize_material("Lead including lead-lined galvanized"), "LEAD")
        self.assertEqual(normalize_material("COPPER"), "COPPER")
        self.assertEqual(normalize_material("Unknown but could be lead"), "UNKNOWN_COULD_BE_LEAD")
        self.assertEqual(normalize_material("Mystery alloy supplied by owner"), "OTHER_RAW")

    def test_verification_methods_keep_unknown_text_as_other_raw(self) -> None:
        self.assertEqual(normalize_method("Records"), "RECORDS")
        self.assertEqual(normalize_method("Field Investigation"), "FIELD_INSPECTION")
        self.assertEqual(normalize_method("Predictive Modeling"), "STATISTICAL_MODEL")
        self.assertEqual(normalize_method("CCTV at curb box"), "OTHER_RAW")

    def test_category_source_error_is_not_treated_as_water_material(self) -> None:
        self.assertEqual(normalize_category("Err:508"), "SOURCE_ERROR")
        self.assertEqual(normalize_category("Lead"), "LEAD")
        self.assertEqual(normalize_category("Unknown - Lead Status Unknown"), "UNKNOWN_LEAD_STATUS")

    def test_address_key_is_deterministic_but_not_claimed_unique(self) -> None:
        first = service_address_id("Buffalo", "10 Main St", "14201")
        second = service_address_id("BUFFALO", "10 MAIN ST.", "14201-1234")
        self.assertEqual(first, second)
        self.assertTrue(str(first).startswith("nys-lsli-address-"))

    def test_nyc_locality_code_is_analysis_label_only(self) -> None:
        row = normalize_row(
            {
                "locality": "BK",
                "street_address": "100 Example Ave",
                "zip_code": "11201",
                "current_public_side_sl": "Copper",
                "customer_sl_material": "Lead including lead-lined galvanized",
                "public_sl_material": "Records",
                "customer_sl_material_1": "Field Inspection",
                "sl_category": "Lead",
                "location": "POINT (-73.99 40.69)",
            },
            source_row_ordinal=17,
        )
        self.assertEqual(row["source_row_ordinal"], 17)
        self.assertEqual(row["nyc_borough"], "BROOKLYN")
        self.assertEqual(row["public_material_normalized"], "COPPER")
        self.assertEqual(row["customer_material_normalized"], "LEAD")
        self.assertNotIn("pws_id", row)

    def test_point_geometry_parses_longitude_latitude(self) -> None:
        lat, lon = parse_location("POINT (-73.99 40.69)")
        self.assertAlmostEqual(lat or 0, 40.69)
        self.assertAlmostEqual(lon or 0, -73.99)
        self.assertEqual(parse_location("POINT (0 0)"), (None, None))

    def test_socrata_computed_region_columns_are_not_agency_schema(self) -> None:
        fields = (*SOURCE_FIELDS, ":@computed_region_9yqb_tdyd", ":@computed_region_43an_4dx5")
        self.assertEqual(_authoritative_metadata_fields(fields), SOURCE_FIELDS)
        with self.assertRaisesRegex(NysServiceLineSourceError, "authoritative schema drift"):
            _authoritative_metadata_fields((*SOURCE_FIELDS, "unexpected_agency_field"))

    def test_bulk_csv_explicitly_selects_only_authoritative_fields(self) -> None:
        query = parse_qs(urlparse(_bulk_csv_url(5_000_000)).query)
        self.assertEqual(query["$limit"], ["5000000"])
        select = query["$select"][0]
        for field in SOURCE_FIELDS:
            self.assertIn(f"{field} AS {field}", select)
        self.assertNotIn(":@computed_region_", select)


if __name__ == "__main__":
    unittest.main()
