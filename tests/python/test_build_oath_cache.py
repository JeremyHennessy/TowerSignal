import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import build_oath_cache
from towersignal.oath import MATCH_BASIS


class BuildOathCacheTests(unittest.TestCase):
    @patch("build_oath_cache.validate_cache")
    @patch("build_oath_cache.write_cache")
    @patch("build_oath_cache.fetch_oath_cases")
    @patch("build_oath_cache.aggregate_inspections")
    @patch("build_oath_cache.normalize_registrations")
    @patch("build_oath_cache.validate_normalized")
    @patch("build_oath_cache.validate_sources")
    @patch("build_oath_cache.fetch_dataset")
    def test_refresh_requests_only_current_registered_system_summons(
        self,
        fetch_dataset_mock,
        validate_sources_mock,
        validate_normalized_mock,
        normalize_registrations_mock,
        aggregate_inspections_mock,
        fetch_oath_cases_mock,
        write_cache_mock,
        validate_cache_mock,
    ):
        registration_snapshot = SimpleNamespace(
            rows=[{"system_id": "CURRENT"}],
            dataset_id="y4fw-iqfr",
            name="registrations",
            retrieved_at="2026-09-08T00:00:00Z",
            source_record_count=5944,
            source_last_updated_at="2026-09-08T00:00:00Z",
        )
        inspection_snapshot = SimpleNamespace(
            rows=[{"system_id": "CURRENT"}, {"system_id": "HISTORICAL_ONLY"}],
            dataset_id="f9wb-g8mb",
            name="inspections",
            retrieved_at="2026-09-08T00:00:00Z",
            source_record_count=124243,
            source_last_updated_at="2026-09-08T00:00:00Z",
        )
        fetch_dataset_mock.side_effect = [registration_snapshot, inspection_snapshot]
        normalize_registrations_mock.return_value = ([{"system_id": "CURRENT"}], {})
        aggregate_inspections_mock.return_value = {
            "CURRENT": [{"violations": [{"summons_number": "0880000001"}]}],
            "HISTORICAL_ONLY": [{"violations": [{"summons_number": "0999999999"}]}],
        }
        fetch_oath_cases_mock.return_value = (
            {"0880000001": {"ticket_number": "0880000001", "match_basis": MATCH_BASIS}},
            {
                "dataset_id": "jz4z-kudi",
                "name": "OATH",
                "retrieved_at": "2026-09-08T00:00:00Z",
                "source_record_count": 59263,
                "source_last_updated_at": "2026-09-08T00:00:00Z",
                "source_query_scope": "fixture",
                "url": "https://data.cityofnewyork.us/City-Government/OATH-Hearings-Division-Case-Status/jz4z-kudi",
                "requested_ticket_count": 1,
                "matched_ticket_count": 1,
                "unmatched_ticket_count": 0,
                "matched_case_count": 1,
            },
        )
        validate_cache_mock.return_value = {
            "status": "PASS",
            "ticket_universe": {"count": 1, "sha256": "0" * 64},
            "cases_by_ticket": {"0880000001": {}},
            "match_ratio": 1.0,
            "size_bytes": 100,
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            build_oath_cache.build(Path(temp_dir) / "oath-cache.json.gz")

        fetch_oath_cases_mock.assert_called_once_with({"0880000001"})
        self.assertNotIn("0999999999", fetch_oath_cases_mock.call_args.args[0])
        write_cache_mock.assert_called_once()
        validate_cache_mock.assert_called_once()
        validate_sources_mock.assert_called_once()
        validate_normalized_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
