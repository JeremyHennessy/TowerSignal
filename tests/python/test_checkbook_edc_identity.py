import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.checkbook import (
    EDC_MATERIAL_FIELDS,
    CheckbookSourceError,
    _collapse_rows,
    _normalize_edc_contract,
)


def edc_line(
    *,
    contract_id="CTA180120100003482",
    entity_contract_number="1850118",
    commodity_line="4",
    vendor="RESTANI CONSTRUCTION CORP.",
    current_amount="6015284.25",
    spent_to_date="2647114.45",
    purpose="Cooling tower maintenance and repair",
):
    return {
        "award_method": "MULTIPLE AWARDS",
        "budget_name": "28th Avenue and Linden Place Area",
        "commodity_line": commodity_line,
        "contract_id": contract_id,
        "contract_industry": "Standardized Services",
        "contract_type": "99",
        "current_amount": current_amount,
        "document_code": "CTA1",
        "end_date": "2013-06-30",
        "entity_contract_number": entity_contract_number,
        "expense_category": "IOTB CONSTRUCTION",
        "original_amount": current_amount,
        "other_government_entities": "NEW YORK CITY ECONOMIC DEVELOPMENT CORPORATION",
        "parent_contract_id": "MMA180120090040040",
        "pin": "10801000046246",
        "prime_vendor": vendor,
        "purpose": purpose,
        "spent_to_date": spent_to_date,
        "start_date": "2009-07-01",
        "version": "4",
    }


class CheckbookEdcIdentityTests(unittest.TestCase):
    def test_shared_contract_id_keeps_distinct_entity_contract_lines(self):
        rows = [
            edc_line(),
            edc_line(
                entity_contract_number="30230001",
                commodity_line="2",
                vendor="NV5 NEW YORK-ENGINEERS, ARCHITECTS, LANDSCAPE ARCHITECTS AND",
                current_amount="413220.26",
                spent_to_date="307176.41",
            ),
        ]

        collapsed = _collapse_rows(
            rows,
            identity_field="contract_id",
            material_fields=EDC_MATERIAL_FIELDS,
        )
        self.assertEqual(len(collapsed), 2)

        contracts = [
            _normalize_edc_contract(row, retrieved_at="2026-08-27T03:00:00Z")
            for row in collapsed
        ]
        self.assertEqual(len({row["procurement_id"] for row in contracts}), 2)
        self.assertEqual({row["source_contract_id"] for row in contracts}, {"CTA180120100003482"})
        self.assertEqual(
            {(row["entity_contract_number"], row["commodity_line"]) for row in contracts},
            {("1850118", "4"), ("30230001", "2")},
        )
        self.assertTrue(
            all(
                row["source_record_identity_basis"] == "contract_id+entity_contract_number+commodity_line"
                for row in contracts
            )
        )

    def test_conflicting_values_within_same_exact_edc_line_still_fail_closed(self):
        rows = [
            edc_line(current_amount="100"),
            edc_line(current_amount="200"),
        ]
        with self.assertRaisesRegex(
            CheckbookSourceError,
            r"contract_id=CTA180120100003482.*entity_contract_number=1850118.*commodity_line=4",
        ):
            _collapse_rows(
                rows,
                identity_field="contract_id",
                material_fields=EDC_MATERIAL_FIELDS,
            )


if __name__ == "__main__":
    unittest.main()
