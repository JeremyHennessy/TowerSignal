import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.checkbook import CITYWIDE_PRIME_MATERIAL_FIELDS, CheckbookSourceError
from towersignal.checkbook_recent import _choose_prime_version_candidate


def row(
    *,
    amount="100",
    spent="50",
    expense_category="Services",
    purpose="Cooling tower cleaning",
    end_date="2027-12-31",
    contract_type="WORK/LABOR",
):
    return {
        "prime_contract_id": "CT1",
        "prime_vendor": "Example Water LLC",
        "prime_contract_purpose": purpose,
        "prime_contract_original_amount": amount,
        "prime_contract_current_amount": amount,
        "prime_vendor_spent_to_date": spent,
        "prime_contract_start_date": "2025-01-01",
        "prime_contract_end_date": end_date,
        "prime_contracting_agency": "Health + Hospitals",
        "prime_contract_version": "2",
        "parent_contract_id": "-",
        "prime_contract_type": contract_type,
        "prime_contract_award_method": "RENEWAL OF CONTRACT",
        "prime_contract_expense_category": expense_category,
        "prime_contract_industry": "Services",
        "prime_contract_pin": "PIN-1",
    }


class CheckbookPlaceholderResolutionTests(unittest.TestCase):
    def test_nonzero_row_wins_and_context_variants_are_retained(self):
        populated = row(
            amount="175",
            spent="120",
            expense_category="DATA PROCESSING EQUIPMENT MAINTENANCE",
            end_date="2027-01-31",
            contract_type="WORK/LABOR",
        )
        placeholder = row(
            amount="0",
            spent="0",
            expense_category="CONTRACTUAL SERVICES GENERAL, DATA PROCESSING EQUIPMENT MAINTENANCE",
            end_date="2027-10-22",
            contract_type="REQUIREMENTS-SERVICES",
        )
        chosen = _choose_prime_version_candidate(
            [populated, placeholder],
            identity="CT1",
            fiscal_year=2027,
            material_fields=CITYWIDE_PRIME_MATERIAL_FIELDS,
        )
        self.assertEqual(chosen["prime_contract_current_amount"], "175")
        self.assertEqual(chosen["prime_vendor_spent_to_date"], "120")
        self.assertEqual(chosen["prime_contract_expense_category"], "DATA PROCESSING EQUIPMENT MAINTENANCE")
        self.assertEqual(chosen["prime_contract_type"], "WORK/LABOR")
        self.assertEqual(chosen["prime_contract_end_date"], "2027-01-31")
        self.assertEqual(chosen["_source_observed_end_dates"], "2027-01-31|2027-10-22")
        self.assertEqual(
            json.loads(chosen["_source_expense_category_variants"]),
            [
                "CONTRACTUAL SERVICES GENERAL, DATA PROCESSING EQUIPMENT MAINTENANCE",
                "DATA PROCESSING EQUIPMENT MAINTENANCE",
            ],
        )
        self.assertEqual(
            json.loads(chosen["_source_contract_type_variants"]),
            ["REQUIREMENTS-SERVICES", "WORK/LABOR"],
        )
        self.assertEqual(chosen["_source_duplicate_row_count"], "2")
        self.assertEqual(chosen["_source_duplicate_resolution"], "NONZERO_OVER_ZERO_PLACEHOLDER")

    def test_distinct_nonblank_identity_values_still_fail_closed(self):
        first = row(amount="175", spent="120", purpose="Cooling tower cleaning")
        second = row(amount="0", spent="0", purpose="Different supported purpose")
        with self.assertRaisesRegex(CheckbookSourceError, "conflicting non-monetary fields"):
            _choose_prime_version_candidate(
                [first, second],
                identity="CT1",
                fiscal_year=2027,
                material_fields=CITYWIDE_PRIME_MATERIAL_FIELDS,
            )


if __name__ == "__main__":
    unittest.main()
