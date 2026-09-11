"""Mirror successful main Pages releases into private Blob without changing the producer.

The follower requires build, deploy, hosted verify AND GitHub history persistence.
It never runs code from source artifacts, writes GitHub history, or deploys a site.
Bootstrap adopts the checksum-pinned migration snapshot without rewriting payloads.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import stat
from datetime import datetime, timezone
import zipfile

from blob_release_store import (ROOT, POINTER, MAX_BYTES, MAX_FILES, PublishError, AzureStore,
                                require, safe_path, encoded, local_records, validate_records,
                                publish_dataset, promote, current_pointer, checked_json,
                                validate_descriptor, verify_dataset)

REPO = 'JeremyHennessy/TowerSignal'
REPO_ID = 1342221875
PAGES_WORKFLOW = 339705737
BASELINE_RUN = 34544249376
BASELINE_SHA = '53f7016404774821051e5ebd02eeb5382dded55f'
BASELINE_HISTORY = 'ec888b6bbba931d98efa50cdbef81125d18ec70b'
BASELINE = ROOT + '/migrations/github-34593386563-1'
BASELINE_MANIFEST = '14fc341268dfdfc0cd0e6df9628f678293c5b44de2a1da9b148745434ac37bcd'
BASELINE_COMPLETE = 'dffeca3b807a708ffad11665fbf1f445cbcf0eac2705a0defce40679749fe688'
REQUIRED = ('systems.json', 'changes.json', 'nys-systems.json', 'nys-changes.json', 'source-health.json')
HISTORY_WRITTEN = ('latest.json', 'events.json', 'nys/latest.json', 'nys/events.json', 'source-health.json')


def get_reader():
    # Existing GET-only reader strips credentials before following artifact redirects.
    from migrate_data_to_blob import GitHubReader
    return GitHubReader()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded(value))


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(parsed.tzinfo is not None, 'Source timestamp lacks timezone')
    return parsed


def successful_source(reader, run_id):
    require(str(run_id).isdigit() and int(run_id) > 0, 'Source run ID must be numeric')
    run = reader.get(f'/actions/runs/{run_id}')
    require(run['id'] == int(run_id) and run['repository']['id'] == REPO_ID and
            run['head_repository']['id'] == REPO_ID and run['head_branch'] == 'main' and
            run['workflow_id'] == PAGES_WORKFLOW and run['path'] == '.github/workflows/pages.yml' and
            run['event'] in ('push', 'schedule', 'workflow_dispatch') and
            run['status'] == 'completed' and run['conclusion'] == 'success' and
            type(run['run_number']) is int and run['run_number'] > 0 and
            re.fullmatch('[0-9a-f]{40}', run['head_sha']),
            'Source is not a successful trusted main Pages release')
    jobs = reader.get(f'/actions/runs/{run_id}/jobs?filter=latest&per_page=100')
    require(jobs['total_count'] == len(jobs['jobs']) <= 100, 'Incomplete source job inventory')
    by_name = {}
    for job in jobs['jobs']:
        require(job['name'] not in by_name, 'Ambiguous source job identity')
        by_name[job['name']] = job
    for name in ('build', 'deploy', 'verify', 'persist-history'):
        job = by_name.get(name, {})
        require(job.get('status') == 'completed' and job.get('conclusion') == 'success',
                f'Required source gate did not pass: {name}')
    return {'workflow_id': PAGES_WORKFLOW, 'run_id': run['id'], 'run_number': run['run_number'],
            'source_sha': run['head_sha'], 'created_at': run['created_at']}, by_name


def history_tree(reader, sha):
    require(re.fullmatch('[0-9a-f]{40}', sha), 'History commit must be pinned')
    tree = reader.get(f'/git/trees/{sha}?recursive=1')
    require(not tree.get('truncated'), 'History Git tree is incomplete')
    files = {}
    for item in tree['tree']:
        name = item['path']
        if name.startswith('data/history/') and item['type'] != 'tree':
            require(item['type'] == 'blob' and item['mode'] in ('100644', '100755'), 'Unsafe history Git object')
            path = safe_path(name.removeprefix('data/history/'))
            require(path not in files, 'Duplicate history Git path')
            files[path] = item
    require(files, 'No persisted history found at the pinned commit')
    return files


def match_git_history(records, tree):
    require({r['path'] for r in records} == set(tree), 'History file inventory differs from Git')
    result = []
    for row in records:
        git = tree[row['path']]
        require(git['size'] == row['bytes'] and
                (not row.get('git_blob_sha') or row['git_blob_sha'] == git['sha']),
                'History size/Git hash differs from pinned Git snapshot')
        result.append({**row, 'git_blob_sha': git['sha']})
    return result


def written_history(records):
    """Exact output projection of the unchanged persist-history job."""
    result = {}
    for row in records:
        name = row['path']
        if name == 'source-health.json':
            target = name
        elif name.startswith('history/'):
            target = name.removeprefix('history/')
            if target not in HISTORY_WRITTEN[:-1] and not target.startswith('segments/'):
                continue
        else:
            continue
        require(target not in result, 'Duplicate generated history path')
        result[target] = (row['bytes'], row['sha256'])
    require(all(n in result for n in HISTORY_WRITTEN) and
            any(n.startswith('segments/') for n in result), 'Generated history is incomplete')
    return result


def check_history_parity(runtime, history, staged_history=None):
    generated = written_history(runtime)
    durable = {r['path']: (r['bytes'], r['sha256']) for r in history}
    require(all(durable.get(n) == v for n, v in generated.items()), 'Runtime/GitHub history parity failed')
    written_names = {n for n in durable if n in HISTORY_WRITTEN or n.startswith('segments/')}
    require(written_names == set(generated), 'Unexpected persisted history segment')
    if staged_history is not None:
        staged = written_history(staged_history)
        require(staged == generated, 'Pages and history-state artifacts disagree')
    # Other persisted inputs (currently oath-cache.json.gz) are retained, not invented or discarded.
    return {'generated_files_matched': len(generated), 'durable_files': len(durable),
            'retained_git_files': sorted(set(durable) - set(generated))}


def check_runtime(records):
    validate_records(records)
    names = {r['path'] for r in records}
    require(set(REQUIRED) <= names and any(n.startswith('details/') for n in names) and
            any(n.startswith('firm-details/') for n in names), 'Incomplete runtime dataset')


def select_artifact(artifacts, name, source, build_job):
    start, end = timestamp(build_job['started_at']), timestamp(build_job['completed_at'])
    matches = [a for a in artifacts if a['name'] == name and
               start <= timestamp(a['created_at']) <= end]
    require(len(matches) == 1, f'No unique {name} artifact belongs to the successful build')
    value = matches[0]
    require(not value['expired'] and value['workflow_run']['id'] == source['run_id'] and
            value['workflow_run']['head_sha'] == source['source_sha'] and
            re.fullmatch(r'sha256:[0-9a-f]{64}', value.get('digest') or ''),
            'Source artifact is expired or lacks exact provenance/digest')
    return value


def unpack_history(archive, destination):
    seen = set()
    total = 0
    with zipfile.ZipFile(archive) as z:
        require(len(z.infolist()) <= MAX_FILES, 'History archive file bound exceeded')
        for entry in z.infolist():
            name = safe_path(entry.filename.rstrip('/'))
            require(not stat.S_ISLNK(entry.external_attr >> 16), 'History archive symlink')
            if entry.is_dir():
                continue
            require(name not in seen and (name.startswith('history/') or name == 'source-health.json'),
                    'Duplicate/unexpected history archive member')
            seen.add(name)
            total += entry.file_size
            require(total <= MAX_BYTES, 'History archive size bound exceeded')
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with z.open(entry) as src, path.open('xb') as dst:
                shutil.copyfileobj(src, dst, 4 * 1024**2)
            require(path.stat().st_size == entry.file_size, 'Truncated history archive member')


def stage(reader, run_id, work):
    from migrate_data_to_blob import extract_runtime, snapshot
    source, jobs = successful_source(reader, run_id)
    artifacts = []
    for page in range(1, 101):
        result = reader.get(f'/actions/runs/{run_id}/artifacts?per_page=100&page={page}')
        artifacts.extend(result['artifacts'])
        if len(artifacts) >= result['total_count']:
            break
    require(len(artifacts) == result['total_count'], 'Incomplete artifact inventory')
    archive_proof = []
    for name in ('github-pages', 'towersignal-history-state'):
        meta = select_artifact(artifacts, name, source, jobs['build'])
        archive = work / f'{name}.zip'
        reader.download(f"/actions/artifacts/{meta['id']}/zip", archive)
        require(archive.stat().st_size == meta['size_in_bytes'], 'Artifact byte count mismatch')
        with archive.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        require('sha256:' + digest == meta['digest'], 'Artifact SHA-256 mismatch')
        archive_proof.append({'id': meta['id'], 'name': name, 'sha256': digest})
        if name == 'github-pages':
            extract_runtime(archive, work / 'runtime')
        else:
            unpack_history(archive, work / 'history-artifact')
    history_sha = reader.get('/git/ref/heads/data/towersignal-history')['object']['sha']
    snapshot(reader, {'sha': history_sha, 'name': 'history', 'ref': 'data/towersignal-history',
                      'paths': ['data/history'], 'required': True}, work / 'snapshots', work)
    history_root = work / 'snapshots/support/history/data/history'
    runtime = local_records(work / 'runtime')
    history = match_git_history(local_records(history_root), history_tree(reader, history_sha))
    check_runtime(runtime)
    parity = check_history_parity(runtime, history, local_records(work / 'history-artifact'))
    source['history_sha'] = history_sha
    save(work / 'report/staged-release.json', {'source': source, 'artifacts': archive_proof,
                                             'history_parity': parity, 'runtime': runtime, 'history': history})
    print('STAGED_RELEASE=' + json.dumps({'source': source, 'history_parity': parity,
                                        'runtime_files': len(runtime), 'history_files': len(history)}), flush=True)


def baseline_plan(store, reader):
    source, _ = successful_source(reader, BASELINE_RUN)
    require(source['source_sha'] == BASELINE_SHA, 'Bootstrap release SHA differs from approved baseline')
    source['history_sha'] = BASELINE_HISTORY
    manifest, _ = checked_json(store, {'blob': BASELINE + '/_migration/manifest.json', 'sha256': BASELINE_MANIFEST})
    receipt, _ = checked_json(store, {'blob': BASELINE + '/_migration/complete.json', 'sha256': BASELINE_COMPLETE})
    require(receipt['status'] == 'COMPLETE' and receipt['manifest_sha256'] == BASELINE_MANIFEST and
            receipt['prefix'] == BASELINE and receipt['source_run_id'] == BASELINE_RUN and
            receipt['source_sha'] == BASELINE_SHA and receipt['all_payload_sha256_readbacks_passed'] is True and
            receipt['exact_file_inventory_passed'] is True and
            manifest['repository'] == REPO and manifest['source_run_id'] == BASELINE_RUN and
            manifest['source_sha'] == BASELINE_SHA, 'Bootstrap proof does not match verified copy')
    validate_records(manifest['records'])
    require(len(manifest['records']) == 22015 and
            sum(r['bytes'] for r in manifest['records']) == 2465142728, 'Baseline inventory changed')
    def subset(prefix):
        return [{**r, 'path': r['path'].removeprefix(prefix)} for r in manifest['records']
                if r['path'].startswith(prefix)]
    runtime = subset('runtime/')
    history = match_git_history(subset('support/history/data/history/'), history_tree(reader, BASELINE_HISTORY))
    check_runtime(runtime)
    return {'source': source, 'runtime': runtime, 'history': history,
            'history_parity': check_history_parity(runtime, history),
            'baseline_manifest_sha256': BASELINE_MANIFEST, 'baseline_complete_sha256': BASELINE_COMPLETE}


def apply(store, reader, plan, work, *, bootstrap=False):
    source = plan['source']
    actual, _ = successful_source(reader, source['run_id'])
    require({**actual, 'history_sha': source['history_sha']} == source, 'Source release changed after staging')
    # Bootstrap reads its approved historical commit. Fresh releases must still match the live Git writer.
    if not bootstrap:
        require(reader.get('/git/ref/heads/data/towersignal-history')['object']['sha'] == source['history_sha'],
                'GitHub history advanced during publication; do not promote this candidate')
    check_runtime(plan['runtime'])
    require(check_history_parity(plan['runtime'], plan['history']) == plan['history_parity'],
            'Staged parity proof no longer matches the data inventory')
    old, _, _ = current_pointer(store)
    if old and old['source']['run_id'] == source['run_id']:
        require(old['source'] == source, 'Same-run source proof differs from current release')
        for kind in ('runtime', 'history'):
            validate_descriptor(store, old[kind], kind, source)
            manifest, _ = checked_json(store, old[kind]['manifest'])
            validate_records(plan[kind])
            expected = {(r['path'], r['bytes'], r['sha256']) for r in plan[kind]}
            existing = {(r['path'], r['bytes'], r['sha256']) for r in manifest['records']}
            require(existing == expected, f'Same-run {kind} payload differs from current release')
            verify_dataset(store, old[kind]['data_prefix'], manifest['records'])
        result = {'status': 'ALREADY_CURRENT', 'source': source, 'current': old, 'payloads_uploaded': False}
    else:
        require(not old or (not bootstrap and source['run_number'] > old['source']['run_number']),
                'Refusing to replace a newer current release')
        release = f"{ROOT}/releases/pages-{source['run_id']}"
        state = f"{ROOT}/state/history/pages-{source['run_id']}"
        runtime_prefix = BASELINE + '/runtime' if bootstrap else release + '/runtime'
        history_prefix = BASELINE + '/support/history/data/history' if bootstrap else state + '/files'
        runtime = publish_dataset(store, None if bootstrap else work / 'runtime', runtime_prefix,
                                  plan['runtime'], release + '/_publication/runtime', 'runtime', source)
        history = publish_dataset(store, None if bootstrap else work / 'snapshots/support/history/data/history',
                                  history_prefix, plan['history'], state + '/_publication', 'history', source)
        # Check the release/history gates again immediately before the only current-pointer update.
        final, _ = successful_source(reader, source['run_id'])
        require(final == actual, 'Source gate changed during publication')
        if not bootstrap:
            require(reader.get('/git/ref/heads/data/towersignal-history')['object']['sha'] == source['history_sha'],
                    'GitHub history advanced before promotion')
        result = {**promote(store, source, runtime, history, bootstrap=bootstrap),
                  'payloads_uploaded': not bootstrap}
    result.update({'operation': 'bootstrap' if bootstrap else 'publish',
                   'history_parity': plan['history_parity'], 'source': source,
                   'publisher_run_id': os.environ.get('GITHUB_RUN_ID'),
                   'publisher_sha': os.environ.get('GITHUB_SHA'),
                   'verified_at': datetime.now(timezone.utc).isoformat(),
                   'github_history_written': False, 'github_sources_deleted': False,
                   'site_deployed': False, 'access_policy_changed': False,
                   'current_pointer': POINTER})
    save(work / 'report/publication-result.json', result)
    print('BLOB_PUBLICATION_RESULT=' + json.dumps(result, sort_keys=True), flush=True)
    if summary := os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(summary, 'a') as f:
            f.write('# Verified private Blob publication\n\n')
            f.write(f"Status: **{result['status']}**. Source release: `{source['run_id']}`.\n\n")
            for kind in ('runtime', 'history'):
                d = result['current'][kind]
                f.write(f"{kind}: {d['files']:,} files, {d['bytes']:,} bytes, `{d['data_prefix']}/`.\n\n")
            f.write('One conditional pointer selects the matched runtime/history pair. '
                    'GitHub source writers, history branch, frontend, hosting and access policy were not changed.\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('stage', 'publish', 'bootstrap'))
    parser.add_argument('--source-run', default='')
    parser.add_argument('--work', required=True, type=Path)
    args = parser.parse_args()
    store = None
    try:
        require(os.environ.get('GITHUB_REPOSITORY') == REPO and
                os.environ.get('GITHUB_REF') == 'refs/heads/main', 'Publication is restricted to main')
        reader = get_reader()
        if args.operation == 'stage':
            stage(reader, args.source_run, args.work)
        else:
            logging.getLogger('azure').setLevel(logging.ERROR)
            store = AzureStore()
            plan = baseline_plan(store, reader) if args.operation == 'bootstrap' else json.loads(
                (args.work / 'report/staged-release.json').read_text())
            save(args.work / 'report/source-plan.json', plan)
            apply(store, reader, plan, args.work, bootstrap=args.operation == 'bootstrap')
    except Exception as error:
        # Never stringify Azure/HTTP exceptions that could include credentials or signed URLs.
        reason = str(error) if isinstance(error, PublishError) else type(error).__name__
        save(args.work / 'report/publication-failure.json', {'status': 'FAILED', 'operation': args.operation,
                                                          'reason': reason})
        print('::error::Blob publication stopped: ' + reason)
        raise SystemExit(1) from None
    finally:
        if store:
            store.close()


if __name__ == '__main__':
    main()
