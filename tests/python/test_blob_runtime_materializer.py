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
        data = self.data[name]
        b.require(len(data) <= limit, 'too large')
        return data, self.head(name)['etag']


class MaterializerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.output = Path(self.tmp.name) / 'data'
        self.store = MemoryStore()
        self.source = {
            'workflow_id': 339705737,
            'run_id': 123,
            'run_number': 7,
            'source_sha': 'a' * 40,
            'created_at': '2026-09-12T12:00:00Z',
            'history_sha': 'b' * 40,
        }
        self.prefix = 'towersignal-data/releases/pages-123/runtime'
        names = list(m.REQUIRED) + ['details/a.json', 'firm-details/a.json']
        names += [f'filler/{index:03}.json' for index in range(93)]
        self.records = []
        for index, name in enumerate(names):
            body = json.dumps({'name': name, 'index': index}).encode()
            self.store.seed(self.prefix + '/' + name, body)
            self.records.append(b.record_bytes(name, body))
        self._seed_release(self.records)

    def tearDown(self):
        self.tmp.cleanup()

    def _seed_release(self, records):
        manifest = {'schema_version': 1, 'kind': 'runtime', 'data_prefix': self.prefix,
                    'source': self.source, 'records': records}
        manifest_bytes = b.encoded(manifest)
        manifest_name = 'towersignal-data/releases/pages-123/_publication/runtime/manifest.json'
        self.store.seed(manifest_name, manifest_bytes)
        manifest_ref = {'blob': manifest_name, 'sha256': hashlib.sha256(manifest_bytes).hexdigest()}
        complete = {
            'schema_version': 1, 'status': 'COMPLETE', 'kind': 'runtime',
            'data_prefix': self.prefix, 'source': self.source, 'manifest': manifest_ref,
            'files': len(records), 'bytes': sum(row['bytes'] for row in records),
            'sha256_readback': True, 'exact_inventory': True, 'unchanged_etags': True,
        }
        complete_bytes = b.encoded(complete)
        complete_name = 'towersignal-data/releases/pages-123/_publication/runtime/complete.json'
        self.store.seed(complete_name, complete_bytes)
        descriptor = {
            'data_prefix': self.prefix,
            'manifest': manifest_ref,
            'complete': {'blob': complete_name, 'sha256': hashlib.sha256(complete_bytes).hexdigest()},
            'files': len(records),
            'bytes': sum(row['bytes'] for row in records),
        }
        pointer = {
            'schema_version': 1,
            'domain': 'TOWERSIGNAL_BLOB_RELEASE',
            'source': self.source,
            'runtime': descriptor,
            'history': {},
            'previous': None,
        }
        self.store.seed(b.POINTER, b.encoded(pointer))

    def test_materializes_current_runtime_exactly(self):
        proof = m.materialize(self.store, self.output)
        self.assertEqual(proof['source'], self.source)
        self.assertEqual(proof['runtime_files'], 100)
        self.assertTrue((self.output / 'systems.json').exists())
        expected = {(r['path'], r['bytes'], r['sha256']) for r in self.records}
        actual = {(r['path'], r['bytes'], r['sha256']) for r in b.local_records(self.output)}
        self.assertEqual(actual, expected)

    def test_corrupted_payload_is_rejected(self):
        target = self.prefix + '/systems.json'
        self.store.data[target] += b'corrupt'
        with self.assertRaises(b.PublishError):
            m.materialize(self.store, self.output)

    def test_missing_required_file_is_rejected_before_download(self):
        records = [row for row in self.records if row['path'] != 'changes.json']
        self._seed_release(records)
        with self.assertRaises(b.PublishError):
            m.materialize(self.store, self.output)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
