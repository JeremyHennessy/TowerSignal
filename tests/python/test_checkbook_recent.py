import sys
import unittest
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.checkbook import CheckbookSourceError, CITYWIDE_SOURCE
from towersignal.checkbook_recent import (
    build_recent_checkbook_cache,
    nyc_fiscal_year,
    recent_nyc_fiscal_years,
)


def prime_row(contract_id, purpose, *, amount="100", spent="50", vendor="Example Water LLC", version="1"):
    return {
        "prime_contract_id": str(contract_id),
        "prime_vendor": vendor,
        "prime_contract_purpose": purpose,
        "prime_contract_original_amount": amount,
        "prime_contract_current_amount": amount,
        "prime_vendor_spent_to_date": spent,
        "prime_contract_start_date": "2024-01-01",
        "prime_contract_end_date": "2028-12-31",
        "prime_contracting_agency": "Health + Hospitals",
        "prime_contract_version": version,
        "parent_contract_id": "",
        "prime_contract_type": "05",
        "prime_contract_award_method": "01",
        "prime_contract_expense_category": "Services",
        "prime_contract_industry": "Services",
        "prime_contract_pin": "PIN-1",
    }


def sub_row(prime_id, reference, purpose, *, paid="25"):
    return {
        "prime_contract_id": str(prime_id),
        "prime_contracting_agency": "Health + Hospitals",
        "sub_vendor": "Sub Water LLC",
        "sub_vendor_mwbe_category": "Non-M/WBE",
        "sub_contract_purpose": purpose,
        "sub_contract_status": "Registered",
        "sub_contract_original_amount": "50",
        "sub_contract_current_amount": "55",
        "sub_vendor_paid_to_date": paid,
        "sub_contract_industry": "Services",
        "sub_contract_start_date": "2025-01-01",
        "sub_contract_end_date": "2027-12-31",
        "sub_contract_reference_id": reference,
        "sub_woman_owned_business": "No",
        "sub_emerging_business": "No",
    }


def edc_row(contract_id, purpose):
    return {
        "contract_id": str(contract_id),
        "prime_vendor": "EDC Water LLC",
        "purpose": purpose,
        "other_government_entities": "NYC Economic Development Corporation",
        "version": "1",
        "parent_contract_id": "",
        "original_amount": "500",
        "current_amount": "550",
        "spent_to_date": "300",
        "contract_type": "52",
        "award_method": "01",
        "expense_category": "Services",
        "start_date": "2024-07-01",
        "end_date": "2028-06-30",
        "pin": "EDC-PIN",
        "document_code": "CT1",
        "contract_industry": "Services",
        "budget_name": "Facilities",
        "entity_contract_number": "123",
        "commodity_line": "Maintenance",
    }


class FakeRecentCheckbookApi:
    def __init__(self, *, prime_by_year=None, sub_by_year=None, edc=None, fail_year=None):
        self.prime_by_year = prime_by_year or {}
        self.sub_by_year = sub_by_year or {}
        self.edc = list(edc or [])
        self.fail_year = fail_year
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
        fiscal_year = int(criteria["fiscal_year"]) if criteria.get("fiscal_year") else None
        self.calls.append((domain, fiscal_year, dict(criteria)))
        if self.fail_year is not None and fiscal_year == self.fail_year:
            raise CheckbookSourceError(f"fixture failure FY{fiscal_year}")

        if domain == "Contracts_OGE":
            rows = self.edc
        elif criteria.get("contract_includes_sub_vendors") == "1":
            rows = list(self.sub_by_year.get(fiscal_year, []))
        else:
            rows = list(self.prime_by_year.get(fiscal_year, []))

        start = records_from - 1
        page = rows[start:start + max_records]
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


