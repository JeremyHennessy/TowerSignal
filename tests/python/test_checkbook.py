import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.checkbook import (
    CITYWIDE_COLUMNS,
    CITYWIDE_EXCLUDED_COLUMNS,
    CITYWIDE_SCOPE,
    CITYWIDE_SOURCE,
    EDC_SCOPE,
    EDC_SOURCE,
    CheckbookSourceError,
    build_checkbook_cache,
    build_request_xml,
    fetch_scope,
    parse_response_xml,
)


def citywide_row(
    contract_id,
    purpose,
    *,
    vendor="Example Water LLC",
    amount="250000",
    spent="125000",
    sub_vendor="",
    sub_purpose="",
    sub_reference="",
):
    return {
        "prime_contract_id": str(contract_id),
        "contract_includes_sub_vendors": "Yes" if sub_vendor else "No",
        "prime_vendor": vendor,
        "prime_vendor_mwbe_category": "Non-M/WBE",
        "prime_contract_purpose": purpose,
        "prime_contract_original_amount": amount,
        "prime_contract_current_amount": amount,
        "prime_vendor_spent_to_date": spent,
        "prime_contract_start_date": "2025-01-01",
        "prime_contract_end_date": "2027-12-31",
        "prime_contracting_agency": "Department of Citywide Administrative Services",
        "prime_oca_number": "OCA-1",
        "prime_contract_version": "1",
        "parent_contract_id": "",
        "prime_contract_type": "05",
        "prime_contract_award_method": "01",
        "prime_contract_expense_category": "Services",
        "prime_contract_industry": "Construction Services",
        "prime_contract_pin": "PIN-1",
        "prime_contract_apt_pin": "",
        "percent_covid_spending": "0",
        "percent_other_spending": "100",
        "prime_woman_owned_business": "No",
        "prime_emerging_business": "No",
        "mocs_registered": "Yes",
        "contract_class": "EXPENSE",
        "document_code": "CT1",
        "sub_vendor": sub_vendor,
        "sub_vendor_mwbe_category": "Non-M/WBE" if sub_vendor else "",
        "sub_contract_purpose": sub_purpose,
        "sub_contract_status": "Registered" if sub_vendor else "",
        "sub_contract_original_amount": "50000" if sub_vendor else "",
        "sub_contract_current_amount": "55000" if sub_vendor else "",
        "sub_vendor_paid_to_date": "20000" if sub_vendor else "",
        "sub_contract_industry": "Services" if sub_vendor else "",
        "sub_contract_start_date": "2025-02-01" if sub_vendor else "",
        "sub_contract_end_date": "2026-12-31" if sub_vendor else "",
        "sub_contract_reference_id": sub_reference,
        "sub_woman_owned_business": "No" if sub_vendor else "",
        "sub_emerging_business": "No" if sub_vendor else "",
    }


def edc_row(contract_id, purpose, *, vendor="EDC Water Services Inc", amount="500000"):
    return {
        "contract_id": str(contract_id),
        "prime_vendor": vendor,
        "purpose": purpose,
        "other_government_entities": "NYC Economic Development Corporation",
        "version": "1",
        "parent_contract_id": "",
        "original_amount": amount,
        "current_amount": amount,
        "spent_to_date": "250000",
        "contract_type": "52",
        "award_method": "01",
        "expense_category": "Services",
        "start_date": "2024-07-01",
        "end_date": "2027-06-30",
        "pin": "EDC-PIN",
        "document_code": "CT1",
        "contract_industry": "Services",
        "budget_name": "Facilities",
        "entity_contract_number": "47840001",
        "commodity_line": "Maintenance",
    }


class FakeCheckbookApi:
    def __init__(self, *, citywide=None, edc=None, api_failure=False):
        self.citywide = list(citywide or [])
        self.edc = list(edc or [])
        self.api_failure = api_failure
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
        self.calls.append(
            {
                "domain": domain,
                "records_from": records_from,
                "max_records": max_records,
                "criteria": criteria,
                "columns": columns,
            }
        )

        if self.api_failure:
            return b"<response><status><result>error</result><messages><message><code>1000</code><description>bad request</description></message></messages></status></response>"

        rows = self.citywide if domain == "Contracts" else self.edc if domain == "Contracts_OGE" else []
        contract_id = criteria.get("contract_id")
        if contract_id:
            identity = "prime_contract_id" if domain == "Contracts" else "contract_id"
            rows = [row for row in rows if row.get(identity) == contract_id]

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


