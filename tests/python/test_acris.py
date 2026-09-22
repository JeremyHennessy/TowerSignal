import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.acris import (
    ACRIS_CACHE_SCHEMA_VERSION,
    MASTER_DATASET_ID,
    AcrisError,
    _metadata,
    ALIAS_BBL_MATCH_BASIS,
    CONDO_ROLLUP_MATCH_BASIS,
    _condo_target_index,
    _legal_address_key,
    browser_property_context,
    canonical_master,
    normalize_address_number,
    normalize_document,
    normalize_street_name,
    summarize_property,
    tower_bbl_hash,
    validate_cache,
    validate_cache_file,
)


class AcrisTests(unittest.TestCase):
    def test_metadata_enrichment_is_nonfatal_when_legacy_view_endpoint_times_out(self):
        with patch("towersignal.acris._request_json", side_effect=AcrisError("timed out")) as request:
            metadata = _metadata(MASTER_DATASET_ID)

        request.assert_called_once()
        _, kwargs = request.call_args
        self.assertEqual(kwargs, {"attempts": 2, "timeout": 15})
        self.assertEqual(metadata["name"], MASTER_DATASET_ID)
        self.assertIsNone(metadata["source_last_updated_at"])
        self.assertEqual(metadata["metadata_status"], "UNAVAILABLE")
        self.assertIn("timed out", metadata["metadata_error"])

    def test_canonical_master_prefers_latest_recorded_then_modified_row(self):
        rows = [
            {"document_id": "D1", "recorded_datetime": "2026-01-01T00:00:00", "modified_date": "2026-01-02T00:00:00", "record_type": "A"},
            {"document_id": "D1", "recorded_datetime": "2026-01-02T00:00:00", "modified_date": "2026-01-01T00:00:00", "record_type": "A"},
        ]
        self.assertIs(canonical_master(rows), rows[1])

    def test_normalized_document_keeps_raw_party_type_without_inference(self):
        document = normalize_document(
            "1002360038",
            {
                "document_id": "D1",
                "doc_type": "DEED",
                "recorded_datetime": "2026-08-01T12:00:00",
                "document_amt": "$2,500,000",
                "percent_trans": "50",
            },
            [{"property_type": "AP", "street_number": "10", "street_name": "MAIN ST", "unit": "2A"}],
            [{"party_type": "1", "name": "EXAMPLE LLC"}, {"party_type": "2", "name": "BUYER LLC"}],
        )
        self.assertEqual(document["match_basis"], "BBL_EXACT_DOCUMENT_ID_EXACT")
        self.assertEqual(document["recorded_date"], "2026-08-01")
        self.assertEqual(document["document_amount"], 2500000.0)
        self.assertEqual(document["percent_transferred"], 50.0)
        self.assertEqual([party["party_type"] for party in document["parties"]], ["1", "2"])

    def test_exact_base_bbl_alias_provenance_is_accepted(self):
        document = normalize_document(
            "1011717513",
            {
                "document_id": "D-BASE",
                "doc_type": "MTGE",
                "recorded_datetime": "2026-06-01T12:00:00",
            },
            [{
                "borough": "1",
                "block": "1171",
                "lot": "0154",
                "property_type": "AP",
                "street_number": "400",
                "street_name": "WEST 61 STREET",
            }],
            [],
            ALIAS_BBL_MATCH_BASIS,
        )
        self.assertEqual(document["bbl"], "1011717513")
        self.assertEqual(document["match_basis"], ALIAS_BBL_MATCH_BASIS)
        self.assertEqual(document["legal_context"][0]["source_bbl"], "1011710154")

    def test_condo_address_normalization_is_exact_and_deterministic(self):
        self.assertEqual(normalize_address_number("0400"), "400")
        self.assertEqual(normalize_street_name("West 61st Street"), "W 61 ST")
        self.assertEqual(normalize_street_name("WEST 61 STREET"), "W 61 ST")
        index = _condo_target_index({
            "1011717513": {"number": "400", "street": "West 61st Street"},
            "1011710154": {"number": "400", "street": "West 61st Street"},
        })
        key = _legal_address_key({
            "borough": "1",
            "block": "1171",
            "lot": "4942",
            "street_number": "400",
            "street_name": "WEST 61 STREET",
        })
        self.assertEqual(index[key], {"1011717513"})
        self.assertNotIn("1011710154", index[key])

    def test_condo_rollup_document_preserves_source_unit_bbl(self):
        document = normalize_document(
            "1011717513",
            {
                "document_id": "D-CONDO",
                "doc_type": "DEED",
                "recorded_datetime": "2026-05-01T12:00:00",
            },
            [{
                "borough": "1",
                "block": "1171",
                "lot": "4942",
                "property_type": "AP",
                "street_number": "400",
                "street_name": "WEST 61 STREET",
                "unit": "34C",
            }],
            [],
            CONDO_ROLLUP_MATCH_BASIS,
        )
        self.assertEqual(document["bbl"], "1011717513")
        self.assertEqual(document["match_basis"], CONDO_ROLLUP_MATCH_BASIS)
        self.assertEqual(document["legal_context"][0]["source_bbl"], "1011714942")

    def test_summary_and_browser_limit_preserve_full_counts(self):
        documents = []
        for index in range(30):
            documents.append({
                "document_id": f"D{index:02d}",
                "bbl": "1002360038",
                "doc_type": "MTGE" if index % 2 else "DEED",
                "recorded_date": f"2026-07-{(index % 28) + 1:02d}",
                "parties": [{"party_type": "1", "name": f"PARTY {index}"}],
                "match_basis": "BBL_EXACT_DOCUMENT_ID_EXACT",
            })
        summary = summarize_property(documents)
        public = browser_property_context(summary, document_limit=25)
        self.assertEqual(summary["recent_document_count"], 30)
        self.assertEqual(summary["deed_count"], 15)
        self.assertEqual(summary["mortgage_count"], 15)
        self.assertEqual(public["recent_document_count"], 30)
        self.assertEqual(public["displayed_document_count"], 25)
        self.assertEqual(len(public["documents"]), 25)

    def test_cache_validation_requires_exact_join_provenance(self):
        document = {
            "document_id": "D1",
            "bbl": "1002360038",
            "doc_type": "DEED",
            "recorded_date": "2026-08-01",
            "parties": [],
            "match_basis": "BBL_EXACT_DOCUMENT_ID_EXACT",
        }
        context = summarize_property([document])
        cache = {
            "schema_version": ACRIS_CACHE_SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "lookback_days": 365,
            "cutoff": "2025-08-23",
            "tower_bbl_universe": {"count": 1, "sha256": tower_bbl_hash(["1002360038"])},
            "sources": [
                {"dataset_id": "bnx9-e6tj"},
                {"dataset_id": "8h5j-fqxa"},
                {"dataset_id": "636b-3b5g"},
            ],
            "metrics": {"tower_bbls_with_recent_relevant_acris": 1, "matched_recent_document_count": 1},
            "properties": {"1002360038": context},
        }
        validate_cache(cache)
        cache["properties"]["1002360038"]["documents"][0]["match_basis"] = "FUZZY"
        with self.assertRaises(Exception):
            validate_cache(cache)

    def test_cache_validation_accepts_provenanced_condo_rollup_and_rejects_missing_source_bbl(self):
        document = {
            "document_id": "D-CONDO",
            "bbl": "1011717513",
            "doc_type": "DEED",
            "recorded_date": "2026-05-01",
            "parties": [],
            "match_basis": CONDO_ROLLUP_MATCH_BASIS,
            "legal_context": [{"source_bbl": "1011714942", "street_number": "400", "street_name": "WEST 61 STREET"}],
        }
        cache = {
            "schema_version": ACRIS_CACHE_SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "lookback_days": 365,
            "cutoff": "2025-09-22",
            "tower_bbl_universe": {"count": 1, "sha256": tower_bbl_hash(["1011717513"])},
            "sources": [{"dataset_id": "bnx9-e6tj"}, {"dataset_id": "8h5j-fqxa"}, {"dataset_id": "636b-3b5g"}],
            "metrics": {"tower_bbls_with_recent_relevant_acris": 1, "matched_recent_document_count": 1},
            "properties": {"1011717513": summarize_property([document])},
        }
        validate_cache(cache)
        cache["properties"]["1011717513"]["documents"][0]["legal_context"] = []
        with self.assertRaisesRegex(Exception, "lacks source unit-BBL provenance"):
            validate_cache(cache)

    def test_cache_file_size_and_age_validation(self):
        document = {
            "document_id": "D1", "bbl": "1002360038", "doc_type": "DEED", "recorded_date": "2026-08-01",
            "parties": [], "match_basis": "BBL_EXACT_DOCUMENT_ID_EXACT",
        }
        cache = {
            "schema_version": ACRIS_CACHE_SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "lookback_days": 365,
            "cutoff": "2025-08-23",
            "tower_bbl_universe": {"count": 1, "sha256": tower_bbl_hash(["1002360038"])},
            "sources": [{"dataset_id": "bnx9-e6tj"}, {"dataset_id": "8h5j-fqxa"}, {"dataset_id": "636b-3b5g"}],
            "metrics": {"tower_bbls_with_recent_relevant_acris": 1, "matched_recent_document_count": 1},
            "properties": {"1002360038": summarize_property([document])},
        }
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "cache.json"
            path.write_text(json.dumps(cache), encoding="utf-8")
            result = validate_cache_file(path, max_age_days=1)
            self.assertEqual(result["cache"]["schema_version"], ACRIS_CACHE_SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
