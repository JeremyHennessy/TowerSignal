"""Source-specific public-health evidence, joined to buildings, never inferred outbreak causation."""
from __future__ import annotations
import hashlib
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from .legionella_alerts import _fetch, _parse_html, _published_date

ROOT = 'https://www.nyc.gov/'
TOPIC = ROOT + 'site/doh/health/health-topics/legionnaires-disease.page'
BRONX = ROOT + 'site/doh/about/press/pr2026/nyc-health-department-orders-cooling-towers-to-be-cleaned-in-south-bronx.page'
CULTURE = ROOT + 'assets/doh/downloads/pdf/cd/cooling-tower-confirmatory-culture-results.pdf'
PCR = ROOT + 'assets/doh/downloads/pdf/cd/ues-cluster-2026-pcr-positive-cooling-towers.pdf'
CLOSURE = ROOT + 'site/doh/about/press/pr2026/health-department-declares-ues-legionnaires-exposure-has-ended.page'
SOURCES = (BRONX, CULTURE, PCR, CLOSURE, TOPIC)
BOUNDARY = ('An exact address resolves a building, not an individual system or outbreak source. '
            'PCR detects bacterial DNA; culture positivity does not establish outbreak causation. '
            'Area context and related episode updates are not positive-test findings.')

def address_key(value: str) -> str:
    text = re.sub(r'\([^)]*\)|\*', '', value.upper()).strip()
    text = text.replace('.', '').replace(',', ' ')
    words = {'STREET': 'ST', 'AVENUE': 'AVE', 'ROAD': 'RD', 'BOULEVARD': 'BLVD', 'PLACE': 'PL',
             'E': 'EAST', 'W': 'WEST', 'N': 'NORTH', 'S': 'SOUTH', 'VLG': 'VILLAGE',
             'FIRST': '1', 'SECOND': '2', 'THIRD': '3', 'FOURTH': '4', 'FIFTH': '5'}
    text = ' '.join(words.get(w, w) for w in text.split())
    return re.sub(r'\b(\d+)(ST|ND|RD|TH)\b', r'\1', text)

def pdf_rows(content: bytes, kind: str) -> tuple[str, list[dict[str, str]]]:
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'source.pdf'
        path.write_bytes(content)
        text = subprocess.run(['pdftotext', '-layout', str(path), '-'], check=True, capture_output=True, text=True, timeout=30).stdout
    dates = set(re.findall(r'\b(\d{1,2})\.(\d{1,2})\.(\d{2,4})\b', text))
    if len(dates) != 1:
        raise ValueError('PDF revision date is absent or ambiguous')
    month, day, year = next(iter(dates))
    revision = datetime(int(year) + (2000 if len(year) == 2 else 0), int(month), int(day)).date().isoformat()
    if not revision.startswith('2026-07-'):
        raise ValueError('Generic result document changed investigation period; requires source-specific review')
    headings = {'Culture Positive': 'CULTURE_POSITIVE', 'Culture Negative': 'CULTURE_NEGATIVE',
                'Test Results Pending': 'CULTURE_PENDING', 'Cleaning Complete': 'PCR_LIST_CLEANING_COMPLETE'}
    group = None
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if line in headings:
            group = headings[line]
        match = re.match(r'^[•●]\s+(\d.+)', line)
        if match:
            if group is None:
                raise ValueError('Address found outside a recognized result section')
            raw = match.group(1).strip()
            result = group
            if kind == 'pcr' and 'unregistered' in raw.lower():
                result = 'UNREGISTERED_BUILDING_LISTED'  # do not infer PCR positive from the document title
            rows.append({'address': re.sub(r'\([^)]*\)|\*', '', raw).strip(), 'source_row': raw,
                         'result': result, 'source_date': revision, 'date_basis': 'DOCUMENT_REVISION_DATE'})
    if not rows or len({address_key(r['address']) for r in rows}) != len(rows):
        raise ValueError('PDF has no address rows or duplicate/ambiguous building rows')
    return revision, rows

def bronx_rows(content: bytes) -> tuple[str, list[dict[str, str]]]:
    html = content.decode('utf-8')
    text = _parse_html(content).text
    published = _published_date(text)
    if not published or 'positive PCR results are located at' not in text:
        raise ValueError('Bronx named-tower section or publication date is missing')
    block = re.search(r'positive PCR results are located at.*?<ul[^>]*>(.*?)</ul>', html, re.I | re.S)
    if not block:
        raise ValueError('Bronx named-building list markup changed')
    rows = []
    for raw in re.findall(r'<li[^>]*>(.*?)</li>', block.group(1), re.I | re.S):
        address = unescape(re.sub(r'<[^>]+>', '', raw)).strip()
        if not re.match(r'^\d', address):
            raise ValueError('Unexpected named-building row')
        rows.append({'address': address, 'source_row': address, 'result': 'PCR_POSITIVE_REMEDIATION_ORDER',
                     'source_date': published, 'date_basis': 'PUBLICATION_DATE'})
    # This release explicitly dates the orders to the day preliminary testing completed.
    order = re.search(r'Preliminary PCR testing was completed by (\w+ \d+), and orders.*?same day', text, re.S)
    if order:
        day = datetime.strptime(order.group(1) + ' ' + published[:4], '%B %d %Y').date().isoformat()
        for row in rows:
            row.update(event_date=day, event_date_basis='PUBLISHED_ORDER_DATE')
    if not rows:
        raise ValueError('No Bronx building records extracted')
    return published, rows

