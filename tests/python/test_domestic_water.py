import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.domestic_water import (
    COMPLIANCE_DATASET_ID,
    MATCH_BASIS,
    SELF_REPORT_DATASET_ID,
    WATER_TANK_LAYER_URL,
    WATER_TANK_LOCATION_BASIS,
    fetch_dwt_compliance_by_bin,
    fetch_dwt_self_reports_by_bin,
    fetch_planimetric_water_tanks_by_bin,
    normalize_arcgis_polygon,
    normalize_compliance_row,
    normalize_self_report_row,
    normalize_water_tank_feature,
    summarize_domestic_water,
)
from towersignal.fetch import SourceFetchError


CLOCKWISE_RING = [
    [-73.9900, 40.7500],
    [-73.9900, 40.7501],
    [-73.9899, 40.7501],
    [-73.9899, 40.7500],
    [-73.9900, 40.7500],
]
COUNTERCLOCKWISE_HOLE = [
    [-73.98998, 40.75002],
    [-73.98992, 40.75002],
    [-73.98992, 40.75008],
    [-73.98998, 40.75008],
    [-73.98998, 40.75002],
]
SECOND_CLOCKWISE_RING = [
    [-73.9910, 40.7510],
    [-73.9910, 40.7511],
    [-73.9909, 40.7511],
    [-73.9909, 40.7510],
    [-73.9910, 40.7510],
]


def layer_metadata():
    return {
        "name": "WATER_TANK",
        "globalIdField": "GlobalID",
        "fields": [
            {"name": "BIN", "alias": "BIN"},
            {"name": "GlobalID", "alias": "GlobalID"},
            {"name": "SOURCE_ID", "alias": "SOURCE_ID"},
            {"name": "FEATURE_CODE", "alias": "FEATURE_CODE"},
            {"name": "STATUS", "alias": "STATUS"},
            {"name": "BASE_ELEV", "alias": "BASE ELEVATION"},
            {"name": "TOP_ELEV", "alias": "TOP ELEVATION"},
            {"name": "HEIGHT", "alias": "HEIGHT"},
        ],
        "editingInfo": {"lastEditDate": 1780000000000},
    }


def tank_feature(*, bin_value="1089811", global_id="WT-1", rings=None):
    return {
        "attributes": {
            "BIN": bin_value,
            "GlobalID": global_id,
            "SOURCE_ID": "901",
            "FEATURE_CODE": "2080",
            "STATUS": "Unchanged",
            "BASE_ELEV": 141.5,
            "TOP_ELEV": 157.0,
            "HEIGHT": 15.5,
        },
        "geometry": {"rings": rings or [CLOCKWISE_RING]},
    }


