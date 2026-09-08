from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'patch target not found in {path}: {old[:140]!r}')
    file.write_text(text.replace(old, new, 1), encoding='utf-8')


replace_once(
    'scripts/towersignal/oath.py',
    '''def _fetch_exact_ticket_fallback(requested: set[str]) -> tuple[dict[str, dict[str, Any]], int]:\n    requested_list = sorted(requested)\n    batches = [\n        requested_list[start : start + DEFAULT_BATCH_SIZE]\n        for start in range(0, len(requested_list), DEFAULT_BATCH_SIZE)\n    ]\n    cases: dict[str, dict[str, Any]] = {}\n    query_row_count = 0\n''',
    '''def _fetch_exact_ticket_fallback(\n    requested: set[str],\n    *,\n    seed_cases: dict[str, dict[str, Any]] | None = None,\n    seed_query_row_count: int = 0,\n) -> tuple[dict[str, dict[str, Any]], int]:\n    requested_list = sorted(requested)\n    cases: dict[str, dict[str, Any]] = dict(seed_cases or {})\n    unresolved = [ticket for ticket in requested_list if ticket not in cases]\n    batches = [\n        unresolved[start : start + DEFAULT_BATCH_SIZE]\n        for start in range(0, len(unresolved), DEFAULT_BATCH_SIZE)\n    ]\n    query_row_count = seed_query_row_count\n''',
)

replace_once(
    'scripts/towersignal/oath.py',
    '''    print(\n        f"[oath] Falling back to {len(batches):,} exact-ticket batches with {worker_count} worker(s) "\n        "after the agency-slice scan could not produce a stable complete snapshot",\n        flush=True,\n    )\n''',
    '''    print(\n        f"[oath] Falling back to {len(batches):,} exact-ticket batches for {len(unresolved):,} unresolved "\n        f"tickets with {worker_count} worker(s) after the agency-slice scan could not produce a stable complete snapshot",\n        flush=True,\n    )\n''',
)

replace_once(
    'scripts/towersignal/oath.py',
    '''                fallback_cases, query_row_count = _fetch_exact_ticket_fallback(requested)\n                return fallback_cases, query_row_count, True\n            if not rows:\n''',
    '''                fallback_cases, query_row_count = _fetch_exact_ticket_fallback(\n                    requested,\n                    seed_cases=cases,\n                    seed_query_row_count=fetched_count,\n                )\n                return fallback_cases, query_row_count, True\n            if not rows:\n''',
)

# Add a regression proving partial exact agency matches are reused after a transport failure.
marker = '''    @patch("towersignal.oath._fetch_exact_ticket_batch")\n    @patch("towersignal.oath.fetch_metadata", return_value={"name": "OATH test", "source_last_updated_at": "2026-09-06T00:00:00Z"})\n    @patch("towersignal.oath.fetch_where")\n    def test_large_ticket_set_does_not_hide_nontransient_agency_page_failure(\n'''
new_test = '''    @patch("towersignal.oath.OATH_AGENCY_MIN_PAGE_SIZE", 1)\n    @patch("towersignal.oath.OATH_AGENCY_PAGE_SIZE", 2)\n    @patch("towersignal.oath._fetch_exact_ticket_batch")\n    @patch("towersignal.oath._fetch_agency_seek_page")\n    @patch("towersignal.oath.fetch_metadata", return_value={"name": "OATH test", "source_last_updated_at": "2026-09-06T00:00:00Z"})\n    @patch("towersignal.oath.fetch_where")\n    def test_page_transport_failure_reuses_partial_agency_matches_and_queries_only_unresolved(\n        self, fetch_where_mock, _fetch_metadata_mock, agency_page_mock, exact_batch_mock\n    ):\n        requested = [f"{index:010d}" for index in range(1000)]\n        fetch_where_mock.return_value = [{"count": "1000"}]\n        agency_page_mock.side_effect = [\n            ([\n                {"ticket_number": requested[0], "hearing_status": "HEARING COMPLETED"},\n                {"ticket_number": requested[1], "hearing_status": "HEARING COMPLETED"},\n            ], 2),\n            SourceFetchError("The read operation timed out"),\n        ]\n\n        queried: list[str] = []\n        def exact_side_effect(batch):\n            queried.extend(batch)\n            return batch, [{"ticket_number": ticket, "hearing_status": "HEARING COMPLETED"} for ticket in batch]\n\n        exact_batch_mock.side_effect = exact_side_effect\n        cases, metadata = fetch_oath_cases(requested)\n\n        self.assertEqual(set(cases), set(requested))\n        self.assertNotIn(requested[0], queried)\n        self.assertNotIn(requested[1], queried)\n        self.assertEqual(len(queried), 998)\n        self.assertEqual(metadata["source_record_count"], 1000)\n        self.assertIn("fell back to exact ticket_number batches", metadata["source_query_scope"])\n\n\n'''
replace_once('tests/python/test_oath_fetch.py', marker, new_test + marker)
