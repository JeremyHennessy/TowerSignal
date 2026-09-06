from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from probe_elap_search import ElapFetchError, main as probe_main  # noqa: E402
from validate_elap_source_probe import validate  # noqa: E402


class ElapSourceProbeTests(unittest.TestCase):
    def _write_probe(self, payload: dict) -> Path:
        handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False)
        with handle:
            json.dump(payload, handle)
        return Path(handle.name)

    def test_validator_accepts_source_unavailable_only_when_allowed(self) -> None:
        path = self._write_probe(
            {
                "search_url": "https://apps.health.ny.gov/pubdoh/applinks/wc/elappublicweb/",
                "probe_status": "SOURCE_UNAVAILABLE",
                "source_error": "timed out",
                "scope_claims_created": 0,
            }
        )
        try:
            with self.assertRaisesRegex(RuntimeError, "ELAP source is unavailable"):
                validate(path)
            payload = validate(path, allow_source_unavailable=True)
        finally:
            path.unlink()

        self.assertEqual(payload["probe_status"], "SOURCE_UNAVAILABLE")
        self.assertEqual(payload["scope_claims_created"], 0)

    def test_probe_main_can_emit_source_unavailable_payload_when_allowed(self) -> None:
        output = io.StringIO()
        with (
            patch.object(sys, "argv", ["probe_elap_search.py", "--allow-source-unavailable"]),
            patch("probe_elap_search.build_probe", side_effect=ElapFetchError("Failed to fetch ELAP public page: timed out")),
            redirect_stdout(output),
        ):
            probe_main()

        payload = json.loads(output.getvalue())
        self.assertEqual(payload["probe_status"], "SOURCE_UNAVAILABLE")
        self.assertEqual(payload["scope_claims_created"], 0)
        self.assertIn("timed out", payload["source_error"])


if __name__ == "__main__":
    unittest.main()
