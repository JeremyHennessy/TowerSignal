import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.fetch import SourceFetchError
from towersignal.planimetrics import (
    DATASET_ID,
    MATCH_BASIS,
    SELECT_FIELDS,
    fetch_planimetric_towers_by_bin,
    normalize_planimetric_row,
)


GEOMETRY = {
    "type": "MultiPolygon",
    "coordinates": [[[[-73.99, 40.75], [-73.9899, 40.75], [-73.9899, 40.7501], [-73.99, 40.75]]]],
}


class PlanimetricTests(unittest.TestCase):
    def test_normalize_preserves_all_public_fields_and_exact_match_provenance(self):
        record = normalize_planimetric_row({
            "the_geom": GEOMETRY,
            "source_id": "12345",
            "feature_co": "1000",
            "sub_featur": "2",
            "bin": "1015862",
            "status": "No change in 2022 collection",
            "globalid": "{ABC-123}",
        })
        self.assertEqual(record["source_id"], "12345")
        self.assertEqual(record["global_id"], "{ABC-123}")
        self.assertEqual(record["bin"], "1015862")
        self.assertEqual(record["feature_code"], "1000")
        self.assertEqual(record["sub_feature_code"], "2")
        self.assertEqual(record["status"], "No change in 2022 collection")
        self.assertEqual(record["geometry"], GEOMETRY)
        self.assertEqual(record["match_basis"], MATCH_BASIS)
        self.assertEqual(record["imagery_year"], 2022)

    def test_fetch_queries_only_requested_bins_and_groups_features_by_exact_bin(self):
        rows = [
            {
                "the_geom": GEOMETRY,
                "source_id": "11",
                "feature_co": "1000",
                "sub_featur": "2",
                "bin": "1015862",
                "status": "No change in 2022 collection",
                "globalid": "A",
            },
            {
                "the_geom": GEOMETRY,
                "source_id": "12",
                "feature_co": "1000",
                "sub_featur": "2",
                "bin": "1015862",
                "status": "Newly collected in 2022",
                "globalid": "B",
            },
        ]
        with patch("towersignal.planimetrics.fetch_count", return_value=82300) as count_mock, \
             patch("towersignal.planimetrics.fetch_metadata", return_value={"name": "Plan imetric", "source_last_updated_at": "2025-12-04T00:00:00Z"}), \
             patch("towersignal.planimetrics.fetch_where", return_value=rows) as where_mock:
            by_bin, metadata = fetch_planimetric_towers_by_bin(["1015862", None, "1015862"])

        count_mock.assert_called_once_with(DATASET_ID)
        where_mock.assert_called_once_with(
            DATASET_ID,
            "bin in (1015862)",
            order_by="bin,source_id",
            select=SELECT_FIELDS,
        )
        self.assertEqual(len(by_bin["1015862"]), 2)
        self.assertEqual(metadata["requested_bin_count"], 1)
        self.assertEqual(metadata["matched_bin_count"], 1)
        self.assertEqual(metadata["matched_feature_count"], 2)
        self.assertEqual(metadata["source_record_count"], 82300)

    def test_filtered_query_refuses_unrequested_bin(self):
        row = {
            "the_geom": GEOMETRY,
            "source_id": "99",
            "feature_co": "1000",
            "sub_featur": "2",
            "bin": "9999999",
            "status": "No change in 2022 collection",
            "globalid": "Z",
        }
        with patch("towersignal.planimetrics.fetch_count", return_value=1), \
             patch("towersignal.planimetrics.fetch_metadata", return_value={"name": "Plan imetric", "source_last_updated_at": None}), \
             patch("towersignal.planimetrics.fetch_where", return_value=[row]):
            with self.assertRaises(SourceFetchError):
                fetch_planimetric_towers_by_bin(["1015862"])

    def test_missing_geometry_fails_closed(self):
        with self.assertRaises(SourceFetchError):
            normalize_planimetric_row({"source_id": "1", "bin": "1015862", "the_geom": None})


if __name__ == "__main__":
    unittest.main()