class CheckbookTests(unittest.TestCase):
    def test_citywide_request_uses_live_safe_contract_and_criteria(self):
        payload = build_request_xml(CITYWIDE_SCOPE, records_from=1, max_records=20000)
        root = ET.fromstring(payload)
        self.assertEqual(root.findtext("type_of_data"), "Contracts")
        self.assertEqual(root.findtext("records_from"), "1")
        self.assertEqual(root.findtext("max_records"), "20000")
        criteria = {
            node.findtext("name"): node.findtext("value")
            for node in root.findall("./search_criteria/criteria")
        }
        self.assertEqual(criteria, {"status": "registered", "category": "expense"})
        columns = {node.text for node in root.findall("./response_columns/column")}
        self.assertTrue(set(CITYWIDE_COLUMNS).issubset(columns))
        self.assertTrue(set(CITYWIDE_EXCLUDED_COLUMNS).isdisjoint(columns))

    def test_edc_request_uses_separate_oge_domain(self):
        root = ET.fromstring(build_request_xml(EDC_SCOPE, records_from=1, max_records=50))
        self.assertEqual(root.findtext("type_of_data"), "Contracts_OGE")
        criteria = {
            node.findtext("name"): node.findtext("value")
            for node in root.findall("./search_criteria/criteria")
        }
        self.assertEqual(criteria["other_government_entities_code"], "z81")

    def test_parse_success_response_preserves_source_strings(self):
        api = FakeCheckbookApi(citywide=[citywide_row("CT0001", "Cooling tower cleaning")])
        count, rows = parse_response_xml(
            api(build_request_xml(CITYWIDE_SCOPE, records_from=1, max_records=10)),
            identity_field="prime_contract_id",
        )
        self.assertEqual(count, 1)
        self.assertEqual(rows[0]["prime_contract_id"], "CT0001")
        self.assertEqual(rows[0]["prime_contract_current_amount"], "250000")

    def test_api_failure_is_not_converted_to_empty_source(self):
        api = FakeCheckbookApi(api_failure=True)
        with self.assertRaisesRegex(CheckbookSourceError, "bad request"):
            fetch_scope(CITYWIDE_SCOPE, request_xml=api, page_size=2)

    def test_exact_one_based_pagination(self):
        api = FakeCheckbookApi(
            citywide=[
                citywide_row("CT1", "Cooling tower cleaning"),
                citywide_row("CT2", "Legionella testing"),
                citywide_row("CT3", "Chiller service"),
            ]
        )
        scope = fetch_scope(CITYWIDE_SCOPE, request_xml=api, page_size=2)
        self.assertEqual(scope.expected_count, 3)
        self.assertEqual(len(scope.rows), 3)
        self.assertEqual([call["records_from"] for call in api.calls], [1, 3])

    def test_count_drift_fails_closed(self):
        api = FakeCheckbookApi(
            citywide=[
                citywide_row("CT1", "Cooling tower cleaning"),
                citywide_row("CT2", "Legionella testing"),
                citywide_row("CT3", "Chiller service"),
            ]
        )
        calls = 0

        def drifting(payload):
            nonlocal calls
            calls += 1
            response = ET.fromstring(api(payload))
            if calls == 2:
                response.find("./result_records/record_count").text = "4"
            return ET.tostring(response, encoding="utf-8")

        with self.assertRaisesRegex(CheckbookSourceError, "record_count changed"):
            fetch_scope(CITYWIDE_SCOPE, request_xml=drifting, page_size=2)

    def test_duplicate_prime_rows_with_subvendors_collapse_without_losing_relevant_subcontract(self):
        first = citywide_row(
            "CT1",
            "Cooling tower water treatment",
            sub_vendor="Sub One LLC",
            sub_purpose="Office furniture",
            sub_reference="SUB-1",
        )
        second = citywide_row(
            "CT1",
            "Cooling tower water treatment",
            sub_vendor="Sub Two LLC",
            sub_purpose="Legionella testing",
            sub_reference="SUB-2",
        )
        api = FakeCheckbookApi(
            citywide=[first, second, citywide_row("CT2", "Bottled water delivery")],
            edc=[edc_row("EDC1", "Office furniture")],
        )
        payload = build_checkbook_cache(
            request_xml=api,
            retrieved_at="2026-08-26T23:00:00Z",
            page_size=2,
        )
        citywide = [row for row in payload["contracts"] if row["source"] == CITYWIDE_SOURCE]
        primes = [row for row in citywide if row["vendor_role"] == "PRIME"]
        subs = [row for row in citywide if row["vendor_role"] == "SUBCONTRACTOR"]
        self.assertEqual(len(primes), 1)
        self.assertEqual(primes[0]["source_contract_id"], "CT1")
        self.assertEqual(len(subs), 1)
        self.assertEqual(subs[0]["source_contract_id"], "SUB-2")
        self.assertEqual(subs[0]["service_category"], "LEGIONELLA_TESTING")
        self.assertEqual(subs[0]["parent_contract_id"], "CT1")

    def test_conflicting_duplicate_prime_material_fails_closed(self):
        first = citywide_row("CT1", "Cooling tower cleaning", amount="100")
        second = citywide_row("CT1", "Cooling tower cleaning", amount="200")
        api = FakeCheckbookApi(citywide=[first, second], edc=[])
        with self.assertRaisesRegex(CheckbookSourceError, "conflicting material fields"):
            build_checkbook_cache(
                request_xml=api,
                retrieved_at="2026-08-26T23:00:00Z",
                page_size=2,
            )

    def test_edc_relevant_contract_normalizes_separately(self):
        api = FakeCheckbookApi(
            citywide=[citywide_row("CT1", "Office furniture")],
            edc=[edc_row("EDC1", "Cooling tower maintenance and repair")],
        )
        payload = build_checkbook_cache(
            request_xml=api,
            retrieved_at="2026-08-26T23:00:00Z",
            page_size=2,
        )
        edc = [row for row in payload["contracts"] if row["source"] == EDC_SOURCE]
        self.assertEqual(len(edc), 1)
        self.assertEqual(edc[0]["source_contract_id"], "EDC1")
        self.assertEqual(edc[0]["service_category"], "COOLING_TOWER_REPAIR")
        self.assertEqual(edc[0]["company_match_confidence"], "UNRESOLVED")
        self.assertEqual(edc[0]["tower_link_confidence"], "UNLINKED")

    def test_build_payload_preserves_counts_health_and_nycha_boundary(self):
        api = FakeCheckbookApi(
            citywide=[
                citywide_row("CT1", "Cooling tower cleaning"),
                citywide_row("CT2", "Bottled water delivery"),
                citywide_row("CT3", "Water services for institutional facilities"),
            ],
            edc=[
                edc_row("EDC1", "Legionella testing"),
                edc_row("EDC2", "Office furniture"),
            ],
        )
        payload = build_checkbook_cache(
            request_xml=api,
            retrieved_at="2026-08-26T23:00:00Z",
            page_size=2,
        )
        summary = payload["summary"]
        self.assertEqual(summary["citywide_source_transaction_count"], 3)
        self.assertEqual(summary["edc_source_transaction_count"], 2)
        self.assertEqual(summary["relevant_contract_count"], 3)
        self.assertEqual(summary["unresolved_vendor_count"], 3)
        self.assertIn("not company revenue", summary["value_semantics"].lower())
        self.assertEqual(payload["source_health"][CITYWIDE_SOURCE]["status"], "WARNING")
        self.assertEqual(payload["source_health"][EDC_SOURCE]["status"], "WARNING")
        self.assertTrue(all(row["raw"] for row in payload["contracts"]))
        self.assertTrue(all(row["facility_match_confidence"] == "UNLINKED" for row in payload["contracts"]))
        deferred = payload["source"]["deferred_scopes"]
        self.assertEqual(deferred[0]["name"], "NYCHA")
        self.assertEqual(deferred[0]["status"], "DEFERRED_SEPARATE_ADAPTER")


if __name__ == "__main__":
    unittest.main()
