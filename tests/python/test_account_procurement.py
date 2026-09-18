import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from build_account_procurement import build, encoded, SOURCES, PAGE_BYTES


class AccountProcurementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'data'; self.root.mkdir()
        self.generated = '2026-09-18T10:00:00Z'
        self.write('systems.json', {'metadata': {'generated_at': self.generated}, 'systems': [{'system_id': '2001'}, {'system_id': '2002'}]})
        for sid in ['2001', '2002']:
            self.write(f'details/20/{sid}.json', {'identity': {'system_id': sid}, 'metadata': {'generated_at': self.generated}})
        for name, collection, _ in SOURCES:
            self.write(name, {'generated_at': self.generated, collection: []})

    def write(self, name, payload):
        path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(encoded(payload))

    def manifest(self, sid='2001'):
        return json.loads((self.root / f'account-procurement/20/{sid}/index.json').read_bytes())

    def run_build(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return build(self.root)

    def record(self, i, **kw):
        return {'procurement_id': f'p{i:03d}', 'source': 'FIXTURE', 'source_record_id': str(i), 'tower_account_system_ids': ['2001'], 'tower_link_confidence': 'CONFIRMED', 'source_url': 'https://example.com/source', **kw}

    def test_exact_links_full_rows_and_complete_paging(self):
        rows = [self.record(i, description='complete source record ' + str(i)) for i in range(43)]
        rows += [self.record(100, tower_link_confidence='CONTEXT'), self.record(101, tower_account_system_ids=['2002']), self.record(102, tower_account_system_ids=[]), self.record(103, tower_account_system_ids=['unknown'])]
        self.write(SOURCES[0][0], {'generated_at': self.generated, 'notices': rows})
        report = self.run_build(); manifest = self.manifest()
        self.assertEqual(manifest['record_count'], 43)
        self.assertEqual([p['record_count'] for p in manifest['pages']], [20, 20, 3])
        loaded = []
        for page in manifest['pages']:
            raw = (self.root / page['path']).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), page['sha256'])
            self.assertEqual(len(raw), page['bytes']); self.assertLessEqual(len(raw), PAGE_BYTES)
            loaded += json.loads(raw)['records']
        self.assertEqual(loaded, rows[:43]); self.assertEqual(self.manifest('2002')['record_count'], 1)
        self.assertEqual(report['linked_account_records'], 44)

    def test_missing_malformed_stale_and_partial_remain_explicit(self):
        (self.root / SOURCES[0][0]).unlink()
        (self.root / SOURCES[1][0]).write_text('{')
        self.write(SOURCES[2][0], {'generated_at': '2026-08-01T00:00:00Z', 'contracts': [self.record(1)]})
        self.write(SOURCES[3][0], {'generated_at': self.generated, 'contracts': [], 'source_health': {'status': 'ERROR', 'pagination_complete': False}})
        self.run_build(); manifest = self.manifest()
        self.assertEqual([s['status'] for s in manifest['sources']], ['UNAVAILABLE', 'MALFORMED', 'STALE', 'INCOMPLETE', 'LOADED'])
        self.assertIsNone(manifest['sources'][0]['record_count'])
        self.assertEqual(manifest['record_count'], 1)  # retained stale-source evidence is not erased

    def test_repeat_generation_is_byte_identical_and_does_not_mutate_inputs(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*.json')}
        self.run_build(); first = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*.json')}
        self.run_build(); second = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*.json')}
        self.assertEqual(first, second)
        for name, raw in before.items(): self.assertEqual(second[name], raw)
        self.assertEqual(self.manifest()['pages'], [])

    def test_oversize_record_refuses_publication_and_preserves_previous_projection(self):
        self.run_build(); before = (self.root / 'account-procurement/20/2001/index.json').read_bytes()
        self.write(SOURCES[0][0], {'generated_at': self.generated, 'notices': [self.record(0, description='x' * PAGE_BYTES)]})
        with self.assertRaisesRegex(ValueError, 'exceeds page budget'): self.run_build()
        self.assertEqual((self.root / 'account-procurement/20/2001/index.json').read_bytes(), before)

    def test_both_producers_publish_projection_before_build_and_blob_inventory_includes_it(self):
        repo = Path(__file__).resolve().parents[2]
        for name in ['pages.yml', 'azure-data-refresh.yml']:
            workflow = (repo / '.github/workflows' / name).read_text()
            self.assertLess(workflow.index('python scripts/build_account_procurement.py'), workflow.index('name: Production build'))
        self.run_build()
        import blob_release_store
        names = {r['path'] for r in blob_release_store.local_records(self.root)}
        self.assertIn('account-procurement/20/2001/index.json', names)


if __name__ == '__main__': unittest.main()
