"""Offline assertions use an in-memory store. They are not live Azure verification."""
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import blob_release_store as b
import publish_pages_to_blob as p


class MemoryStore:
    def __init__(self):
        self.data = {}
        self.metadata = {}
        self.versions = {}
        self.writes = []
        self.race = False
        self.corrupt = set()
        self.fail_create = None
        self.mutate_list = False
        self.lists = 0

    def seed(self, name, value, metadata=None):
        self.data[name] = value
        self.metadata[name] = metadata or {}
        self.versions[name] = self.versions.get(name, 0) + 1

    def head(self, name):
        if name not in self.data:
            raise FileNotFoundError(name)
        return {'name': name, 'bytes': len(self.data[name]), 'etag': str(self.versions[name]),
                'metadata': self.metadata[name]}

    def list(self, prefix):
        self.lists += 1
        if self.mutate_list and self.lists % 2 == 0:
            for n in self.versions:
                self.versions[n] += 1
        return [self.head(n) for n in sorted(self.data) if n.startswith(prefix + '/')]

    def chunks(self, name, etag=None):
        prop = self.head(name)
        if etag is not None and prop['etag'] != etag:
            raise b.PublishError('ETag changed')
        value = self.data[name]
        yield value + b'x' if name in self.corrupt else value

    def read(self, name, limit):
        value = b''.join(self.chunks(name))
        b.require(len(value) <= limit, 'too large')
        return value, self.head(name)['etag']

    def create(self, name, stream, size, content_type):
        b.AzureStore.allow_write(name)
        if self.fail_create and self.fail_create in name:
            raise b.PublishError('Injected write failure')
        if name not in self.data:
            value = stream.read()
            assert len(value) == size
            self.seed(name, value)
            self.writes.append(name)

    def cas(self, name, value, etag):
        if self.race:
            raise b.PublishError('Injected HTTP 412')
        actual = self.head(name)['etag'] if name in self.data else None
        b.require(actual == etag, 'CAS conflict')
        self.seed(name, value)
        self.writes.append(name)


def source(number=1):
    return {'workflow_id': p.PAGES_WORKFLOW, 'run_id': number + 100, 'run_number': number,
            'source_sha': 'a' * 40, 'created_at': '2026-09-11T01:00:00Z', 'history_sha': 'b' * 40}


