import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.fetch import SourceFetchError
from towersignal.oath import fetch_oath_cases


class OathBatchFetchTests(unittest.TestCase):
    @patch("towersignal.oath.fetch_metadata", return_value={"name": "OATH test", "source_last_updated_at": "2026-09-06T00:00:00Z"})
    @patch("towersignal.oath.fetch_where")
    def test_parallel_batches_preserve_exact_ticket_identity(self, fetch_where_mock, _fetch_metadata_mock):
        requested = ["0880900460", "0880900470", "0880900480", "0880900490"]

        def fetch_side_effect(
            dataset_id,
            where,
            order_by=None,
            select=None,
            api_root=None,
            request_retries=None,
            request_timeout=None,
        ):
            self.assertEqual(dataset_id, "jz4z-kudi")
            self.assertIsNone(order_by)
            self.assertIsNotNone(select)
            self.assertEqual(request_retries, 1)
            self.assertEqual(request_timeout, 30)
            tickets = re.findall(r"'([^']+)'", where)
            return [{"ticket_number": ticket, "hearing_status": "HEARING COMPLETED"} for ticket in tickets]

        fetch_where_mock.side_effect = fetch_side_effect
        cases, metadata = fetch_oath_cases(requested, batch_size=2, max_workers=2)

        self.assertEqual(set(cases), set(requested))
        self.assertEqual(metadata["requested_ticket_count"], 4)
        self.assertEqual(metadata["matched_ticket_count"], 4)
        self.assertEqual(metadata["unmatched_ticket_count"], 0)
        self.assertEqual(metadata["source_record_count"], 4)
        self.assertEqual(metadata["source_query_scope"], "Exact ticket_number queries for summonses present in NYC Cooling Tower System Inspection Results")
        self.assertEqual(fetch_where_mock.call_count, 2)

        queried_tickets = []
        for call in fetch_where_mock.call_args_list:
            queried_tickets.extend(re.findall(r"'([^']+)'", call.args[1]))
        self.assertCountEqual(queried_tickets, requested)

    @patch("towersignal.oath.time.sleep")
    @patch("towersignal.oath.fetch_metadata", return_value={"name": "OATH test", "source_last_updated_at": "2026-09-06T00:00:00Z"})
    @patch("towersignal.oath.fetch_where")
    def test_rate_limited_batch_retries_without_losing_exact_identity(self, fetch_where_mock, _fetch_metadata_mock, sleep_mock):
        requested = ["0880900460", "0880900470"]
        calls = 0

        def fetch_side_effect(
            dataset_id,
            where,
            order_by=None,
            select=None,
            api_root=None,
            request_retries=None,
            request_timeout=None,
        ):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise SourceFetchError("HTTP Error 429: Too Many Requests")
            tickets = re.findall(r"'([^']+)'", where)
            return [{"ticket_number": ticket, "hearing_status": "HEARING COMPLETED"} for ticket in tickets]

        fetch_where_mock.side_effect = fetch_side_effect
        cases, metadata = fetch_oath_cases(requested, batch_size=2, max_workers=1)

        self.assertEqual(set(cases), set(requested))
        self.assertEqual(metadata["matched_ticket_count"], 2)
        self.assertEqual(fetch_where_mock.call_count, 2)
        sleep_mock.assert_called_once_with(10)

    @patch("towersignal.oath.time.sleep")
    @patch("towersignal.oath.fetch_metadata", return_value={"name": "OATH test", "source_last_updated_at": "2026-09-06T00:00:00Z"})
    @patch("towersignal.oath.fetch_where")
    def test_timeout_batch_retries_without_losing_exact_identity(self, fetch_where_mock, _fetch_metadata_mock, sleep_mock):
        requested = ["0880900460", "0880900470"]
        calls = 0

        def fetch_side_effect(
            dataset_id,
            where,
            order_by=None,
            select=None,
            api_root=None,
            request_retries=None,
            request_timeout=None,
        ):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise SourceFetchError("The read operation timed out")
            tickets = re.findall(r"'([^']+)'", where)
            return [{"ticket_number": ticket, "hearing_status": "HEARING COMPLETED"} for ticket in tickets]

        fetch_where_mock.side_effect = fetch_side_effect
        cases, metadata = fetch_oath_cases(requested, batch_size=2, max_workers=1)

        self.assertEqual(set(cases), set(requested))
        self.assertEqual(metadata["matched_ticket_count"], 2)
        self.assertEqual(fetch_where_mock.call_count, 2)
        sleep_mock.assert_called_once_with(10)

    @patch("towersignal.oath.fetch_metadata", return_value={"name": "OATH test", "source_last_updated_at": "2026-09-06T00:00:00Z"})
    @patch("towersignal.oath.fetch_where")
    def test_large_ticket_set_uses_stable_cooling_tower_agency_slice(self, fetch_where_mock, _fetch_metadata_mock):
        requested = [f"{index:010d}" for index in range(1000)]
        extra_agency_ticket = "9999999999"

        def fetch_side_effect(
            dataset_id,
            where,
            order_by=None,
            select=None,
            api_root=None,
            request_retries=None,
            request_timeout=None,
            limit=50000,
            offset=None,
        ):
            self.assertEqual(dataset_id, "jz4z-kudi")
            self.assertIn("COOLING TOWERS - DOHMH", where)
            self.assertEqual(request_retries, 4)
            self.assertEqual(request_timeout, 30)
            if select == "count(*) as count":
                self.assertEqual(limit, 1)
                self.assertIsNone(order_by)
                self.assertIsNone(offset)
                return [{"count": str(len(requested) + 1)}]
            self.assertEqual(order_by, "ticket_number")
            self.assertEqual(limit, 50000)
            self.assertEqual(offset, 0)
            return [
                *({"ticket_number": ticket, "hearing_status": "HEARING COMPLETED"} for ticket in requested),
                {"ticket_number": extra_agency_ticket, "hearing_status": "HEARING COMPLETED"},
            ]

        fetch_where_mock.side_effect = fetch_side_effect
        cases, metadata = fetch_oath_cases(requested)

        self.assertEqual(set(cases), set(requested))
        self.assertNotIn(extra_agency_ticket, cases)
        self.assertEqual(metadata["requested_ticket_count"], len(requested))
        self.assertEqual(metadata["matched_ticket_count"], len(requested))
        self.assertEqual(metadata["source_record_count"], len(requested) + 1)
        self.assertIn("issuing_agency='COOLING TOWERS - DOHMH'", metadata["source_query_scope"])
        self.assertEqual(fetch_where_mock.call_count, 3)

    @patch("towersignal.oath.fetch_metadata", return_value={"name": "OATH test", "source_last_updated_at": "2026-09-06T00:00:00Z"})
    @patch("towersignal.oath.fetch_where")
    def test_large_ticket_set_restarts_when_agency_slice_changes_mid_scan(self, fetch_where_mock, _fetch_metadata_mock):
        requested = [f"{index:010d}" for index in range(1000)]
        stable_rows = [{"ticket_number": ticket, "hearing_status": "HEARING COMPLETED"} for ticket in requested]
        responses = [
            [{"count": "1001"}],
            stable_rows,
            [{"count": "1000"}],
            [{"count": "1000"}],
            stable_rows,
            [{"count": "1000"}],
        ]
        fetch_where_mock.side_effect = responses

        cases, metadata = fetch_oath_cases(requested)

        self.assertEqual(set(cases), set(requested))
        self.assertEqual(metadata["source_record_count"], 1000)
        self.assertEqual(metadata["matched_ticket_count"], 1000)
        self.assertEqual(fetch_where_mock.call_count, 6)

    @patch("towersignal.oath.fetch_where")
    def test_large_ticket_set_fails_closed_when_agency_slice_never_stabilizes(self, fetch_where_mock):
        requested = [f"{index:010d}" for index in range(1000)]
        rows = [{"ticket_number": ticket, "hearing_status": "HEARING COMPLETED"} for ticket in requested]
        fetch_where_mock.side_effect = [
            [{"count": "1001"}], rows, [{"count": "1000"}],
            [{"count": "1000"}], rows[:-1], [{"count": "999"}],
        ]

        with self.assertRaisesRegex(SourceFetchError, "did not stabilize"):
            fetch_oath_cases(requested)

        self.assertEqual(fetch_where_mock.call_count, 6)


if __name__ == "__main__":
    unittest.main()
