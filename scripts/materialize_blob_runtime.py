"""Materialize the current verified TowerSignal runtime from private Azure Blob.

This is a read-only consumer of the production-current release pointer. It validates
pointer/manifest/completion provenance, downloads every runtime file, and verifies
size + SHA-256 before the UI-only Pages release is allowed to use the data.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil

from blob_release_store import (
    AzureStore,
    POINTER,
    checked_json,
    current_pointer,
    local_records,
    require,
    validate_descriptor,
    validate_records,
)

REQUIRED = (
    'systems.json',
    'changes.json',
    'nys-systems.json',
    'nys-changes.json',
    'source-health.json',
)


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
    pointer, pointer_etag, _ = current_pointer(store)
    require(pointer is not None, f'No verified runtime pointer exists at {POINTER}')
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
