"""Offline fixtures for data-only orchestration; not claims of live Azure success."""
from __future__ import annotations

import copy
from datetime import datetime, timezone, timedelta
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import blob_release_store as b
import blob_data_refresh as d
import publish_pages_to_blob as p
from test_blob_release_publisher import MemoryStore, source


class Store(MemoryStore):
    def create(self, name, stream, size, content_type):
        d.DataStore.allow_write(name)
        if self.fail_create and self.fail_create in name:
            raise b.PublishError('Simulated upload failure')
        if name not in self.data:
            value = stream.read()
            assert len(value) == size
            self.seed(name, value)
            self.writes.append(name)


class Reader:
    def __init__(self, run=1001, attempt=1):
        self.run = {'id': run, 'run_number': run-1000, 'run_attempt': attempt,
                    'repository': {'id': d.REPO_ID}, 'head_repository': {'id': d.REPO_ID},
                    'head_branch': 'main', 'path': d.WORKFLOW, 'event': 'workflow_dispatch',
                    'head_sha': 'c'*40, 'workflow_id': 999, 'status': 'in_progress',
                    'conclusion': None, 'created_at': d.now()}
        self.jobs = {'total_count': 2, 'jobs': [{'name': 'generate', 'status': 'completed',
                     'conclusion': 'success', 'started_at': d.now(), 'completed_at': d.now()},
                     {'name': 'publish', 'status': 'in_progress', 'conclusion': None}]}
    def get(self, path):
        if '/jobs?' in path:
            return copy.deepcopy(self.jobs)
        if path == f"/actions/runs/{self.run['id']}":
            return copy.deepcopy(self.run)
        raise AssertionError(path)
    def env(self):
        return {'GITHUB_RUN_ID': str(self.run['id']), 'GITHUB_SHA': self.run['head_sha'],
                'GITHUB_REPOSITORY': d.REPO, 'GITHUB_REF': 'refs/heads/main',
                'GITHUB_RUN_ATTEMPT': str(self.run['run_attempt'])}


def files(root, values):
    root.mkdir(parents=True, exist_ok=True)
    for name, body in values.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)


def fixture_payload(when):
    result = {n: b'{}' for n in p.REQUIRED}
    result.update({'systems.json': b.encoded({'metadata': {'generated_at': when}, 'systems': []}),
                   'nys-systems.json': b.encoded({'metadata': {'generated_at': when}, 'systems': []}),
                   'source-health.json': b.encoded({'generated_at': when, 'sources': []}),
                   'details/20/a.json': b'{}', 'firm-details/kn/a.json': b'{}'})
    result.update({'history/'+n: n.encode() for n in p.HISTORY_WRITTEN[:-1]})
    result['history/segments/core.json'] = b'core'
    return result


class DataRefreshTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        initial = MemoryStore()
        s = source(1)
        payload = fixture_payload(d.now())
        hist = {n.removeprefix('history/'): v for n,v in payload.items() if n.startswith('history/')}
        hist['source-health.json'] = payload['source-health.json']
        hist['oath-cache.json.gz'] = b'old source cache'
        descriptors = []
        for kind, data in [('runtime', payload), ('history', hist)]:
            local = self.root / 'initial' / kind
            files(local, data)
            base = b.ROOT + '/releases/pages-101/'
            descriptors.append(b.publish_dataset(initial, local, base+kind, b.local_records(local),
                                                 base+'_publication/'+kind, kind, s))
        b.promote(initial, s, *descriptors)
        self.store = Store()
        self.store.data = initial.data
        self.store.versions = initial.versions
        self.store.metadata = initial.metadata
        self.reader = Reader()
        self.work = self.root / 'work'
        self.work.mkdir()
        self.make_caches(self.work)

    def tearDown(self):
        self.temp.cleanup()

    def make_caches(self, root):
        for kind, (checkout, relative) in d.CACHE_LOCATIONS.items():
            directory = root / checkout
            files(directory, {relative: kind.encode()})
            for cmd in [['git','init','-q'], ['git','config','user.name','Unit test'],
                        ['git','config','user.email','test@example.invalid'], ['git','add','.'],
                        ['git','commit','-qm','Fixture cache']]:
                subprocess.run(cmd, cwd=directory, check=True, capture_output=True)

    def prepare(self):
        with patch.dict(os.environ, self.reader.env()):
            d.prepare(self.store, self.reader, self.work)
        return json.loads((self.work/d.WORK/'report/input.json').read_text())

    def candidate(self):
        proof = self.prepare()
        when = (datetime.now(timezone.utc)+timedelta(seconds=1)).isoformat()
        data = fixture_payload(when)
        files(self.work/'public/data', data)
        files(self.work/'dist/data', data)
        with patch.dict(os.environ, self.reader.env()):
            d.seal(self.work)
        sealed = d.unpack_candidate(self.work/d.WORK/'candidate.tar.gz', self.work/d.WORK/'staged')
        return proof, sealed

    def publish(self):
        with patch.dict(os.environ, self.reader.env()):
            return d.publish(self.store, self.reader, self.work)

    def test_restore_keeps_previous_history_and_uses_current_oath_cache(self):
        before = self.store.data[b.POINTER]
        proof = self.prepare()
        self.assertEqual((self.work/d.HISTORY/'oath-cache.json.gz').read_bytes(), b'oath')
        self.assertEqual((self.work/d.HISTORY/'latest.json').read_bytes(), b'latest.json')
        self.assertEqual(self.store.data[b.POINTER], before)
        self.assertEqual(self.store.writes, [])
        self.assertEqual(set(proof['cache_inputs']), {'oath','acris','checkbook'})

    def test_missing_blob_history_does_not_fall_back_to_git(self):
        current,_,_=d.read_current(self.store)
        del self.store.data[current['history']['data_prefix']+'/latest.json']
        with self.assertRaises(b.PublishError):
            self.prepare()
        self.assertEqual(self.store.writes, [])

    def test_bad_history_checksum_rejected(self):
        current,_,_=d.read_current(self.store)
        self.store.seed(current['history']['data_prefix']+'/latest.json', b'wrong bytes')
        with self.assertRaises(b.PublishError):
            self.prepare()

    def test_successful_full_publication_uses_data_identity_and_retains_parent(self):
        before=self.store.data[b.POINTER]
        _, sealed=self.candidate()
        result=self.publish()
        self.assertEqual(result['status'], 'CURRENT')
        self.assertEqual(result['current']['source']['kind'], 'data-only')
        self.assertEqual(result['current']['source']['workflow_id'], 999)
        self.assertEqual(result['current']['revision'], 1)
        self.assertEqual(self.store.data[result['current']['previous']['blob']], before)
        self.assertEqual(result['current']['history']['files'], len(sealed['history']))
        self.assertFalse(result['site_deployed'])
        self.assertFalse(result['github_history_written'])
        self.assertTrue(all('/data-1001-1/' in n or n == b.POINTER for n in self.store.writes))

    def test_retry_reverifies_without_writing(self):
        self.candidate(); self.publish()
        before=self.store.data[b.POINTER]
        writes=list(self.store.writes)
        result=self.publish()
        self.assertEqual(result['status'], 'ALREADY_CURRENT')
        self.assertEqual(self.store.data[b.POINTER],before)
        self.assertEqual(self.store.writes,writes)

    def test_two_generations_restore_blob_history_and_advance_lineage(self):
        self.candidate(); self.publish()
        first=self.store.data[b.POINTER]
        self.work=self.root/'second'; self.work.mkdir(); self.make_caches(self.work)
        self.reader=Reader(1002)
        proof,_=self.candidate()
        self.assertEqual(proof['parent']['current']['source']['run_id'],1001)
        result=self.publish()
        self.assertEqual(result['current']['revision'],2)
        self.assertEqual(self.store.data[result['current']['previous']['blob']],first)

    def test_unknown_current_pointer_rejected(self):
        current=json.loads(self.store.data[b.POINTER]); current['source']['workflow_id']=42
        self.store.seed(b.POINTER,b.encoded(current))
        with self.assertRaises(b.PublishError): self.prepare()
        self.assertEqual(self.store.writes,[])

    def test_unknown_source_workflow_and_fork_block_storage_use(self):
        for key,value in [('head_branch','branch'),('path','.github/workflows/other.yml'),
                          ('head_repository',{'id':1}),('event','pull_request'),('conclusion','failure')]:
            reader=Reader();reader.run[key]=value
            with self.subTest(key=key), patch.dict(os.environ,reader.env()), self.assertRaises(b.PublishError):
                d.source_context(reader)

    def test_source_generation_failure_and_incomplete_job_listing_block_publish(self):
        self.candidate()
        for change in ('failed','missing','truncated'):
            original=copy.deepcopy(self.reader.jobs)
            if change=='failed': self.reader.jobs['jobs'][0]['conclusion']='failure'
            elif change=='missing': self.reader.jobs['jobs'][0]['name']='not-generate'
            else: self.reader.jobs['total_count']=3
            with self.subTest(change=change), self.assertRaises(b.PublishError): self.publish()
            self.reader.jobs=original
        self.assertEqual(self.store.writes,[])

    def test_changed_parent_stops_before_upload(self):
        self.candidate()
        self.store.seed(b.POINTER,self.store.data[b.POINTER])  # Identical bytes but a changed ETag still conflicts.
        with self.assertRaisesRegex(b.PublishError,'Current release changed'): self.publish()
        self.assertEqual(self.store.writes,[])

    def test_conditional_conflict_does_not_replace_current(self):
        self.candidate(); before=self.store.data[b.POINTER]; self.store.race=True
        with self.assertRaises(b.PublishError): self.publish()
        self.assertEqual(self.store.data[b.POINTER],before)

    def test_corrupt_upload_cannot_promote(self):
        self.candidate();before=self.store.data[b.POINTER]
        self.store.corrupt.add(b.ROOT+'/releases/data-1001-1/runtime/systems.json')
        with self.assertRaises(b.PublishError): self.publish()
        self.assertEqual(self.store.data[b.POINTER],before)

    def test_changed_same_run_payload_is_not_accepted(self):
        self.candidate();self.publish();before=self.store.data[b.POINTER]
        path=self.work/d.WORK/'staged/candidate.json';proof=json.loads(path.read_text())
        proof['runtime'][0]['sha256']='f'*64;d.save(path,proof)
        with self.assertRaisesRegex(b.PublishError,'Same-run payload differs'): self.publish()
        self.assertEqual(self.store.data[b.POINTER],before)

    def test_modified_local_runtime_does_not_upload(self):
        self.candidate()
        (self.work/d.WORK/'staged/runtime/systems.json').write_bytes(b'changed')
        with self.assertRaises(b.PublishError): self.publish()
        self.assertEqual(self.store.writes,[])

    def test_old_generation_date_not_relabelled_as_fresh(self):
        self.prepare();data=fixture_payload('2025-01-01T00:00:00Z')
        files(self.work/'public/data',data);files(self.work/'dist/data',data)
        with patch.dict(os.environ,self.reader.env()),self.assertRaisesRegex(b.PublishError,'Fresh generation timestamp'):
            d.seal(self.work)

    def test_previous_history_mutation_fails_sealing(self):
        self.prepare();data=fixture_payload(d.now())
        files(self.work/'public/data',data);files(self.work/'dist/data',data)
        (self.work/d.HISTORY/'latest.json').write_bytes(b'damaged')
        with patch.dict(os.environ,self.reader.env()),self.assertRaisesRegex(b.PublishError,'Previous history'):
            d.seal(self.work)

    def test_browser_tested_files_must_match_generated_files(self):
        self.prepare();data=fixture_payload(d.now())
        files(self.work/'public/data',data);files(self.work/'dist/data',data)
        (self.work/'dist/data/systems.json').write_bytes(b'wrong candidate')
        with patch.dict(os.environ,self.reader.env()),self.assertRaisesRegex(b.PublishError,'Browser-tested build'):
            d.seal(self.work)

    def test_cache_git_content_mismatch_fails(self):
        (self.work/'.acris-store/data/acris/cache.json').write_bytes(b'not committed')
        with self.assertRaisesRegex(b.PublishError,'Cache checkout bytes'): self.prepare()

    def test_unsafe_tar_paths_and_links_are_rejected(self):
        for i,(name,link) in enumerate([('../bad',False),('runtime/../bad',False),('/bad',False),
                                       ('runtime/link',True),('source.py',False)]):
            arc=self.root/f'bad{i}.tgz'
            with tarfile.open(arc,'w:gz') as tar:
                item=tarfile.TarInfo(name)
                if link: item.type=tarfile.SYMTYPE;item.linkname='/tmp'
                else: item.size=2
                tar.addfile(item,None if link else io.BytesIO(b'{}'))
            with self.subTest(name=name),self.assertRaises(b.PublishError):
                d.unpack_candidate(arc,self.root/f'out{i}')

    def test_digest_pinned_artifact_stage_and_publisher_retry_identity(self):
        _,proof=self.candidate()
        archive_bytes=(self.work/d.WORK/'candidate.tar.gz').read_bytes()
        package=io.BytesIO()
        with zipfile.ZipFile(package,'w') as z: z.writestr('candidate.tar.gz',archive_bytes)
        payload=package.getvalue()
        reader=Reader(); reader.run=self.reader.run.copy()
        artifact_time=d.now()
        reader.jobs['jobs'][0]['started_at']=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()
        reader.jobs['jobs'][0]['completed_at']=(datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat()
        meta={'id':55,'name':'data-candidate-1001-1','created_at':artifact_time,'expired':False,
              'workflow_run':{'id':1001,'head_sha':'c'*40},'size_in_bytes':len(payload),
              'digest':'sha256:'+hashlib.sha256(payload).hexdigest()}
        original_get=reader.get
        reader.get=lambda path: {'total_count':1,'artifacts':[meta]} if '/artifacts?' in path else original_get(path)
        def download(path,out):
            self.assertEqual(path,'/actions/artifacts/55/zip')
            out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(payload)
        reader.download=download
        target=self.root/'stage-only';target.mkdir()
        with patch.dict(os.environ,reader.env()): result=d.stage(reader,target)
        self.assertEqual(result,proof)
        self.assertEqual(json.loads((target/d.WORK/'report/staged.json').read_text())['artifact_id'],55)
        meta['digest']='sha256:'+'0'*64
        broken=self.root/'stage-bad';broken.mkdir()
        with patch.dict(os.environ,reader.env()),self.assertRaisesRegex(b.PublishError,'Artifact digest mismatch'):
            d.stage(reader,broken)

    def test_old_pages_publisher_fails_closed_after_data_authority_handoff(self):
        self.candidate();self.publish()
        before=self.store.data[b.POINTER]
        with self.assertRaises(b.PublishError): b.current_pointer(self.store)
        self.assertEqual(self.store.data[b.POINTER],before)

    def test_write_boundary_cannot_touch_migration_or_cache_data(self):
        for name in [p.BASELINE+'/runtime/a',b.ROOT+'/caches/acris/x',b.ROOT+'/pointers/runtime-current.json',
                     'unrelated/data.json',b.ROOT+'/releases/data-1-1/../../evil']:
            with self.subTest(name=name),self.assertRaises(b.PublishError): d.DataStore.allow_write(name)
        d.DataStore.allow_write(b.ROOT+'/releases/data-1-1/runtime/a.json')
        d.DataStore.allow_write(b.ROOT+'/state/history/data-1-1/files/latest.json')

    def test_workflow_preserves_all_original_source_build_commands_and_limits(self):
        root=Path(__file__).resolve().parents[2]
        pages=(root/'.github/workflows/pages.yml').read_text()
        segment=pages[pages.index('      - name: Fetch, validate and generate current NYC data\n'):
                      pages.index('      - name: Stage history state for post-deploy persistence\n')]
        workflow=(root/d.WORKFLOW).read_text()
        self.assertIn(segment,workflow)
        self.assertIn("- cron: '17 10 * * *'",workflow)
        self.assertIn('needs: generate',workflow)
        self.assertIn('contents: read',workflow)
        self.assertIn('cancel-in-progress: false',workflow)
        self.assertIn('npx playwright test --config playwright.data-only.config.ts',workflow)
        for bad in ['contents: write','pages: write','deploy-pages@','configure-pages@','static-web-apps-deploy',
                    'continue-on-error:', 'git push', 'pull_request:']:
            self.assertNotIn(bad,workflow)
        self.assertLess(workflow.index('Verify generated data transport'),workflow.index('Seal exact runtime'))


if __name__=='__main__':
    unittest.main()
