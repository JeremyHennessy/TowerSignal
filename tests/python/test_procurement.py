import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.procurement import (
    ClassificationResult,
    classify_procurement,
    company_alias_record,
    company_record,
    derive_company_metrics,
    normalize_company_name,
    normalize_contract,
    normalize_notice,
    parse_iso_date,
    parse_money,
    procurement_history_events,
    procurement_source_health,
    resolve_company,
)


class ProcurementArchitectureTests(unittest.TestCase):
    def test_money_normalization_handles_public_api_formats(self):
        self.assertEqual(parse_money("$1,234,567.89"), 1234567.89)
        self.assertEqual(parse_money("(125.50)"), -125.50)
        self.assertIsNone(parse_money(""))
        self.assertIsNone(parse_money("not-money"))

    def test_date_normalization_handles_common_source_formats(self):
        self.assertEqual(parse_iso_date("2026-08-26T00:00:00.000"), "2026-08-26")
        self.assertEqual(parse_iso_date("08/26/2026"), "2026-08-26")
        self.assertEqual(parse_iso_date("20260826"), "2026-08-26")
        self.assertIsNone(parse_iso_date("unknown"))

    def test_high_confidence_cooling_tower_classification_preserves_evidence(self):
        result = classify_procurement("Cooling Tower Cleaning and Disinfection at Bellevue Hospital")
        self.assertIsInstance(result, ClassificationResult)
        self.assertEqual(result.service_category, "COOLING_TOWER_CLEANING")
        self.assertEqual(result.confidence, "CONFIRMED")
        self.assertIn("cooling tower cleaning", result.matched_terms)
        self.assertIn("Bellevue", result.source_text)

    def test_specific_legionella_and_water_treatment_categories(self):
        self.assertEqual(classify_procurement("Legionella testing and sampling services").service_category, "LEGIONELLA_TESTING")
        self.assertEqual(classify_procurement("Condenser water treatment program").service_category, "COOLING_WATER_TREATMENT")
        self.assertEqual(classify_procurement("Boiler water treatment chemicals").service_category, "BOILER_WATER_TREATMENT")

    def test_broad_water_services_requires_verification(self):
        result = classify_procurement("Provide water services for institutional facilities")
        self.assertEqual(result.service_category, "OTHER_RELEVANT_WATER_SERVICE")
        self.assertEqual(result.confidence, "VERIFY")

    def test_negative_context_does_not_become_cooling_tower_intelligence(self):
        for description in (
            "Bottled water delivery services",
            "Water meter replacement",
            "Stormwater management services",
            "Swimming pool maintenance and water treatment",
        ):
            with self.subTest(description=description):
                result = classify_procurement(description)
                self.assertEqual(result.service_category, "UNRELATED")

    def test_company_normalization_handles_legal_suffix_aliases_without_acronym_merge(self):
        self.assertEqual(normalize_company_name("Rochester Midland Corporation"), "ROCHESTER MIDLAND")
        self.assertEqual(normalize_company_name("ROCHESTER MIDLAND CORP."), "ROCHESTER MIDLAND")
        self.assertEqual(normalize_company_name("RMC"), "RMC")

    def test_authoritative_vendor_id_is_confirmed_resolution(self):
        company = company_record("Rochester Midland Corporation", company_id="company-rmc")
        aliases = [
            company_alias_record(
                "company-rmc",
                "ROCHESTER MIDLAND CORP",
                source="CHECKBOOK_NYC",
                source_vendor_id="V-100",
                confidence="CONFIRMED",
                resolution_method="AUTHORITATIVE_VENDOR_ID",
            )
        ]
        result = resolve_company(
            "Rochester Midland Corp",
            source="CHECKBOOK_NYC",
            source_vendor_id="V-100",
            address=None,
            companies=[company],
            aliases=aliases,
        )
        self.assertEqual(result.company_id, "company-rmc")
        self.assertEqual(result.confidence, "CONFIRMED")
        self.assertEqual(result.resolution_method, "AUTHORITATIVE_VENDOR_ID")

    def test_normalized_name_and_compatible_address_is_strong(self):
        company = company_record("Example Water Technologies", company_id="company-example")
        aliases = [
            company_alias_record(
                "company-example",
                "EXAMPLE WATER TECHNOLOGIES LLC",
                source="OPEN_BOOK_NY",
                address="10 Main Street, Albany NY 12207",
                confidence="STRONG",
                resolution_method="NORMALIZED_NAME_AND_ADDRESS",
            )
        ]
        result = resolve_company(
            "Example Water Technologies Inc.",
            source="OPEN_BOOK_NY",
            source_vendor_id=None,
            address="10 MAIN ST, ALBANY NY 12207",
            companies=[company],
            aliases=aliases,
        )
        self.assertEqual(result.company_id, "company-example")
        self.assertEqual(result.confidence, "STRONG")

    def test_acronym_only_match_does_not_silently_merge(self):
        company = company_record("Rochester Midland Corporation", company_id="company-rmc")
        aliases = [
            company_alias_record(
                "company-rmc",
                "RMC",
                source="MANUAL_REVIEW",
                confidence="VERIFY",
                resolution_method="ACRONYM_REVIEW",
            )
        ]
        result = resolve_company(
            "RMC",
            source="CITY_RECORD",
            source_vendor_id=None,
            address=None,
            companies=[company],
            aliases=aliases,
        )
        self.assertEqual(result.company_id, "company-rmc")
        self.assertEqual(result.confidence, "VERIFY")

    def test_generic_company_words_are_not_used_for_fuzzy_merges(self):
        companies = [
            company_record("Alpha Water Services", company_id="company-alpha"),
            company_record("Beta Water Services", company_id="company-beta"),
        ]
        result = resolve_company(
            "Water Services",
            source="OPEN_BOOK_NY",
            source_vendor_id=None,
            address=None,
            companies=companies,
            aliases=[],
        )
        self.assertIsNone(result.company_id)
        self.assertEqual(result.confidence, "UNRESOLVED")

    def test_contract_normalization_keeps_procurement_separate_from_tower_linkage(self):
        company = company_record("Rochester Midland Corporation", company_id="company-rmc")
        resolution = resolve_company(
            "Rochester Midland Corp",
            source="CHECKBOOK_NYC",
            source_vendor_id=None,
            address=None,
            companies=[company],
            aliases=[],
        )
        contract = normalize_contract(
            source="CHECKBOOK_NYC",
            source_record_id="row-1",
            source_contract_id="CT-123",
            vendor_raw="Rochester Midland Corp",
            buyer_name="NYC Health + Hospitals",
            title="Cooling tower water treatment",
            description="Provide cooling tower water treatment and chemicals",
            retrieved_at="2026-08-26T20:00:00Z",
            raw={"contract": "CT-123"},
            company_resolution=resolution,
            current_amount="$250,000",
            spend_to_date="125000",
            start_date="01/01/2026",
            end_date="12/31/2028",
            facility_raw="Bellevue Hospital",
            facility_match_confidence="CONTEXT",
            tower_account_system_ids=[],
            tower_link_confidence="UNLINKED",
        )
        self.assertEqual(contract["company_id"], "company-rmc")
        self.assertEqual(contract["service_category"], "COOLING_WATER_TREATMENT")
        self.assertEqual(contract["current_amount"], 250000.0)
        self.assertEqual(contract["facility_match_confidence"], "CONTEXT")
        self.assertEqual(contract["tower_link_confidence"], "UNLINKED")
        self.assertEqual(contract["tower_account_system_ids"], [])
        self.assertEqual(contract["raw"], {"contract": "CT-123"})

    def test_notice_normalization_never_promotes_unrelated_hvac_keyword_noise(self):
        notice = normalize_notice(
            source="NYC_CITY_RECORD",
            source_record_id="notice-1",
            notice_id="N-1",
            title="Bottled water delivery",
            procurement_text="Delivery of bottled water for HVAC staff offices",
            retrieved_at="2026-08-26T20:00:00Z",
            raw={"id": "N-1"},
            due_date="09/15/2026",
        )
        self.assertEqual(notice["service_category"], "UNRELATED")
        self.assertEqual(notice["due_date"], "2026-09-15")

    def test_source_health_fails_closed_on_partial_pagination(self):
        health = procurement_source_health(
            source="CHECKBOOK_NYC",
            last_success=None,
            last_attempt="2026-08-26T20:00:00Z",
            record_count=100,
            relevant_record_count=12,
            normalized_contract_count=10,
            normalized_notice_count=0,
            resolved_company_count=8,
            unresolved_vendor_count=2,
            facility_link_count=1,
            exact_tower_link_count=0,
            pagination_complete=False,
            schema_valid=True,
            freshness="CURRENT",
        )
        self.assertEqual(health["status"], "FAILED")
        self.assertIn("PAGINATION_INCOMPLETE", health["status_reasons"])

    def test_entity_resolution_uncertainty_is_visible_in_source_health(self):
        health = procurement_source_health(
            source="OPEN_BOOK_NY",
            last_success="2026-08-26T20:00:00Z",
            last_attempt="2026-08-26T20:00:00Z",
            record_count=100,
            relevant_record_count=12,
            normalized_contract_count=12,
            normalized_notice_count=0,
            resolved_company_count=10,
            unresolved_vendor_count=2,
            facility_link_count=0,
            exact_tower_link_count=0,
            pagination_complete=True,
            schema_valid=True,
            freshness="CURRENT",
        )
        self.assertEqual(health["status"], "WARNING")
        self.assertIn("ENTITY_RESOLUTION_UNCERTAINTY", health["status_reasons"])

    def test_company_metrics_are_explicitly_observed_public_metrics(self):
        contracts = [
            {
                "buyer_name": "Hospital A",
                "current_amount": 100000.0,
                "spend_to_date": 50000.0,
                "start_date": "2025-01-01",
                "end_date": "2027-01-01",
                "service_category": "COOLING_WATER_TREATMENT",
                "state": "NY",
            },
            {
                "buyer_name": "Hospital A",
                "current_amount": 50000.0,
                "spend_to_date": 25000.0,
                "start_date": "2023-01-01",
                "end_date": "2024-01-01",
                "service_category": "LEGIONELLA_TESTING",
                "state": "NY",
            },
            {
                "buyer_name": "University B",
                "current_amount": 25000.0,
                "spend_to_date": 10000.0,
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "service_category": "HVAC_MECHANICAL",
                "state": "NJ",
            },
        ]
        metrics = derive_company_metrics(contracts, as_of=date(2026, 8, 26))
        self.assertEqual(metrics["observed_contract_count"], 3)
        self.assertEqual(metrics["active_contract_count"], 2)
        self.assertEqual(metrics["observed_contract_value"], 175000.0)
        self.assertEqual(metrics["observed_customer_count"], 2)
        self.assertEqual(metrics["repeat_customer_count"], 1)
        self.assertEqual(metrics["geographic_state_count"], 2)
        self.assertEqual(metrics["water_treatment_contract_count"], 1)
        self.assertEqual(metrics["legionella_contract_count"], 1)

    def test_first_procurement_baseline_creates_no_synthetic_event_flood(self):
        current = {
            "contract-1": {"source": "CHECKBOOK_NYC", "current_amount": 100.0},
            "contract-2": {"source": "OPEN_BOOK_NY", "current_amount": 200.0},
        }
        self.assertEqual(procurement_history_events(None, current, observed_at="2026-08-26T20:00:00Z"), [])

    def test_subsequent_history_detects_value_due_date_and_new_records(self):
        previous = {
            "contract-1": {"source": "CHECKBOOK_NYC", "current_amount": 100.0, "company_id": "a"},
            "notice-1": {"source": "NYC_CITY_RECORD", "notice_id": "N-1", "due_date": "2026-09-01"},
        }
        current = {
            "contract-1": {"source": "CHECKBOOK_NYC", "current_amount": 150.0, "company_id": "a"},
            "notice-1": {"source": "NYC_CITY_RECORD", "notice_id": "N-1", "due_date": "2026-09-15"},
            "contract-2": {"source": "OPEN_BOOK_NY", "current_amount": 200.0, "company_id": "b"},
        }
        events = procurement_history_events(previous, current, observed_at="2026-08-27T20:00:00Z")
        self.assertEqual(
            {event["event_type"] for event in events},
            {"CONTRACT_VALUE_CHANGED", "PROCUREMENT_DUE_DATE_CHANGED", "CONTRACT_ADDED"},
        )


if __name__ == "__main__":
    unittest.main()
