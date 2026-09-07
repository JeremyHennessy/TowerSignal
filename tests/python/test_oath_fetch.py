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

    @patch("towersignal.oath.OATH_MIN_SPLIT_BATCH_SIZE", 2)
    @patch("towersignal.oath.time.sleep")
    @patch("towersignal.oath.fetch_metadata", return_value={"name": "OATH test", "source_last_updated_at": "2026-09-06T00:00:00Z"})
    @patch("towersignal.oath.fetch_where")
    def test_repeated_large_batch_timeout_splits_until_queries_succeed(
        self, fetch_where_mock, _fetch_metadata_mock, sleep_mock
    ):
        requested = [f"{index:010d}" for index in range(8)]
        calls_by_size = {}

        def fetch_side_effect(
            dataset_id,
            where,
            order_by=None,
            select=None,
            api_root=None,
            request_retries=None,
            request_timeout=None,
        ):
            tickets = re.findall(r"'([^']+)'", where)
            size = len(tickets)
            calls_by_size[size] = calls_by_size.get(size, 0) + 1
            if size > 2:
                raise SourceFetchError("The read operation timed out")
            return [{"ticket_number": ticket, "hearing_status": "HEARING COMPLETED"} for ticket in tickets]

        fetch_where_mock.side_effect = fetch_side_effect
        cases, metadata = fetch_oath_cases(requested, batch_size=8, max_workers=1)

        self.assertEqual(set(cases), set(requested))
        self.assertEqual(metadata["matched_ticket_count"], 8)
        self.assertEqual(calls_by_size[8], 2)
        self.assertEqual(calls_by_size[4], 4)
        self.assertEqual(calls_by_size[2], 4)
        self.assertEqual(sleep_mock.call_count, 3)

    @patch("towersignal.oath.OATH_MIN_SPLIT_BATCH_SIZE", 2)
    @patch("towersignal.oath.time.sleep")
    @patch("towersignal.oath.fetch_metadata", return_value={"name": "OATH test", "source_last_updated_at": "2026-09-06T00:00:00Z"})
    @patch("towersignal.oath.fetch_where")
    def test_smallest_timeout_batch_still_fails_closed(
        self, fetch_where_mock, _fetch_metadata_mock, sleep_mock
    ):
        requested = ["0880900460", "0880900470"]
        fetch_where_mock.side_effect = SourceFetchError("The read operation timed out")
        with self.assertRaises(SourceFetchError):
            fetch_oath_cases(requested, batch_size=2, max_workers=1)
        self.assertEqual(fetch_where_mock.call_count, 4)
        self.assertEqual(sleep_mock.call_count, 3)

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
            if select == "count(*) as count":
                self.assertEqual(request_retries, 4)
                self.assertEqual(request_timeout, 30)
                self.assertEqual(limit, 1)
                self.assertIsNone(order_by)
                self.assertIsNone(offset)
                return [{"count": str(len(requested) + 1)}]
            self.assertEqual(request_retries, 1)
            self.assertEqual(request_timeout, 20)
            self.assertEqual(order_by, "ticket_number")
            self.assertEqual(limit, 10000)
            self.assertIsNone(offset)
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

    @patch("towersignal.oath._fetch_exact_ticket_batch")
    @patch("towersignal.oath.fetch_metadata", return_value={"name": "OATH test", "source_last_updated_at": "2026-09-06T00:00:00Z"})
    @patch("towersignal.oath.fetch_where")
    def test_large_ticket_set_falls_back_to_exact_batches_when_agency_slice_never_stabilizes(
        self, fetch_where_mock, _fetch_metadata_mock, exact_batch_mock
    ):
        requested = [f"{index:010d}" for index in range(1000)]
        rows = [{"ticket_number": ticket, "hearing_status": "HEARING COMPLETED"} for ticket in requested]
        fetch_where_mock.side_effect = [
            [{"count": "1001"}], rows, [{"count": "1000"}],
            [{"count": "1000"}], rows[:-1], [{"count": "999"}],
        ]

        def exact_side_effect(batch):
            return batch, [{"ticket_number": ticket, "hearing_status": "HEARING COMPLETED"} for ticket in batch]

        exact_batch_mock.side_effect = exact_side_effect
        cases, metadata = fetch_oath_cases(requested)

        self.assertEqual(set(cases), set(requested))
        self.assertEqual(fetch_where_mock.call_count, 6)
        self.assertEqual(exact_batch_mock.call_count, 4)
        self.assertIn("fell back to exact ticket_number batches", metadata["source_query_scope"])
        self.assertEqual(metadata["source_record_count"], len(requested))

    @patch("towersignal.oath.validate_match_coverage")
    @patch("towersignal.oath.OATH_AGENCY_MIN_PAGE_SIZE", 1)
    @patch("towersignal.oath.OATH_AGENCY_PAGE_SIZE", 2)
    @patch("towersignal.oath.fetch_metadata", return_value={"name": "OATH test", "source_last_updated_at": "2026-09-06T00:00:00Z"})
    @patch("towersignal.oath.fetch_where")
    def test_large_ticket_set_uses_ticket_seek_cursor_between_pages(
        self, fetch_where_mock, _fetch_metadata_mock, _coverage_mock
    ):
        requested = ["0000000001", "0000000002", "0000000003"] + [f"9{index:09d}" for index in range(997)]
        fetch_where_mock.side_effect = [
            [{"count": "4"}],
            [
                {"ticket_number": "0000000001", "hearing_status": "HEARING COMPLETED"},
                {"ticket_number": "0000000002", "hearing_status": "HEARING COMPLETED"},
            ],
            [
                {"ticket_number": "0000000003", "hearing_status": "HEARING COMPLETED"},
                {"ticket_number": "9999999999", "hearing_status": "HEARING COMPLETED"},
            ],
            [],
            [{"count": "4"}],
        ]

        cases, metadata = fetch_oath_cases(requested)

        self.assertEqual(set(cases), {"0000000001", "0000000002", "0000000003"})
        self.assertEqual(metadata["source_record_count"], 4)
        second_page_where = fetch_where_mock.call_args_list[2].args[1]
        self.assertIn("ticket_number > '0000000002'", second_page_where)
        self.assertIsNone(fetch_where_mock.call_args_list[1].kwargs.get("offset"))


    @patch("towersignal.oath._fetch_exact_ticket_batch")
    @patch("towersignal.oath.fetch_metadata", return_value={"name": "OATH test", "source_last_updated_at": "2026-09-06T00:00:00Z"})
    @patch("towersignal.oath.fetch_where")
    def test_large_ticket_set_shrinks_agency_page_after_timeout_before_fallback(
        self, fetch_where_mock, _fetch_metadata_mock, exact_batch_mock
    ):
        requested = [f"{index:010d}" for index in range(1000)]
        page_limits = []
        count_calls = 0

        def side_effect(dataset_id, where, order_by=None, select=None, **kwargs):
            nonlocal count_calls
            if select == "count(*) as count":
                count_calls += 1
                return [{"count": "1000"}]
            page_limits.append(kwargs.get("limit"))
            if len(page_limits) == 1:
                raise SourceFetchError("The read operation timed out")
            return [{"ticket_number": ticket, "hearing_status": "HEARING COMPLETED"} for ticket in requested]

        fetch_where_mock.side_effect = side_effect
        cases, metadata = fetch_oath_cases(requested)

        self.assertEqual(set(cases), set(requested))
        self.assertEqual(page_limits, [10000, 5000])
        self.assertEqual(count_calls, 2)
        exact_batch_mock.assert_not_called()
        self.assertEqual(metadata["matched_ticket_count"], 1000)
        self.assertNotIn("fell back to exact ticket_number batches", metadata["source_query_scope"])

    @patch("towersignal.oath.OATH_AGENCY_PAGE_RETRIES", 2)
    @patch("towersignal.oath.OATH_AGENCY_MIN_PAGE_SIZE", 2)
    @patch("towersignal.oath.OATH_AGENCY_PAGE_SIZE", 2)
    @patch("towersignal.oath.time.sleep")
    @patch("towersignal.oath._fetch_exact_ticket_batch")
    @patch("towersignal.oath.fetch_metadata", return_value={"name": "OATH test", "source_last_updated_at": "2026-09-06T00:00:00Z"})
    @patch("towersignal.oath.fetch_where")
    def test_large_ticket_set_falls_back_only_after_minimum_agency_page_retries_exhausted(
        self, fetch_where_mock, _fetch_metadata_mock, exact_batch_mock, sleep_mock
    ):
        requested = [f"{index:010d}" for index in range(1000)]
        fetch_where_mock.side_effect = [
            [{"count": "1000"}],
            SourceFetchError("The read operation timed out"),
            SourceFetchError("The read operation timed out"),
        ]

        def exact_side_effect(batch):
            return batch, [{"ticket_number": ticket, "hearing_status": "HEARING COMPLETED"} for ticket in batch]

        exact_batch_mock.side_effect = exact_side_effect
        cases, metadata = fetch_oath_cases(requested)

        self.assertEqual(set(cases), set(requested))
        self.assertEqual(fetch_where_mock.call_count, 3)
        self.assertEqual(exact_batch_mock.call_count, 4)
        self.assertEqual(sleep_mock.call_count, 1)
        self.assertIn("fell back to exact ticket_number batches", metadata["source_query_scope"])

    @patch("towersignal.oath._fetch_exact_ticket_batch")
    @patch("towersignal.oath.fetch_metadata", return_value={"name": "OATH test", "source_last_updated_at": "2026-09-06T00:00:00Z"})
    @patch("towersignal.oath.fetch_where")
    def test_large_ticket_set_does_not_hide_nontransient_agency_page_failure(
        self, fetch_where_mock, _fetch_metadata_mock, exact_batch_mock
    ):
        requested = [f"{index:010d}" for index in range(1000)]
        fetch_where_mock.side_effect = [
            [{"count": "1000"}],
            SourceFetchError("OATH agency response schema invalid"),
        ]

        with self.assertRaises(SourceFetchError):
            fetch_oath_cases(requested)
        exact_batch_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
