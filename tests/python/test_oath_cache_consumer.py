import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import build_data
from towersignal.oath import MATCH_BASIS
from towersignal.oath_cache import build_cache_payload, write_cache
from towersignal.oath_cache_consumer import cases_and_metadata_for_current_tickets


class OathCacheConsumerTests(unittest.TestCase):
    def _write_cache(self, path: Path, *, generated_at: str | None = None) -> None:
        tickets = {"0880000001", "0880000002", "0880000003"}
        cases = {
            "0880000001": {"ticket_number": "0880000001", "match_basis": MATCH_BASIS},
            "0880000002": {"ticket_number": "0880000002", "match_basis": MATCH_BASIS},
        }
        inspection = SimpleNamespace(
            dataset_id="f9wb-g8mb",
            name="inspection fixture",
            retrieved_at="2026-09-08T00:00:00Z",
            source_record_count=123456,
            source_last_updated_at="2026-09-08T00:00:00Z",
        )
        oath_metadata = {
            "dataset_id": "jz4z-kudi",
            "name": "OATH fixture",
            "retrieved_at": "2026-09-08T00:00:00Z",
            "source_record_count": 59263,
            "source_last_updated_at": "2026-09-08T00:00:00Z",
            "source_query_scope": "fixture exact summons lifecycle",
            "url": "https://data.cityofnewyork.us/City-Government/OATH-Hearings-Division-Case-Status/jz4z-kudi",
            "requested_ticket_count": 3,
            "matched_ticket_count": 2,
            "unmatched_ticket_count": 1,
            "matched_case_count": 2,
        }
        payload = build_cache_payload(
            inspection_snapshot=inspection,
            requested_tickets=tickets,
            cases_by_ticket=cases,
            oath_metadata=oath_metadata,
            generated_at=generated_at,
        )
        write_cache(path, payload)

    def test_consumer_intersects_to_current_product_tickets_and_recomputes_counts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "oath-cache.json.gz"
            self._write_cache(cache_path)

            cases, metadata, result = cases_and_metadata_for_current_tickets(
                cache_path,
                {"0880000001", "0880000003"},
                require_production_volume=False,
            )

            self.assertEqual(set(cases), {"0880000001"})
            self.assertEqual(metadata["requested_ticket_count"], 2)
            self.assertEqual(metadata["matched_ticket_count"], 1)
            self.assertEqual(metadata["unmatched_ticket_count"], 1)
            self.assertEqual(metadata["matched_case_count"], 1)
            self.assertEqual(metadata["cache_ticket_universe_count"], 3)
            self.assertEqual(result["status"], "PASS")

    def test_consumer_rejects_stale_verified_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "oath-cache.json.gz"
            stale = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat().replace("+00:00", "Z")
            self._write_cache(cache_path, generated_at=stale)

            with self.assertRaisesRegex(ValueError, "stale"):
                cases_and_metadata_for_current_tickets(
                    cache_path,
                    {"0880000001"},
                    max_age_days=2,
                    require_production_volume=False,
                )

    def test_build_entrypoint_excludes_non_current_system_inspection_tickets(self):
        inspections = {
            "CURRENT": [{"violations": [{"summons_number": "0880000001"}]}],
            "HISTORICAL_ONLY": [{"violations": [{"summons_number": "0999999999"}]}],
        }

        tickets = build_data.current_registered_system_summons(inspections, {"CURRENT"})

        self.assertEqual(tickets, {"0880000001"})


if __name__ == "__main__":
    unittest.main()
