import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.checkbook import CITYWIDE_PRIME_MATERIAL_FIELDS, CheckbookSourceError
from towersignal.checkbook_recent import _choose_prime_version_candidate


def row(*, amount="100", spent="50", expense_category="Services", purpose="Cooling tower cleaning"):
    return {
        "prime_contract_id": "CT1",
        "prime_vendor": "Example Water LLC",
        "prime_contract_purpose": purpose,
        "prime_contract_original_amount": amount,
        "prime_contract_current_amount": amount,
        "prime_vendor_spent_to_date": spent,
        "prime_contract_start_date": "2025-01-01",
        "prime_contract_end_date": "2027-12-31",
        "prime_contracting_agency": "Health + Hospitals",
        "prime_contract_version": "2",
        "parent_contract_id": "-",
        "prime_contract_type": "WORK/LABOR",
        "prime_contract_award_method": "RENEWAL OF CONTRACT",
        "prime_contract_expense_category": expense_category,
        "prime_contract_industry": "Services",
        "prime_contract_pin": "PIN-1",
    }


class CheckbookPlaceholderResolutionTests(unittest.TestCase):
    def test_nonzero_row_wins_when_zero_placeholder_only_omits_descriptive_value(self):
        populated = row(amount="175", spent="120", expense_category="Services")
        placeholder = row(amount="0", spent="0", expense_category="")
        chosen = _choose_prime_version_candidate(
            [populated, placeholder],
            identity="CT1",
            fiscal_year=2027,
            material_fields=CITYWIDE_PRIME_MATERIAL_FIELDS,
        )
        self.assertEqual(chosen["prime_contract_current_amount"], "175")
        self.assertEqual(chosen["prime_vendor_spent_to_date"], "120")
        self.assertEqual(chosen["prime_contract_expense_category"], "Services")
        self.assertEqual(chosen["_source_duplicate_row_count"], "2")
        self.assertEqual(chosen["_source_duplicate_resolution"], "NONZERO_OVER_ZERO_PLACEHOLDER")

    def test_distinct_nonblank_descriptive_values_still_fail_closed(self):
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
