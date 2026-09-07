from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'patch target not found in {path}: {old[:120]!r}')
    file.write_text(text.replace(old, new, 1), encoding='utf-8')


replace_once(
    'scripts/towersignal/oath.py',
    '''OATH_AGENCY_SLICE_MIN_REQUESTED = 1000\nOATH_AGENCY_PAGE_SIZE = 25000\nOATH_AGENCY_SNAPSHOT_ATTEMPTS = 2\n''',
    '''OATH_AGENCY_SLICE_MIN_REQUESTED = 1000\nOATH_AGENCY_PAGE_SIZE = 10000\nOATH_AGENCY_MIN_PAGE_SIZE = 500\nOATH_AGENCY_PAGE_RETRIES = 3\nOATH_AGENCY_PAGE_REQUEST_RETRIES = 1\nOATH_AGENCY_PAGE_TIMEOUT_SECONDS = 20\nOATH_AGENCY_SNAPSHOT_ATTEMPTS = 2\n''',
)

helper = '''\n\ndef _fetch_agency_seek_page(page_where: str, page_size: int) -> tuple[list[dict[str, Any]], int]:\n    current_size = max(OATH_AGENCY_MIN_PAGE_SIZE, min(page_size, OATH_AGENCY_PAGE_SIZE))\n    transient_attempt = 0\n    while True:\n        try:\n            rows = fetch_where(\n                OATH_DATASET_ID,\n                page_where,\n                order_by="ticket_number",\n                select=OATH_SELECT,\n                request_retries=OATH_AGENCY_PAGE_REQUEST_RETRIES,\n                request_timeout=OATH_AGENCY_PAGE_TIMEOUT_SECONDS,\n                limit=current_size,\n            )\n            return rows, current_size\n        except SourceFetchError as exc:\n            if not _is_transient_oath_error(exc):\n                raise\n            if _is_timeout_oath_error(exc) and current_size > OATH_AGENCY_MIN_PAGE_SIZE:\n                next_size = max(OATH_AGENCY_MIN_PAGE_SIZE, current_size // 2)\n                print(\n                    f"[oath] OATH agency seek page timed out at {current_size:,} rows; "\n                    f"retrying the same cursor at {next_size:,} rows",\n                    flush=True,\n                )\n                current_size = next_size\n                transient_attempt = 0\n                continue\n            transient_attempt += 1\n            if transient_attempt >= OATH_AGENCY_PAGE_RETRIES:\n                raise\n            delay = 5 * transient_attempt\n            print(\n                f"[oath] Transient OATH agency-page error at {current_size:,} rows; "\n                f"retrying the same cursor in {delay}s",\n                flush=True,\n            )\n            time.sleep(delay)\n'''
replace_once(
    'scripts/towersignal/oath.py',
    '\n\ndef _fetch_exact_ticket_fallback(requested: set[str]) -> tuple[dict[str, dict[str, Any]], int]:\n',
    helper + '\n\ndef _fetch_exact_ticket_fallback(requested: set[str]) -> tuple[dict[str, dict[str, Any]], int]:\n',
)

replace_once(
    'scripts/towersignal/oath.py',
    '''        cases: dict[str, dict[str, Any]] = {}\n        fetched_count = 0\n        cursor: str | None = None\n        while True:\n''',
    '''        cases: dict[str, dict[str, Any]] = {}\n        fetched_count = 0\n        cursor: str | None = None\n        page_size = OATH_AGENCY_PAGE_SIZE\n        while True:\n''',
)

replace_once(
    'scripts/towersignal/oath.py',
    '''            try:\n                rows = fetch_where(\n                    OATH_DATASET_ID,\n                    page_where,\n                    order_by="ticket_number",\n                    select=OATH_SELECT,\n                    request_retries=OATH_RATE_LIMIT_RETRIES,\n                    request_timeout=OATH_REQUEST_TIMEOUT_SECONDS,\n                    limit=OATH_AGENCY_PAGE_SIZE,\n                )\n            except SourceFetchError as exc:\n                if not _is_transient_oath_error(exc):\n                    raise\n                print(\n                    f"[oath] Transient OATH agency-page failure ({exc}); "\n                    "using exact-ticket fallback instead of abandoning the lifecycle build",\n                    flush=True,\n                )\n                fallback_cases, query_row_count = _fetch_exact_ticket_fallback(requested)\n                return fallback_cases, query_row_count, True\n''',
    '''            try:\n                rows, page_size = _fetch_agency_seek_page(page_where, page_size)\n            except SourceFetchError as exc:\n                if not _is_transient_oath_error(exc):\n                    raise\n                print(\n                    f"[oath] OATH agency seek page still failed at the minimum adaptive page size ({exc}); "\n                    "using exact-ticket fallback instead of abandoning the lifecycle build",\n                    flush=True,\n                )\n                fallback_cases, query_row_count = _fetch_exact_ticket_fallback(requested)\n                return fallback_cases, query_row_count, True\n''',
)

replace_once(
    'scripts/towersignal/oath.py',
    '''            if len(rows) < OATH_AGENCY_PAGE_SIZE:\n                break\n''',
    '''            if len(rows) < page_size:\n                break\n''',
)

# Stable agency test: count calls keep the existing count retry contract; data pages use the lightweight adaptive contract.
replace_once(
    'tests/python/test_oath_fetch.py',
    '''            self.assertEqual(request_retries, 4)\n            self.assertEqual(request_timeout, 30)\n            if select == "count(*) as count":\n                self.assertEqual(limit, 1)\n                self.assertIsNone(order_by)\n                self.assertIsNone(offset)\n                return [{"count": str(len(requested) + 1)}]\n            self.assertEqual(order_by, "ticket_number")\n            self.assertEqual(limit, 25000)\n''',
    '''            if select == "count(*) as count":\n                self.assertEqual(request_retries, 4)\n                self.assertEqual(request_timeout, 30)\n                self.assertEqual(limit, 1)\n                self.assertIsNone(order_by)\n                self.assertIsNone(offset)\n                return [{"count": str(len(requested) + 1)}]\n            self.assertEqual(request_retries, 1)\n            self.assertEqual(request_timeout, 20)\n            self.assertEqual(order_by, "ticket_number")\n            self.assertEqual(limit, 10000)\n''',
)

