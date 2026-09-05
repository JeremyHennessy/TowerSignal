from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.checkbook_nycha import (  # noqa: E402
    build_payload,
    classify_nycha_water,
    fetch_partition,
    normalize_row,
    parse_nycha_response,
)


class CheckbookNychaTests(unittest.TestCase):
    def test_parser_accepts_nycha_transaction_container(self) -> None:
        xml = """
        <response>
          <status><result>success</result></status>
          <result_records>
            <record_count>1</record_count>
            <nycha_contract_transactions>
              <transaction>
                <contract_id>PO123</contract_id>
                <release_number>4</release_number>
                <line_number>8</line_number>
                <purpose>Water treatment</purpose>
              </transaction>
            </nycha_contract_transactions>
          </result_records>
        </response>
        """
        count, rows = parse_nycha_response(xml)
        self.assertEqual(count, 1)
        self.assertEqual(rows[0]["contract_id"], "PO123")
        self.assertEqual(rows[0]["line_number"], "8")

    def test_monochloramine_is_domestic_water_disinfection(self) -> None:
        result = classify_nycha_water("Citywide monochloramine treatment and water sampling")
        self.assertIn(result["service_category"], {"WATER_DISINFECTION", "DISINFECTION"})
        self.assertNotEqual(result["service_category"], "UNRELATED")

    def test_wastewater_is_excluded_without_explicit_protected_evidence(self) -> None:
        result = classify_nycha_water("Wastewater treatment pump repair")
        self.assertEqual(result["service_category"], "UNRELATED")
        self.assertEqual(result["classification_layer"], "NYCHA_CONTEXT_GUARD")

    def test_cooling_tower_evidence_survives_site_context(self) -> None:
        result = classify_nycha_water("Cooling tower maintenance at wastewater facility")
        self.assertEqual(result["service_category"], "COOLING_TOWER_MAINTENANCE")

    def test_line_and_contract_amounts_are_preserved_separately(self) -> None:
        row = {
            "contract_id": "PO-1",
            "release_number": "2",
            "line_number": "3",
            "shipment_number": "1",
            "approved_date": "2026-01-02",
            "purpose": "Domestic water treatment",
            "item_description": "Water treatment service",
            "vendor": "EXAMPLE WATER LLC",
            "location": "Development A",
            "line_current_amount": "100.00",
            "release_current_amount": "500.00",
            "contract_current_amount": "5000.00",
        }
        normalized = normalize_row(row, fiscal_year=2026, retrieved_at="2026-09-04T00:00:00Z")
        assert normalized is not None
        self.assertEqual(normalized["line_current_amount"], 100.0)
        self.assertEqual(normalized["release_current_amount"], 500.0)
        self.assertEqual(normalized["contract_current_amount"], 5000.0)
        self.assertEqual(normalized["company_match_confidence"], "UNRESOLVED")
        self.assertEqual(normalized["location_link_confidence"], "NYCHA_SOURCE_CONTEXT")

    def test_release_line_identity_changes_with_line_number(self) -> None:
        base = {
            "contract_id": "PO-1",
            "release_number": "2",
            "shipment_number": "1",
            "approved_date": "2026-01-02",
            "purpose": "Domestic water treatment",
            "item_description": "Water treatment service",
            "vendor": "EXAMPLE WATER LLC",
        }
        first = normalize_row({**base, "line_number": "3"}, fiscal_year=2026, retrieved_at="x")
        second = normalize_row({**base, "line_number": "4"}, fiscal_year=2026, retrieved_at="x")
        assert first is not None and second is not None
        self.assertNotEqual(first["source_record_id"], second["source_record_id"])

    def test_fetch_partition_uses_bounded_purpose_query(self) -> None:
        calls: list[dict[str, str]] = []

        def api(payload: bytes) -> bytes:
            import xml.etree.ElementTree as ET

            root = ET.fromstring(payload)
            criteria = {
                node.findtext("name"): node.findtext("value")
                for node in root.findall("./search_criteria/criteria")
            }
            calls.append(criteria)
            response = ET.Element("response")
            status = ET.SubElement(response, "status")
            ET.SubElement(status, "result").text = "success"
            records = ET.SubElement(response, "result_records")
            ET.SubElement(records, "record_count").text = "0"
            ET.SubElement(records, "nycha_contract_transactions")
            return ET.tostring(response, encoding="utf-8")

        partition = fetch_partition(2026, purpose_query="water", request_xml=api, page_size=10)
        self.assertEqual(partition.expected_count, 0)
        self.assertEqual(calls[0]["fiscal_year"], "2026")
        self.assertEqual(calls[0]["purpose"], "water")

    def test_build_payload_dedupes_overlapping_purpose_query_rows(self) -> None:
        import xml.etree.ElementTree as ET

        row = {
            "contract_id": "PO-1",
            "release_number": "2",
            "line_number": "3",
            "shipment_number": "1",
            "approved_date": "2026-01-02",
            "purpose": "Domestic water treatment",
            "item_description": "Water treatment service",
            "vendor": "EXAMPLE WATER LLC",
            "location": "Development A",
            "line_current_amount": "100.00",
        }

        def api(payload: bytes) -> bytes:
            root = ET.fromstring(payload)
            records_from = int(root.findtext("records_from") or "1")
            criteria = {
                node.findtext("name"): node.findtext("value")
                for node in root.findall("./search_criteria/criteria")
            }
            rows = [row] if criteria.get("purpose") in {"water", "domestic"} else []
            page = rows[records_from - 1:records_from]
            response = ET.Element("response")
            status = ET.SubElement(response, "status")
            ET.SubElement(status, "result").text = "success"
            records = ET.SubElement(response, "result_records")
            ET.SubElement(records, "record_count").text = str(len(rows))
            transactions = ET.SubElement(records, "nycha_contract_transactions")
            for source_row in page:
                transaction = ET.SubElement(transactions, "transaction")
                for key, value in source_row.items():
                    ET.SubElement(transaction, key).text = value
            return ET.tostring(response, encoding="utf-8")

        payload = build_payload(
            as_of=date(2026, 9, 5),
            fiscal_year_count=1,
            purpose_query_terms=("water", "domestic"),
            page_size=1,
            request_xml=api,
        )
        self.assertEqual(payload["summary"]["source_record_count"], 2)
        self.assertEqual(payload["summary"]["unique_scanned_release_line_count"], 1)
        self.assertEqual(payload["summary"]["relevant_release_line_count"], 1)
        self.assertEqual(len(payload["source_health"]), 2)
        self.assertEqual({source["purpose_query"] for source in payload["source_health"]}, {"water", "domestic"})


if __name__ == "__main__":
    unittest.main()