def resolve_rows(records: list[dict[str, Any]], systems: list[dict[str, Any]], aliases: dict[str, list[str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    index: dict[tuple[str, str], set[str]] = {}
    by_bin: dict[str, list[dict[str, Any]]] = {}
    for row in systems:
        bin_value = str(row.get('bin') or '')
        if not re.fullmatch(r'\d{7}', bin_value):
            continue
        by_bin.setdefault(bin_value, []).append(row)
        for address in [row.get('address') or '', *aliases.get(bin_value, [])]:
            if address:
                index.setdefault((row.get('borough', ''), address_key(address)), set()).add(bin_value)
    linked, unresolved = [], []
    for record in records:
        bins = index.get((record['borough'], address_key(record['address'])), set())
        if len(bins) != 1:
            unresolved.append({**record, 'resolution': 'AMBIGUOUS_BUILDING' if bins else 'NO_EXACT_ADDRESS_MATCH', 'candidate_bins': sorted(bins)})
            continue
        bin_value = next(iter(bins))
        for system in by_bin[bin_value]:
            linked.append({**record, 'system_id': system['system_id'], 'system_address': system['address'],
                           'bin': bin_value, 'bbl': system.get('bbl'), 'match_basis': 'NORMALIZED_ADDRESS_BOROUGH_TO_UNIQUE_BIN',
                           'scope': 'BUILDING_LEVEL', 'outbreak_source_confirmed': False})
    return linked, unresolved

def collect_links(systems: list[dict[str, Any]], aliases: dict[str, list[str]], source_dir: Path | None = None, evidence_dir: Path | None = None) -> dict[str, Any]:
    documents = []
    raw_sources: dict[str, bytes] = {}
    records = []
    for url in SOURCES:
        if source_dir:
            data = (source_dir / url.rsplit('/', 1)[-1]).read_bytes()
        else:
            data, _ = _fetch(url)
        raw_sources[url] = data
        if evidence_dir:
            evidence_dir.mkdir(parents=True, exist_ok=True)
            (evidence_dir / url.rsplit("/",1)[-1]).write_bytes(data)
        title = _parse_html(data).title if not url.endswith('.pdf') else ('Cooling Tower Confirmatory Culture Results' if url == CULTURE else 'Upper East Side PCR-Positive Cooling Tower Systems')
        if url in (PCR, CULTURE):
            published, rows = pdf_rows(data, 'pcr' if url == PCR else 'culture')
        elif url == BRONX:
            published, rows = bronx_rows(data)
        else:
            published, rows = _published_date(_parse_html(data).text), []
        episode = 'NYC-BRONX-2026-09' if url == BRONX else 'NYC-UES-2026-07'
        for row in rows:
            records.append({**row, 'source_url': url, 'source_title': title, 'source_sha256': hashlib.sha256(data).hexdigest(),
                            'episode_id': episode, 'borough': 'Bronx' if url == BRONX else 'Manhattan'})
        documents.append({'url': url, 'title': title, 'published_date': published,
                          'item_id': hashlib.sha256(url.encode()).hexdigest(), 'content_sha256': hashlib.sha256(data).hexdigest(),
                          'content_bytes': len(data), 'retrieved_at': None if source_dir else datetime.now(timezone.utc).isoformat(),
                          'record_count': len(rows), 'document_type': 'PDF' if url.endswith('.pdf') else 'HTML'})
    closure = _parse_html(raw_sources[CLOSURE]).text
    closed = 'Every building complied' in closure and 'no longer an elevated risk' in closure
    closure_day = _published_date(closure) if closed else None
    for record in records:
        record['episode_status'] = 'CLOSED' if record['episode_id'] == 'NYC-UES-2026-07' and closed else 'INVESTIGATION_REPORTED'
        record['episode_closed_at'] = closure_day if record['episode_status'] == 'CLOSED' else None
        record['closure_source_url'] = CLOSURE if record['episode_status'] == 'CLOSED' else None
    linked, unresolved = resolve_rows(records, systems, aliases)
    by_system: dict[str, list[dict[str, Any]]] = {}
    for record in linked:
        by_system.setdefault(record['system_id'], []).append(record)
    return {'domain': 'LEGIONELLA_BUILDING_EVIDENCE', 'schema_version': '1.0', 'boundary': BOUNDARY,
            'documents': documents, 'records': records, 'linked_records': linked, 'unresolved': unresolved, 'by_system': by_system,
            'summary': {'source_documents': len(documents), 'published_building_observations': len(records),
                        'linked_building_observations': len(records) - len(unresolved), 'unresolved_building_observations': len(unresolved),
                        'matched_systems': len(by_system), 'matched_buildings': len({r['bin'] for r in linked})}}
