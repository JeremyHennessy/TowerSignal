import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.fetch import SourceFetchError
from towersignal.oath import _fetch_agency_seek_page


class OathServiceUnavailableTests(unittest.TestCase):
    @patch("towersignal.oath.time.sleep")
    @patch("towersignal.oath.fetch_where")
    def test_http_503_retries_same_agency_page(self, fetch_where_mock, sleep_mock):
        fetch_where_mock.side_effect = [
            SourceFetchError("HTTP Error 503: Service Unavailable"),
            [{"ticket_number": "0880000001", "hearing_status": "HEARING COMPLETED"}],
        ]

        rows, page_size = _fetch_agency_seek_page("issuing_agency='COOLING TOWERS - DOHMH'", 10000)

        self.assertEqual(rows[0]["ticket_number"], "0880000001")
        self.assertEqual(page_size, 10000)
        self.assertEqual(fetch_where_mock.call_count, 2)
        self.assertEqual(
            [call.kwargs["limit"] for call in fetch_where_mock.call_args_list],
            [10000, 10000],
        )
        sleep_mock.assert_called_once_with(5)


if __name__ == "__main__":
    unittest.main()
