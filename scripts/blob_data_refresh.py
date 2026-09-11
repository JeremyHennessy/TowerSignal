"""Independent data producer: verified Blob history in, fresh paired release out.

GitHub access is read-only. The existing Pages publisher and migration snapshot
are untouched. New versions use lineage and compare-and-swap, not comparisons of
unrelated workflow run numbers. No site or authentication deployment occurs.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import zipfile

import blob_release_store as b
from publish_pages_to_blob import (REPO, REPO_ID, PAGES_WORKFLOW, check_runtime,
                                  check_history_parity, written_history, get_reader)

WORKFLOW = '.github/workflows/azure-data-refresh.yml'
KIND = 'data-only'
CACHE_LOCATIONS = {
    'acris': ('.acris-store', 'data/acris/cache.json'),
    'checkbook': ('.checkbook-store', 'data/checkbook/cache.json'),
    'oath': ('.oath-store', 'data/history/oath-cache.json.gz'),
}
WORK = Path('.data-refresh')
HISTORY = Path('.history-store/data/history')


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b.encoded(value))


def dt(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    b.require(result.tzinfo is not None, 'Timestamp lacks timezone')
    return result


def source_context(reader, *, generation_required=False):
    env = os.environ
    run_id = env.get('GITHUB_RUN_ID', '')
    b.require(env.get('GITHUB_REPOSITORY') == REPO and env.get('GITHUB_REF') == 'refs/heads/main' and
              run_id.isdigit(), 'Only the trusted main data workflow may use storage')
    run = reader.get(f'/actions/runs/{run_id}')
    b.require(run['id'] == int(run_id) and run['repository']['id'] == REPO_ID and
              run['head_repository']['id'] == REPO_ID and run['head_branch'] == 'main' and
              run['path'] == WORKFLOW and run['event'] in ('schedule', 'workflow_dispatch') and
              run['head_sha'] == env.get('GITHUB_SHA') and
              re.fullmatch('[0-9a-f]{40}', run['head_sha']) and
              run['status'] in ('in_progress', 'completed') and run.get('conclusion') in (None, 'success'),
              'Unexpected source workflow, commit, event, or conclusion')
    job = None
    if generation_required:
        result = reader.get(f'/actions/runs/{run_id}/jobs?filter=latest&per_page=100')
        b.require(result['total_count'] == len(result['jobs']) <= 100, 'Incomplete generation job listing')
        matches = [j for j in result['jobs'] if j['name'] == 'generate']
        b.require(len(matches) == 1 and matches[0]['status'] == 'completed' and
                  matches[0]['conclusion'] == 'success', 'Generation and validation job has not succeeded')
        job = matches[0]
    source = {'kind': KIND, 'workflow_path': WORKFLOW, 'workflow_id': run['workflow_id'],
              'run_id': run['id'], 'run_number': run['run_number'], 'run_attempt': run['run_attempt'],
              'source_sha': run['head_sha'], 'created_at': run['created_at']}
    return source, job


def read_current(store):
    raw, etag = store.read(b.POINTER, 128 * 1024)
    current = json.loads(raw)
    source = current.get('source', {})
    pages = source.get('workflow_id') == PAGES_WORKFLOW and not source.get('kind')
    data = source.get('kind') == KIND and source.get('workflow_path') == WORKFLOW
    b.require(current.get('schema_version') == 1 and current.get('domain') == 'TOWERSIGNAL_BLOB_RELEASE'
              and (pages or data) and re.fullmatch('[0-9a-f]{40}', source.get('source_sha', ''))
              and type(source.get('run_id')) is int and source['run_id'] > 0,
              'Unrecognized current release; refuse to invent a baseline')
    return current, raw, etag


class DataStore(b.AzureStore):
    @staticmethod
    def allow_write(name):
        b.safe_path(name)
        b.require(re.fullmatch(r'towersignal-data/(?:releases|state/history)/data-[0-9]+-[0-9]+/.+', name),
                  'Data producer writes only its immutable data release/state namespace')
    # Inherited cas permits only the single canonical production pointer.


def download_records(store, prefix, records, root):
    b.validate_records(records)
    b.require(not root.exists(), 'History restore directory must be empty')
    root.mkdir(parents=True)
    def copy(row):
        name = prefix + '/' + row['path']
        props = store.head(name)
        b.require(props['bytes'] == row['bytes'], 'History Blob size differs from manifest')
        path = root / b.safe_path(row['path'])
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as out:
            for block in store.chunks(name, props['etag']):
                out.write(block)
        size, sha, git = b.hash_file(path)
        b.require(size == row['bytes'] and sha == row['sha256'] and
                  (not row.get('git_blob_sha') or git == row['git_blob_sha']), 'History restore checksum failed')
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(copy, records))
    b.require([(r['path'], r['bytes'], r['sha256']) for r in b.local_records(root)] ==
              sorted((r['path'], r['bytes'], r['sha256']) for r in records), 'Restored history inventory differs')


def cache_proof(root):
    result = {}
    for name, (checkout, relative) in CACHE_LOCATIONS.items():
        directory = root / checkout
        sha = subprocess.check_output(['git', '-C', str(directory), 'rev-parse', 'HEAD'], text=True).strip()
        b.require(re.fullmatch('[0-9a-f]{40}', sha), 'Cache checkout is not a pinned Git commit')
        file = directory / relative
        b.require(file.is_file() and not file.is_symlink(), f'Required source cache missing: {name}')
        size, digest, git = b.hash_file(file)
        recorded = subprocess.check_output(['git', '-C', str(directory), 'rev-parse', f'HEAD:{relative}'], text=True).strip()
        b.require(git == recorded, 'Cache checkout bytes differ from their Git object')
        result[name] = {'commit': sha, 'path': relative, 'bytes': size, 'sha256': digest, 'git_blob_sha': git}
    return result


def prepare(store, reader, root):
    source, _ = source_context(reader)
    work = root / WORK
    b.require(not (work / 'report/input.json').exists(), 'Input receipt already exists')
    parent, raw, etag = read_current(store)
    b.validate_descriptor(store, parent['history'], 'history', parent['source'])
    manifest, _ = b.checked_json(store, parent['history']['manifest'])
    b.verify_dataset(store, parent['history']['data_prefix'], manifest['records'])
    download_records(store, parent['history']['data_prefix'], manifest['records'], root / HISTORY)
    caches = cache_proof(root)
    # OATH is a source cache, not a new history observation. Its independently
    # refreshed Git object replaces only this local input; events/latest remain
    # exactly those restored from the paired Blob history descriptor.
    shutil.copyfile(root / '.oath-store/data/history/oath-cache.json.gz', root / HISTORY / 'oath-cache.json.gz')
    proof = {'schema_version': 1, 'source': source, 'generation_started_at': now(),
             'parent': {'current': parent, 'etag': etag, 'sha256': hashlib.sha256(raw).hexdigest(),
                        'raw': raw.decode('utf-8')}, 'input_history': manifest['records'], 'cache_inputs': caches}
    save(work / 'report/input.json', proof)
    print('DATA_INPUTS_VERIFIED=' + json.dumps({'parent_run': parent['source']['run_id'],
          'history_files': len(manifest['records']), 'cache_commits': {k:v['commit'] for k,v in caches.items()}}), flush=True)


def inventory_key(records):
    return sorted((r['path'], r['bytes'], r['sha256']) for r in records)


def seal(root):
    """Called only after the unchanged data validators/build and browser data tests."""
    work = root / WORK
    proof = json.loads((work / 'report/input.json').read_text())
    b.require(proof['source']['run_id'] == int(os.environ['GITHUB_RUN_ID']) and
              proof['source']['source_sha'] == os.environ['GITHUB_SHA'] and
              proof['source']['run_attempt'] == int(os.environ['GITHUB_RUN_ATTEMPT']), 'Input/run mismatch')
    b.require(cache_proof(root) == proof['cache_inputs'], 'Source caches changed during generation')
    inputs = b.local_records(root / HISTORY)
    expected_inputs = {r['path']: (r['bytes'], r['sha256']) for r in proof['input_history']}
    oath = proof['cache_inputs']['oath']
    expected_inputs['oath-cache.json.gz'] = (oath['bytes'], oath['sha256'])
    b.require({r['path']: (r['bytes'], r['sha256']) for r in inputs} == expected_inputs,
              'Previous history or OATH input changed during generation')
    runtime = b.local_records(root / 'public/data')
    check_runtime(runtime)
    b.require(inventory_key(runtime) == inventory_key(b.local_records(root / 'dist/data')),
              'Browser-tested build and generated runtime bytes differ')
    start = dt(proof['generation_started_at'])
    cutoff = datetime.now(timezone.utc) + timedelta(minutes=5)
    generated = {}
    for name in ('systems.json', 'nys-systems.json', 'source-health.json'):
        payload = json.loads((root / 'public/data' / name).read_text())
        observed = (payload.get('metadata') or payload).get('generated_at')
        b.require(observed and start <= dt(observed) <= cutoff, f'Fresh generation timestamp missing: {name}')
        generated[name] = observed
    history_root = work / 'candidate/history'
    b.require(not history_root.exists(), 'Sealed history directory already exists')
    shutil.copytree(root / HISTORY, history_root)
    # This is the same history projection the Pages persist-history job writes.
    # Clear only local old segments, then retain other inputs, including OATH.
    if (history_root / 'segments').exists():
        shutil.rmtree(history_root / 'segments')
    for relative in written_history(runtime):
        src = root / 'public/data' / ('source-health.json' if relative == 'source-health.json' else 'history/' + relative)
        target = history_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
    history = b.local_records(history_root)
    parity = check_history_parity(runtime, history)
    final = {**proof, 'runtime': runtime, 'history': history, 'history_parity': parity,
             'generated_at': generated, 'sealed_at': now(), 'site_deployed': False,
             'browser_gate': 'local Chromium and WebKit data transport, not hosted UI/auth'}
    save(work / 'report/candidate.json', final)
    # The archive is data only. Source code and credentials are never included.
    out = work / 'candidate.tar.gz'
    with tarfile.open(out, 'w:gz') as tar:
        for kind, directory, records in [('runtime', root / 'public/data', runtime), ('history', history_root, history)]:
            for row in records:
                tar.add(directory / row['path'], arcname=kind + '/' + row['path'], recursive=False)
        tar.add(work / 'report/candidate.json', arcname='candidate.json', recursive=False)
    print('DATA_CANDIDATE_SEALED=' + json.dumps({'runtime_files': len(runtime), 'history_files': len(history),
                                             'history_parity': parity, 'generated_at': generated}), flush=True)


def unpack_candidate(archive, destination):
    b.require(not destination.exists(), 'Candidate staging directory must be empty')
    total = 0
    seen = set()
    with tarfile.open(archive, 'r:gz') as tar:
        for entry in tar:
            name = b.safe_path(entry.name)
            b.require(entry.isfile() and not entry.issym() and not entry.islnk() and name not in seen,
                      'Candidate contains a directory, special file, link or duplicate')
            b.require(name == 'candidate.json' or name.startswith(('runtime/', 'history/')), 'Unexpected candidate path')
            total += entry.size
            seen.add(name)
            b.require(len(seen) <= b.MAX_FILES * 2 + 1 and total <= b.MAX_BYTES, 'Candidate exceeds safety bound')
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(entry) as src, path.open('xb') as dst:
                shutil.copyfileobj(src, dst, b.CHUNK)
            b.require(path.stat().st_size == entry.size, 'Candidate extraction was truncated')
    b.require('candidate.json' in seen, 'No sealed candidate manifest')
    proof = json.loads((destination / 'candidate.json').read_text())
    for kind in ('runtime', 'history'):
        b.validate_records(proof[kind])
        b.require(inventory_key(b.local_records(destination / kind)) == inventory_key(proof[kind]),
                  f'Sealed {kind} checksum/inventory mismatch')
    expected = {'candidate.json'} | {k + '/' + r['path'] for k in ('runtime', 'history') for r in proof[k]}
    b.require(seen == expected, 'Candidate has unexpected data files')
    check_runtime(proof['runtime'])
    b.require(check_history_parity(proof['runtime'], proof['history']) == proof['history_parity'], 'Sealed history parity differs')
    return proof


def stage(reader, root):
    source, generate = source_context(reader, generation_required=True)
    result = reader.get(f"/actions/runs/{source['run_id']}/artifacts?per_page=100")
    b.require(result['total_count'] == len(result['artifacts']) <= 100, 'Incomplete artifact list')
    lo, hi = dt(generate['started_at']), dt(generate['completed_at'])
    matches = [a for a in result['artifacts'] if a['name'].startswith(f"data-candidate-{source['run_id']}-") and
               lo <= dt(a['created_at']) <= hi]
    b.require(len(matches) == 1, 'No unique sealed artifact from the successful generate job')
    meta = matches[0]
    b.require(not meta['expired'] and meta['workflow_run']['id'] == source['run_id'] and
              meta['workflow_run']['head_sha'] == source['source_sha'] and
              re.fullmatch('sha256:[0-9a-f]{64}', meta.get('digest') or ''), 'Artifact provenance is invalid')
    work = root / WORK
    package = work / 'candidate.zip'
    reader.download(f"/actions/artifacts/{meta['id']}/zip", package)
    b.require(package.stat().st_size == meta['size_in_bytes'], 'Artifact byte count differs')
    with package.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    b.require(meta['digest'] == 'sha256:' + digest, 'Artifact digest mismatch')
    with zipfile.ZipFile(package) as z:
        b.require(z.namelist() == ['candidate.tar.gz'] and z.infolist()[0].file_size <= b.MAX_BYTES, 'Unexpected artifact ZIP')
        with z.open('candidate.tar.gz') as src, (work / 'candidate.tar.gz').open('xb') as dst:
            shutil.copyfileobj(src, dst, b.CHUNK)
    proof = unpack_candidate(work / 'candidate.tar.gz', work / 'staged')
    compare = {**source, 'run_attempt': proof['source']['run_attempt']}
    b.require(compare == proof['source'] and 0 < proof['source']['run_attempt'] <= source['run_attempt'] and
              meta['name'] == f"data-candidate-{source['run_id']}-{proof['source']['run_attempt']}", 'Sealed source identity differs')
    save(work / 'report/staged.json', {'artifact_id': meta['id'], 'artifact_sha256': digest,
                                      'source': proof['source'], 'generated_at': proof['generated_at']})
    return proof


def unchanged_parent(store, proof):
    parent, raw, etag = read_current(store)
    expected = proof['parent']
    b.require(etag == expected['etag'] and raw.decode('utf-8') == expected['raw'] and
              hashlib.sha256(raw).hexdigest() == expected['sha256'] and parent == expected['current'],
              'Current release changed since history was loaded; candidate cannot advance')
    return parent, raw, etag


def publish(store, reader, root):
    proof = json.loads((root / WORK / 'staged/candidate.json').read_text())
    source = proof['source']
    actual, _ = source_context(reader, generation_required=True)
    b.require({**actual, 'run_attempt': source['run_attempt']} == source, 'Source gate changed before publication')
    current, _, etag = read_current(store)
    if current['source'] == source:
        # An ambiguous successful CAS is a retry only if the full dataset is identical.
        for kind in ('runtime', 'history'):
            b.validate_descriptor(store, current[kind], kind, source)
            manifest, _ = b.checked_json(store, current[kind]['manifest'])
            b.require(inventory_key(manifest['records']) == inventory_key(proof[kind]), 'Same-run payload differs')
            b.verify_dataset(store, current[kind]['data_prefix'], manifest['records'])
        result = {'status': 'ALREADY_CURRENT', 'current': current, 'etag': etag}
    else:
        parent, previous, expected_etag = unchanged_parent(store, proof)
        key = f"data-{source['run_id']}-{source['run_attempt']}"
        release = b.ROOT + '/releases/' + key
        state = b.ROOT + '/state/history/' + key
        descriptors = {}
        for kind, prefix, meta_prefix in [('runtime', release + '/runtime', release + '/_publication/runtime'),
                                         ('history', state + '/files', state + '/_publication')]:
            descriptors[kind] = b.publish_dataset(store, root / WORK / 'staged' / kind, prefix,
                                                  proof[kind], meta_prefix, kind, source)
        provenance = b.immutable_json(store, release + '/_publication/provenance.json', proof)
        # A previous pointer is an exact byte backup, not reserialized inferred state.
        backup = release + '/_publication/previous-current.json'
        store.create(backup, io.BytesIO(previous), len(previous), 'application/json')
        b.verify_one(store, backup, b.record_bytes(backup, previous))
        for kind in ('runtime', 'history'):
            selector, _ = store.read(b.ROOT + f'/pointers/{kind}-current.json', 4096)
            b.require(json.loads(selector) == {'schema_version': 1, 'resolve_via': b.POINTER, 'select': kind},
                      'Current selector contract changed')
        actual, _ = source_context(reader, generation_required=True)
        b.require({**actual, 'run_attempt': source['run_attempt']} == source, 'Source gates changed during upload')
        unchanged_parent(store, proof)
        current = {'schema_version': 1, 'domain': 'TOWERSIGNAL_BLOB_RELEASE', 'source': source,
                   'revision': parent.get('revision', 0) + 1, **descriptors, 'provenance': provenance,
                   'previous': {'blob': backup, 'sha256': hashlib.sha256(previous).hexdigest()},
                   'generation_started_at': proof['generation_started_at']}
        raw = b.encoded(current)
        store.cas(b.POINTER, raw, expected_etag)
        downloaded, new_etag = store.read(b.POINTER, 128 * 1024)
        b.require(downloaded == raw, 'Current pointer readback differs')
        result = {'status': 'CURRENT', 'current': current, 'etag': new_etag}
    result.update({'verified_at': now(), 'source': source, 'generated_at': proof['generated_at'],
                   'history_parity': proof['history_parity'], 'site_deployed': False,
                   'github_history_written': False, 'storage_access_policy_changed': False})
    save(root / WORK / 'report/publication-result.json', result)
    print('DATA_REFRESH_RESULT=' + json.dumps(result, sort_keys=True), flush=True)
    if summary := os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(summary, 'a') as out:
            out.write('# Data-only Blob refresh\n\n')
            out.write(f"Status: **{result['status']}**. Run: `{source['run_id']}`. No website deployment.\n\n")
            for kind in ('runtime', 'history'):
                desc = result['current'][kind]
                out.write(f"{kind}: **{desc['files']:,} files / {desc['bytes']:,} bytes**.\n\n")
            out.write('All payload checksums and inventories passed before paired pointer promotion.\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('prepare', 'seal', 'stage', 'publish'))
    args = parser.parse_args()
    root = Path.cwd()
    store = None
    try:
        if args.operation == 'seal':
            seal(root)
        elif args.operation == 'stage':
            stage(get_reader(), root)
        else:
            logging.getLogger('azure').setLevel(logging.ERROR)
            store = DataStore()
            if args.operation == 'prepare':
                prepare(store, get_reader(), root)
            else:
                publish(store, get_reader(), root)
    except Exception as error:
        message = str(error) if isinstance(error, b.PublishError) else type(error).__name__
        save(root / WORK / 'report/failure.json', {'status': 'FAILED', 'operation': args.operation, 'reason': message})
        print('::error::Data refresh stopped: ' + message)
        raise SystemExit(1) from None
    finally:
        if store:
            store.close()


if __name__ == '__main__':
    main()
