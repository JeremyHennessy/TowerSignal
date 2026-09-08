import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_live_data
from towersignal.oath import MATCH_BASIS


class VerifyLiveDataCacheTests(unittest.TestCase):
    @patch("verify_live_data.validate_cache")
    def test_oath_sample_uses_verified_cache_and_records_provenance(self, validate_cache_mock):
        cached_case = {
            "ticket_number": "0880000001",
            "match_basis": MATCH_BASIS,
            "hearing_status": "HEARING COMPLETED",
        }
        validate_cache_mock.return_value = {
            "cache": {"generated_at": "2026-09-07T16:01:42Z"},
            "cases_by_ticket": {"0880000001": cached_case},
            "age_days": 1.1,
            "ticket_universe": {"count": 40900, "sha256": "a" * 64},
        }
        original_fetch = verify_live_data.baseline.fetch_oath_cases

        def fake_baseline_verify(_systems, _details, output, _sample_size):
            cases, metadata = verify_live_data.baseline.fetch_oath_cases(["0880000001"])
            self.assertEqual(cases, {"0880000001": cached_case})
            self.assertEqual(metadata["verification_source"], "verified_durable_oath_cache")
            output.write_text(json.dumps({"method": "legacy", "result": "PASS"}), encoding="utf-8")

        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            verify_live_data.baseline,
            "verify",
            side_effect=fake_baseline_verify,
        ):
            output = Path(temp_dir) / "verification.json"
            verify_live_data.verify(
                Path("systems.json"),
                Path("details"),
                output,
                5,
                Path("oath-cache.json.gz"),
            )
            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertIs(verify_live_data.baseline.fetch_oath_cases, original_fetch)
        self.assertIn("production-validated durable OATH cache", report["method"])
        self.assertEqual(report["oath_verification_source"]["type"], "verified_durable_cache")
        self.assertEqual(report["oath_verification_source"]["ticket_universe_count"], 40900)
        validate_cache_mock.assert_called_once_with(Path("oath-cache.json.gz"), require_production_volume=True)

    @patch("verify_live_data.baseline.verify")
    def test_without_cache_preserves_previous_live_verifier(self, baseline_verify_mock):
        verify_live_data.verify(Path("systems.json"), Path("details"), Path("verification.json"), 3, None)
        baseline_verify_mock.assert_called_once_with(
            Path("systems.json"),
            Path("details"),
            Path("verification.json"),
            3,
        )


if __name__ == "__main__":
    unittest.main()
