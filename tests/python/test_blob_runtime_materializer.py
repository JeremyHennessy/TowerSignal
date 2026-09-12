import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import blob_release_store as b
import materialize_blob_runtime as m


class MemoryStore:
    def __init__(self):
        self.data = {}
        self.metadata = {}
        self.version = {}

    def seed(self, name, data):
        self.data[name] = data
        self.version[name] = self.version.get(name, 0) + 1

    def head(self, name):
        if name not in self.data:
            raise FileNotFoundError(name)
        return {'name': name, 'bytes': len(self.data[name]), 'etag': str(self.version[name]), 'metadata': {}}

    def list(self, prefix):
        return [self.head(name) for name in sorted(self.data) if name.startswith(prefix + '/')]

    def chunks(self, name, etag=None):
        prop = self.head(name)
        if etag is not None:
            b.require(prop['etag'] == etag, 'ETag changed')
        yield self.data[name]

    def read(self, name, limit):
        if name not in self.data:
            raise FileNotFoundError(name)
        data = self.data[name]
        b.require(len(data) <= limit, 'too large')
        return data, self.head(name)['etag']


class MaterializerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.output = Path(self.tmp.name) / 'data'
        self.store = MemoryStore()
        self.pages_source = {
            'workflow_id': m.PAGES_WORKFLOW_ID,
            'run_id': 123,
            'run_number': 7,
            'source_sha': 'a' * 40,
            'created_at': '2026-09-12T12:00:00Z',
            'history_sha': 'b' * 40,
        }
        self.data_source = {
            'kind': m.DATA_KIND,
            'workflow_path': m.DATA_WORKFLOW_PATH,
            'workflow_id': m.DATA_WORKFLOW_ID,
            'run_id': 456,
            'run_number': 2,
            'run_attempt': 1,
            'source_sha': 'c' * 40,
            'created_at': '2026-09-12T13:35:50Z',
        }
        names = list(m.REQUIRED) + ['details/a.json', 'firm-details/a.json']
        names += [f'filler/{index:03}.json' for index in range(93)]
        self.payloads = {
            name: json.dumps({'name': name, 'index': index}).encode()
            for index, name in enumerate(names)
        }
        self.pages_prefix = self._seed_release(self.pages_source)

    def tearDown(self):
        self.tmp.cleanup()

    def _expected_prefix(self, source):
        if source.get('kind') == m.DATA_KIND:
            return f"towersignal-data/releases/data-{source['run_id']}-{source['run_attempt']}/runtime"
        return f"towersignal-data/releases/pages-{source['run_id']}/runtime"

    def _publication_prefix(self, source):
        if source.get('kind') == m.DATA_KIND:
            key = f"data-{source['run_id']}-{source['run_attempt']}"
        else:
            key = f"pages-{source['run_id']}"
        return f'towersignal-data/releases/{key}/_publication/runtime'

    def _seed_release(self, source, *, records=None, pointer_overrides=None, prefix=None):
        prefix = prefix or self._expected_prefix(source)
        if records is None:
            records = []
            for name, body in self.payloads.items():
                self.store.seed(prefix + '/' + name, body)
                records.append(b.record_bytes(name, body))
        publication = self._publication_prefix(source)
        manifest = {'schema_version': 1, 'kind': 'runtime', 'data_prefix': prefix,
                    'source': source, 'records': records}
        manifest_bytes = b.encoded(manifest)
        manifest_name = publication + '/manifest.json'
        self.store.seed(manifest_name, manifest_bytes)
        manifest_ref = {'blob': manifest_name, 'sha256': hashlib.sha256(manifest_bytes).hexdigest()}
        complete = {
            'schema_version': 1, 'status': 'COMPLETE', 'kind': 'runtime',
            'data_prefix': prefix, 'source': source, 'manifest': manifest_ref,
            'files': len(records), 'bytes': sum(row['bytes'] for row in records),
            'sha256_readback': True, 'exact_inventory': True, 'unchanged_etags': True,
        }
        complete_bytes = b.encoded(complete)
        complete_name = publication + '/complete.json'
        self.store.seed(complete_name, complete_bytes)
        descriptor = {
            'data_prefix': prefix,
            'manifest': manifest_ref,
            'complete': {'blob': complete_name, 'sha256': hashlib.sha256(complete_bytes).hexdigest()},
            'files': len(records),
            'bytes': sum(row['bytes'] for row in records),
        }
        pointer = {
            'schema_version': 1,
            'domain': m.RELEASE_DOMAIN,
            'source': source,
            'runtime': descriptor,
            'history': {},
            'previous': None,
        }
        pointer.update(pointer_overrides or {})
        self.store.seed(b.POINTER, b.encoded(pointer))
        self.records = records
        return prefix

    def test_materializes_pages_runtime_exactly(self):
        proof = m.materialize(self.store, self.output)
        self.assertEqual(proof['source'], self.pages_source)
        self.assertEqual(proof['source_contract'], m.PAGES_CONTRACT)
        self.assertEqual(proof['runtime_files'], 100)
        self.assertTrue((self.output / 'systems.json').exists())
        expected = {(r['path'], r['bytes'], r['sha256']) for r in self.records}
        actual = {(r['path'], r['bytes'], r['sha256']) for r in b.local_records(self.output)}
        self.assertEqual(actual, expected)

    def test_materializes_verified_data_refresh_runtime(self):
        self.store = MemoryStore()
        prefix = self._seed_release(self.data_source)
        proof = m.materialize(self.store, self.output)
        self.assertEqual(proof['source'], self.data_source)
        self.assertEqual(proof['source_contract'], m.DATA_CONTRACT)
        self.assertEqual(proof['runtime']['data_prefix'], prefix)
        self.assertEqual(proof['runtime_files'], 100)

    def test_unknown_pointer_domain_is_rejected_before_download(self):
        self._seed_release(self.pages_source, pointer_overrides={'domain': 'OTHER'})
        with self.assertRaises(b.PublishError):
            m.materialize(self.store, self.output)
        self.assertFalse(self.output.exists())

    def test_untrusted_data_workflow_identity_is_rejected(self):
        for field, value in [('workflow_id', 1), ('workflow_path', '.github/workflows/other.yml'),
                             ('kind', 'other'), ('run_attempt', 0)]:
            with self.subTest(field=field):
                self.store = MemoryStore()
                source = copy.deepcopy(self.data_source)
                source[field] = value
                prefix_source = self.data_source if field in ('kind', 'run_attempt') else source
                prefix = self._expected_prefix(prefix_source)
                self._seed_release(source, prefix=prefix)
                with self.assertRaises(b.PublishError):
                    m.materialize(self.store, self.output)
                self.assertFalse(self.output.exists())

    def test_data_runtime_prefix_must_match_source_identity(self):
        self.store = MemoryStore()
        self._seed_release(self.data_source, prefix='towersignal-data/releases/data-999-1/runtime')
        with self.assertRaises(b.PublishError):
            m.materialize(self.store, self.output)
        self.assertFalse(self.output.exists())

    def test_descriptor_source_mismatch_is_rejected(self):
        self.store = MemoryStore()
        source = copy.deepcopy(self.data_source)
        self._seed_release(source)
        pointer = json.loads(self.store.data[b.POINTER])
        pointer['source'] = {**source, 'source_sha': 'd' * 40}
        self.store.seed(b.POINTER, b.encoded(pointer))
        with self.assertRaises(b.PublishError):
            m.materialize(self.store, self.output)

    def test_corrupted_payload_is_rejected(self):
        target = self.pages_prefix + '/systems.json'
        self.store.data[target] += b'corrupt'
        with self.assertRaises(b.PublishError):
            m.materialize(self.store, self.output)

    def test_missing_required_file_is_rejected_before_download(self):
        records = [row for row in self.records if row['path'] != 'changes.json']
        self._seed_release(self.pages_source, records=records)
        with self.assertRaises(b.PublishError):
            m.materialize(self.store, self.output)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
