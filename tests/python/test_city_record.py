import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.city_record import (
    METADATA_URL,
    REQUIRED_FIELDS,
    RESOURCE_URL,
    build_city_record_payload,
    city_record_scopes,
    fetch_city_record_metadata,
    fetch_scope,
    normalize_city_record_row,
)


class FakeCityRecordApi:
    def __init__(self, *, metadata_fields=None, rows_by_where=None, malformed_page=False, fail=False):
        self.metadata_fields = set(metadata_fields or REQUIRED_FIELDS)
        self.rows_by_where = rows_by_where or {}
        self.malformed_page = malformed_page
        self.fail = fail
        self.calls = []

    def __call__(self, url, params=None, **_kwargs):
        self.calls.append((url, params))
        if self.fail:
            raise TimeoutError("source timeout")
        if url == METADATA_URL:
            return {
                "name": "City Record Online",
                "rowsUpdatedAt": 1787500000,
                "columns": [{"fieldName": field} for field in sorted(self.metadata_fields)],
            }
        if url != RESOURCE_URL:
            raise AssertionError(url)
        params = params or {}
        where = params.get("$where")
        rows = list(self.rows_by_where.get(where, []))
        if params.get("$select") == "count(*) AS count":
            return [{"count": str(len(rows))}]
        if self.malformed_page:
            return {"unexpected": True}
        offset = int(params.get("$offset", 0))
        limit = int(params.get("$limit", len(rows)))
        return rows[offset:offset + limit]


def row(request_id, title, *, notice_type="Solicitation", due="2026-09-15T00:00:00.000", start="2026-08-20T00:00:00.000", vendor=None, amount=None):
    return {
        "request_id": str(request_id),
        "start_date": start,
        "end_date": start,
        "agency_name": "Health + Hospitals",
        "type_of_notice_description": notice_type,
        "category_description": "Services (other than human services)",
        "short_title": title,
        "selection_method_description": "Competitive Sealed Bids",
        "section_name": "Procurement",
        "pin": f"PIN-{request_id}",
        "due_date": due,
        "contact_name": "Procurement Contact",
        "contact_phone": "212-555-0100",
        "email": "procurement@example.nyc.gov",
        "contract_amount": amount,
        "additional_description_1": title,
        "other_info_1": "Public procurement notice",
        "vendor_name": vendor,
        "vendor_address": "1 Main St" if vendor else None,
        "printout_1": title,
        "document_links": f"https://example.nyc.gov/notices/{request_id}",
        "address_to_request": "100 Centre Street",
    }


