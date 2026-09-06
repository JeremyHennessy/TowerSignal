import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.checkbook import CITYWIDE_SOURCE, EDC_SOURCE
from verify_live_checkbook import verify_cache


def _citywide_row(contract_id: str, fiscal_year: int, *, amount: str = "250000") -> dict[str, str]:
    return {
        "prime_contract_id": contract_id,
        "prime_vendor": "Example Water LLC",
        "prime_contract_purpose": "Cooling tower water treatment",
        "prime_contract_original_amount": amount,
        "prime_contract_current_amount": amount,
        "prime_vendor_spent_to_date": "125000",
        "prime_contract_start_date": "2025-01-01",
        "prime_contract_end_date": "2027-12-31",
        "prime_contracting_agency": "Department of Citywide Administrative Services",
        "prime_contract_version": "1",
        "parent_contract_id": "",
        "prime_contract_type": "05",
        "prime_contract_award_method": "01",
        "prime_contract_expense_category": "Services",
        "prime_contract_industry": "Construction Services",
        "prime_contract_pin": "PIN-1",
        "_test_fiscal_year": str(fiscal_year),
    }


def _edc_row(contract_id: str) -> dict[str, str]:
    return {
        "contract_id": contract_id,
        "prime_vendor": "EDC Water LLC",
        "purpose": "Chiller service",
        "original_amount": "500",
        "current_amount": "550",
        "spent_to_date": "300",
        "start_date": "2024-07-01",
        "end_date": "2028-06-30",
        "other_government_entities": "NYC Economic Development Corporation",
    }


class FakeCheckbookApi:
    def __init__(self, *, citywide=None, edc=None):
        self.citywide = list(citywide or [])
        self.edc = list(edc or [])
        self.calls = []

    def __call__(self, payload):
        root = ET.fromstring(payload)
        domain = root.findtext("type_of_data")
        records_from = int(root.findtext("records_from") or "1")
        max_records = int(root.findtext("max_records") or "100")
        criteria = {
            node.findtext("name"): node.findtext("value")
            for node in root.findall("./search_criteria/criteria")
        }
        columns = [node.text or "" for node in root.findall("./response_columns/column")]
        self.calls.append({"domain": domain, "criteria": criteria})

        rows = self.edc if domain == "Contracts_OGE" else self.citywide
        if criteria.get("contract_id"):
            identity = "contract_id" if domain == "Contracts_OGE" else "prime_contract_id"
            rows = [row for row in rows if row.get(identity) == criteria["contract_id"]]
        if criteria.get("fiscal_year"):
            rows = [row for row in rows if row.get("_test_fiscal_year") == criteria["fiscal_year"]]

        page = rows[records_from - 1 : records_from - 1 + max_records]
        response = ET.Element("response")
        status = ET.SubElement(response, "status")
        ET.SubElement(status, "result").text = "success"
        result_records = ET.SubElement(response, "result_records")
        ET.SubElement(result_records, "record_count").text = str(len(rows))
        transactions = ET.SubElement(result_records, "contract_transactions")
        for source_row in page:
            transaction = ET.SubElement(transactions, "transaction")
            for column in columns:
                ET.SubElement(transaction, column).text = str(source_row.get(column, ""))
        return ET.tostring(response, encoding="utf-8")


class VerifyLiveCheckbookTests(unittest.TestCase):
    def _write_cache(self, contracts):
        handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False)
        with handle:
            json.dump({"generated_at": "2026-09-05T14:18:24Z", "contracts": contracts}, handle)
        return Path(handle.name)

    def test_citywide_verifier_replays_cached_fiscal_year_partition(self):
        cached_raw = _citywide_row("CT1", 2027, amount="250000")
        stale_same_contract = _citywide_row("CT1", 2026, amount="100000")
        api = FakeCheckbookApi(citywide=[stale_same_contract, cached_raw])
        cache = self._write_cache(
            [
                {
                    "procurement_id": "contract-citywide-1",
                    "source": CITYWIDE_SOURCE,
                    "vendor_role": "PRIME",
                    "source_contract_id": "CT1",
                    "source_fiscal_year": 2027,
                    "raw": cached_raw,
                }
            ]
        )

        try:
            result = verify_cache(cache, sample_size=1, request_xml=api)
        finally:
            cache.unlink()

        self.assertEqual(result["result"], "PASS")
        self.assertEqual(api.calls[0]["criteria"]["fiscal_year"], "2027")

    def test_edc_verifier_keeps_contract_id_lookup(self):
        cached_raw = _edc_row("EDC1")
        api = FakeCheckbookApi(edc=[cached_raw])
        cache = self._write_cache(
            [
                {
                    "procurement_id": "contract-edc-1",
                    "source": EDC_SOURCE,
                    "vendor_role": "PRIME",
                    "source_contract_id": "EDC1",
                    "raw": cached_raw,
                }
            ]
        )

        try:
            result = verify_cache(cache, sample_size=1, request_xml=api)
        finally:
            cache.unlink()

        self.assertEqual(result["result"], "PASS")
        self.assertNotIn("fiscal_year", api.calls[0]["criteria"])


if __name__ == "__main__":
    unittest.main()
