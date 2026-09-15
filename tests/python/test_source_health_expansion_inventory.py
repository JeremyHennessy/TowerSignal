from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('source_health_inventory_builder', ROOT / 'scripts/build_coverage_audit.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SourceHealthExpansionInventoryTests(unittest.TestCase):
    def test_both_published_cache_artifacts_are_in_the_inventory_once(self):
        contracts = module.ARTIFACT_CONTRACTS
        for filename in ('property-enforcement.json', 'legionella-alerts.json'):
            self.assertEqual(sum(row[1] == filename for row in contracts), 1)
        enforcement = next(row for row in contracts if row[1] == 'property-enforcement.json')
        alerts = next(row for row in contracts if row[1] == 'legionella-alerts.json')
        self.assertIn('not an active-SWO ledger', enforcement[2])
        self.assertIn('generic Labor Law', enforcement[2])
        self.assertIn('ZIP context is not property attribution', alerts[2])
        self.assertIn('no Priority Score change', alerts[2])


if __name__ == '__main__':
    unittest.main()