class CityRecordTests(unittest.TestCase):
    def test_scopes_are_bounded_and_deterministic(self):
        scopes = dict(city_record_scopes(date(2026, 8, 26), award_lookback_days=730))
        self.assertIn("type_of_notice_description = 'Solicitation'", scopes["OPEN_SOLICITATIONS"])
        self.assertIn("due_date >= '2026-08-26T00:00:00.000'", scopes["OPEN_SOLICITATIONS"])
        self.assertIn("type_of_notice_description = 'Award'", scopes["RECENT_AWARDS"])
        self.assertIn("start_date >= '2024-08-26T00:00:00.000'", scopes["RECENT_AWARDS"])

    def test_schema_validation_accepts_required_fields(self):
        metadata = fetch_city_record_metadata(request_json=FakeCityRecordApi())
        self.assertEqual(metadata["dataset_id"], "dg92-zbpx")
        self.assertTrue(REQUIRED_FIELDS.issubset(set(metadata["field_names"])))

    def test_schema_change_fails_closed(self):
        fields = set(REQUIRED_FIELDS)
        fields.remove("request_id")
        with self.assertRaisesRegex(RuntimeError, "request_id"):
            fetch_city_record_metadata(request_json=FakeCityRecordApi(metadata_fields=fields))

    def test_pagination_retrieves_exact_count_and_orders_by_request_id(self):
        where = "scope"
        api = FakeCityRecordApi(rows_by_where={where: [row(1, "Cooling tower cleaning"), row(2, "Legionella testing"), row(3, "Chiller service")]})
        result = fetch_scope("TEST", where, request_json=api, page_size=2)
        self.assertEqual(result.expected_count, 3)
        self.assertEqual(len(result.rows), 3)
        page_calls = [params for url, params in api.calls if url == RESOURCE_URL and params.get("$select") is None]
        self.assertEqual([call["$offset"] for call in page_calls], [0, 2])
        self.assertTrue(all(call["$order"] == "request_id ASC" for call in page_calls))

    def test_empty_scope_is_valid_complete_source_state(self):
        result = fetch_scope("EMPTY", "none", request_json=FakeCityRecordApi(rows_by_where={"none": []}), page_size=2)
        self.assertEqual(result.expected_count, 0)
        self.assertEqual(result.rows, ())
        self.assertTrue(result.pagination_complete)

    def test_malformed_page_fails_closed(self):
        api = FakeCityRecordApi(rows_by_where={"scope": [row(1, "Cooling tower repair")]}, malformed_page=True)
        with self.assertRaisesRegex(RuntimeError, "not a list"):
            fetch_scope("TEST", "scope", request_json=api)

    def test_duplicate_request_ids_fail_closed(self):
        api = FakeCityRecordApi(rows_by_where={"scope": [row(1, "Cooling tower repair"), row(1, "Cooling tower repair")]})
        with self.assertRaisesRegex(RuntimeError, "duplicate request_id"):
            fetch_scope("TEST", "scope", request_json=api)

    def test_source_timeout_is_not_converted_to_empty_results(self):
        with self.assertRaises(TimeoutError):
            fetch_city_record_metadata(request_json=FakeCityRecordApi(fail=True))

    def test_normalization_preserves_raw_provenance_and_source_reported_amount_warning(self):
        source = row(77, "Cooling tower cleaning and disinfection", vendor="Example Water LLC", amount="250000")
        item = normalize_city_record_row(source, retrieved_at="2026-08-26T20:00:00Z", scope="RECENT_AWARDS")
        self.assertEqual(item["source"], "NYC_CITY_RECORD")
        self.assertEqual(item["service_category"], "COOLING_TOWER_CLEANING")
        self.assertEqual(item["service_confidence"], "CONFIRMED")
        self.assertEqual(item["vendor_raw"], "Example Water LLC")
        self.assertEqual(item["company_match_confidence"], "UNRESOLVED")
        self.assertEqual(item["amount"], 250000.0)
        self.assertEqual(item["amount_evidence"], "SOURCE_REPORTED_UNVALIDATED")
        self.assertEqual(item["raw"]["request_id"], "77")

    def test_build_payload_classifies_after_complete_scoped_retrieval(self):
        as_of = date(2026, 8, 26)
        scopes = dict(city_record_scopes(as_of, award_lookback_days=730))
        api = FakeCityRecordApi(rows_by_where={
            scopes["OPEN_SOLICITATIONS"]: [
                row(1, "Cooling tower cleaning and disinfection"),
                row(2, "Bottled water delivery"),
                row(3, "Water services for institutional facilities"),
            ],
            scopes["RECENT_AWARDS"]: [
                row(4, "Cooling tower water treatment", notice_type="Award", vendor="Rochester Midland Corp", amount="500000"),
                row(5, "Office furniture", notice_type="Award", vendor="Furniture Inc", amount="10000"),
            ],
        })
        payload = build_city_record_payload(
            as_of=as_of,
            award_lookback_days=730,
            request_json=api,
            retrieved_at="2026-08-26T20:00:00Z",
        )
        summary = payload["summary"]
        self.assertEqual(summary["scoped_record_count"], 5)
        self.assertEqual(summary["relevant_record_count"], 3)
        self.assertEqual(summary["open_relevant_opportunities"], 2)
        self.assertEqual(summary["recent_relevant_awards"], 1)
        self.assertEqual(summary["unresolved_vendor_count"], 1)
        self.assertEqual(payload["source_health"]["status"], "WARNING")
        self.assertTrue(payload["source_health"]["pagination_complete"])
        self.assertTrue(payload["source_health"]["schema_valid"])
        request_ids = {notice["source_record_id"] for notice in payload["notices"]}
        self.assertEqual(request_ids, {"1", "3", "4"})


if __name__ == "__main__":
    unittest.main()