replace_once(
    'tests/python/test_oath_fetch.py',
    '''    @patch("towersignal.oath.validate_match_coverage")\n    @patch("towersignal.oath.OATH_AGENCY_PAGE_SIZE", 2)\n''',
    '''    @patch("towersignal.oath.validate_match_coverage")\n    @patch("towersignal.oath.OATH_AGENCY_MIN_PAGE_SIZE", 1)\n    @patch("towersignal.oath.OATH_AGENCY_PAGE_SIZE", 2)\n''',
)

old_timeout_test = '''    @patch("towersignal.oath._fetch_exact_ticket_batch")\n    @patch("towersignal.oath.fetch_metadata", return_value={"name": "OATH test", "source_last_updated_at": "2026-09-06T00:00:00Z"})\n    @patch("towersignal.oath.fetch_where")\n    def test_large_ticket_set_falls_back_when_first_agency_page_times_out(\n        self, fetch_where_mock, _fetch_metadata_mock, exact_batch_mock\n    ):\n        requested = [f"{index:010d}" for index in range(1000)]\n        fetch_where_mock.side_effect = [\n            [{"count": "1000"}],\n            SourceFetchError("The read operation timed out"),\n        ]\n\n        def exact_side_effect(batch):\n            return batch, [{"ticket_number": ticket, "hearing_status": "HEARING COMPLETED"} for ticket in batch]\n\n        exact_batch_mock.side_effect = exact_side_effect\n        cases, metadata = fetch_oath_cases(requested)\n\n        self.assertEqual(set(cases), set(requested))\n        self.assertEqual(fetch_where_mock.call_count, 2)\n        self.assertEqual(exact_batch_mock.call_count, 4)\n        self.assertEqual(metadata["matched_ticket_count"], 1000)\n        self.assertIn("fell back to exact ticket_number batches", metadata["source_query_scope"])\n'''
new_timeout_test = '''    @patch("towersignal.oath._fetch_exact_ticket_batch")\n    @patch("towersignal.oath.fetch_metadata", return_value={"name": "OATH test", "source_last_updated_at": "2026-09-06T00:00:00Z"})\n    @patch("towersignal.oath.fetch_where")\n    def test_large_ticket_set_shrinks_agency_page_after_timeout_before_fallback(\n        self, fetch_where_mock, _fetch_metadata_mock, exact_batch_mock\n    ):\n        requested = [f"{index:010d}" for index in range(1000)]\n        page_limits = []\n        count_calls = 0\n\n        def side_effect(dataset_id, where, order_by=None, select=None, **kwargs):\n            nonlocal count_calls\n            if select == "count(*) as count":\n                count_calls += 1\n                return [{"count": "1000"}]\n            page_limits.append(kwargs.get("limit"))\n            if len(page_limits) == 1:\n                raise SourceFetchError("The read operation timed out")\n            return [{"ticket_number": ticket, "hearing_status": "HEARING COMPLETED"} for ticket in requested]\n\n        fetch_where_mock.side_effect = side_effect\n        cases, metadata = fetch_oath_cases(requested)\n\n        self.assertEqual(set(cases), set(requested))\n        self.assertEqual(page_limits, [10000, 5000])\n        self.assertEqual(count_calls, 2)\n        exact_batch_mock.assert_not_called()\n        self.assertEqual(metadata["matched_ticket_count"], 1000)\n        self.assertNotIn("fell back to exact ticket_number batches", metadata["source_query_scope"])\n\n    @patch("towersignal.oath.OATH_AGENCY_PAGE_RETRIES", 2)\n    @patch("towersignal.oath.OATH_AGENCY_MIN_PAGE_SIZE", 2)\n    @patch("towersignal.oath.OATH_AGENCY_PAGE_SIZE", 2)\n    @patch("towersignal.oath.time.sleep")\n    @patch("towersignal.oath._fetch_exact_ticket_batch")\n    @patch("towersignal.oath.fetch_metadata", return_value={"name": "OATH test", "source_last_updated_at": "2026-09-06T00:00:00Z"})\n    @patch("towersignal.oath.fetch_where")\n    def test_large_ticket_set_falls_back_only_after_minimum_agency_page_retries_exhausted(\n        self, fetch_where_mock, _fetch_metadata_mock, exact_batch_mock, sleep_mock\n    ):\n        requested = [f"{index:010d}" for index in range(1000)]\n        fetch_where_mock.side_effect = [\n            [{"count": "1000"}],\n            SourceFetchError("The read operation timed out"),\n            SourceFetchError("The read operation timed out"),\n        ]\n\n        def exact_side_effect(batch):\n            return batch, [{"ticket_number": ticket, "hearing_status": "HEARING COMPLETED"} for ticket in batch]\n\n        exact_batch_mock.side_effect = exact_side_effect\n        cases, metadata = fetch_oath_cases(requested)\n\n        self.assertEqual(set(cases), set(requested))\n        self.assertEqual(fetch_where_mock.call_count, 3)\n        self.assertEqual(exact_batch_mock.call_count, 4)\n        self.assertEqual(sleep_mock.call_count, 1)\n        self.assertIn("fell back to exact ticket_number batches", metadata["source_query_scope"])\n'''
replace_once('tests/python/test_oath_fetch.py', old_timeout_test, new_timeout_test)
