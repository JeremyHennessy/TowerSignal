"""Source-scoped official health findings. Building identity is not individual-tower attribution."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any
from .legionella_alerts import _fetch, _parse_html

TOPIC = 'https://www.nyc.gov/site/doh/health/health-topics/legionnaires-disease.page'
BRONX_INITIAL = 'https://www.nyc.gov/site/doh/about/press/pr2026/nyc-health-department-investigating-legionnaires-cluster-in-the-bronx.page'
BRONX_ORDER = 'https://www.nyc.gov/site/doh/about/press/pr2026/nyc-health-department-orders-cooling-towers-to-be-cleaned-in-south-bronx.page'
CULTURE = 'https://www.nyc.gov/assets/doh/downloads/pdf/cd/cooling-tower-confirmatory-culture-results.pdf'
PCR = 'https://www.nyc.gov/assets/doh/downloads/pdf/cd/ues-cluster-2026-pcr-positive-cooling-towers.pdf'
UES_RELATED = [
    'https://www.nyc.gov/site/doh/about/press/pr2026/preliminary-list-ues-cooling-towers-confirmed-live-legionella.page',
    'https://www.nyc.gov/site/doh/about/press/pr2026/health-department-declares-ues-legionnaires-exposure-has-ended.page',
]
BOUNDARY = ('An official named-building match applies at building scope. It does not identify which registered system or equipment tested positive, and does not establish the source of human infections. ZIP-code matches are area context only.')


def normalized_address(value: Any) -> str:
    text = re.sub(r'[.,*]', '', str(value or '').upper())
    text = re.sub(r'\([^)]*\)', '', text)
    text = re.sub(r'\b(\d+)(?:ST|ND|RD|TH)\b', r'\1', text)
    replacements = {'EAST': 'E', 'WEST': 'W', 'NORTH': 'N', 'SOUTH': 'S', 'STREET': 'ST',
                    'AVENUE': 'AVE', 'AV': 'AVE', 'BOULEVARD': 'BLVD', 'ROAD': 'RD',
                    'FIRST': '1', 'SECOND': '2', 'THIRD': '3', 'FOURTH': '4', 'FIFTH': '5'}
    return ' '.join(replacements.get(token, token) for token in text.split())


def canonical_bin(value: Any) -> str | None:
    from towersignal.planimetrics import normalize_bin as assigned_bin
    return assigned_bin(value)

class ListParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_li = False
        self.parts: list[str] = []
        self.items: list[str] = []
    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == 'li':
            self.in_li, self.parts = True, []
    def handle_data(self, data: str) -> None:
        if self.in_li:
            self.parts.append(data)
    def handle_endtag(self, tag: str) -> None:
        if tag == 'li' and self.in_li:
            self.items.append(' '.join(' '.join(self.parts).split()))
            self.in_li = False


def parse_bronx_orders(content: bytes) -> list[dict[str, Any]]:
    html = content.decode('utf-8', errors='replace')
    text = _parse_html(content).text
    if not all(term.lower() in text.lower() for term in ('10 cooling towers', 'PCR', 'September 13, 2026')):
        raise ValueError('Bronx order source contract changed; review the named-building results before publishing')
    anchor = re.search(r'The 10 cooling towers with positive PCR results are located at', html, re.I)
    block = re.search(r'<ul\b[^>]*>.*?</ul>', html[anchor.end():], re.I | re.S) if anchor else None
    if not block:
        raise ValueError('Bronx named-tower result list not found')
    parser = ListParser()
    parser.feed(block.group())
    addresses = [a for a in parser.items if re.match(r'^\d+\s', a)]
    if len(addresses) != 10 or len(set(map(normalized_address, addresses))) != 10:
        raise ValueError('Bronx list cardinality changed; partial extraction refused')
    return [{'cluster_id': 'NYC-BRONX-2026-09', 'borough': 'BRONX', 'address': address,
             'result': 'PCR_POSITIVE', 'action': 'REMEDIATION_ORDER_REPORTED',
             'document_date': '2026-09-13', 'date_basis': 'DOCUMENT_PUBLICATION',
             'event_date': '2026-09-12', 'event_date_basis': 'ORDER_ISSUED_DATE_REPORTED',
             'deadline': '2026-09-14', 'source_url': BRONX_ORDER,
             'related_article_urls': [BRONX_INITIAL, BRONX_ORDER, TOPIC],
             'completion': 'NOT_ESTABLISHED', 'outbreak_attribution': 'NOT_ESTABLISHED',
             'evidence_text': address} for address in addresses]


def parse_result_pdf(text: str, url: str) -> list[dict[str, Any]]:
    dates = re.findall(r'\b(\d{1,2})\.(\d{1,2})\.(\d{2,4})\b', text)
    if not dates:
        raise ValueError('Official results document lacks a parseable printed date')
    parsed_dates = {datetime(int(y) + (2000 if len(y) == 2 else 0), int(m), int(d)).date().isoformat() for m, d, y in dates}
    if len(parsed_dates) != 1:
        raise ValueError('Results document has inconsistent printed dates; manual review required')
    document_date = parsed_dates.pop()
    if not document_date.startswith('2026-'):
        raise ValueError('Known Upper East Side document changed year; review cluster identity')
    mode: str | None = None
    results: list[dict[str, Any]] = []
    for line in text.splitlines():
        clean = line.strip()
        if clean in ('Culture Positive', 'Culture Negative', 'Test Results Pending', 'Cleaning Complete'):
            mode = clean
        match = re.match(r'^[•●\u00b7]\s*(\d.+)$', clean)
        if not match or mode is None:
            continue
        address = match.group(1).strip()
        if not re.search(r'\b(?:Street|Avenue)\b', address, re.I):
            raise ValueError('Unrecognized named-building result row: ' + address)
        result = {'Culture Positive': 'CULTURE_POSITIVE', 'Culture Negative': 'CULTURE_NEGATIVE', 'Test Results Pending': 'CULTURE_PENDING', 'Cleaning Complete': 'PCR_POSITIVE'}[mode]
        if mode == 'Cleaning Complete' and re.search(r'PCR negative', address, re.I):
            result = 'PCR_NEGATIVE'
        results.append({'cluster_id': 'NYC-UES-2026-07', 'borough': 'MANHATTAN',
                        'address': re.sub(r'\s*\([^)]*\)|\s*\*', '', address).strip(),
                        'result': result, 'action': 'HISTORICAL_RESULT',
                        'document_date': document_date, 'date_basis': 'DOCUMENT_PUBLICATION',
                        'event_date': None, 'event_date_basis': 'SAMPLE_DATE_NOT_PUBLISHED',
                        'source_url': url, 'related_article_urls': [url, TOPIC, *UES_RELATED],
                        'completion': 'CLEANING_REPORTED_COMPLETE' if mode == 'Cleaning Complete' else 'NOT_ESTABLISHED',
                        'outbreak_attribution': 'NOT_ESTABLISHED', 'evidence_text': clean})
    if len(results) < 20 or len({normalized_address(r['address']) for r in results}) != len(results):
        raise ValueError('Incomplete or duplicate official PDF result rows')
    return results


def collect_documents(evidence_dir: Path | None = None) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    topic, _ = _fetch(TOPIC)
    text = _parse_html(topic).text
    ues_start = text.find('Upper East Side Legionnaires')
    ues = text[ues_start:] if ues_start >= 0 else ''
    ues_closed = 'has concluded its investigation' in ues
    bronx_reported = bool(re.search(r'currently investigating.*?(?:Melrose|Morrisania).*?South Bronx', text, re.I | re.S))
    if evidence_dir:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir/'topic.html').write_bytes(topic)
    for url in (BRONX_ORDER, PCR, CULTURE):
        content, _ = _fetch(url)
        content_hash = sha256(content).hexdigest()
        retrieved = datetime.now(timezone.utc).isoformat()
        if evidence_dir:
            (evidence_dir/url.rsplit('/', 1)[-1]).write_bytes(content)
        if url.endswith('.pdf'):
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder)/'source.pdf'
                path.write_bytes(content)
                parsed = subprocess.run(['pdftotext', '-layout', str(path), '-'], capture_output=True, check=True, timeout=30).stdout.decode('utf-8')
            if evidence_dir:
                (evidence_dir/(url.rsplit('/', 1)[-1] + '.txt')).write_text(parsed)
            records = parse_result_pdf(parsed, url)
        else:
            records = parse_bronx_orders(content)
        for record in records:
            status = 'STATUS_NOT_ESTABLISHED'
            if record['cluster_id'] == 'NYC-UES-2026-07' and ues_closed:
                status = 'CLOSED_REPORTED'
            elif record['cluster_id'] == 'NYC-BRONX-2026-09' and bronx_reported:
                status = 'INVESTIGATION_REPORTED'
            record.update(content_sha256=content_hash, retrieved_at=retrieved, cluster_status=status, cluster_status_source=TOPIC)
            record['observation_id'] = sha256(f"{url}|{record['cluster_id']}|{normalized_address(record['address'])}|{record['result']}".encode()).hexdigest()
        observations.extend(records)
        sources.append({'url': url, 'content_sha256': content_hash, 'retrieved_at': retrieved, 'record_count': len(records)})
    sources.append({'url': TOPIC, 'content_sha256': sha256(topic).hexdigest(), 'retrieved_at': datetime.now(timezone.utc).isoformat(), 'ues_closed_reported': ues_closed})
    areas = []
    for cluster, borough, zips, marker in (
        ('NYC-BRONX-2026-09', 'BRONX', ['10451', '10456'], 'Melrose'),
        ('NYC-UES-2026-07', 'MANHATTAN', ['10028', '10128', '10075'], 'Carnegie Hill'),
    ):
        if marker in text and all(z in text for z in zips):
            areas.append({'cluster_id': cluster, 'borough': borough, 'zip_codes': zips, 'source_url': TOPIC,
                          'scope': 'PUBLISHED_ZIP_AREA_CONTEXT', 'score_points': 0,
                          'cluster_status': 'CLOSED_REPORTED' if cluster == 'NYC-UES-2026-07' and ues_closed else 'INVESTIGATION_REPORTED' if cluster == 'NYC-BRONX-2026-09' and bronx_reported else 'STATUS_NOT_ESTABLISHED',
                          'basis': 'Registered postal code intersects published ZIP list; not an implicated-tower match.'})
    return {'observations': observations, 'sources': sources, 'areas': areas, 'evidence_boundary': BOUNDARY}


def match_documents(documents: dict[str, Any], systems: list[dict[str, Any]]) -> dict[str, Any]:
    index: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_system = {str(r['system_id']): {'building_observations': [], 'area_context': []} for r in systems}
    for row in systems:
        index[(str(row.get('borough') or '').upper(), normalized_address(row.get('address')))].append(row)
    matched, unresolved = [], []
    for observation in documents['observations']:
        candidates = index.get((observation['borough'], normalized_address(observation['address'])), [])
        bins = {canonical_bin(r.get('bin')) for r in candidates}
        if not candidates or None in bins or len(bins) != 1:
            unresolved.append({**observation, 'match_status': 'UNMATCHED' if not candidates else 'AMBIGUOUS', 'candidate_system_ids': sorted(str(r['system_id']) for r in candidates)})
            continue
        record = {**observation, 'match_basis': 'NORMALIZED_ADDRESS_BOROUGH_SINGLE_BIN',
                  'match_scope': 'NAMED_BUILDING_NOT_INDIVIDUAL_SYSTEM', 'bin': next(iter(bins)),
                  'system_ids': sorted(str(r['system_id']) for r in candidates), 'evidence_boundary': BOUNDARY}
        matched.append(record)
        for sid in record['system_ids']:
            by_system[sid]['building_observations'].append(record)
    for area in documents.get('areas', []):
        for row in systems:
            if str(row.get('borough') or '').upper() == area['borough'] and str(row.get('zip') or '') in area['zip_codes']:
                by_system[str(row['system_id'])]['area_context'].append(area)
    return {'domain': 'LEGIONELLA_PROPERTY_MATCHES', 'evidence_boundary': BOUNDARY,
            'sources': documents['sources'], 'matched_observations': matched, 'unresolved': unresolved, 'by_system': by_system,
            'summary': {'matched_observation_count': len(matched), 'unresolved_observation_count': len(unresolved),
                        'named_buildings_matched': len({(r['cluster_id'], r['bin']) for r in matched}),
                        'systems_with_named_building_evidence': sum(bool(v['building_observations']) for v in by_system.values()),
                        'systems_with_area_context': sum(bool(v['area_context']) for v in by_system.values())}}
