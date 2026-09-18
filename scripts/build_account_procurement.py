"""Build bounded, source-preserving Account procurement slices from existing caches.

No external collection or fuzzy matching. Input records and runtime history are
never modified. Missing sources remain explicit; output is deterministic for the
same input bytes. All pages are <=256 KiB and contain <=20 complete source rows.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile

SOURCES = (
    ('procurement-city-record.json', 'notices', 'City Record'),
    ('procurement-checkbook.json', 'contracts', 'Checkbook NYC'),
    ('procurement-nys-authorities.json', 'contracts', 'NYS authorities'),
    ('procurement-openbook-water.json', 'contracts', 'Open Book NY'),
    ('procurement-nycha-water.json', 'records', 'NYCHA'),
)
PAGE_BYTES = 256 * 1024
MANIFEST_BYTES = 64 * 1024
DOMAIN = 'TOWERSIGNAL_ACCOUNT_PROCUREMENT'
ID = re.compile(r'[A-Za-z0-9_-]{1,64}')


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def source_state(root, filename, collection, label, as_of):
    state = {'file': filename, 'name': label, 'status': 'UNAVAILABLE',
             'generated_at': None, 'sha256': None, 'record_count': None,
             'source_health': None, 'reason': 'Source payload unavailable'}
    try:
        raw = (root / filename).read_bytes()
    except FileNotFoundError:
        return state, []
    state['sha256'] = hashlib.sha256(raw).hexdigest()
    try:
        payload = json.loads(raw)
        rows = payload[collection]
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise ValueError('Expected normalized record array')
        state.update(status='LOADED', generated_at=payload.get('generated_at'),
                     record_count=len(rows), source_health=payload.get('source_health'), reason=None)
        health = payload.get('source_health')
        entries = health if isinstance(health, list) else list(health.values()) if isinstance(health, dict) and 'status' not in health else [health]
        incomplete = [entry for entry in entries if isinstance(entry, dict) and (
            entry.get('pagination_complete') is False or entry.get('schema_valid') is False
            or re.search(r'fail|error|unavailable|blocked|incomplete', str(entry.get('status', '')), re.I))]
        if incomplete:
            state.update(status='INCOMPLETE', reason='Publisher/source-health checks report incomplete coverage')
        observed = timestamp(state['generated_at'])
        if observed is None:
            state.update(status='UNVERIFIED', reason='Source generation time unavailable')
        elif (as_of - observed).total_seconds() > 7 * 86400:
            state.update(status='STALE', reason='Retained source generation is more than seven days before this snapshot')
        return state, rows
    except (ValueError, KeyError, TypeError):
        state.update(status='MALFORMED', reason='Source payload is not a valid normalized collection', record_count=None)
        return state, []


def build(output: Path):
    systems = json.loads((output / 'systems.json').read_bytes())
    ids = [row['system_id'] for row in systems['systems']]
    if len(ids) != len(set(ids)) or not ids or any(not isinstance(sid, str) or not ID.fullmatch(sid) for sid in ids):
        raise ValueError('Invalid or duplicate registry system IDs')
    generated_at = systems['metadata']['generated_at']
    as_of = timestamp(generated_at)
    if as_of is None:
        raise ValueError('Missing registry generation timestamp')
    accounts = {sid: {} for sid in ids}
    states = []
    for filename, collection, label in SOURCES:
        state, rows = source_state(output, filename, collection, label, as_of)
        states.append(state)
        for record in rows:
            links = record.get('tower_account_system_ids')
            if record.get('tower_link_confidence') not in ('CONFIRMED', 'STRONG') or not isinstance(links, list):
                continue
            key = record.get('procurement_id') or f"{record.get('source')}:{record.get('source_record_id')}"
            for sid in links:
                if isinstance(sid, str) and sid in accounts and key not in accounts[sid]:
                    accounts[sid][key] = record
    destination = output / 'account-procurement'
    # Staging outside the runtime tree avoids publishing partial/unvalidated files.
    stage = Path(tempfile.mkdtemp(prefix='.account-procurement-', dir=output.parent))
    total_records = total_pages = maximum = 0
    try:
        for sid in sorted(ids):
            relative = Path(sid[:2].lower()) / sid
            folder = stage / relative
            folder.mkdir(parents=True)
            detail = json.loads((output / 'details' / sid[:2].lower() / f'{sid}.json').read_bytes())
            if detail['identity']['system_id'] != sid:
                raise ValueError('Detail identity differs from registry')
            detail_generation = detail['metadata']['generated_at']
            if timestamp(detail_generation) is None:
                raise ValueError('Missing detail generation timestamp')
            def sort_key(record):
                date = next((record.get(k) for k in ('due_date', 'award_date', 'start_date', 'notice_start_date') if record.get(k) is not None), '')
                return str(date)
            rows = sorted(accounts[sid].values(), key=lambda record: str(record.get('procurement_id', '')))
            rows.sort(key=sort_key, reverse=True)
            pages = []
            def page_body(records):
                return encoded({'domain': DOMAIN + '_PAGE', 'schema_version': 1, 'system_id': sid,
                                'generated_at': detail_generation, 'records': records})
            def flush(records):
                nonlocal maximum, total_pages
                raw = page_body(records)
                if len(raw) > PAGE_BYTES:
                    raise ValueError(f'One complete procurement record exceeds page budget for {sid}')
                digest = hashlib.sha256(raw).hexdigest()
                name = f'{len(pages):04d}-{digest}.json'
                (folder / name).write_bytes(raw)
                pages.append({'path': f'account-procurement/{relative.as_posix()}/{name}',
                              'sha256': digest, 'bytes': len(raw), 'record_count': len(records)})
                maximum = max(maximum, len(raw)); total_pages += 1
            batch = []
            for record in rows:
                if batch and (len(batch) == 20 or len(page_body(batch + [record])) > PAGE_BYTES):
                    flush(batch); batch = []
                batch.append(record)
            if batch:
                flush(batch)
            manifest = {'domain': DOMAIN, 'schema_version': 1, 'system_id': sid,
                        'generated_at': detail_generation, 'record_count': len(rows),
                        'sources': states, 'pages': pages}
            raw = encoded(manifest)
            if len(raw) > MANIFEST_BYTES:
                raise ValueError(f'Account manifest exceeds budget for {sid}')
            (folder / 'index.json').write_bytes(raw)
            maximum = max(maximum, len(raw)); total_records += len(rows)
        # Successful staging validates completeness before replacing the old projection.
        if destination.exists():
            shutil.rmtree(destination)
        stage.rename(destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    report = {'accounts': len(ids), 'linked_account_records': total_records,
              'pages': total_pages, 'largest_response_bytes': maximum,
              'source_states': [{k: s[k] for k in ('name', 'status', 'record_count')} for s in states]}
    print(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('public/data'))
    build(parser.parse_args().output)
