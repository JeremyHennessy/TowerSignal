from __future__ import annotations

import unittest

from scripts.build_toronto_ewrb_market_context import build


class TorontoEwrbMarketContextTests(unittest.TestCase):
    def test_aggregate_contract_and_repaired_years(self) -> None:
        payload = build()
        self.assertEqual(payload['scope'], 'TORONTO_AGGREGATE_ONLY')
        self.assertEqual(payload['toronto_reporting_rows'], 11595)
        self.assertEqual(payload['reporting_years'], [2018, 2019, 2020, 2021, 2022, 2023, 2024])
        counts = {item['year']: item['reporting_rows'] for item in payload['annual']}
        self.assertEqual(counts, {2018: 253, 2019: 1328, 2020: 1430, 2021: 1415, 2022: 2445, 2023: 2265, 2024: 2459})
        self.assertEqual(sum(counts.values()), 11595)
        self.assertEqual(payload['identity_contract']['property_level_links'], 0)
        self.assertEqual(payload['identity_contract']['tower_evidence_effect'], 'NONE')
        self.assertEqual(payload['identity_contract']['relationship_effect'], 'NONE')

    def test_aggregate_does_not_publish_individual_building_rows(self) -> None:
        payload = build()
        serialized_keys = set(payload)
        self.assertNotIn('properties', serialized_keys)
        self.assertNotIn('rows', serialized_keys)
        self.assertTrue(payload['overall_top_property_types'])
        self.assertTrue(payload['overall_top_postal_fsa'])
        for year in payload['annual']:
            self.assertNotIn('ewrb_ids', year)
            self.assertNotIn('properties', year)


if __name__ == '__main__':
    unittest.main()