class RecentCheckbookTests(unittest.TestCase):
    def test_nyc_fiscal_year_boundary_and_recent_window(self):
        self.assertEqual(nyc_fiscal_year(date(2026, 6, 30)), 2026)
        self.assertEqual(nyc_fiscal_year(date(2026, 7, 1)), 2027)
        self.assertEqual(recent_nyc_fiscal_years(date(2026, 8, 27), 5), (2023, 2024, 2025, 2026, 2027))

    def test_recent_builder_selects_latest_version_and_nonzero_source_row(self):
        api = FakeRecentCheckbookApi(
            prime_by_year={
                2025: [prime_row("CT1", "Cooling tower water treatment", amount="100", spent="20", version="1")],
                2027: [
                    prime_row("CT1", "Cooling tower water treatment", amount="150", spent="100", version="1"),
                    prime_row("CT1", "Cooling tower water treatment", amount="175", spent="120", version="2"),
                    prime_row("CT1", "Cooling tower water treatment", amount="0", spent="0", version="2"),
                    prime_row("CT2", "Bottled water delivery", amount="50", spent="50"),
                ],
            },
            sub_by_year={
                2026: [sub_row("CT1", "SUB-1", "Legionella testing", paid="10")],
                2027: [sub_row("CT1", "SUB-1", "Legionella testing", paid="40")],
            },
            edc=[edc_row("EDC1", "Chiller service")],
        )
        payload = build_recent_checkbook_cache(
            as_of=date(2026, 8, 27),
            fiscal_year_count=3,
            request_xml=api,
            retrieved_at="2026-08-27T01:00:00Z",
            page_size=2,
        )
        self.assertEqual(payload["source"]["historical_coverage"]["fiscal_years"], [2025, 2026, 2027])
        self.assertTrue(all(fiscal_year is not None for domain, fiscal_year, _ in api.calls if domain == "Contracts"))

        primes = [
            row for row in payload["contracts"]
            if row["source"] == CITYWIDE_SOURCE and row["vendor_role"] == "PRIME"
        ]
        self.assertEqual(len(primes), 1)
        self.assertEqual(primes[0]["source_contract_id"], "CT1")
        self.assertEqual(primes[0]["current_amount"], 175.0)
        self.assertEqual(primes[0]["spend_to_date"], 120.0)
        self.assertEqual(primes[0]["contract_version"], "2")
        self.assertEqual(primes[0]["source_fiscal_year"], 2027)
        self.assertEqual(primes[0]["source_duplicate_row_count"], 2)
        self.assertEqual(primes[0]["source_duplicate_resolution"], "NONZERO_OVER_ZERO_PLACEHOLDER")

        subs = [
            row for row in payload["contracts"]
            if row["source"] == CITYWIDE_SOURCE and row["vendor_role"] == "SUBCONTRACTOR"
        ]
        self.assertEqual(len(subs), 1)
        self.assertEqual(subs[0]["spend_to_date"], 40.0)
        self.assertEqual(subs[0]["source_fiscal_year"], 2027)
        self.assertEqual(payload["summary"]["citywide_source_transaction_count"], 5)
        self.assertEqual(payload["summary"]["citywide_subvendor_source_transaction_count"], 2)
        self.assertEqual(payload["summary"]["citywide_unique_prime_contract_count"], 2)
        self.assertEqual(payload["summary"]["citywide_relevant_prime_contract_count"], 1)

    def test_unrelated_prime_vendor_variants_do_not_block_relevant_cache(self):
        api = FakeRecentCheckbookApi(
            prime_by_year={
                2027: [
                    prime_row("IRRELEVANT", "Shelter and facilities services", amount="100", vendor="Entity A"),
                    prime_row("IRRELEVANT", "Shelter and facilities services", amount="0", spent="0", vendor="Entity B"),
                    prime_row("RELEVANT", "Cooling tower cleaning", amount="200", vendor="Water Vendor"),
                ]
            }
        )
        payload = build_recent_checkbook_cache(
            as_of=date(2026, 8, 27),
            fiscal_year_count=1,
            request_xml=api,
            retrieved_at="2026-08-27T01:00:00Z",
            page_size=3,
        )
        primes = [row for row in payload["contracts"] if row["vendor_role"] == "PRIME"]
        self.assertEqual([row["source_contract_id"] for row in primes], ["RELEVANT"])
        self.assertEqual(payload["summary"]["citywide_unique_prime_contract_count"], 2)
        self.assertEqual(payload["summary"]["citywide_relevant_prime_contract_count"], 1)

    def test_relevant_prime_vendor_variants_remain_unresolved_source_evidence(self):
        api = FakeRecentCheckbookApi(
            prime_by_year={
                2027: [
                    prime_row("CT1", "Cooling tower cleaning", amount="200", vendor="Water Vendor Legal Name"),
                    prime_row("CT1", "Cooling tower cleaning", amount="0", spent="0", vendor="Water Vendor Alias"),
                ]
            }
        )
        payload = build_recent_checkbook_cache(
            as_of=date(2026, 8, 27),
            fiscal_year_count=1,
            request_xml=api,
            retrieved_at="2026-08-27T01:00:00Z",
            page_size=2,
        )
        contract = payload["contracts"][0]
        self.assertEqual(contract["vendor_raw"], "Water Vendor Legal Name")
        self.assertEqual(contract["source_vendor_variants"], ["Water Vendor Alias", "Water Vendor Legal Name"])
        self.assertEqual(contract["vendor_evidence_resolution"], "MULTIPLE_SOURCE_VARIANTS_UNRESOLVED")
        self.assertIsNone(contract["company_id"])
        self.assertEqual(contract["company_match_confidence"], "UNRESOLVED")
        self.assertEqual(contract["company_resolution_method"], "SOURCE_VENDOR_VARIANTS_NOT_RESOLVED")

    def test_two_nonzero_monetary_variants_still_fail_closed(self):
        api = FakeRecentCheckbookApi(
            prime_by_year={
                2027: [
                    prime_row("CT1", "Cooling tower cleaning", amount="100", spent="50", version="2"),
                    prime_row("CT1", "Cooling tower cleaning", amount="200", spent="75", version="2"),
                ]
            }
        )
        with self.assertRaisesRegex(CheckbookSourceError, "conflicting monetary fields"):
            build_recent_checkbook_cache(
                as_of=date(2026, 8, 27),
                fiscal_year_count=1,
                request_xml=api,
                retrieved_at="2026-08-27T01:00:00Z",
                page_size=2,
            )

    def test_partition_failure_propagates_instead_of_publishing_partial_cache(self):
        api = FakeRecentCheckbookApi(fail_year=2026)
        with self.assertRaisesRegex(CheckbookSourceError, "FY2026"):
            build_recent_checkbook_cache(
                as_of=date(2026, 8, 27),
                fiscal_year_count=3,
                request_xml=api,
                retrieved_at="2026-08-27T01:00:00Z",
                page_size=2,
            )


if __name__ == "__main__":
    unittest.main()
