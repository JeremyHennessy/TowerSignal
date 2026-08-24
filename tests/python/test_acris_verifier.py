import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_live_acris  # noqa: E402


class AcrisVerifierTests(unittest.TestCase):
    def test_verifier_batches_five_document_evidence_by_source(self):
        documents = [
            {
                "document_id": "D1",
                "bbl": "1000100001",
                "doc_type": "DEED",
                "recorded_date": "2026-08-01",
                "parties": [{"party_type": "1", "name": "SELLER LLC"}],
            },
            {
                "document_id": "D2",
                "bbl": "2000200002",
                "doc_type": "MTGE",
                "recorded_date": "2026-08-02",
                "parties": [{"party_type": "2", "name": "LENDER LLC"}],
            },
        ]
        cache = {
            "properties": {
                "1000100001": {"documents": [documents[0]]},
                "2000200002": {"documents": [documents[1]]},
            }
        }
        calls = []

        def fake_request_rows(dataset_id, where, select, attempts=4):
            calls.append((dataset_id, where, select, attempts))
            if dataset_id == verify_live_acris.MASTER_DATASET_ID:
                return [
                    {"document_id": "D1", "doc_type": "DEED", "recorded_datetime": "2026-08-01T10:00:00"},
                    {"document_id": "D2", "doc_type": "MTGE", "recorded_datetime": "2026-08-02T10:00:00"},
                ]
            if dataset_id == verify_live_acris.LEGALS_DATASET_ID:
                return [
                    {"document_id": "D1", "borough": "1", "block": "10", "lot": "1"},
                    {"document_id": "D2", "borough": "2", "block": "20", "lot": "2"},
                ]
            if dataset_id == verify_live_acris.PARTIES_DATASET_ID:
                return [
                    {"document_id": "D1", "party_type": "1", "name": "SELLER LLC"},
                    {"document_id": "D2", "party_type": "2", "name": "LENDER LLC"},
                ]
            raise AssertionError(dataset_id)

        with patch.object(verify_live_acris, "load_cache", return_value=cache), patch.object(
            verify_live_acris, "request_rows", side_effect=fake_request_rows
        ):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                verify_live_acris.verify(Path("unused.json"), sample_size=2)

        self.assertEqual(
            [call[0] for call in calls],
            [
                verify_live_acris.MASTER_DATASET_ID,
                verify_live_acris.LEGALS_DATASET_ID,
                verify_live_acris.PARTIES_DATASET_ID,
            ],
        )
        self.assertTrue(all("document_id in (" in call[1] for call in calls))
        self.assertTrue(all("'D1'" in call[1] and "'D2'" in call[1] for call in calls))
        self.assertIn('"status": "PASS"', output.getvalue())
        self.assertIn('"sample_size": 2', output.getvalue())


if __name__ == "__main__":
    unittest.main()
