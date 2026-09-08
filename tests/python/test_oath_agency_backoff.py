from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.fetch import SourceFetchError
from towersignal.oath import _fetch_agency_seek_page


class OathAgencyBackoffTests(unittest.TestCase):
    @patch("towersignal.oath.OATH_AGENCY_PAGE_RETRIES", 3)
    @patch("towersignal.oath.OATH_AGENCY_MIN_PAGE_SIZE", 500)
    @patch("towersignal.oath.OATH_AGENCY_PAGE_SIZE", 10000)
    @patch("towersignal.oath.time.sleep")
    @patch("towersignal.oath.fetch_where")
    def test_sustained_rate_limit_shrinks_same_seek_page_before_fallback(
        self, fetch_where_mock, sleep_mock
    ):
        fetch_where_mock.side_effect = [
            SourceFetchError("HTTP Error 429: Too Many Requests"),
            SourceFetchError("HTTP Error 429: Too Many Requests"),
            SourceFetchError("HTTP Error 429: Too Many Requests"),
            [{"ticket_number": "0880986673", "hearing_status": "HEARING COMPLETED"}],
        ]

        rows, page_size = _fetch_agency_seek_page(
            "issuing_agency='COOLING TOWERS - DOHMH' AND ticket_number > '0880885913'",
            10000,
        )

        self.assertEqual(rows[0]["ticket_number"], "0880986673")
        self.assertEqual(page_size, 5000)
        self.assertEqual(
            [call.kwargs["limit"] for call in fetch_where_mock.call_args_list],
            [10000, 10000, 10000, 5000],
        )
        self.assertEqual(sleep_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
