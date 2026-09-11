import importlib.util
from pathlib import Path
import sys
import unittest

scripts = Path(__file__).resolve().parents[2] / 'scripts'
sys.path.insert(0, str(scripts))
import reconcile_blob_copy as m

class ReconcileTests(unittest.TestCase):
    def setUp(self):
        self.prefix = 'test-prefix'
        self.files = [{'path': 'runtime/a.json', 'bytes': 3}, {'path': 'runtime/details/20/b.json', 'bytes': 0}]
        self.rows = [{'name': self.prefix + '/' + r['path'], 'bytes': r['bytes'], 'metadata': {'sha256': 'test'}} for r in self.files]
    def check(self, rows):
        return m.compare_inventory(rows, self.files, self.prefix)
    def directory(self, name, size=0, marked=True):
        return {'name': self.prefix + '/' + name, 'bytes': size, 'metadata': {'hdi_isfolder': 'true'} if marked else {}}
    def test_flat_listing(self):
        self.assertTrue(self.check(self.rows)['file_inventory_passed'])
    def test_expected_file_empty_is_not_directory(self):
        self.assertEqual(self.check(self.rows)['confirmed_parent_directories'], [])
    def test_only_marked_manifest_parents_are_recognized(self):
        dirs = [self.directory(n) for n in ['runtime', 'runtime/details', 'runtime/details/20']]
        report = self.check(self.rows + dirs)
        self.assertTrue(report['file_inventory_passed'])
        self.assertEqual(len(report['confirmed_parent_directories']), 3)
    def test_unmarked_zero_byte_extra_rejected(self):
        self.assertFalse(self.check(self.rows + [self.directory('runtime', marked=False)])['file_inventory_passed'])
    def test_unexpected_marked_folder_rejected(self):
        self.assertFalse(self.check(self.rows + [self.directory('unrelated')])['file_inventory_passed'])
    def test_nonempty_marked_folder_rejected(self):
        self.assertFalse(self.check(self.rows + [self.directory('runtime', size=1)])['file_inventory_passed'])
    def test_directory_cannot_substitute_for_manifest_file(self):
        rows = [self.rows[0], self.directory('runtime/details/20/b.json')]
        self.assertFalse(self.check(rows)['file_inventory_passed'])
    def test_missing_file(self):
        report = self.check(self.rows[:1])
        self.assertFalse(report['file_inventory_passed'])
        self.assertEqual(len(report['missing_files']), 1)
    def test_wrong_size_or_type_not_coerced(self):
        for value in [4, None, '3']:
            report = self.check([{**self.rows[0], 'bytes': value}, self.rows[1]])
            self.assertFalse(report['file_inventory_passed'])
    def test_extra_regular_file(self):
        self.assertFalse(self.check(self.rows + [self.directory('extra.json')])['file_inventory_passed'])
    def test_cross_prefix_and_duplicate_list_fail(self):
        for rows in [self.rows + [self.rows[0]], self.rows + [{'name': 'other/file', 'bytes': 0}]]:
            with self.assertRaises(m.MigrationError): self.check(rows)

if __name__ == '__main__': unittest.main()
