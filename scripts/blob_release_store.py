"""Private, create-only Blob datasets and one conditional runtime/history pointer.

No method changes access policies, deletes data, or writes the migration snapshot.
The Azure SDK is imported only by the live adapter; offline tests need no SDK.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import threading

ROOT = 'towersignal-data'
POINTER = ROOT + '/pointers/production-current.json'
MAX_FILES = 100_000
MAX_BYTES = 12 * 1024**3
CHUNK = 4 * 1024**2


class PublishError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise PublishError(message)


def safe_path(value):
    require(isinstance(value, str) and value and '\\' not in value and
            not any(ord(c) < 32 for c in value) and ':' not in value,
            'Invalid data path')
    require(all(p not in ('', '.', '..') for p in value.split('/')) and
            not value.startswith('/'), 'Unsafe data path component')
    return value


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def record_bytes(path, data):
    return {'path': safe_path(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def hash_file(path):
    size = path.stat().st_size
    sha = hashlib.sha256()
    git = hashlib.sha1(f'blob {size}\0'.encode())
    count = 0
    with path.open('rb') as f:
        while data := f.read(CHUNK):
            count += len(data)
            sha.update(data)
            git.update(data)
    require(count == size, 'Local file changed while hashing')
    return size, sha.hexdigest(), git.hexdigest()


def local_records(root):
    require(root.is_dir() and not root.is_symlink(), 'Dataset root is missing or unsafe')
    result = []
    for path in sorted(root.rglob('*')):
        require(not path.is_symlink(), 'Symlink in dataset')
        if path.is_dir():
            continue
        require(path.is_file(), 'Non-regular data file')
        size, sha, git = hash_file(path)
        result.append({'path': safe_path(path.relative_to(root).as_posix()),
                       'bytes': size, 'sha256': sha, 'git_blob_sha': git})
    validate_records(result)
    return result


def validate_records(records):
    require(isinstance(records, list) and 0 < len(records) <= MAX_FILES, 'Invalid file count')
    names = set()
    total = 0
    for r in records:
        name = safe_path(r['path'])
        require(name not in names and type(r['bytes']) is int and r['bytes'] >= 0 and
                re.fullmatch(r'[0-9a-f]{64}', r['sha256']), 'Invalid or duplicate file record')
        names.add(name)
        total += r['bytes']
    require(total <= MAX_BYTES, 'Dataset exceeds transfer bound')
    return records


def compare_inventory(rows, records, prefix):
    """Only manifest-derived, positively marked, zero-length folders may be excluded."""
    validate_records(records)
    expected = {prefix + '/' + r['path']: r['bytes'] for r in records}
    parents = {str(p) for name in expected for p in PurePosixPath(name).parents
               if str(p).startswith(prefix + '/')}
    actual = {}
    folders = []
    for row in rows:
        name = row['name']
        require(name.startswith(prefix + '/') and name not in actual, 'Unsafe/duplicate Blob listing')
        require(type(row['bytes']) is int and row['bytes'] >= 0, 'Invalid listed byte count')
        marked = str((row.get('metadata') or {}).get('hdi_isfolder', '')).lower() == 'true'
        if marked:
            require(name.rstrip('/') in parents and row['bytes'] == 0 and name not in expected,
                    'Unexpected or nonempty directory object')
            folders.append(name)
        actual[name] = row
    folder_set = set(folders)
    files = {n: r['bytes'] for n, r in actual.items() if n not in folder_set}
    require(files == expected, 'Blob file inventory differs from manifest')
    return {name: actual[name]['etag'] for name in expected}, folders


def verify_one(store, name, record, etag=None):
    sha = hashlib.sha256()
    git = hashlib.sha1(f"blob {record['bytes']}\0".encode())
    count = 0
    for block in store.chunks(name, etag):
        count += len(block)
        require(count <= record['bytes'], 'Blob readback exceeds source size')
        sha.update(block)
        git.update(block)
    require(count == record['bytes'] and sha.hexdigest() == record['sha256'],
            f"SHA-256 readback mismatch: {record['path']}")
    if record.get('git_blob_sha'):
        require(git.hexdigest() == record['git_blob_sha'], 'Git/Blob history bytes differ')


def verify_dataset(store, prefix, records):
    before, folders = compare_inventory(store.list(prefix), records, prefix)
    for name in folders:
        prop = store.head(name)
        require(prop['bytes'] == 0 and str(prop['metadata'].get('hdi_isfolder', '')).lower() == 'true',
                'Folder identity not confirmed')
    def check(r):
        name = prefix + '/' + r['path']
        verify_one(store, name, r, before[name])
    with ThreadPoolExecutor(max_workers=12) as pool:
        for count, _ in enumerate(pool.map(check, sorted(records, key=lambda r: -r['bytes'])), 1):
            if count % 2000 == 0 or count == len(records):
                print(f'Verified {count}/{len(records)} dataset files', flush=True)
    after, _ = compare_inventory(store.list(prefix), records, prefix)
    require(before == after, 'Payload ETags changed during verification')
    return {'files': len(records), 'bytes': sum(r['bytes'] for r in records),
            'sha256_readback': True, 'exact_inventory': True, 'unchanged_etags': True}


def immutable_json(store, name, value):
    data = encoded(value)
    store.create(name, io.BytesIO(data), len(data), 'application/json')
    verify_one(store, name, record_bytes(name, data))
    return {'blob': name, 'sha256': hashlib.sha256(data).hexdigest()}


def publish_dataset(store, local_root, prefix, records, metadata_prefix, kind, source):
    """local_root=None adopts an already copied dataset without rewriting its objects."""
    validate_records(records)
    if local_root is not None:
        require(local_records(local_root) == records, 'Local dataset changed after staging')
        def upload(r):
            with (local_root / r['path']).open('rb') as f:
                store.create(prefix + '/' + r['path'], f, r['bytes'],
                             'application/json' if r['path'].endswith('.json') else 'application/octet-stream')
        with ThreadPoolExecutor(max_workers=12) as pool:
            list(pool.map(upload, records))
    result = verify_dataset(store, prefix, records)
    manifest = {'schema_version': 1, 'kind': kind, 'data_prefix': prefix,
                'source': source, 'records': records}
    manifest_ref = immutable_json(store, metadata_prefix + '/manifest.json', manifest)
    receipt = {'schema_version': 1, 'status': 'COMPLETE', 'kind': kind,
               'data_prefix': prefix, 'source': source, 'manifest': manifest_ref, **result}
    complete_ref = immutable_json(store, metadata_prefix + '/complete.json', receipt)
    return {'data_prefix': prefix, 'manifest': manifest_ref, 'complete': complete_ref,
            'files': result['files'], 'bytes': result['bytes']}


def checked_json(store, ref, limit=24 * 1024**2):
    data, etag = store.read(ref['blob'], limit)
    require(hashlib.sha256(data).hexdigest() == ref['sha256'], 'Published JSON checksum mismatch')
    return json.loads(data), etag


def validate_descriptor(store, descriptor, kind, source):
    manifest, _ = checked_json(store, descriptor['manifest'])
    complete, _ = checked_json(store, descriptor['complete'])
    require(manifest['kind'] == kind and manifest['source'] == source and
            manifest['data_prefix'] == descriptor['data_prefix'] and
            complete['manifest'] == descriptor['manifest'] and complete['source'] == source and
            complete['kind'] == kind and complete['data_prefix'] == descriptor['data_prefix'] and
            complete['status'] == 'COMPLETE' and
            all(complete.get(k) is True for k in ('sha256_readback', 'exact_inventory', 'unchanged_etags')),
            'Dataset completion proof is inconsistent')
    validate_records(manifest['records'])
    require(descriptor['files'] == complete['files'] == len(manifest['records']) and
            descriptor['bytes'] == complete['bytes'] == sum(r['bytes'] for r in manifest['records']),
            'Completion counts do not match manifest')


def current_pointer(store):
    try:
        data, etag = store.read(POINTER, 128 * 1024)
    except FileNotFoundError:
        return None, None, None
    value = json.loads(data)
    require(value.get('schema_version') == 1 and value.get('domain') == 'TOWERSIGNAL_BLOB_RELEASE' and
            type(value.get('source', {}).get('run_number')) is int and
            value['source'].get('workflow_id') == 339705737,
            'Existing current pointer is not a recognized Pages release')
    return value, etag, data


def promote(store, source, runtime, history, *, bootstrap=False):
    """One ETag-guarded JSON change selects BOTH runtime and matching durable history."""
    for kind, desc in [('runtime', runtime), ('history', history)]:
        validate_descriptor(store, desc, kind, source)
    candidate = {'schema_version': 1, 'domain': 'TOWERSIGNAL_BLOB_RELEASE',
                 'source': source, 'runtime': runtime, 'history': history}
    old, etag, previous = current_pointer(store)
    if old:
        if all(old.get(k) == v for k, v in candidate.items()):
            return {'status': 'ALREADY_CURRENT', 'current': old, 'etag': etag}
        require(not bootstrap, 'Bootstrap cannot replace an existing current pointer')
        require(source['workflow_id'] == old['source']['workflow_id'] and
                source['run_number'] > old['source']['run_number'],
                'Refusing an older or conflicting same-run publication')
    # These stable selectors cannot drift independently into mixed release states.
    for kind in ('runtime', 'history'):
        immutable_json(store, f'{ROOT}/pointers/{kind}-current.json',
                       {'schema_version': 1, 'resolve_via': POINTER, 'select': kind})
    if previous is not None:
        backup = f"{ROOT}/releases/pages-{source['run_id']}/_publication/previous-current.json"
        store.create(backup, io.BytesIO(previous), len(previous), 'application/json')
        verify_one(store, backup, record_bytes(backup, previous))
        candidate['previous'] = {'blob': backup, 'sha256': hashlib.sha256(previous).hexdigest()}
    else:
        candidate['previous'] = None
    data = encoded(candidate)
    store.cas(POINTER, data, etag)
    current, new_etag = store.read(POINTER, 128 * 1024)
    require(current == data, 'Current pointer readback differs after conditional publish')
    return {'status': 'CURRENT', 'current': candidate, 'etag': new_etag}


class AzureStore:
    """Account-key access stays on the runner. Writes are path-allowlisted."""
    def __init__(self):
        values = tuple(os.environ.get(k, '') for k in
                       ('AZURE_STORAGE_ACCOUNT', 'AZURE_STORAGE_CONTAINER', 'AZURE_STORAGE_PREFIX'))
        require(values == ('pharm3r', 'data', ROOT), 'Unapproved Azure destination')
        require(bool(os.environ.get('AZURE_STORAGE_KEY')), 'Missing AZURE_STORAGE_KEY')
        self.key = os.environ['AZURE_STORAGE_KEY']
        self.local = threading.local()
        self.clients = []
        self.lock = threading.Lock()

    def _container(self):
        if not hasattr(self.local, 'client'):
            from azure.storage.blob import BlobServiceClient
            client = BlobServiceClient('https://pharm3r.blob.core.windows.net', credential=self.key,
                                       retry_total=3, connection_timeout=15, read_timeout=120,
                                       max_single_get_size=8 * 1024**2, max_chunk_get_size=CHUNK)
            self.local.client = client
            with self.lock:
                self.clients.append(client)
        return self.local.client.get_container_client('data')

    def _blob(self, name):
        require(safe_path(name).startswith(ROOT + '/'), 'Read outside TowerSignal prefix')
        return self._container().get_blob_client(name)

    @staticmethod
    def allow_write(name):
        safe_path(name)
        require(re.fullmatch(r'towersignal-data/(?:releases|state/history)/pages-[0-9]+/.+', name) or
                name in (POINTER, ROOT + '/pointers/runtime-current.json', ROOT + '/pointers/history-current.json'),
                'Write outside approved publication paths')

    @staticmethod
    def _props(prop):
        return {'name': prop.name, 'bytes': prop.size, 'etag': str(prop.etag),
                'metadata': dict(prop.metadata or {})}

    def head(self, name):
        return self._props(self._blob(name).get_blob_properties())

    def list(self, prefix):
        require(safe_path(prefix).startswith(ROOT + '/'), 'Listing outside TowerSignal prefix')
        rows = []
        for item in self._container().list_blobs(name_starts_with=prefix + '/', include=['metadata']):
            rows.append(self._props(item))
            require(len(rows) <= MAX_FILES * 3, 'Blob inventory exceeded bound')
        return rows

    def chunks(self, name, etag=None):
        from azure.core import MatchConditions
        options = {'etag': etag, 'match_condition': MatchConditions.IfNotModified} if etag else {}
        yield from self._blob(name).download_blob(max_concurrency=1, **options).chunks()

    def read(self, name, limit):
        from azure.core.exceptions import ResourceNotFoundError
        try:
            prop = self.head(name)
            require(prop['bytes'] <= limit and
                    str(prop['metadata'].get('hdi_isfolder', '')).lower() != 'true',
                    'JSON object is too large or is a directory')
            data = bytearray()
            for chunk in self.chunks(name, prop['etag']):
                data.extend(chunk)
                require(len(data) <= limit, 'JSON response exceeds bound')
            return bytes(data), prop['etag']
        except ResourceNotFoundError:
            raise FileNotFoundError(name) from None

    def create(self, name, stream, size, content_type):
        from azure.core.exceptions import ResourceExistsError
        from azure.storage.blob import ContentSettings
        self.allow_write(name)
        try:
            self._blob(name).upload_blob(stream, length=size, overwrite=False, max_concurrency=1,
                                         content_settings=ContentSettings(content_type=content_type,
                                                                         cache_control='private, no-cache'))
        except ResourceExistsError:
            pass  # Caller MUST verify every byte; an existing object is never overwritten.

    def cas(self, name, data, etag):
        from azure.core import MatchConditions
        from azure.storage.blob import ContentSettings
        require(name == POINTER, 'Only the production pointer supports updates')
        kwargs = {'etag': etag, 'match_condition': MatchConditions.IfNotModified} if etag else {}
        self._blob(name).upload_blob(data, length=len(data), overwrite=etag is not None,
                                     content_settings=ContentSettings(content_type='application/json',
                                                                     cache_control='private, no-store'), **kwargs)

    def close(self):
        for client in self.clients:
            client.close()
