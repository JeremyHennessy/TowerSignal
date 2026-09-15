"""Resolve explicit outbreak building lists separately from ZIP context.

Only reviewed source sections assert results. Meeting venues and incidental
addresses cannot become positive-tower evidence. No fuzzy property matching.
"""
from __future__ import annotations
import hashlib
import json
import re
import subprocess
import unicodedata
from collections import defaultdict
from datetime import datetime
from html.parser import HTMLParser
from typing import Any
from towersignal.legionella_alerts import _fetch

TOPIC = 'https://www.nyc.gov/site/doh/health/health-topics/legionnaires-disease.page'
PRESS = 'https://www.nyc.gov/site/doh/about/press/pr2026/'
BRONX_INITIAL = PRESS + 'nyc-health-department-investigating-legionnaires-cluster-in-the-bronx.page'
BRONX_LIST = PRESS + 'nyc-health-department-orders-cooling-towers-to-be-cleaned-in-south-bronx.page'
CULTURE = 'https://www.nyc.gov/assets/doh/downloads/pdf/cd/cooling-tower-confirmatory-culture-results.pdf'
PCR = 'https://www.nyc.gov/assets/doh/downloads/pdf/cd/ues-cluster-2026-pcr-positive-cooling-towers.pdf'
SOURCES = (TOPIC, BRONX_INITIAL, BRONX_LIST, CULTURE, PCR)
EVENTS = (
    {'event_id': 'nyc-2026-south-bronx', 'name': 'South Bronx · Melrose and Morrisania', 'borough': 'Bronx', 'year': 2026, 'zip_codes': ['10451', '10456'], 'initial_url': BRONX_INITIAL},
    {'event_id': 'nyc-2026-upper-east-side', 'name': 'Upper East Side · Carnegie Hill and Yorkville', 'borough': 'Manhattan', 'year': 2026, 'zip_codes': ['10028', '10075', '10128'], 'initial_url': PRESS + 'nyc-health-dept-investigating-legionnaires-cluster-ues.page'},
)
DOMAIN = 'LEGIONELLA_TOWER_LINKS'
BOUNDARY = 'A named building is not an identified individual tower system. PCR/culture results do not establish the source of an outbreak. ZIP matches are area context only, not test results or proof of exposure. Priority Score is unchanged.'


def fingerprint(value: bytes | str) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def normalized_address(value: str | None) -> str:
    text = unicodedata.normalize('NFKC', value or '').upper().strip()
    text = re.sub(r'[.,]', '', text)
    text = re.sub(r'\b(\d+)(ST|ND|RD|TH)\b', r'\1', text)
    replacements = {'STREET': 'ST', 'AVENUE': 'AVE', 'BOULEVARD': 'BLVD', 'ROAD': 'RD', 'PLACE': 'PL', 'EAST': 'E', 'WEST': 'W', 'NORTH': 'N', 'SOUTH': 'S'}
    text = ' '.join(replacements.get(part, part) for part in text.split())
    for word, number in [('FIRST', '1'), ('SECOND', '2'), ('THIRD', '3'), ('FOURTH', '4'), ('FIFTH', '5')]:
        text = re.sub(r'\b' + word + r'(?= AVE$)', number, text)
    return text


def identifier(value: Any, length: int) -> str | None:
    text = re.sub(r'\.0$', '', str(value or '').strip())
    return text if re.fullmatch(r'\d{' + str(length) + '}', text) else None


