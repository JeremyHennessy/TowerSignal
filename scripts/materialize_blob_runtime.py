"""Materialize the current verified TowerSignal runtime from private Azure Blob.

This is a read-only consumer of the production-current release pointer. It validates
pointer/manifest/completion provenance, downloads every runtime file, and verifies
size + SHA-256 before the UI-only Pages release is allowed to use the data.

The canonical pointer may be promoted either by the verified Pages publisher or by
the independent verified data-only refresh workflow. The stricter Pages writer guard
in blob_release_store deliberately remains unchanged; this reader recognizes only
these two explicit source contracts.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import shutil

from blob_release_store import (
    AzureStore,
    POINTER,
    checked_json,
    local_records,
    require,
    validate_descriptor,
    validate_records,
)

RELEASE_DOMAIN = 'TOWERSIGNAL_BLOB_RELEASE'
PAGES_WORKFLOW_ID = 339705737
DATA_WORKFLOW_ID = 355813764
DATA_WORKFLOW_PATH = '.github/workflows/azure-data-refresh.yml'
DATA_KIND = 'data-only'
PAGES_CONTRACT = 'pages-release-v1'
DATA_CONTRACT = 'data-refresh-v1'

REQUIRED = (
    'systems.json',
    'changes.json',
    'nys-systems.json',
    'nys-changes.json',
    'source-health.json',
)


def trusted_source_contract(source: object) -> str:
    require(isinstance(source, dict), 'Production pointer source is not an object')
    require(type(source.get('run_id')) is int and source['run_id'] > 0 and
            type(source.get('run_number')) is int and source['run_number'] > 0 and
            isinstance(source.get('created_at'), str) and source['created_at'] and
            re.fullmatch(r'[0-9a-f]{40}', str(source.get('source_sha', ''))),
            'Production pointer source identity is incomplete')

    if source.get('kind') is None and source.get('workflow_id') == PAGES_WORKFLOW_ID:
        return PAGES_CONTRACT

    if (source.get('kind') == DATA_KIND and
            source.get('workflow_id') == DATA_WORKFLOW_ID and
            source.get('workflow_path') == DATA_WORKFLOW_PATH and
            type(source.get('run_attempt')) is int and source['run_attempt'] > 0):
        return DATA_CONTRACT

    raise RuntimeError('unreachable') if False else require(False, 'Production pointer source is not trusted')


def read_runtime_pointer(store) -> tuple[dict, str, str]:
    raw, etag = store.read(POINTER, 128 * 1024)
    try:
        pointer = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError('Production pointer is not valid JSON') from exc
    require(isinstance(pointer, dict) and pointer.get('schema_version') == 1 and
            pointer.get('domain') == RELEASE_DOMAIN,
            'Production pointer domain/schema is not recognized')
    contract = trusted_source_contract(pointer.get('source'))
    runtime = pointer.get('runtime')
    require(isinstance(runtime, dict), 'Production pointer has no runtime descriptor')

    source = pointer['source']
    prefix = runtime.get('data_prefix', '')
    if contract == DATA_CONTRACT:
        expected = f"towersignal-data/releases/data-{source['run_id']}-{source['run_attempt']}/runtime"
        require(prefix == expected, 'Data-refresh runtime prefix does not match source identity')
    else:
        require(isinstance(prefix, str) and prefix.startswith('towersignal-data/releases/pages-'),
                'Pages runtime prefix is outside the trusted release namespace')

    return pointer, etag, contract


def _download_one(store, prefix: str, record: dict, output: Path) -> None:
    target = output / record['path']
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + '.part')
    require(not temp.exists(), f'Stale partial download exists: {record["path"]}')
    digest = hashlib.sha256()
    count = 0
    try:
        with temp.open('xb') as handle:
            for chunk in store.chunks(prefix + '/' + record['path']):
                count += len(chunk)
                require(count <= record['bytes'], f'Blob exceeds manifest size: {record["path"]}')
                digest.update(chunk)
                handle.write(chunk)
        require(count == record['bytes'], f'Blob size mismatch: {record["path"]}')
        require(digest.hexdigest() == record['sha256'], f'Blob checksum mismatch: {record["path"]}')
        temp.replace(target)
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def materialize(store, output: Path) -> dict:
    pointer, pointer_etag, source_contract = read_runtime_pointer(store)
    source = pointer['source']
    runtime = pointer['runtime']
    validate_descriptor(store, runtime, 'runtime', source)
    manifest, _ = checked_json(store, runtime['manifest'])
    records = validate_records(manifest['records'])
    names = {record['path'] for record in records}
    require(set(REQUIRED) <= names, 'Verified runtime is missing required TowerSignal files')
    require(any(name.startswith('details/') for name in names), 'Verified runtime has no account details')
    require(any(name.startswith('firm-details/') for name in names), 'Verified runtime has no firm details')
    require(len(records) >= 100, f'Verified runtime inventory is unexpectedly small: {len(records)}')

    if output.exists():
        require(output.is_dir() and not output.is_symlink(), 'Output path is unsafe')
        shutil.rmtree(output)
    output.mkdir(parents=True)

    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(_download_one, store, runtime['data_prefix'], record, output)
                   for record in records]
        for index, future in enumerate(futures, 1):
            future.result()
            if index % 2000 == 0 or index == len(futures):
                print(f'Materialized {index}/{len(futures)} verified runtime files', flush=True)

    local = local_records(output)
    expected = {(row['path'], row['bytes'], row['sha256']) for row in records}
    actual = {(row['path'], row['bytes'], row['sha256']) for row in local}
    require(actual == expected, 'Materialized runtime inventory differs from published manifest')

    return {
        'schema_version': 1,
        'pointer_blob': POINTER,
        'pointer_etag': pointer_etag,
        'source_contract': source_contract,
        'source': source,
        'runtime': runtime,
        'runtime_manifest': runtime['manifest'],
        'runtime_files': len(records),
        'runtime_bytes': sum(row['bytes'] for row in records),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--proof', required=True, type=Path)
    args = parser.parse_args()
    store = AzureStore()
    try:
        proof = materialize(store, args.output)
    finally:
        store.close()
    args.proof.parent.mkdir(parents=True, exist_ok=True)
    args.proof.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(proof, indent=2, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
