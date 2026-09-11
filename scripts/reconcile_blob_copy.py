"""Inspect or finalize ONLY the existing, fully read-back-checked copy.

Inspection makes no Azure writes. Finalization never re-uploads/deletes payloads;
it requires all file identities, sizes and SHA-256 values to pass, and allows
only positively identified empty directory objects at manifest-derived parents.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import logging
import os
from pathlib import Path, PurePosixPath
import threading
import zipfile

from migrate_data_to_blob import (GitHubReader, MigrationError, REPO, CHUNK,
                                 require, safe_path, json_file, file_record,
                                 verify_readback, transfer_one, utc_now,
                                 destination_from_env)

COPY_RUN = 34593386563
COPY_SHA = 'e88e4c76030ccc4064c91209d5883244639c8823'
PREFIX = 'towersignal-data/migrations/github-34593386563-1'
REPORT_ID = 10261071229
REPORT_DIGEST = 'f029d07793832299426a8e0641a84cecb0ca2efe45cef4ab7181bfed06249c4d'
REPORT_BYTES = 1103908
SOURCE_RUN = 34544249376
SOURCE_SHA = '53f7016404774821051e5ebd02eeb5382dded55f'


def stage_manifest(work: Path) -> None:
    reader = GitHubReader()
    meta = reader.get(f'/actions/artifacts/{REPORT_ID}')
    require(meta['name'] == 'azure-data-copy-34593386563-1' and not meta['expired'] and
            meta['digest'] == 'sha256:' + REPORT_DIGEST and
            meta['workflow_run']['id'] == COPY_RUN and
            meta['workflow_run']['head_sha'] == COPY_SHA,
            'Original copy report provenance mismatch')
    archive = work / 'copy-report.zip'
    reader.download(f'/actions/artifacts/{REPORT_ID}/zip', archive)
    record = file_record(work, archive)
    require(record['sha256'] == REPORT_DIGEST and record['bytes'] == REPORT_BYTES,
            'Original report archive checksum mismatch')
    with zipfile.ZipFile(archive) as package:
        require(set(package.namelist()) == {'manifest.json', 'failure.json'} and
                len(package.infolist()) == 2, 'Unexpected copy report archive')
        require(package.getinfo('manifest.json').file_size < 20 * 1024**2, 'Manifest is too large')
        manifest_bytes = package.read('manifest.json')
    # Preserve the original source manifest bytes, not a regenerated inventory.
    (work / 'report').mkdir(parents=True, exist_ok=True)
    (work / 'report/manifest.json').write_bytes(manifest_bytes)
    manifest = load_manifest(work)
    print(json.dumps({'manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
                      'source_payload_files': len(manifest['records']),
                      'source_payload_bytes': sum(r['bytes'] for r in manifest['records'])}))


def load_manifest(work: Path) -> dict:
    manifest = json.loads((work / 'report/manifest.json').read_text())
    require(manifest['repository'] == REPO and manifest['source_run_id'] == SOURCE_RUN and
            manifest['source_sha'] == SOURCE_SHA and len(manifest['records']) == 22015 and
            sum(r['bytes'] for r in manifest['records']) == 2465142728,
            'Original manifest does not match the approved copy')
    for row in manifest['records']:
        require(row['path'] == safe_path(row['path']) and row['bytes'] >= 0 and
                len(row['sha256']) == 64, 'Invalid manifest file')
    require(len({r['path'] for r in manifest['records']}) == len(manifest['records']),
            'Duplicate source manifest paths')
    return manifest


def compare_inventory(rows: list[dict], records: list[dict], prefix: str) -> dict:
    expected = {prefix + '/' + row['path']: row['bytes'] for row in records}
    parents = set()
    for name in expected:
        parents.update(str(p) for p in PurePosixPath(name).parents if str(p).startswith(prefix + '/'))
    actual = {}
    directory_names = []
    rejected = []
    for row in rows:
        name = row['name']
        require(name.startswith(prefix + '/') and name not in actual, 'Unsafe or duplicate listed object')
        actual[name] = row
        folder = str((row.get('metadata') or {}).get('hdi_isfolder', '')).lower() == 'true'
        if folder:
            # Never ignore an arbitrary zero-byte file or a directory outside expected parents.
            if name.rstrip('/') not in parents or row['bytes'] != 0 or name in expected:
                rejected.append(name)
            else:
                directory_names.append(name)
    directories = set(directory_names)
    missing = sorted(set(expected) - set(actual))
    extra_files = sorted(set(actual) - set(expected) - directories)
    wrong = [{'path': name, 'expected': size, 'actual': actual[name]['bytes'],
              'actual_type': type(actual[name]['bytes']).__name__}
             for name, size in expected.items() if name in actual and actual[name]['bytes'] != size]
    return {'expected_file_count': len(expected), 'listed_object_count': len(rows),
            'missing_files': missing, 'extra_files': extra_files, 'size_mismatches': wrong,
            'confirmed_parent_directories': sorted(directories),
            'invalid_directory_objects': sorted(rejected),
            'file_inventory_passed': not (missing or extra_files or wrong or rejected)}


def list_inventory(container) -> list[dict]:
    # SDK iterator follows every continuation token. Only this immutable prefix is listed.
    return [{'name': blob.name, 'bytes': blob.size, 'etag': str(blob.etag),
             'metadata': dict(blob.metadata or {}),
             'resource_type': getattr(blob, 'resource_type', None)}
            for blob in container.list_blobs(name_starts_with=PREFIX + '/', include=['metadata'])]


def inspect(container, records: list[dict], work: Path) -> tuple[dict, list[dict]]:
    rows = list_inventory(container)
    report = compare_inventory(rows, records, PREFIX)
    json_file(work / 'report/inventory-inspection.json', {'prefix': PREFIX, **report, 'objects': rows})
    details = {**report, 'extra_file_samples': [r for r in rows if r['name'] in report['extra_files']][:20],
               'directory_samples': [r for r in rows if r['name'] in report['confirmed_parent_directories']][:10]}
    print('INVENTORY_INSPECTION=' + json.dumps(details, sort_keys=True), flush=True)
    return report, rows


def reconcile(work: Path, mode: str) -> None:
    from azure.storage.blob import BlobServiceClient
    logging.getLogger('azure').setLevel(logging.ERROR)
    account, container_name, _, _ = destination_from_env()
    manifest = load_manifest(work)
    records = manifest['records']
    settings = dict(account_url=f'https://{account}.blob.core.windows.net',
                    credential=os.environ['AZURE_STORAGE_KEY'], retry_total=3,
                    connection_timeout=15, read_timeout=120,
                    max_single_get_size=8 * 1024**2, max_chunk_get_size=CHUNK)
    with BlobServiceClient(**settings) as client:
        container = client.get_container_client(container_name)
        report, before = inspect(container, records, work)
        if mode == 'inspect':
            return  # Read-only even when an inventory mismatch is present.
        require(report['file_inventory_passed'], 'Cannot finalize: file inventory differs from source')
        # Confirm every excluded directory via an independent authenticated properties read.
        for name in report['confirmed_parent_directories']:
            properties = container.get_blob_client(name).get_blob_properties()
            require(properties.size == 0 and
                    str((properties.metadata or {}).get('hdi_isfolder', '')).lower() == 'true',
                    'Directory identity was not confirmed by Blob properties')
        local = threading.local()
        clients = []
        lock = threading.Lock()
        def check(row):
            if not hasattr(local, 'client'):
                local.client = BlobServiceClient(**settings)
                with lock:
                    clients.append(local.client)
            blob = local.client.get_blob_client(container=container_name, blob=PREFIX + '/' + row['path'])
            try:
                verify_readback(blob, row)
            except Exception as error:
                raise MigrationError(f"Readback failed: {row['path']} ({type(error).__name__})") from None
        try:
            with ThreadPoolExecutor(max_workers=12) as pool:
                futures = [pool.submit(check, r) for r in sorted(records, key=lambda r: -r['bytes'])]
                for count, future in enumerate(as_completed(futures), 1):
                    future.result()
                    if count % 2000 == 0 or count == len(records):
                        print(f'Reconciled SHA-256 readback {count}/{len(records)}', flush=True)
        finally:
            for service in clients:
                service.close()
        after = list_inventory(container)
        after_report = compare_inventory(after, records, PREFIX)
        require(after_report['file_inventory_passed'], 'Inventory changed during final readback')
        names = {PREFIX + '/' + r['path'] for r in records}
        require({r['name']: r['etag'] for r in before if r['name'] in names} ==
                {r['name']: r['etag'] for r in after if r['name'] in names},
                'A payload ETag changed during final verification')
        totals = defaultdict(lambda: {'files': 0, 'bytes': 0})
        for row in records:
            group = row['path'].split('/')[0]
            if group == 'support': group += '/' + row['path'].split('/')[1]
            totals[group]['files'] += 1
            totals[group]['bytes'] += row['bytes']
        manifest_path = work / 'report/manifest.json'
        manifest_record = file_record(work / 'report', manifest_path)
        manifest_record['path'] = '_migration/manifest.json'
        transfer_one(container.get_blob_client(PREFIX + '/' + manifest_record['path']), manifest_path, manifest_record)
        receipt = {'schema_version': 1, 'status': 'COMPLETE', 'completed_at': utc_now(),
                   'account': account, 'container': container_name, 'prefix': PREFIX,
                   'original_copy_run_id': COPY_RUN, 'original_copy_sha': COPY_SHA,
                   'verification_run_id': os.environ['GITHUB_RUN_ID'],
                   'verification_code_sha': os.environ['GITHUB_SHA'],
                   'source_run_id': SOURCE_RUN, 'source_sha': SOURCE_SHA,
                   'verified_payload_files': len(records),
                   'verified_payload_bytes': sum(r['bytes'] for r in records),
                   'all_payload_sha256_readbacks_passed': True,
                   'exact_file_inventory_passed': True,
                   'confirmed_directory_objects_before_receipts': len(report['confirmed_parent_directories']),
                   'manifest_sha256': manifest_record['sha256'], 'groups': dict(totals),
                   'snapshot_status': manifest['snapshots'],
                   'payloads_reuploaded_or_deleted': False, 'github_sources_deleted': False,
                   'application_changed': False, 'history_branch_written': False,
                   'storage_access_policy_changed': False}
        complete_path = work / 'report/complete.json'
        json_file(complete_path, receipt)
        complete_record = file_record(work / 'report', complete_path)
        complete_record['path'] = '_migration/complete.json'
        transfer_one(container.get_blob_client(PREFIX + '/' + complete_record['path']), complete_path, complete_record)
        final_report = compare_inventory(list_inventory(container), records + [manifest_record, complete_record], PREFIX)
        require(final_report['file_inventory_passed'], 'Receipt inventory did not reconcile')
        receipt['total_file_objects_including_receipts'] = len(records) + 2
        receipt['total_directory_objects'] = len(final_report['confirmed_parent_directories'])
        json_file(work / 'report/result.json', receipt)
        print('MIGRATION_FINAL_RESULT=' + json.dumps(receipt, sort_keys=True), flush=True)
        if summary := os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(summary, 'a') as out:
                out.write('# Private TowerSignal data copy: COMPLETE\n\n')
                out.write(f"Destination: `{account}/{container_name}/{PREFIX}/`\n\n")
                out.write(f"All {len(records):,} payload files ({receipt['verified_payload_bytes']:,} bytes) passed SHA-256 readback. ")
                out.write('File inventory reconciles exactly; manifest-derived directory objects are identified separately. '
                          'The original GitHub sources, application and storage policies are unchanged.\n')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['stage', 'inspect', 'finalize'])
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.mode == 'stage': stage_manifest(args.work)
        else: reconcile(args.work, args.mode)
    except Exception as error:
        reason = str(error) if isinstance(error, MigrationError) else type(error).__name__
        json_file(args.work / 'report/reconcile-failure.json', {'status': 'FAILED', 'mode': args.mode, 'reason': reason})
        print('::error::Reconciliation stopped: ' + reason)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
