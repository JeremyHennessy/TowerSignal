from __future__ import annotations

import io
import sys
import unittest
from http.client import RemoteDisconnected
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.fetch import _request_json


class SourceFetchRetryTests(unittest.TestCase):
    @patch("towersignal.fetch.time.sleep")
    @patch("towersignal.fetch.urlopen")
    def test_remote_disconnect_is_retried(self, urlopen_mock, sleep_mock):
        urlopen_mock.side_effect = [
            RemoteDisconnected("remote end closed connection without response"),
            io.BytesIO(b'{"ok": true}'),
        ]

        payload = _request_json("https://example.test/source", retries=2, timeout=1)

        self.assertEqual(payload, {"ok": True})
        self.assertEqual(urlopen_mock.call_count, 2)
        sleep_mock.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()