class Blocks(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tag: str | None = None
        self.parts: list[str] = []
        self.blocks: list[tuple[str, str]] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ('script', 'style'):
            self.skip += 1
        if not self.skip and tag in ('h1', 'h2', 'h3', 'h4', 'p', 'li'):
            self.tag, self.parts = tag, []

    def handle_data(self, data: str) -> None:
        if self.tag and not self.skip:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in ('script', 'style') and self.skip:
            self.skip -= 1
        if tag == self.tag:
            self.blocks.append((tag, ' '.join(''.join(self.parts).split())))
            self.tag, self.parts = None, []


def html_blocks(content: bytes) -> list[tuple[str, str]]:
    parser = Blocks()
    parser.feed(content.decode('utf-8', errors='strict'))
    return parser.blocks


def scoped_list(blocks: list[tuple[str, str]], introduction: str) -> list[str]:
    index = next((i for i, (_, text) in enumerate(blocks) if re.search(introduction, text, re.I)), None)
    if index is None:
        raise ValueError('Explicit cooling-tower list introduction missing')
    addresses: list[str] = []
    for tag, text in blocks[index + 1:]:
        if tag != 'li':
            break
        if not re.fullmatch(r'\d+[A-Za-z]?(?:-\d+)?\s+[\w .\-]+', text):
            raise ValueError('Unrecognized building-list row: ' + text)
        addresses.append(text)
    if not addresses:
        raise ValueError('Explicit list is empty; refusing to convert parse failure to zero')
    return list(dict.fromkeys(addresses))


def date_from_text(text: str) -> str | None:
    match = re.search(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(20\d{2})\b', text)
    return datetime.strptime(' '.join(match.groups()), '%B %d %Y').date().isoformat() if match else None


def parse_pdf(text: str, kind: str) -> tuple[str, list[dict[str, Any]]]:
    # The footer is authoritative, never the potentially outdated link label.
    dates = set()
    for line in text.splitlines():
        m = re.fullmatch(r'\s*(\d{1,2})\.(\d{1,2})\.(\d{2}|20\d{2})\s*', line)
        if m:
            month, day, year = map(int, m.groups())
            dates.add(datetime(year + 2000 if year < 100 else year, month, day).date().isoformat())
    if len(dates) != 1:
        raise ValueError('Missing/ambiguous document version date')
    date = dates.pop()
    if not date.startswith('2026-'):
        raise ValueError('Generic PDF URL no longer belongs to reviewed 2026 incident')
    headings = {'Culture Positive': 'CULTURE_POSITIVE', 'Culture Negative': 'CULTURE_NEGATIVE', 'Test Results Pending': 'CULTURE_PENDING', 'Cleaning Complete': 'PCR_POSITIVE'}
    current: str | None = None
    records = []
    for line in text.splitlines():
        line = line.strip()
        if line in headings:
            current = headings[line]
            continue
        match = re.match(r'^[•●\uf0b7]\s*(\d.+?)\s*$', line)
        if not match:
            continue
        if not current or (kind == 'culture' and current == 'PCR_POSITIVE'):
            raise ValueError('Unclassified PDF building row')
        raw = match.group(1)
        address = re.sub(r'\s*\([^)]*\)\s*', '', raw).rstrip(' *').strip()
        if not re.fullmatch(r'\d+[A-Za-z]?\s+[\w .\-]+', address):
            raise ValueError('Ambiguous PDF address: ' + raw)
        records.append({'published_address': address, 'result': current, 'source_locator': current.replace('_', ' ').title(), 'source_row': raw,
                        'source_note': 'PCR-negative footnote; remediated as stated in this document' if raw.endswith('*') and 'Tested PCR negative' in text else (raw[len(address):].strip() or None),
                        'remediation': 'CLEANING_COMPLETE_REPORTED' if kind == 'pcr' else 'NOT_DETERMINED_FROM_THIS_SECTION'})
    if not records or not any(r['result'] == ('CULTURE_POSITIVE' if kind == 'culture' else 'PCR_POSITIVE') for r in records):
        raise ValueError('Required result section missing or empty')
    return date, records


def resolve_building(record: dict[str, Any], borough: str, systems: list[dict[str, Any]]) -> dict[str, Any]:
    key = normalized_address(record['published_address'])
    candidates = [row for row in systems if row.get('borough') == borough and normalized_address(row.get('address')) == key]
    bins = {identifier(row.get('bin'), 7) for row in candidates}
    if not candidates:
        return {'status': 'UNMATCHED', 'match_basis': 'NONE', 'systems': [], 'reason': 'No exact normalized address + borough in the current registry; no fuzzy match used'}
    if None in bins or len(bins) != 1:
        return {'status': 'AMBIGUOUS', 'match_basis': 'NONE', 'systems': [], 'reason': 'Address does not resolve to one valid building BIN'}
    bin_value = next(iter(bins))
    linked = [row for row in systems if identifier(row.get('bin'), 7) == bin_value and row.get('borough') == borough]
    return {'status': 'MATCHED', 'match_basis': 'EXACT_NORMALIZED_ADDRESS_BOROUGH_THEN_BIN', 'bin': bin_value,
            'systems': [{key: row.get(key) for key in ('system_id', 'address', 'bin', 'bbl', 'borough', 'zip', 'latitude', 'longitude', 'active_equipment')} for row in sorted(linked, key=lambda row: row['system_id'])],
            'system_specific': False, 'entity_level': 'BUILDING', 'reason': 'Official source names this building; it does not identify which registered system or unit tested positive'}


def parse_sources(documents: dict[str, bytes]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    topic = html_blocks(documents[TOPIC])
    topic_text = '\n'.join(text for _, text in topic)
    if 'Melrose' not in topic_text or 'Morrisania' not in topic_text:
        raise ValueError('Current topic page no longer exposes reviewed South Bronx incident')
    initial_text = '\n'.join(text for _, text in html_blocks(documents[BRONX_INITIAL]))
    for zipcode in EVENTS[0]['zip_codes']:
        if zipcode not in initial_text:
            raise ValueError('South Bronx official area definition changed')
    press = html_blocks(documents[BRONX_LIST])
    press_date = date_from_text('\n'.join(text for _, text in press))
    if press_date != '2026-09-13':
        raise ValueError('Unexpected dated Bronx remediation release')
    press_addresses = scoped_list(press, r'^The \d+ cooling towers with positive PCR results are located at:')
    topic_addresses = scoped_list(topic, r'^The following buildings have cooling towers that tested positive in a PCR test')
    records = []
    docs = []
    for url in SOURCES:
        content = documents[url]
        date = None
        title = next((text for tag, text in html_blocks(content) if tag == 'h1'), '') if not url.endswith('.pdf') else ''
        if url.endswith('.pdf'):
            result = subprocess.run(['pdftotext', '-layout', '-', '-'], input=content, capture_output=True, check=True, timeout=30)
            date, parsed = parse_pdf(result.stdout.decode('utf-8'), 'culture' if url == CULTURE else 'pcr')
            title = 'Cooling Tower Confirmatory Culture Results' if url == CULTURE else 'Upper East Side PCR-positive cooling towers · cleaning complete'
            for row in parsed:
                records.append({**row, 'event_id': EVENTS[1]['event_id'], 'borough': 'Manhattan', 'source_url': url, 'source_date': date})
        elif url == BRONX_LIST:
            date = press_date
            for address in press_addresses:
                records.append({'published_address': address, 'event_id': EVENTS[0]['event_id'], 'borough': 'Bronx', 'result': 'PCR_POSITIVE', 'remediation': 'CLEANING_ORDER_REPORTED', 'source_url': url, 'source_date': date,
                                'source_locator': 'The 10 cooling towers with positive PCR results', 'source_row': address, 'source_note': 'Cleaning ordered by September 14; completion is not established by an order'})
        elif url == TOPIC:
            for address in topic_addresses:
                records.append({'published_address': address, 'event_id': EVENTS[0]['event_id'], 'borough': 'Bronx', 'result': 'PCR_POSITIVE', 'remediation': 'CLEANING_ORDER_REPORTED', 'source_url': url, 'source_date': None,
                                'source_locator': 'Legionnaires’ Disease Investigation · PCR-positive building list', 'source_row': address, 'source_note': 'Undated live-page observation; culture testing described as continuing'})
        elif url == BRONX_INITIAL:
            date = date_from_text(initial_text)
        docs.append({'source_url': url, 'title': title, 'source_date': date, 'content_sha256': fingerprint(content), 'content_bytes': len(content)})
    ues_start = topic_text.find('Upper East Side Legionnaires')
    ues_text = topic_text[ues_start:] if ues_start >= 0 else ''
    statuses = [
        {'event_id': EVENTS[0]['event_id'], 'status': 'INVESTIGATING_AS_REPORTED' if re.search(r'currently investigating.*Melrose', topic_text) else 'STATUS_REQUIRES_REVIEW', 'status_source_url': TOPIC},
        {'event_id': EVENTS[1]['event_id'], 'status': 'CONCLUDED_AS_REPORTED' if 'has concluded its investigation' in ues_text else 'STATUS_REQUIRES_REVIEW', 'status_source_url': TOPIC},
    ]
    return records, docs + [{'incident_statuses': statuses}]


def build_payload(systems: list[dict[str, Any]], documents: dict[str, bytes], alerts: dict[str, Any], *, collected_at: str, previous: dict[str, Any] | None = None) -> dict[str, Any]:
    assertions, source_documents = parse_sources(documents)
    statuses = source_documents.pop()['incident_statuses']
    versions = {doc['source_url']: doc for doc in source_documents}
    for doc in source_documents:
        doc['retrieved_at'] = collected_at
    for record in assertions:
        record['content_sha256'] = versions[record['source_url']]['content_sha256']
        record['retrieved_at'] = collected_at
        record['observation_id'] = fingerprint('|'.join(str(record.get(key) or '') for key in ('event_id', 'source_url', 'content_sha256', 'published_address', 'result')))
        record['resolution'] = resolve_building(record, record['borough'], systems)
    if previous and previous.get('domain') != DOMAIN:
        raise ValueError('Previous tower-link cache has an unexpected domain')
    history = {row['observation_id']: row for row in (previous or {}).get('observation_history', [])}
    for row in assertions:
        history.setdefault(row['observation_id'], row)
    events = []
    all_links: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for spec, status in zip(EVENTS, statuses):
        buildings: dict[str, dict[str, Any]] = {}
        for row in (row for row in assertions if row['event_id'] == spec['event_id']):
            key = normalized_address(row['published_address'])
            entry = buildings.setdefault(key, {'published_address': row['published_address'], 'resolution': row['resolution'], 'observations': []})
            entry['observations'].append({key: value for key, value in row.items() if key != 'resolution'})
        named = {s['system_id'] for b in buildings.values() for s in b['resolution']['systems']}
        area = {row['system_id'] for row in systems if row.get('borough') == spec['borough'] and row.get('zip') in spec['zip_codes']}
        for sid in sorted(named | area):
            observations = [o for b in buildings.values() if any(s['system_id'] == sid for s in b['resolution']['systems']) for o in b['observations']]
            all_links[sid].append({'event_id': spec['event_id'], 'relationship': 'NAMED_BUILDING' if sid in named else 'AREA_CONTEXT', 'source_listed_building': sid in named, 'shares_published_zip': sid in area, 'system_specific': False, 'observation_ids': [o['observation_id'] for o in observations]})
        related = []
        for item in alerts.get('items', []):
            text = f"{item.get('title', '')} {item.get('url', '')}".lower()
            dated_2026 = str(item.get('published_date') or '').startswith('2026') or '/pr2026/' in text or item.get('url') in (CULTURE, PCR)
            pattern = r'south.bronx|melrose|morrisania|cluster.in.the.bronx' if spec['borough'] == 'Bronx' else r'upper.east.side|\bues\b|carnegie.hill|yorkville'
            if dated_2026 and re.search(pattern, text):
                related.append({'item_id': item['item_id'], 'title': item.get('title'), 'url': item['url'], 'published_date': item.get('published_date'), 'relationship': 'SAME_INCIDENT_NOT_INDIVIDUAL_TOWER_ASSERTION'})
        events.append({**spec, **status, 'status_observed_at': collected_at, 'buildings': list(buildings.values()), 'related_articles': related,
                       'named_building_count': sum(b['resolution']['status'] == 'MATCHED' for b in buildings.values()), 'published_building_count': len(buildings), 'named_system_count': len(named), 'area_only_system_count': len(area - named), 'zip_context_system_count': len(area), 'linked_system_count': len(named | area), 'unresolved_building_count': sum(b['resolution']['status'] != 'MATCHED' for b in buildings.values()), 'boundary': BOUNDARY})
    projection = [{key: row.get(key) for key in ('system_id', 'address', 'borough', 'bin', 'bbl', 'zip')} for row in sorted(systems, key=lambda r: r['system_id'])]
    return {'schema_version': '1.0', 'domain': DOMAIN, 'generated_at': collected_at, 'registry_identity_sha256': fingerprint(json.dumps(projection, sort_keys=True)), 'registry_system_count': len(systems), 'source_documents': source_documents, 'events': events, 'system_links': dict(sorted(all_links.items())), 'observation_history': sorted(history.values(), key=lambda row: row['observation_id']), 'coverage': {'reviewed_incidents': len(events), 'alert_items_considered': len(alerts.get('items', [])), 'related_article_count': sum(len(e['related_articles']) for e in events), 'scope': 'Reviewed 2026 South Bronx and Upper East Side incidents. Other retained articles are not claimed to have property-level matching.'}, 'evidence_boundary': BOUNDARY}


def collect_documents() -> dict[str, bytes]:
    # A source/parse failure aborts before replacing an existing cache.
    return {url: _fetch(url)[0] for url in SOURCES}
