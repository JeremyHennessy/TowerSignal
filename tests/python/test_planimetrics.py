import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.fetch import SourceFetchError
from towersignal.planimetrics import (
    DATASET_ID,
    EXPECTED_FEATURE_CODE,
    FEATURE_IDENTITY_BASIS,
    FILTERED_QUERY_LIMIT,
    MATCH_BASIS,
    SELECT_FIELDS,
    SUB_FEATURE_DOMAIN,
    SUB_FEATURE_DOMAIN_SOURCE_URL,
    fetch_planimetric_towers_by_bin,
    normalize_bin,
    normalize_planimetric_row,
)


GEOMETRY = {
    "type": "MultiPolygon",
    "coordinates": [[[[-73.99, 40.75], [-73.9899, 40.75], [-73.9899, 40.7501], [-73.99, 40.75]]]],
}


def row(*, globalid="A", source_id="0.0", bin_value="1015862", sub_feature="212000", status="Unchanged"):
    return {
        "the_geom": GEOMETRY,
        "source_id": source_id,
        "feature_co": EXPECTED_FEATURE_CODE,
        "sub_featur": sub_feature,
        "bin": bin_value,
        "status": status,
        "globalid": globalid,
    }


class PlanimetricTests(unittest.TestCase):
    def test_bin_normalization_is_strict(self):
        self.assertEqual(normalize_bin("1015862"), "1015862")
        self.assertEqual(normalize_bin("1015862.0"), "1015862")
        self.assertIsNone(normalize_bin("101-5862"))
        self.assertIsNone(normalize_bin("BIN 1015862"))

    def test_normalize_preserves_public_fields_and_authoritative_roof_level(self):
        record = normalize_planimetric_row(row(globalid="{ABC-123}", source_id="12345", sub_feature="212000"))
        self.assertEqual(record["source_id"], "12345")
        self.assertEqual(record["global_id"], "{ABC-123}")
        self.assertEqual(record["bin"], "1015862")
        self.assertEqual(record["feature_code"], "2120")
        self.assertEqual(record["sub_feature_code"], "212000")
        self.assertEqual(record["location_level"], "ROOF_LEVEL")
        self.assertEqual(record["status"], "Unchanged")
        self.assertEqual(record["geometry"], GEOMETRY)
        self.assertEqual(record["match_basis"], MATCH_BASIS)
        self.assertEqual(record["feature_identity_basis"], FEATURE_IDENTITY_BASIS)
        self.assertEqual(record["imagery_year"], 2022)

    def test_ground_level_code_is_source_domain_not_inference(self):
        record = normalize_planimetric_row(row(sub_feature="212010"))
        self.assertEqual(record["location_level"], "GROUND_LEVEL")
        self.assertEqual(SUB_FEATURE_DOMAIN, {"212000": "ROOF_LEVEL", "212010": "GROUND_LEVEL"})
        self.assertIn("Cooling_Towers_2022/FeatureServer/3", SUB_FEATURE_DOMAIN_SOURCE_URL)

    def test_unexpected_sub_feature_code_fails_closed(self):
        with self.assertRaises(SourceFetchError):
            normalize_planimetric_row(row(sub_feature="212099"))

    def test_missing_sub_feature_code_fails_closed(self):
        with self.assertRaises(SourceFetchError):
            normalize_planimetric_row(row(sub_feature=None))

    def test_unexpected_feature_code_fails_closed(self):
        source = row()
        source["feature_co"] = "9999"
        with self.assertRaises(SourceFetchError):
            normalize_planimetric_row(source)

    def test_fetch_queries_only_requested_bins_and_groups_features_by_exact_bin(self):
        rows = [
            row(globalid="A", sub_feature="212000", status="Unchanged"),
            row(globalid="B", sub_feature="212010", status="New"),
        ]
        with patch("towersignal.planimetrics.fetch_count", return_value=82300) as count_mock, \
             patch("towersignal.planimetrics.fetch_metadata", return_value={"name": "Planimetric", "source_last_updated_at": "2025-12-04T00:00:00Z"}), \
             patch("towersignal.planimetrics.fetch_where", return_value=rows) as where_mock:
            by_bin, metadata = fetch_planimetric_towers_by_bin(["1015862", None, "1015862"])

        count_mock.assert_called_once_with(DATASET_ID)
        where_mock.assert_called_once_with(
            DATASET_ID,
            "bin in (1015862)",
            order_by="bin,globalid",
            select=SELECT_FIELDS,
        )
        self.assertEqual(len(by_bin["1015862"]), 2)
        self.assertEqual(metadata["requested_bin_count"], 1)
        self.assertEqual(metadata["matched_bin_count"], 1)
        self.assertEqual(metadata["matched_feature_count"], 2)
        self.assertEqual(metadata["source_record_count"], 82300)
        self.assertEqual(metadata["feature_identity_basis"], FEATURE_IDENTITY_BASIS)
        self.assertEqual(metadata["sub_feature_domain"], SUB_FEATURE_DOMAIN)
        self.assertEqual(metadata["location_level_counts"], {"ROOF_LEVEL": 1, "GROUND_LEVEL": 1})

    def test_duplicate_source_id_is_allowed_when_globalids_are_unique(self):
        rows = [row(globalid="A"), row(globalid="B")]
        with patch("towersignal.planimetrics.fetch_count", return_value=2), \
             patch("towersignal.planimetrics.fetch_metadata", return_value={"name": "Planimetric", "source_last_updated_at": None}), \
             patch("towersignal.planimetrics.fetch_where", return_value=rows):
            by_bin, _ = fetch_planimetric_towers_by_bin(["1015862"])
        self.assertEqual([feature["global_id"] for feature in by_bin["1015862"]], ["A", "B"])

    def test_duplicate_globalid_fails_closed(self):
        rows = [row(globalid="A", source_id="11"), row(globalid="A", source_id="12")]
        with patch("towersignal.planimetrics.fetch_count", return_value=2), \
             patch("towersignal.planimetrics.fetch_metadata", return_value={"name": "Planimetric", "source_last_updated_at": None}), \
             patch("towersignal.planimetrics.fetch_where", return_value=rows):
            with self.assertRaises(SourceFetchError):
                fetch_planimetric_towers_by_bin(["1015862"])

    def test_missing_globalid_fails_closed_even_when_source_id_exists(self):
        source = row()
        source["globalid"] = None
        with self.assertRaises(SourceFetchError):
            normalize_planimetric_row(source)

    def test_filtered_query_refuses_unrequested_bin(self):
        source = row(globalid="Z", source_id="99", bin_value="9999999")
        with patch("towersignal.planimetrics.fetch_count", return_value=1), \
             patch("towersignal.planimetrics.fetch_metadata", return_value={"name": "Planimetric", "source_last_updated_at": None}), \
             patch("towersignal.planimetrics.fetch_where", return_value=[source]):
            with self.assertRaises(SourceFetchError):
                fetch_planimetric_towers_by_bin(["1015862"])

    def test_filtered_query_refuses_possible_truncation(self):
        with patch("towersignal.planimetrics.fetch_count", return_value=FILTERED_QUERY_LIMIT), \
             patch("towersignal.planimetrics.fetch_metadata", return_value={"name": "Planimetric", "source_last_updated_at": None}), \
             patch("towersignal.planimetrics.fetch_where", return_value=[{}] * FILTERED_QUERY_LIMIT):
            with self.assertRaises(SourceFetchError):
                fetch_planimetric_towers_by_bin(["1015862"])

    def test_missing_geometry_fails_closed(self):
        source = row()
        source["the_geom"] = None
        with self.assertRaises(SourceFetchError):
            normalize_planimetric_row(source)


if __name__ == "__main__":
    unittest.main()