class FakeReader:
    def __init__(self, s=None):
        s = s or source()
        self.s = s
        self.run = {'id': s['run_id'], 'run_number': s['run_number'], 'workflow_id': p.PAGES_WORKFLOW,
                    'repository': {'id': p.REPO_ID}, 'head_repository': {'id': p.REPO_ID},
                    'head_branch': 'main', 'path': '.github/workflows/pages.yml', 'event': 'push',
                    'status': 'completed', 'conclusion': 'success', 'head_sha': s['source_sha'],
                    'created_at': s['created_at']}
        self.jobs = {'total_count': 4, 'jobs': [
            {'name': n, 'status': 'completed', 'conclusion': 'success',
             'started_at': '2026-09-11T01:00:00Z', 'completed_at': '2026-09-11T02:00:00Z'}
            for n in ('build', 'deploy', 'verify', 'persist-history')]}
        self.history_sha = s['history_sha']

    def get(self, path):
        if '/jobs?' in path:
            return copy.deepcopy(self.jobs)
        if path.startswith('/actions/runs/'):
            return copy.deepcopy(self.run)
        if path == '/git/ref/heads/data/towersignal-history':
            return {'object': {'sha': self.history_sha}}
        raise AssertionError(path)


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = MemoryStore()
        self.s = source()

    def tearDown(self):
        self.tmp.cleanup()

    def pair(self, number=1, payload=b'first'):
        s = source(number)
        result = []
        for kind in ('runtime', 'history'):
            local = self.root / f'{number}-{kind}'
            local.mkdir(exist_ok=True)
            (local / 'a.json').write_bytes(payload)
            prefix = f'{b.ROOT}/releases/pages-{s["run_id"]}/{kind}'
            desc = b.publish_dataset(self.store, local, prefix, b.local_records(local),
                                     f'{b.ROOT}/releases/pages-{s["run_id"]}/_publication/{kind}', kind, s)
            result.append(desc)
        return s, result[0], result[1]

    def test_first_publication_commits_matched_pair(self):
        s, runtime, history = self.pair()
        result = b.promote(self.store, s, runtime, history)
        self.assertEqual(result['status'], 'CURRENT')
        self.assertEqual(result['current']['runtime'], runtime)
        self.assertEqual(result['current']['history'], history)
        self.assertEqual(self.store.writes[-1], b.POINTER)

    def test_two_realistic_cycles_preserve_previous_pointer(self):
        s, r, h = self.pair()
        b.promote(self.store, s, r, h)
        old = self.store.data[b.POINTER]
        s2, r2, h2 = self.pair(2, b'next')
        result = b.promote(self.store, s2, r2, h2)
        self.assertEqual(result['current']['source']['run_number'], 2)
        self.assertEqual(self.store.data[result['current']['previous']['blob']], old)

    def test_repeat_promotion_is_idempotent(self):
        s, r, h = self.pair()
        b.promote(self.store, s, r, h)
        writes = list(self.store.writes)
        self.assertEqual(b.promote(self.store, s, r, h)['status'], 'ALREADY_CURRENT')
        self.assertEqual(self.store.writes, writes)

    def test_old_run_cannot_regress_pointer(self):
        s, r, h = self.pair(2)
        b.promote(self.store, s, r, h)
        current = self.store.data[b.POINTER]
        a, x, y = self.pair(1)
        with self.assertRaises(b.PublishError):
            b.promote(self.store, a, x, y)
        self.assertEqual(self.store.data[b.POINTER], current)

    def test_bootstrap_never_overwrites_existing_pointer(self):
        s, r, h = self.pair()
        b.promote(self.store, s, r, h)
        a, x, y = self.pair(2)
        with self.assertRaises(b.PublishError):
            b.promote(self.store, a, x, y, bootstrap=True)

    def test_conditional_update_conflict_keeps_old_pointer(self):
        s, r, h = self.pair()
        b.promote(self.store, s, r, h)
        old = self.store.data[b.POINTER]
        a, x, y = self.pair(2)
        self.store.race = True
        with self.assertRaises(b.PublishError):
            b.promote(self.store, a, x, y)
        self.assertEqual(self.store.data[b.POINTER], old)

    def test_missing_complete_proof_never_advances(self):
        s, r, h = self.pair()
        del self.store.data[h['complete']['blob']]
        with self.assertRaises(FileNotFoundError):
            b.promote(self.store, s, r, h)
        self.assertNotIn(b.POINTER, self.store.data)

    def test_mismatched_history_source_never_advances(self):
        s, r, _ = self.pair()
        _, _, h = self.pair(2)
        with self.assertRaises(b.PublishError):
            b.promote(self.store, s, r, h)
        self.assertNotIn(b.POINTER, self.store.data)

    def test_conflicting_selector_fails_before_pointer(self):
        s, r, h = self.pair()
        self.store.seed(b.ROOT + '/pointers/history-current.json', b'wrong')
        with self.assertRaises(b.PublishError):
            b.promote(self.store, s, r, h)
        self.assertNotIn(b.POINTER, self.store.data)

    def test_corrupted_blob_blocks_complete_receipt(self):
        local = self.root / 'data'
        local.mkdir(); (local / 'a.json').write_bytes(b'ok')
        prefix = b.ROOT + '/releases/pages-101/runtime'
        self.store.corrupt.add(prefix + '/a.json')
        with self.assertRaises(b.PublishError):
            b.publish_dataset(self.store, local, prefix, b.local_records(local),
                              b.ROOT + '/releases/pages-101/_publication/runtime', 'runtime', self.s)
        self.assertFalse(any(n.endswith('/complete.json') for n in self.store.data))

    def test_existing_different_bytes_are_not_overwritten(self):
        local = self.root / 'data'; local.mkdir(); (local / 'a.json').write_bytes(b'new')
        prefix = b.ROOT + '/releases/pages-101/runtime'
        self.store.seed(prefix + '/a.json', b'old')
        with self.assertRaises(b.PublishError):
            b.publish_dataset(self.store, local, prefix, b.local_records(local),
                              b.ROOT + '/releases/pages-101/_publication/runtime', 'runtime', self.s)
        self.assertEqual(self.store.data[prefix + '/a.json'], b'old')

    def test_local_mutation_is_detected(self):
        local = self.root / 'data'; local.mkdir(); (local / 'a.json').write_bytes(b'old')
        records = b.local_records(local); (local / 'a.json').write_bytes(b'new')
        with self.assertRaises(b.PublishError):
            b.publish_dataset(self.store, local, b.ROOT + '/releases/pages-101/runtime', records,
                              b.ROOT + '/releases/pages-101/_publication/runtime', 'runtime', self.s)
        self.assertEqual(self.store.writes, [])

    def test_adoption_reads_existing_payloads_without_reupload(self):
        prefix = p.BASELINE + '/runtime'
        self.store.seed(prefix + '/a.json', b'{}')
        records = [b.record_bytes('a.json', b'{}')]
        b.publish_dataset(self.store, None, prefix, records,
                          b.ROOT + '/releases/pages-101/_publication/runtime', 'runtime', self.s)
        self.assertFalse(any(n.startswith(p.BASELINE) for n in self.store.writes))

    def test_directory_markers_are_not_confused_with_files(self):
        prefix = b.ROOT + '/releases/pages-101/runtime'
        self.store.seed(prefix + '/sub', b'', {'hdi_isfolder': 'true'})
        self.store.seed(prefix + '/sub/a.json', b'ok')
        result = b.verify_dataset(self.store, prefix, [b.record_bytes('sub/a.json', b'ok')])
        self.assertEqual(result['files'], 1)

    def test_unmarked_extra_and_bad_folder_are_rejected(self):
        prefix = b.ROOT + '/releases/pages-101/runtime'
        records = [b.record_bytes('a.json', b'ok')]
        for name, body, meta in [('extra', b'', {}), ('other', b'', {'hdi_isfolder': 'true'}),
                                 ('a.json', b'', {'hdi_isfolder': 'true'})]:
            with self.subTest(name=name):
                store = MemoryStore(); store.seed(prefix + '/a.json', b'ok')
                store.seed(prefix + '/' + name, body, meta)
                with self.assertRaises(b.PublishError):
                    b.verify_dataset(store, prefix, records)

    def test_missing_file_detected(self):
        with self.assertRaises(b.PublishError):
            b.verify_dataset(self.store, b.ROOT + '/releases/pages-101/runtime', [b.record_bytes('a', b'ok')])

    def test_etag_change_blocks_completion(self):
        prefix = b.ROOT + '/releases/pages-101/runtime'
        self.store.seed(prefix + '/a', b'ok'); self.store.mutate_list = True
        with self.assertRaises(b.PublishError):
            b.verify_dataset(self.store, prefix, [b.record_bytes('a', b'ok')])

    def test_git_blob_hash_checked_on_readback(self):
        prefix = p.BASELINE + '/support/history/data/history'
        self.store.seed(prefix + '/a', b'ok')
        record = {**b.record_bytes('a', b'ok'), 'git_blob_sha': '0'*40}
        with self.assertRaises(b.PublishError):
            b.verify_dataset(self.store, prefix, [record])

    def test_write_boundary_and_paths(self):
        for path in [p.BASELINE+'/runtime/a', 'other/file', b.ROOT+'/caches/acris/a',
                     b.ROOT+'/pointers/unknown.json', b.ROOT+'/releases/pages-1/../a']:
            with self.subTest(path=path), self.assertRaises(b.PublishError):
                b.AzureStore.allow_write(path)
        for path in ['../a', '/a', 'a//b', 'a/./b', 'a\\b', 'a\nb']:
            with self.subTest(path=path), self.assertRaises(b.PublishError):
                b.safe_path(path)

    def test_duplicate_and_invalid_record_types_rejected(self):
        good = b.record_bytes('a', b'ok')
        for rows in [[good, good], [{**good, 'bytes': True}], [{**good, 'sha256': 'x'*64}]]:
            with self.assertRaises(b.PublishError):
                b.validate_records(rows)

    def test_runtime_history_parity_and_retained_oath_cache(self):
        runtime = [b.record_bytes('history/'+n, n.encode()) for n in p.HISTORY_WRITTEN[:-1]]
        runtime += [b.record_bytes('history/segments/core.json', b'core'), b.record_bytes('source-health.json', b'health')]
        history = [{**r, 'path': r['path'].removeprefix('history/')} for r in runtime]
        history += [b.record_bytes('oath-cache.json.gz', b'persisted')]
        proof = p.check_history_parity(runtime, history)
        self.assertEqual(proof['retained_git_files'], ['oath-cache.json.gz'])
        altered = copy.deepcopy(history); altered[0]['sha256'] = '0'*64
        with self.assertRaises(b.PublishError):
            p.check_history_parity(runtime, altered)
        with self.assertRaises(b.PublishError):
            p.check_history_parity(runtime, history, runtime[:-1])

    def test_history_git_tree_inventory_and_size(self):
        r = b.record_bytes('a', b'ok')
        tree = {'a': {'size': 2, 'sha': hashlib.sha1(b'blob 2\0ok').hexdigest()}}
        self.assertEqual(p.match_git_history([r], tree)[0]['git_blob_sha'], tree['a']['sha'])
        with self.assertRaises(b.PublishError):
            p.match_git_history([r], {})
        with self.assertRaises(b.PublishError):
            p.match_git_history([{**r, 'bytes': 3}], tree)

    def test_source_gate_rejects_failure_skips_and_foreign_context(self):
        for field, value in [('event', 'pull_request'), ('head_branch', 'unreviewed'), ('conclusion', 'failure'),
                             ('status', 'in_progress'), ('path', '.github/workflows/other.yml'),
                             ('workflow_id', 1), ('head_repository', {'id': 1})]:
            reader = FakeReader(); reader.run[field] = value
            with self.subTest(field=field), self.assertRaises(b.PublishError):
                p.successful_source(reader, reader.s['run_id'])
        for job in range(4):
            reader = FakeReader(); reader.jobs['jobs'][job]['conclusion'] = 'skipped'
            with self.assertRaises(b.PublishError):
                p.successful_source(reader, reader.s['run_id'])

    def test_incomplete_job_listing_rejected(self):
        reader = FakeReader(); reader.jobs['total_count'] = 5
        with self.assertRaises(b.PublishError):
            p.successful_source(reader, reader.s['run_id'])

    def test_duplicate_gate_name_rejected(self):
        reader = FakeReader(); reader.jobs['jobs'][3]['name'] = 'build'
        with self.assertRaises(b.PublishError):
            p.successful_source(reader, reader.s['run_id'])

    def test_valid_source_proof(self):
        reader = FakeReader(); proof, _ = p.successful_source(reader, reader.s['run_id'])
        self.assertEqual(proof, {k:v for k,v in reader.s.items() if k != 'history_sha'})

    def test_artifact_selection_bound_to_build_time_digest_and_sha(self):
        reader = FakeReader(); build = reader.jobs['jobs'][0]
        a = {'name': 'github-pages', 'created_at': '2026-09-11T01:50:00Z', 'expired': False,
             'workflow_run': {'id': self.s['run_id'], 'head_sha': self.s['source_sha']}, 'digest': 'sha256:'+'a'*64}
        self.assertEqual(p.select_artifact([a], 'github-pages', self.s, build), a)
        for changes in [{'expired': True}, {'digest': None}, {'created_at': '2026-09-11T00:50:00Z'}]:
            with self.assertRaises(b.PublishError):
                p.select_artifact([{**a, **changes}], 'github-pages', self.s, build)
        with self.assertRaises(b.PublishError):
            p.select_artifact([a,a], 'github-pages', self.s, build)

    def test_history_archive_paths_and_duplicates(self):
        for name in ['../outside', '/absolute', 'run-me.sh']:
            archive = self.root / 'bad.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr(name, b'no')
            with self.assertRaises(b.PublishError):
                p.unpack_history(archive, self.root/'out')
        archive = self.root/'valid.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('history/latest.json', b'{}'); z.writestr('source-health.json', b'{}')
        p.unpack_history(archive, self.root/'valid')
        self.assertEqual((self.root/'valid/history/latest.json').read_bytes(), b'{}')

    def test_missing_destination_key_and_wrong_account_rejected(self):
        with patch.dict('os.environ', {}, clear=True), self.assertRaises(b.PublishError):
            b.AzureStore()
        env = {'AZURE_STORAGE_ACCOUNT':'other', 'AZURE_STORAGE_CONTAINER':'data',
               'AZURE_STORAGE_PREFIX':b.ROOT, 'AZURE_STORAGE_KEY':'not-a-real-key'}
        with patch.dict('os.environ', env, clear=True), self.assertRaises(b.PublishError):
            b.AzureStore()

    def test_apply_fails_before_upload_when_history_advanced(self):
        reader = FakeReader(); reader.history_sha = 'c'*40
        with self.assertRaises(b.PublishError):
            p.apply(self.store, reader, {'source': self.s}, self.root)
        self.assertEqual(self.store.writes, [])

    def test_failed_upload_cannot_touch_existing_current(self):
        s, r, h = self.pair(); b.promote(self.store, s, r, h)
        current = self.store.data[b.POINTER]
        self.store.fail_create = '/pages-102/'
        with self.assertRaises(b.PublishError):
            self.pair(2)
        self.assertEqual(self.store.data[b.POINTER], current)

    def application_plan(self, number):
        work = self.root / f'work-{number}'
        runtime = work / 'runtime'
        history = work / 'snapshots/support/history/data/history'
        values = {n: b'{}' for n in p.REQUIRED}
        values.update({'details/20/a.json': b'{}', 'firm-details/kn/a.json': b'{}'})
        values.update({'history/'+n: n.encode() for n in p.HISTORY_WRITTEN[:-1]})
        values['history/segments/core.json'] = b'core'
        for name, data in values.items():
            out = runtime / name; out.parent.mkdir(parents=True, exist_ok=True); out.write_bytes(data)
        hist = {n.removeprefix('history/'): d for n,d in values.items() if n.startswith('history/')}
        hist['source-health.json'] = values['source-health.json']
        hist['oath-cache.json.gz'] = b'retained Git input'
        for name,data in hist.items():
            out=history/name; out.parent.mkdir(parents=True,exist_ok=True); out.write_bytes(data)
        rr, hr = b.local_records(runtime), b.local_records(history)
        return work, {'source': source(number), 'runtime': rr, 'history': hr,
                      'history_parity': p.check_history_parity(rr,hr)}

    def test_full_publisher_two_cycles_and_repeat(self):
        work, plan = self.application_plan(1)
        first = p.apply(self.store, FakeReader(source(1)), plan, work)
        self.assertEqual(first['status'], 'CURRENT')
        self.assertEqual(first['history_parity']['retained_git_files'], ['oath-cache.json.gz'])
        work2, plan2 = self.application_plan(2)
        next_result = p.apply(self.store, FakeReader(source(2)), plan2, work2)
        self.assertEqual(next_result['status'], 'CURRENT')
        old_bytes = self.store.data[b.POINTER]
        writes = list(self.store.writes)
        again = p.apply(self.store, FakeReader(source(2)), plan2, work2)
        self.assertEqual(again['status'], 'ALREADY_CURRENT')
        self.assertEqual(self.store.data[b.POINTER], old_bytes)
        self.assertEqual(self.store.writes, writes)

    def test_same_run_with_different_payload_is_not_idempotent(self):
        work, plan = self.application_plan(1)
        p.apply(self.store, FakeReader(source(1)), plan, work)
        before = self.store.data[b.POINTER]
        writes = list(self.store.writes)
        (work / 'runtime/systems.json').write_bytes(b'{"changed":true}')
        plan['runtime'] = b.local_records(work / 'runtime')
        with self.assertRaisesRegex(b.PublishError, 'Same-run runtime payload differs'):
            p.apply(self.store, FakeReader(source(1)), plan, work)
        self.assertEqual(self.store.data[b.POINTER], before)
        self.assertEqual(self.store.writes, writes)

    def test_full_bootstrap_adopts_both_without_payload_writes(self):
        work,plan = self.application_plan(1)
        for kind, local, prefix in [('runtime', work/'runtime', p.BASELINE+'/runtime'),
                                    ('history', work/'snapshots/support/history/data/history',
                                     p.BASELINE+'/support/history/data/history')]:
            for row in plan[kind]:
                self.store.seed(prefix+'/'+row['path'], (local/row['path']).read_bytes())
        result=p.apply(self.store, FakeReader(source(1)), plan, work, bootstrap=True)
        self.assertEqual(result['status'], 'CURRENT')
        self.assertFalse(result['payloads_uploaded'])
        self.assertFalse(any(n.startswith(p.BASELINE) for n in self.store.writes))

    def test_full_failure_never_changes_current(self):
        work,plan=self.application_plan(1)
        p.apply(self.store, FakeReader(source(1)), plan, work)
        before=self.store.data[b.POINTER]
        work2,plan2=self.application_plan(2)
        self.store.corrupt.add(b.ROOT+'/state/history/pages-102/files/latest.json')
        with self.assertRaises(b.PublishError):
            p.apply(self.store, FakeReader(source(2)), plan2, work2)
        self.assertEqual(self.store.data[b.POINTER], before)

    def test_workflow_follows_success_without_changes_to_producer(self):
        text = (Path(__file__).resolve().parents[2]/'.github/workflows/azure-data-publish.yml').read_text()
        self.assertIn('workflow_run:', text)
        self.assertIn('workflows: [Deploy GitHub Pages]', text)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", text)
        self.assertIn('actions: read', text)
        self.assertIn('contents: read', text)
        self.assertNotIn('contents: write', text)
        self.assertNotIn('pull_request:', text)
        self.assertNotIn('deploy-pages@', text)
        self.assertNotIn('static-web-apps-deploy', text)
        self.assertIn('ref: ${{ github.sha }}', text)


if __name__ == '__main__':
    unittest.main()
