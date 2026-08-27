from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.nys_authority_procurement import DATASETS, build_payload, normalize_row  # noqa: E402


class NysAuthorityProcurementTests(unittest.TestCase):
    def test_normalize_row_preserves_source_semantics(self) -> None:
        row = {
            "authority_name": "Example State Authority",
            "fiscal_year_end_date": "2025-12-31T00:00:00.000",
            "vendor_name": "Example Water LLC",
            "vendor_address_1": "1 Main St",
            "vendor_city": "Albany",
            "vendor_state": "NY",
            "procurement_description": "Cooling tower water treatment and biocide service",
            "type_of_procurement": "Other Professional Services",
            "award_process": "Authority Contract - Competitive Bid",
            "award_date": "2024-02-05T00:00:00.000",
            "contract_begin_date": "2024-03-01T00:00:00.000",
            "contract_end_date": "2026-02-28T00:00:00.000",
            "contract_amount": "250000",
            "amount_expended": "125000",
        }
        record = normalize_row("NYS_ABO_STATE_AUTHORITIES", "ehig-g5x3", row, retrieved_at="2026-08-27T00:00:00Z")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["service_category"], "COOLING_WATER_TREATMENT")
        self.assertEqual(record["vendor_raw"], "Example Water LLC")
        self.assertEqual(record["buyer_name"], "Example State Authority")
        self.assertEqual(record["current_amount"], 250000.0)
        self.assertEqual(record["spend_to_date"], 125000.0)
        self.assertIn("not vendor revenue", record["observed_value_evidence"].lower())
        self.assertEqual(record["source_url"], "https://data.ny.gov/d/ehig-g5x3")

    def test_unrelated_row_is_rejected(self) -> None:
        row = {
            "authority_name": "Example Authority",
            "vendor_name": "Bottle Company",
            "procurement_description": "Bottled water delivery for offices",
        }
        self.assertIsNone(normalize_row("NYS_ABO_STATE_AUTHORITIES", "ehig-g5x3", row, retrieved_at="2026-08-27T00:00:00Z"))

    @patch("towersignal.nys_authority_procurement._fetch_metadata")
    @patch("towersignal.nys_authority_procurement._fetch_count")
    @patch("towersignal.nys_authority_procurement._fetch_search")
    def test_build_payload_deduplicates_search_hits_and_keeps_cohort_aliases(self, fetch_search, fetch_count, fetch_metadata) -> None:
        fetch_metadata.return_value = {"rowsUpdatedAt": 1787000000}
        fetch_count.return_value = 100
        relevant = {
            "authority_name": "Authority",
            "fiscal_year_end_date": "2025-12-31",
            "vendor_name": "ROCHESTER MIDLAND CORP",
            "procurement_description": "Water treatment service",
            "award_date": "2023-07-01",
            "contract_amount": "100000",
        }
        fetch_search.side_effect = lambda dataset_id, term: [relevant] if dataset_id == DATASETS[0][1] and term in {"water treatment", "ROCHESTER MIDLAND CORP"} else []
        payload = build_payload(cohort_aliases=["ROCHESTER MIDLAND CORP"], retrieval_terms=["water treatment"])
        self.assertEqual(payload["summary"]["source_dataset_count"], 4)
        self.assertEqual(payload["summary"]["relevant_contract_count"], 1)
        self.assertEqual(payload["contracts"][0]["vendor_raw"], "ROCHESTER MIDLAND CORP")
        self.assertEqual(len({row["procurement_id"] for row in payload["contracts"]}), 1)


if __name__ == "__main__":
    unittest.main()
