"""Frozen audit checkpoint integrity tests; NOT live source or browser acceptance.
Usage: python test_continuation_checkpoint.py --audit-dir /path/to/continuation/audit
The full independent collectors/checkers and JSON censuses are in the downloadable
continuation checkpoint. These tests check their frozen accounting/proof boundaries.
"""
import argparse
import json
import unittest
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--audit-dir', type=Path, required=True)
args, remaining = parser.parse_known_args()

def read(name):
    return json.loads((args.audit_dir / (name + '.json')).read_text())

class FrozenCheckpointTests(unittest.TestCase):
    def test_multiset_values_and_counts_match(self):
        result = read('extended-attachment-results')
        self.assertEqual(result['record_value_multiset_comparisons'], 7 * result['accounts'])
        self.assertEqual(result['attachment_discrepancy_edges'], 0)

    def test_raw_field_checks_are_not_schema_count(self):
        rows = read('water-direct-field-contracts')
        self.assertEqual(len(rows), 68)
        self.assertEqual(sum(row['tested_rows'] for row in rows), 7930905)
        self.assertFalse(any(row['discrepancy_count'] for row in rows))

    def test_independent_selector_prediction(self):
        result = read('pinned-selector-results')
        self.assertEqual(result['selector_accounts_executed'], 4893)
        self.assertTrue(result['prediction_set_equal'])
        self.assertEqual(result['unsafe_dwt_confirmed_rows'], 548)

    def test_attachment_and_relationship_grains_stay_separate(self):
        result = read('unsafe-bin-expanded-summary')
        self.assertEqual(result['combined_edges'], result['prior_stage_edges'] + result['additional_domestic_water_edges'] + result['additional_building_water_edges'])
        self.assertEqual(result['combined_edges'], 488)

    def test_new_artifact_invalid_keys_and_relations(self):
        result = read('pages242-comparison-summary')
        self.assertTrue(result['account_id_sets_equal'])
        self.assertEqual(result['new_placeholder_system_bins'], 0)
        self.assertEqual(result['former_placeholder_accounts_remaining_unsafe_dwt_water_rows'], 0)
        self.assertEqual(result['new_placeholder_firm_tower_link_edges'], 0)

    def test_new_artifact_selector_boundaries(self):
        result = read('pages242-selector-results')
        self.assertEqual(result['placeholder_bin_confirmed_service_rows'], 0)
        self.assertEqual(result['former_placeholder_geometry_facade_rows'], 0)
        self.assertEqual(result['hpd_summary_detail_discrepancies'], 0)
        self.assertEqual(result['remaining_exact_bbl_role_label_defects'], 33)

    def test_remaining_market_identity_defect_not_hidden(self):
        result = read('pages242-market-site-collapse-results')
        self.assertEqual(result['placeholder_sites_with_multiple_distinct_source_bbls'], 14)
        self.assertEqual(result['sites_with_tower_links'], 0)

    def test_nys_gaps_remain_source_unverified(self):
        rows = read('nys-missing-field-unverified-census')
        self.assertEqual(len(rows), 363)
        self.assertTrue(all(row['retrieval'] == 'NOT_QUERIED_IN_THIS_CONTINUATION' for row in rows))
        self.assertTrue(all(row['diagnosis'].startswith('UNRESOLVED') for row in rows))

    def test_ledgers_do_not_claim_authenticated_completion(self):
        result = read('ledger-coverage')
        self.assertEqual(result['source_fields_enumerated'], 1288)
        self.assertEqual(sum(result['source_field_dispositions'].values()), 1288)
        self.assertEqual(result['source_field_dispositions']['UNRESOLVED'], 1123)
        self.assertEqual(result['current_authenticated_renderer_coverage'], 0)

if __name__ == '__main__':
    unittest.main(argv=['test_continuation_checkpoint.py', *remaining], verbosity=2)
