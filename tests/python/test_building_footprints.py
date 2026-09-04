import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.building_footprints import (
    DATASET_ID,
    FILTERED_QUERY_LIMIT,
    MATCH_BASIS,
    SELECT_FIELDS,
    feature_identity,
    fetch_building_footprints_by_bin,
    normalize_building_footprint_row,
)
from towersignal.fetch import SourceFetchError


GEOMETRY = {
    "type": "MultiPolygon",
    "coordinates": [[[[-73.99, 40.75], [-73.9898, 40.75], [-73.9898, 40.7502], [-73.99, 40.75]]]],
}


class BuildingFootprintTests(unittest.TestCase):
    def test_normalize_preserves_roof_context_and_exact_match_provenance(self):
        record = normalize_building_footprint_row({
            "the_geom": GEOMETRY,
            "name": "Example Building",
            "bin": "1051442.0",
            "doitt_id": "123456",
            "shape_area": "4000.5",
            "base_bbl": "1012340056",
            "objectid": "789",
            "construction_year": "1964",
            "feature_code": "2100",
            "geom_source": "Photogrammetric",
            "ground_elevation": "42.5",
            "height_roof": "133.75",
            "last_edited_date": "2026-08-30T12:00:00.000",
            "last_status_type": "Constructed",
            "mappluto_bbl": "1012340056",
        })
        self.assertEqual(record["bin"], "1051442")
        self.assertEqual(record["doitt_id"], "123456")
        self.assertEqual(record["object_id"], "789")
        self.assertEqual(record["shape_area"], 4000.5)
        self.assertEqual(record["construction_year"], 1964)
        self.assertEqual(record["geometry_source"], "Photogrammetric")
        self.assertEqual(record["ground_elevation_ft"], 42.5)
        self.assertEqual(record["height_roof_ft"], 133.75)
        self.assertEqual(record["geometry"], GEOMETRY)
        self.assertEqual(record["match_basis"], MATCH_BASIS)
        self.assertEqual(record["feature_identity_basis"], "DOITT_ID")
        self.assertEqual(feature_identity(record), "DOITT:123456")

    def test_objectid_is_allowed_as_current_feature_identity_fallback(self):
        record = normalize_building_footprint_row({
            "the_geom": GEOMETRY,
            "bin": "1051442",
            "doitt_id": None,
            "objectid": "789",
        })
        self.assertEqual(record["feature_identity_basis"], "OBJECTID")
        self.assertEqual(feature_identity(record), "OBJECTID:789")

    def test_missing_feature_identity_fails_closed(self):
        with self.assertRaises(SourceFetchError):
            normalize_building_footprint_row({"the_geom": GEOMETRY, "bin": "1051442"})

    def test_fetch_queries_only_requested_bins_and_groups_current_footprints(self):
        rows = [
            {"the_geom": GEOMETRY, "bin": "1051442", "doitt_id": "1", "objectid": "11"},
            {"the_geom": GEOMETRY, "bin": "1051442", "doitt_id": "2", "objectid": "12"},
        ]
        with patch("towersignal.building_footprints.fetch_count", return_value=1083016), \
             patch("towersignal.building_footprints.fetch_metadata", return_value={"name": "BUILDING", "source_last_updated_at": "2026-09-01T00:00:00Z"}), \
             patch("towersignal.building_footprints.fetch_where", return_value=rows) as where_mock:
            by_bin, metadata = fetch_building_footprints_by_bin(["1051442", None, "1051442"])

        where_mock.assert_called_once_with(
            DATASET_ID,
            "bin in (1051442)",
            order_by="bin,doitt_id,objectid",
            select=SELECT_FIELDS,
        )
        self.assertEqual(len(by_bin["1051442"]), 2)
        self.assertEqual(metadata["requested_bin_count"], 1)
        self.assertEqual(metadata["matched_bin_count"], 1)
        self.assertEqual(metadata["matched_feature_count"], 2)
        self.assertEqual(metadata["source_record_count"], 1083016)

    def test_duplicate_feature_identity_fails_closed(self):
        rows = [
            {"the_geom": GEOMETRY, "bin": "1051442", "doitt_id": "1", "objectid": "11"},
            {"the_geom": GEOMETRY, "bin": "1051442", "doitt_id": "1", "objectid": "12"},
        ]
        with patch("towersignal.building_footprints.fetch_count", return_value=2), \
             patch("towersignal.building_footprints.fetch_metadata", return_value={"name": "BUILDING", "source_last_updated_at": None}), \
             patch("towersignal.building_footprints.fetch_where", return_value=rows):
            with self.assertRaises(SourceFetchError):
                fetch_building_footprints_by_bin(["1051442"])

    def test_filtered_query_refuses_unrequested_bin(self):
        row = {"the_geom": GEOMETRY, "bin": "9999999", "doitt_id": "1", "objectid": "11"}
        with patch("towersignal.building_footprints.fetch_count", return_value=1), \
             patch("towersignal.building_footprints.fetch_metadata", return_value={"name": "BUILDING", "source_last_updated_at": None}), \
             patch("towersignal.building_footprints.fetch_where", return_value=[row]):
            with self.assertRaises(SourceFetchError):
                fetch_building_footprints_by_bin(["1051442"])

    def test_filtered_query_refuses_possible_truncation(self):
        with patch("towersignal.building_footprints.fetch_count", return_value=FILTERED_QUERY_LIMIT), \
             patch("towersignal.building_footprints.fetch_metadata", return_value={"name": "BUILDING", "source_last_updated_at": None}), \
             patch("towersignal.building_footprints.fetch_where", return_value=[{}] * FILTERED_QUERY_LIMIT):
            with self.assertRaises(SourceFetchError):
                fetch_building_footprints_by_bin(["1051442"])

    def test_missing_geometry_fails_closed(self):
        with self.assertRaises(SourceFetchError):
            normalize_building_footprint_row({"bin": "1051442", "doitt_id": "1", "the_geom": None})


if __name__ == "__main__":
    unittest.main()
