from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_provider_resolution_review import validate  # noqa: E402


class ProviderResolutionValidatorTests(unittest.TestCase):
    def _write(self, payload: dict) -> Path:
        handle = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
        with handle:
            json.dump(payload, handle)
        self.addCleanup(Path(handle.name).unlink, missing_ok=True)
        return Path(handle.name)

    def test_zero_merge_count_is_accepted(self) -> None:
        payload = {
            "schema_version": "1.0",
            "domain": "PROVIDER_IDENTITY_REVIEW",
            "summary": {
                "provider_count": 1,
                "alias_review_candidate_count": 0,
                "dec_name_match_count": 0,
                "providers_with_dec_name_match": 0,
                "merge_applied_count": 0,
            },
            "alias_review_candidates": [],
            "dec_name_matches": [],
        }
        result = validate(self._write(payload), require_production_volume=False)
        self.assertEqual(result["summary"]["merge_applied_count"], 0)

    def test_nonzero_merge_count_is_rejected(self) -> None:
        payload = {
            "schema_version": "1.0",
            "domain": "PROVIDER_IDENTITY_REVIEW",
            "summary": {
                "provider_count": 1,
                "alias_review_candidate_count": 0,
                "dec_name_match_count": 0,
                "providers_with_dec_name_match": 0,
                "merge_applied_count": 1,
            },
            "alias_review_candidates": [],
            "dec_name_matches": [],
        }
        with self.assertRaisesRegex(RuntimeError, "unexpectedly applied a merge"):
            validate(self._write(payload), require_production_volume=False)


if __name__ == "__main__":
    unittest.main()
