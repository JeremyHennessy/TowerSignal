"""Copy pinned TowerSignal data to private Blob Storage; never switch or delete sources.

Stage needs a GitHub read token only. Upload needs the existing Azure key only.
A COMPLETE receipt is published only after every object has been read back and
SHA-256 checked and the destination inventory exactly matches the source manifest.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tarfile
import threading
from urllib.parse import urlparse
import zipfile

REPO = 'JeremyHennessy/TowerSignal'
DESTINATION = ('pharm3r', 'data', 'towersignal-data')
CHUNK = 4 * 1024 * 1024
MAX_BYTES = 12 * 1024**3
MAX_FILES = 100000


class MigrationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise MigrationError(message)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_path(value: str) -> str:
    require(bool(value) and not value.startswith('/') and '\\' not in value,
            'Unsafe archive or manifest path')
    parts = value.split('/')
    require('..' not in parts and not any(ord(c) < 32 for c in value), 'Unsafe path component')
    normalized = str(PurePosixPath(value))
    require(normalized != '.' and ':' not in normalized, 'Invalid file path')
    return normalized


def hash_stream(stream, *, git_size: int | None = None) -> tuple[int, str, str | None]:
    sha = hashlib.sha256()
    git = hashlib.sha1() if git_size is not None else None
    if git is not None:
        git.update(f'blob {git_size}\0'.encode())
    count = 0
    while block := stream.read(CHUNK):
        count += len(block)
        sha.update(block)
        if git is not None:
            git.update(block)
    return count, sha.hexdigest(), git.hexdigest() if git is not None else None


def file_record(root: Path, file: Path) -> dict:
    require(file.is_file() and not file.is_symlink(), 'Only regular files are permitted')
    with file.open('rb') as stream:
        size, digest, _ = hash_stream(stream)
    return {'path': safe_path(file.relative_to(root).as_posix()), 'bytes': size, 'sha256': digest}


def json_file(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


class GitHubReader:
    """Only GET requests. Never forward GitHub credentials to redirect hosts."""
    def __init__(self):
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        token = os.environ.get('GH_TOKEN')
        require(bool(token), 'Missing GH_TOKEN')
        self.session = requests.Session()
        self.session.headers.update({'Authorization': f'Bearer {token}',
                                     'Accept': 'application/vnd.github+json',
                                     'X-GitHub-Api-Version': '2022-11-28'})
        self.session.mount('https://', HTTPAdapter(max_retries=Retry(
            total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=['GET'])))

    def get(self, path: str):
        require(path.startswith('/') and '://' not in path, 'Invalid GitHub API path')
        response = self.session.get(f'https://api.github.com/repos/{REPO}{path}',
                                    timeout=(15, 120), allow_redirects=False)
        require(response.status_code == 200, f'GitHub read failed: HTTP {response.status_code}')
        return response.json()

    def download(self, api_path: str, output: Path) -> None:
        import requests
        response = self.session.get(f'https://api.github.com/repos/{REPO}{api_path}',
                                    timeout=(15, 120), allow_redirects=False, stream=True)
        require(response.status_code in (302, 301, 307),
                f'GitHub archive redirect failed: HTTP {response.status_code}')
        target = response.headers.get('Location', '')
        response.close()
        parsed = urlparse(target)
        host = parsed.hostname or ''
        require(parsed.scheme == 'https' and not parsed.username and
                (host == 'codeload.github.com' or host.endswith('.blob.core.windows.net') or
                 host.endswith('.githubusercontent.com') or host.endswith('.actions.githubusercontent.com')),
                'Unexpected archive download host')
        output.parent.mkdir(parents=True, exist_ok=True)
        # A fresh request has no API Authorization header; signed URLs never enter reports.
        with requests.get(target, timeout=(15, 120), stream=True, allow_redirects=False) as data:
            require(data.status_code == 200, f'Archive download failed: HTTP {data.status_code}')
            total = 0
            with output.open('xb') as stream:
                for block in data.iter_content(CHUNK):
                    total += len(block)
                    require(total <= MAX_BYTES, 'Archive exceeds migration size limit')
                    stream.write(block)


def extract_runtime(archive: Path, destination: Path) -> tuple[int, int]:
    """Extract every data/ file from the exact Pages artifact, preserving bytes."""
    files = 0
    total = 0
    seen = set()
    with zipfile.ZipFile(archive) as package:
        require(package.namelist() == ['artifact.tar'], 'Unexpected Pages ZIP layout')
        with package.open('artifact.tar') as packed, tarfile.open(fileobj=packed, mode='r|*') as tar:
            for item in tar:
                if item.name in ('.', './') and item.isdir():
                    continue
                name = safe_path(item.name)
                require(item.isdir() or item.isfile(), 'Pages archive contains a link or special file')
                if not item.isfile() or not name.startswith('data/'):
                    continue
                relative = safe_path(name[5:])
                require(relative not in seen, 'Duplicate runtime file')
                seen.add(relative)
                files += 1
                total += item.size
                require(files <= MAX_FILES and total <= MAX_BYTES, 'Runtime safety limit exceeded')
                output = destination / relative
                output.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(item) as source, output.open('xb') as target:
                    shutil.copyfileobj(source, target, CHUNK)
                require(output.stat().st_size == item.size, 'Runtime file extraction truncated')
    require(files > 0, 'No runtime data was found')
    return files, total


def snapshot(reader: GitHubReader, spec: dict, stage: Path, work: Path) -> dict:
    """Copy only selected data/config/schema paths, checking each Git blob SHA."""
    sha = spec['sha']
    require(bool(re.fullmatch(r'[0-9a-f]{40}', sha)), 'Snapshot commit is not pinned')
    tree = reader.get(f'/git/trees/{sha}?recursive=1')
    require(not tree.get('truncated'), 'Source Git tree is incomplete')
    expected = {}
    for item in tree['tree']:
        name = safe_path(item['path'])
        if any(name.startswith(prefix + '/') for prefix in spec['paths']) and item['type'] != 'tree':
            require(item['type'] == 'blob' and item['mode'] in ('100644', '100755'),
                    'Source snapshot contains a link or submodule')
            expected[name] = item
    summary = {'name': spec['name'], 'ref': spec['ref'], 'sha': sha,
               'paths': spec['paths'], 'files': len(expected), 'status': 'copied'}
    if not expected:
        require(not spec.get('required', True), f"Required snapshot missing: {spec['name']}")
        summary['status'] = 'absent-at-pinned-commit'
        return summary
    archive = work / f"snapshot-{spec['name']}.tar.gz"
    reader.download(f'/tarball/{sha}', archive)
    copied = set()
    root_prefix = None
    destination = stage / 'support' / spec['name']
    with tarfile.open(archive, 'r:gz') as tar:
        for item in tar:
            name = safe_path(item.name)
            parts = name.split('/', 1)
            if root_prefix is None:
                root_prefix = parts[0]
            require(parts[0] == root_prefix, 'Multiple snapshot archive roots')
            if len(parts) == 1:
                continue
            relative = parts[1]
            if relative not in expected:
                continue
            require(item.isfile() and relative not in copied, 'Invalid snapshot archive member')
            expected_file = expected[relative]
            require(item.size == expected_file['size'], 'Snapshot file size mismatch')
            output = destination / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(item) as source, output.open('xb') as target:
                shutil.copyfileobj(source, target, CHUNK)
            with output.open('rb') as source:
                size, _, git_sha = hash_stream(source, git_size=item.size)
            require(size == item.size and git_sha == expected_file['sha'], 'Snapshot Git blob hash mismatch')
            copied.add(relative)
    require(copied == set(expected), 'Snapshot archive did not contain all selected Git files')
    archive.unlink()  # Local temporary archive only; no remote source deletion.
    return summary


def stage_data(plan_path: Path, work: Path) -> None:
    plan = json.loads(plan_path.read_text())
    require(plan['repository'] == REPO, 'Unexpected source repository')
    reader = GitHubReader()
    run = reader.get(f"/actions/runs/{plan['source_run_id']}")
    require(run['head_sha'] == plan['source_sha'] and run['head_branch'] == 'main' and
            run['path'] == '.github/workflows/pages.yml' and run['status'] == 'completed' and
            run['conclusion'] == 'success', 'Pinned source release is not verified successful')
    jobs = reader.get(f"/actions/runs/{plan['source_run_id']}/jobs?per_page=100&filter=latest")
    require(jobs['total_count'] <= 100, 'Source job listing needs pagination')
    by_name = {job['name']: job for job in jobs['jobs']}
    require(all(by_name.get(name, {}).get('conclusion') == 'success'
                for name in ('build', 'deploy', 'verify', 'persist-history')),
            'Source release did not finish every required gate')
    stage = work / 'payload'
    require(not stage.exists(), 'Use an empty local staging directory')
    stage.mkdir(parents=True)
    artifacts = []
    for spec in plan['artifacts']:
        info = reader.get(f"/actions/artifacts/{spec['id']}")
        require(not info['expired'] and info['name'] == spec['name'] and
                info['digest'] == 'sha256:' + spec['sha256'] and
                info['workflow_run']['id'] == plan['source_run_id'] and
                info['workflow_run']['head_sha'] == plan['source_sha'],
                'Pinned artifact metadata mismatch or expired artifact')
        archive = stage / 'archives' / f"{spec['name']}-{spec['id']}.zip"
        reader.download(f"/actions/artifacts/{spec['id']}/zip", archive)
        record = file_record(stage, archive)
        require(record['sha256'] == spec['sha256'] and record['bytes'] == info['size_in_bytes'],
                'Artifact ZIP SHA-256 or byte count mismatch')
        artifacts.append({**spec, 'bytes': record['bytes']})
        if spec['name'] == 'github-pages':
            count, size = extract_runtime(archive, stage / 'runtime')
            print(f'Staged every runtime file: {count} files, {size} bytes', flush=True)
    for name in plan['required_runtime_files']:
        require((stage / 'runtime' / safe_path(name)).is_file(), f'Required runtime file missing: {name}')
    require(any((stage / 'runtime/details').rglob('*.json')), 'Account details are missing')
    require(any((stage / 'runtime/firm-details').rglob('*.json')), 'Firm details are missing')
    snapshots = [snapshot(reader, spec, stage, work) for spec in plan['snapshots']]
    provenance = {'source_plan': plan, 'snapshots': snapshots, 'artifacts': artifacts,
                  'source_run_attempt': run['run_attempt'], 'staged_at': utc_now(),
                  'meaning': 'Byte-preserving snapshot. Copying does not refresh source observation dates.',
                  'scope': 'All runtime data plus persisted history/caches and data/config/schema support. '
                           'No live Neon database, browser-local state, or regenerated/unpublished source data.'}
    json_file(stage / 'provenance.json', provenance)
    records = [file_record(stage, file) for file in sorted(stage.rglob('*')) if file.is_file()]
    require(len(records) <= MAX_FILES and sum(row['bytes'] for row in records) <= MAX_BYTES,
            'Staged payload exceeds the bounded migration limit')
    manifest = {'schema_version': 1, 'repository': REPO, 'source_run_id': plan['source_run_id'],
                'source_sha': plan['source_sha'], 'records': records, 'snapshots': snapshots}
    json_file(work / 'report' / 'manifest.json', manifest)
    print(json.dumps({'staged_files': len(records), 'staged_bytes': sum(r['bytes'] for r in records),
                      'snapshots': snapshots}), flush=True)


def destination_from_env() -> tuple[str, str, str, str]:
    values = tuple(os.environ.get(name, '') for name in
                   ('AZURE_STORAGE_ACCOUNT', 'AZURE_STORAGE_CONTAINER', 'AZURE_STORAGE_PREFIX'))
    require(values == DESTINATION, 'Destination must remain pharm3r/data/towersignal-data')
    require(bool(os.environ.get('AZURE_STORAGE_KEY')), 'Missing AZURE_STORAGE_KEY')
    run = os.environ.get('GITHUB_RUN_ID', '')
    attempt = os.environ.get('GITHUB_RUN_ATTEMPT', '')
    require(run.isdigit() and attempt.isdigit(), 'Missing numeric migration run identity')
    return (*values, f'{values[2]}/migrations/github-{run}-{attempt}')


def verify_readback(blob, record: dict) -> None:
    sha = hashlib.sha256()
    count = 0
    for block in blob.download_blob(max_concurrency=1).chunks():
        count += len(block)
        sha.update(block)
    require(count == record['bytes'] and sha.hexdigest() == record['sha256'],
            f"Blob readback mismatch: {record['path']}")


def transfer_one(blob, source: Path, record: dict) -> None:
    from azure.core.exceptions import ResourceExistsError
    from azure.storage.blob import ContentSettings
    suffix = source.suffix.lower()
    content_type = {'.json': 'application/json', '.gz': 'application/gzip', '.zip': 'application/zip',
                    '.csv': 'text/csv', '.sql': 'text/plain', '.md': 'text/markdown'}.get(suffix, 'application/octet-stream')
    with source.open('rb') as stream:
        try:
            blob.upload_blob(stream, length=record['bytes'], overwrite=False, max_concurrency=1,
                             metadata={'sha256': record['sha256']},
                             content_settings=ContentSettings(content_type=content_type,
                                                              cache_control='private, max-age=0'))
        except ResourceExistsError:
            # Ambiguous transport success/retry is safe only if all existing bytes match.
            pass
    verify_readback(blob, record)


def verify_inventory(container, prefix: str, records: list[dict]) -> None:
    expected = {prefix + '/' + row['path']: row['bytes'] for row in records}
    actual = {blob.name: blob.size for blob in container.list_blobs(name_starts_with=prefix + '/')}
    require(actual == expected, 'Destination inventory does not match all source names and byte counts')


def upload_data(work: Path) -> None:
    from azure.storage.blob import BlobServiceClient
    logging.getLogger('azure').setLevel(logging.ERROR)
    account, container_name, _, prefix = destination_from_env()
    stage = work / 'payload'
    manifest_path = work / 'report' / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    require(manifest['repository'] == REPO, 'Invalid staged repository')
    records = manifest['records']
    require(len(records) == len({r['path'] for r in records}), 'Duplicate manifest destinations')
    for row in records:
        require(row['path'] == safe_path(row['path']) and
                (stage / row['path']).resolve().is_relative_to(stage.resolve()), 'Unsafe staged path')
        require(file_record(stage, stage / row['path']) == row, 'Staged source changed before upload')
    local = threading.local()
    clients = []
    lock = threading.Lock()

    def container():
        if not hasattr(local, 'service'):
            local.service = BlobServiceClient(
                account_url=f'https://{account}.blob.core.windows.net',
                credential=os.environ['AZURE_STORAGE_KEY'], retry_total=3,
                connection_timeout=15, read_timeout=120,
                max_block_size=8 * 1024**2, max_single_put_size=32 * 1024**2,
                max_single_get_size=8 * 1024**2, max_chunk_get_size=CHUNK)
            with lock:
                clients.append(local.service)
        return local.service.get_container_client(container_name)

    def transfer(row):
        blob = container().get_blob_client(prefix + '/' + row['path'])
        try:
            transfer_one(blob, stage / row['path'], row)
        except Exception as error:
            # No exception repr: SDK messages may include credential-bearing transport details.
            raise MigrationError(f"Transfer failed for {row['path']} ({type(error).__name__})") from None
        return row

    totals = defaultdict(lambda: {'files': 0, 'bytes': 0})
    done_bytes = 0
    try:
        with ThreadPoolExecutor(max_workers=12) as pool:
            futures = [pool.submit(transfer, row) for row in sorted(records, key=lambda r: -r['bytes'])]
            try:
                for done, future in enumerate(as_completed(futures), 1):
                    row = future.result()
                    group = row['path'].split('/')[0]
                    if group == 'support':
                        group += '/' + row['path'].split('/')[1]
                    totals[group]['files'] += 1
                    totals[group]['bytes'] += row['bytes']
                    done_bytes += row['bytes']
                    if done % 1000 == 0 or done == len(records):
                        print(f'Uploaded and SHA-256 readback verified {done}/{len(records)} files; {done_bytes} bytes', flush=True)
            except Exception:
                for future in futures:
                    future.cancel()
                raise
        verify_inventory(container(), prefix, records)
        manifest_record = file_record(work / 'report', manifest_path)
        manifest_record['path'] = '_migration/manifest.json'
        transfer_one(container().get_blob_client(prefix + '/' + manifest_record['path']),
                     manifest_path, manifest_record)
        receipt = {'schema_version': 1, 'status': 'COMPLETE', 'completed_at': utc_now(),
                   'source_run_id': manifest['source_run_id'], 'source_sha': manifest['source_sha'],
                   'migration_run_id': os.environ['GITHUB_RUN_ID'],
                   'migration_code_sha': os.environ.get('GITHUB_SHA'),
                   'account': account, 'container': container_name, 'prefix': prefix,
                   'verified_payload_files': len(records), 'verified_payload_bytes': done_bytes,
                   'groups': dict(totals), 'snapshot_status': manifest['snapshots'],
                   'all_payload_sha256_readbacks_passed': True, 'exact_inventory_passed': True,
                   'manifest_sha256': manifest_record['sha256'],
                   'github_sources_deleted': False, 'application_changed': False,
                   'storage_access_policy_changed': False, 'history_branch_written': False}
        complete_path = work / 'report' / 'complete.json'
        json_file(complete_path, receipt)
        complete_record = file_record(work / 'report', complete_path)
        complete_record['path'] = '_migration/complete.json'
        transfer_one(container().get_blob_client(prefix + '/' + complete_record['path']),
                     complete_path, complete_record)
        verify_inventory(container(), prefix, records + [manifest_record, complete_record])
        receipt['total_blob_files_including_receipts'] = len(records) + 2
        json_file(work / 'report' / 'result.json', receipt)
        print('MIGRATION_RESULT=' + json.dumps(receipt, sort_keys=True), flush=True)
        if summary := os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(summary, 'a') as output:
                output.write('# TowerSignal private data copy: COMPLETE\n\n')
                output.write(f"Destination: `{account}/{container_name}/{prefix}/`\n\n")
                output.write(f'All **{len(records):,}** payload files (**{done_bytes:,} bytes**) were downloaded again and SHA-256 verified.\n\n')
                output.write('Source names/counts/sizes and the uploaded manifest/complete receipts were verified. No GitHub data was deleted; app and storage policies were not changed.\n')
    finally:
        for client in clients:
            client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['stage', 'upload'])
    parser.add_argument('--plan', type=Path, default=Path('config/azure-data-copy-20260911.json'))
    parser.add_argument('--work', type=Path, default=Path('.blob-migration'))
    args = parser.parse_args()
    try:
        if args.mode == 'stage':
            stage_data(args.plan, args.work)
        else:
            upload_data(args.work)
    except Exception as error:
        # Log only our bounded diagnostics; never SDK/HTTP exception URLs or keys.
        reason = str(error) if isinstance(error, MigrationError) else type(error).__name__
        json_file(args.work / 'report' / 'failure.json', {'status': 'FAILED', 'mode': args.mode,
                                                       'reason': reason, 'at': utc_now(),
                                                       'live_data_or_application_switched': False})
        print('::error::Data copy failed: ' + reason, file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