class DomesticWaterTests(unittest.TestCase):
    def test_single_ring_arcgis_polygon_becomes_geojson_polygon(self):
        geometry = normalize_arcgis_polygon({"rings": [CLOCKWISE_RING]})
        self.assertEqual(geometry["type"], "Polygon")
        self.assertEqual(geometry["coordinates"], [CLOCKWISE_RING])

    def test_multipart_arcgis_polygon_assigns_hole_and_becomes_multipolygon(self):
        geometry = normalize_arcgis_polygon({
            "rings": [CLOCKWISE_RING, COUNTERCLOCKWISE_HOLE, SECOND_CLOCKWISE_RING]
        })
        self.assertEqual(geometry["type"], "MultiPolygon")
        self.assertEqual(len(geometry["coordinates"]), 2)
        self.assertEqual(geometry["coordinates"][0][0], CLOCKWISE_RING)
        self.assertEqual(geometry["coordinates"][0][1], COUNTERCLOCKWISE_HOLE)
        self.assertEqual(geometry["coordinates"][1][0], SECOND_CLOCKWISE_RING)

    def test_invalid_arcgis_geometry_fails_closed(self):
        with self.assertRaises(SourceFetchError):
            normalize_arcgis_polygon({"rings": [[[0, 0], [1, 1], [0, 0]]]})

    def test_water_tank_feature_preserves_exact_bin_elevation_and_roof_capture_provenance(self):
        record = normalize_water_tank_feature(tank_feature())
        self.assertEqual(record["bin"], "1089811")
        self.assertEqual(record["global_id"], "WT-1")
        self.assertEqual(record["source_id"], "901")
        self.assertEqual(record["base_elevation_ft"], 141.5)
        self.assertEqual(record["top_elevation_ft"], 157.0)
        self.assertEqual(record["height_ft"], 15.5)
        self.assertEqual(record["location_level"], "ROOF_LEVEL")
        self.assertEqual(record["location_basis"], WATER_TANK_LOCATION_BASIS)
        self.assertEqual(record["match_basis"], MATCH_BASIS)
        self.assertEqual(record["imagery_year"], 2022)

    def test_water_tank_feature_requires_bin_and_globalid(self):
        bad_bin = tank_feature(bin_value="BIN 1089811")
        with self.assertRaises(SourceFetchError):
            normalize_water_tank_feature(bad_bin)
        missing_global = tank_feature()
        missing_global["attributes"]["GlobalID"] = None
        with self.assertRaises(SourceFetchError):
            normalize_water_tank_feature(missing_global)

    def test_arcgis_fetch_uses_dynamic_exact_bin_query_and_count(self):
        request_urls = []

        def fake_request(url):
            request_urls.append(url)
            if url.startswith(WATER_TANK_LAYER_URL + "?"):
                return layer_metadata()
            if "returnCountOnly=true" in url:
                return {"count": 12345}
            if "/query?" in url:
                return {"features": [tank_feature()], "exceededTransferLimit": False}
            raise AssertionError(url)

        with patch("towersignal.domestic_water._request_json", side_effect=fake_request):
            by_bin, metadata = fetch_planimetric_water_tanks_by_bin(["1089811", "1089811", None])

        self.assertEqual(len(by_bin["1089811"]), 1)
        self.assertEqual(metadata["source_record_count"], 12345)
        self.assertEqual(metadata["requested_bin_count"], 1)
        self.assertEqual(metadata["matched_bin_count"], 1)
        self.assertEqual(metadata["matched_feature_count"], 1)
        query_url = next(url for url in request_urls if "/query?" in url and "returnCountOnly" not in url)
        self.assertIn("BIN+IN+%281089811%29", query_url)
        self.assertIn("outSR=4326", query_url)
        self.assertIn("returnGeometry=true", query_url)

    def test_arcgis_transfer_limit_fails_closed(self):
        def fake_request(url):
            if url.startswith(WATER_TANK_LAYER_URL + "?"):
                return layer_metadata()
            if "returnCountOnly=true" in url:
                return {"count": 2}
            return {"features": [tank_feature()], "exceededTransferLimit": True}

        with patch("towersignal.domestic_water._request_json", side_effect=fake_request):
            with self.assertRaises(SourceFetchError):
                fetch_planimetric_water_tanks_by_bin(["1089811"])

    def test_arcgis_duplicate_globalid_fails_closed(self):
        def fake_request(url):
            if url.startswith(WATER_TANK_LAYER_URL + "?"):
                return layer_metadata()
            if "returnCountOnly=true" in url:
                return {"count": 2}
            return {
                "features": [tank_feature(global_id="DUP"), tank_feature(global_id="DUP")],
                "exceededTransferLimit": False,
            }

        with patch("towersignal.domestic_water._request_json", side_effect=fake_request):
            with self.assertRaises(SourceFetchError):
                fetch_planimetric_water_tanks_by_bin(["1089811"])

    def test_arcgis_unexpected_bin_fails_closed(self):
        def fake_request(url):
            if url.startswith(WATER_TANK_LAYER_URL + "?"):
                return layer_metadata()
            if "returnCountOnly=true" in url:
                return {"count": 1}
            return {"features": [tank_feature(bin_value="9999999")], "exceededTransferLimit": False}

        with patch("towersignal.domestic_water._request_json", side_effect=fake_request):
            with self.assertRaises(SourceFetchError):
                fetch_planimetric_water_tanks_by_bin(["1089811"])

    def test_compliance_row_normalization_preserves_regulatory_fields(self):
        record = normalize_compliance_row({
            "bin": "1089811",
            "house": "16",
            "street_name": "E 39 ST",
            "zip_code": "10016",
            "borough": "Manhattan",
            "status": "Active",
            "number_of_dwt": "2",
            "activity_type": "Inspection",
            "activity_year": "2026",
            "violation_code": "DWT-1",
            "law_section": "81.07",
            "violation_text": "Example source text",
            "compliance_year": "2026",
            "date_of_occurrence": "2026-05-10T00:00:00.000",
            "summons_number": "123456789",
        })
        self.assertEqual(record["bin"], "1089811")
        self.assertEqual(record["number_of_dwt"], 2)
        self.assertEqual(record["activity_type"], "Inspection")
        self.assertEqual(record["violation_code"], "DWT-1")
        self.assertEqual(record["summons_number"], "123456789")
        self.assertEqual(record["match_basis"], MATCH_BASIS)

    def test_self_report_normalization_preserves_optional_condition_and_water_quality_fields(self):
        record = normalize_self_report_row({
            "bin": "1089811",
            "reporting_year": "2026",
            "tank_num": "1",
            "inspection_by_firm": "Example Inspector",
            "inspection_date": "2026-06-01T00:00:00.000",
            "si_result_sediment": "P",
            "si_result_biological_growth": "A",
            "si_result_debris_insects": "N",
            "si_result_rodent_bird": "N",
            "sample_collected": "Y",
            "coliform": "A",
            "ecoli": "A",
            "meet_standards": "Y",
            "latitude": "40.75",
            "longitude": "-73.99",
        })
        self.assertEqual(record["tank_num"], "1")
        self.assertEqual(record["sediment_result"], "P")
        self.assertEqual(record["biological_growth_result"], "A")
        self.assertEqual(record["sample_collected"], "Y")
        self.assertEqual(record["coliform"], "A")
        self.assertEqual(record["meet_standards"], "Y")
        self.assertEqual(record["latitude"], 40.75)
        self.assertEqual(record["longitude"], -73.99)

    def test_socrata_fetches_use_exact_quoted_bin_filters(self):
        compliance_rows = [{"bin": "1089811", "activity_year": "2026"}]
        self_report_rows = [{"bin": "1089811", "reporting_year": "2026", "tank_num": "1"}]
        with patch("towersignal.domestic_water.fetch_count", return_value=100), \
             patch("towersignal.domestic_water.fetch_metadata", return_value={"name": "DWT", "source_last_updated_at": None}), \
             patch("towersignal.domestic_water.fetch_where", side_effect=[compliance_rows, self_report_rows]) as where_mock:
            compliance, compliance_meta = fetch_dwt_compliance_by_bin(["1089811"])
            self_reports, self_report_meta = fetch_dwt_self_reports_by_bin(["1089811"])

        self.assertEqual(compliance["1089811"][0]["activity_year"], "2026")
        self.assertEqual(self_reports["1089811"][0]["tank_num"], "1")
        self.assertEqual(compliance_meta["dataset_id"], COMPLIANCE_DATASET_ID)
        self.assertEqual(self_report_meta["dataset_id"], SELF_REPORT_DATASET_ID)
        self.assertEqual(where_mock.call_args_list[0].args[1], "bin in ('1089811')")
        self.assertEqual(where_mock.call_args_list[1].args[1], "bin in ('1089811')")

    def test_domestic_water_summary_keeps_evidence_families_separate(self):
        summary = summarize_domestic_water(
            [normalize_water_tank_feature(tank_feature())],
            [
                normalize_compliance_row({
                    "bin": "1089811",
                    "status": "Active",
                    "number_of_dwt": "2",
                    "activity_type": "Audit",
                    "activity_year": "2026",
                    "compliance_year": "2026",
                    "violation_code": "V1",
                })
            ],
            [
                normalize_self_report_row({
                    "bin": "1089811",
                    "reporting_year": "2026",
                    "inspection_date": "2026-06-01",
                    "meet_standards": "Y",
                })
            ],
        )
        self.assertEqual(summary["planimetric_tank_count"], 1)
        self.assertEqual(summary["compliance_record_count"], 1)
        self.assertEqual(summary["self_report_record_count"], 1)
        self.assertEqual(summary["latest_reported_dwt_count"], 2)
        self.assertEqual(summary["violation_record_count"], 1)
        self.assertEqual(summary["latest_self_report_meet_standards"], "Y")


if __name__ == "__main__":
    unittest.main()
