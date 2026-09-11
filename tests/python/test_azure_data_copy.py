"""Offline checks: source integrity, path isolation and actual-content verification."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location('azure_data_copy', Path(__file__).resolve().parents[2] / 'scripts/migrate_data_to_blob.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def pages_zip(path, members):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode='w') as tar:
        for name, content, kind in members:
            item = tarfile.TarInfo(name)
            item.type = kind
            item.size = len(content) if kind == tarfile.REGTYPE else 0
            if kind == tarfile.SYMTYPE:
                item.linkname = '/etc/passwd'
            tar.addfile(item, io.BytesIO(content))
    with zipfile.ZipFile(path, 'w') as package:
        package.writestr('artifact.tar', data.getvalue())


class MigrationTests(unittest.TestCase):
    def test_paths(self):
        self.assertEqual(m.safe_path('./data/details/20/123.json'), 'data/details/20/123.json')
        for value in ['', '.', '/data/a', '../a', 'data/../x', 'data\\x', 'C:/a', 'data/a\n']:
            with self.subTest(value=value), self.assertRaises(m.MigrationError):
                m.safe_path(value)

    def test_hash_stream(self):
        size, sha, git = m.hash_stream(io.BytesIO(b'abc'), git_size=3)
        self.assertEqual((size, sha, git), (3, hashlib.sha256(b'abc').hexdigest(), hashlib.sha1(b'blob 3\0abc').hexdigest()))

    def test_all_runtime_files_preserved_not_frontend(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pages_zip(root / 'a.zip', [('./data/a.json', b'{"test":1}\n', tarfile.REGTYPE),
                                     ('./data/details/20/a.json', b'x', tarfile.REGTYPE),
                                     ('./data/.gitkeep', b'', tarfile.REGTYPE),
                                     ('./index.html', b'html', tarfile.REGTYPE)])
            count, size = m.extract_runtime(root / 'a.zip', root / 'out')
            self.assertEqual((count, size), (3, 12))
            self.assertEqual((root / 'out/a.json').read_bytes(), b'{"test":1}\n')
            self.assertTrue((root / 'out/.gitkeep').exists())
            self.assertFalse((root / 'out/index.html').exists())

    def test_unsafe_tar_members_rejected(self):
        for name, kind in [('./data/../../bad', tarfile.REGTYPE),
                           ('./data/link', tarfile.SYMTYPE),
                           ('./data/link', tarfile.LNKTYPE),
                           ('/data/bad', tarfile.REGTYPE)]:
            with self.subTest(name=name, kind=kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                pages_zip(root / 'a.zip', [(name, b'x', kind)])
                with self.assertRaises(m.MigrationError):
                    m.extract_runtime(root / 'a.zip', root / 'out')

    def test_duplicate_tar_members_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pages_zip(root / 'a.zip', [('data/a', b'x', tarfile.REGTYPE), ('./data/a', b'y', tarfile.REGTYPE)])
            with self.assertRaises(m.MigrationError):
                m.extract_runtime(root / 'a.zip', root / 'out')

    def test_wrong_zip_layout_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with zipfile.ZipFile(root / 'a.zip', 'w') as z:
                z.writestr('../artifact.tar', b'bad')
            with self.assertRaises(m.MigrationError):
                m.extract_runtime(root / 'a.zip', root / 'out')

    def test_readback_hash_and_size_not_metadata(self):
        blob = types.SimpleNamespace(download_blob=lambda **_: types.SimpleNamespace(chunks=lambda: iter([b'a', b'bc'])))
        valid = {'path': 'runtime/a.json', 'bytes': 3, 'sha256': hashlib.sha256(b'abc').hexdigest()}
        m.verify_readback(blob, valid)
        for invalid in [{**valid, 'bytes': 2}, {**valid, 'sha256': '0' * 64}]:
            with self.assertRaises(m.MigrationError):
                m.verify_readback(blob, invalid)

    def test_inventory_requires_exact_names_sizes_and_no_extra_files(self):
        expected = [{'path': 'runtime/a.json', 'bytes': 3}]
        for data, valid in [([('safe/runtime/a.json', 3)], True),
                            ([], False), ([('safe/runtime/a.json', 2)], False),
                            ([('safe/runtime/a.json', 3), ('safe/x', 0)], False)]:
            def listing(**kwargs):
                self.assertEqual(kwargs, {'name_starts_with': 'safe/'})
                return [types.SimpleNamespace(name=n, size=s) for n, s in data]
            client = types.SimpleNamespace(list_blobs=listing)
            if valid:
                m.verify_inventory(client, 'safe', expected)
            else:
                with self.assertRaises(m.MigrationError):
                    m.verify_inventory(client, 'safe', expected)

    def test_destination_and_credentials_are_separate_from_source(self):
        env = dict(zip(('AZURE_STORAGE_ACCOUNT', 'AZURE_STORAGE_CONTAINER', 'AZURE_STORAGE_PREFIX'), m.DESTINATION))
        env.update(AZURE_STORAGE_KEY='offline-test-only', GITHUB_RUN_ID='12', GITHUB_RUN_ATTEMPT='1')
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(m.destination_from_env()[-1], 'towersignal-data/migrations/github-12-1')
        for name in ['AZURE_STORAGE_KEY', 'AZURE_STORAGE_ACCOUNT', 'AZURE_STORAGE_CONTAINER', 'AZURE_STORAGE_PREFIX', 'GITHUB_RUN_ID']:
            invalid = {**env, name: ''}
            with self.subTest(name=name), patch.dict(os.environ, invalid, clear=True), self.assertRaises(m.MigrationError):
                m.destination_from_env()

    def test_snapshot_missing_is_explicit_never_substituted(self):
        reader = types.SimpleNamespace(get=lambda _: {'tree': [], 'truncated': False})
        source = {'name': 'oath', 'ref': 'data/oath', 'sha': 'a' * 40, 'paths': ['data/oath'], 'required': False}
        result = m.snapshot(reader, source, Path('/unused'), Path('/unused'))
        self.assertEqual(result['status'], 'absent-at-pinned-commit')
        with self.assertRaises(m.MigrationError):
            m.snapshot(reader, {**source, 'required': True}, Path('/unused'), Path('/unused'))

    def test_snapshot_truncated_tree_rejected(self):
        reader = types.SimpleNamespace(get=lambda _: {'tree': [], 'truncated': True})
        with self.assertRaises(m.MigrationError):
            m.snapshot(reader, {'sha': 'a' * 40}, Path('/unused'), Path('/unused'))

    def test_source_release_failure_blocks_before_download(self):
        run = {'head_sha': 'a' * 40, 'head_branch': 'main', 'path': '.github/workflows/pages.yml',
               'status': 'completed', 'conclusion': 'failure'}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            m.json_file(root / 'plan.json', {'repository': m.REPO, 'source_run_id': 1, 'source_sha': 'a' * 40})
            with patch.object(m, 'GitHubReader', return_value=types.SimpleNamespace(get=lambda _: run)), self.assertRaises(m.MigrationError):
                m.stage_data(root / 'plan.json', root / 'work')
            self.assertFalse((root / 'work/payload').exists())

    def test_stage_complete_pinned_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pages_zip(root / 'source.zip', [('data/systems.json', b'{}', tarfile.REGTYPE),
                                           ('data/details/20/a.json', b'{}', tarfile.REGTYPE),
                                           ('data/firm-details/fi/a.json', b'{}', tarfile.REGTYPE)])
            digest = hashlib.sha256((root / 'source.zip').read_bytes()).hexdigest()
            plan = {'repository': m.REPO, 'source_run_id': 1, 'source_sha': 'a'*40,
                    'artifacts': [{'id': 2, 'name': 'github-pages', 'sha256': digest}],
                    'snapshots': [], 'required_runtime_files': ['systems.json']}
            m.json_file(root / 'plan.json', plan)
            run = {'head_sha': 'a'*40, 'head_branch': 'main', 'path': '.github/workflows/pages.yml',
                   'status': 'completed', 'conclusion': 'success', 'run_attempt': 1}
            jobs = {'total_count': 4, 'jobs': [{'name': n, 'conclusion': 'success'} for n in ('build','deploy','verify','persist-history')]}
            artifact = {'expired': False, 'name': 'github-pages', 'digest': 'sha256:'+digest,
                        'size_in_bytes': (root / 'source.zip').stat().st_size,
                        'workflow_run': {'id': 1, 'head_sha': 'a'*40}}
            def get(path):
                if '/jobs?' in path: return jobs
                if '/artifacts/' in path: return artifact
                return run
            def download(_, dest):
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root / 'source.zip', dest)
            reader = types.SimpleNamespace(get=get, download=download)
            with patch.object(m, 'GitHubReader', return_value=reader):
                m.stage_data(root / 'plan.json', root / 'work')
            manifest = json.loads((root / 'work/report/manifest.json').read_text())
            self.assertEqual(len(manifest['records']), 5)
            self.assertFalse((root / 'work/report/complete.json').exists())
            artifact['digest'] = 'sha256:' + '0'*64
            with patch.object(m, 'GitHubReader', return_value=reader), self.assertRaises(m.MigrationError):
                m.stage_data(root / 'plan.json', root / 'bad-work')


    def test_copy_publishes_complete_only_after_verified_bytes(self):
        for corrupt in (False, True):
            with self.subTest(corrupt=corrupt), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                payload = root / 'payload'
                payload.mkdir()
                (payload / 'a.json').write_bytes(b'original')
                record = m.file_record(payload, payload / 'a.json')
                m.json_file(root / 'report/manifest.json', {'repository': m.REPO, 'source_run_id': 1,
                           'source_sha': 'a'*40, 'snapshots': [], 'records': [record]})
                stored = {}
                class Exists(Exception): pass
                class Blob:
                    def __init__(self, name): self.name = name
                    def upload_blob(self, source, **kwargs):
                        self_outer.assertFalse(kwargs['overwrite'])
                        if self.name in stored: raise Exists()
                        stored[self.name] = source.read()
                    def download_blob(self, **kwargs):
                        data = stored[self.name]
                        if corrupt and self.name.endswith('/a.json'): data = b'corrupt!'
                        return types.SimpleNamespace(chunks=lambda: iter([data]))
                class Container:
                    def get_blob_client(self, name): return Blob(name)
                    def list_blobs(self, *, name_starts_with):
                        return [types.SimpleNamespace(name=k, size=len(v)) for k,v in stored.items() if k.startswith(name_starts_with)]
                class Service:
                    def __init__(self, **kwargs):
                        self_outer.assertEqual(kwargs['account_url'], 'https://pharm3r.blob.core.windows.net')
                    def get_container_client(self, name):
                        self_outer.assertEqual(name, 'data')
                        return Container()
                    def close(self): pass
                self_outer = self
                modules = {'azure': types.ModuleType('azure'), 'azure.storage': types.ModuleType('azure.storage'),
                           'azure.storage.blob': types.ModuleType('azure.storage.blob'),
                           'azure.core': types.ModuleType('azure.core'), 'azure.core.exceptions': types.ModuleType('azure.core.exceptions')}
                modules['azure.storage.blob'].BlobServiceClient = Service
                modules['azure.storage.blob'].ContentSettings = lambda **k: k
                modules['azure.core.exceptions'].ResourceExistsError = Exists
                env = dict(zip(('AZURE_STORAGE_ACCOUNT', 'AZURE_STORAGE_CONTAINER', 'AZURE_STORAGE_PREFIX'), m.DESTINATION))
                env.update(AZURE_STORAGE_KEY='not-real', GITHUB_RUN_ID='99', GITHUB_RUN_ATTEMPT='1')
                with patch.dict(sys.modules, modules), patch.dict(os.environ, env, clear=True):
                    if corrupt:
                        with self.assertRaises(m.MigrationError): m.upload_data(root)
                    else:
                        m.upload_data(root)
                self.assertEqual(any(n.endswith('/_migration/complete.json') for n in stored), not corrupt)
                self.assertTrue(all(n.startswith('towersignal-data/migrations/github-99-1/') for n in stored))
                self.assertTrue((payload / 'a.json').exists())

    def test_snapshot_file_checked_against_git_hash(self):
        for tamper in (False, True):
            with self.subTest(tamper=tamper), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                data = b'good'
                sha = hashlib.sha1(b'blob 4\0' + data).hexdigest()
                reader_data = {'truncated': False, 'tree': [{'path': 'data/cache/a.json', 'type': 'blob',
                               'mode': '100644', 'size': 4, 'sha': sha}]}
                def download(_, dest):
                    with tarfile.open(dest, 'w:gz') as tar:
                        item = tarfile.TarInfo('root/data/cache/a.json')
                        item.size = 4
                        tar.addfile(item, io.BytesIO(b'evil' if tamper else data))
                reader = types.SimpleNamespace(get=lambda _: reader_data, download=download)
                spec = {'name': 'cache', 'sha': 'a'*40, 'ref': 'data/cache', 'paths': ['data/cache']}
                if tamper:
                    with self.assertRaises(m.MigrationError): m.snapshot(reader, spec, root/'payload', root)
                else:
                    result = m.snapshot(reader, spec, root/'payload', root)
                    self.assertEqual(result['files'], 1)
                    self.assertEqual((root/'payload/support/cache/data/cache/a.json').read_bytes(), data)


if __name__ == '__main__':
    unittest.main()
