from __future__ import annotations

import io
import sys
import unittest
from http.client import RemoteDisconnected
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from towersignal.fetch import SourceFetchError, _request_json


class SourceTransportRetryTests(unittest.TestCase):
    def test_remote_disconnect_is_retried_before_returning_authoritative_payload(self):
        with patch("towersignal.fetch.time.sleep"), patch(
            "towersignal.fetch.urlopen",
            side_effect=[RemoteDisconnected("remote closed connection"), io.BytesIO(b'[{"ok": true}]')],
        ) as urlopen:
            self.assertEqual(_request_json("https://example.test/source", retries=2), [{"ok": True}])
        self.assertEqual(urlopen.call_count, 2)

    def test_connection_reset_is_retried(self):
        with patch("towersignal.fetch.time.sleep"), patch(
            "towersignal.fetch.urlopen",
            side_effect=[ConnectionResetError("reset"), io.BytesIO(b'{"ok": true}')],
        ) as urlopen:
            self.assertEqual(_request_json("https://example.test/source", retries=2), {"ok": True})
        self.assertEqual(urlopen.call_count, 2)

    def test_exhausted_remote_disconnects_fail_closed(self):
        with patch("towersignal.fetch.time.sleep"), patch(
            "towersignal.fetch.urlopen", side_effect=RemoteDisconnected("remote closed connection")
        ) as urlopen:
            with self.assertRaisesRegex(SourceFetchError, "after 3 attempts"):
                _request_json("https://example.test/source", retries=3)
        self.assertEqual(urlopen.call_count, 3)


if __name__ == "__main__":
    unittest.main()
