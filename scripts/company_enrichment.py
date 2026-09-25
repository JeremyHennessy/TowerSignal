"""Bounded official-page observations. Never publishes profile or ownership changes."""
from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import os
import re
import socket
import ssl
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlsplit

MAX_BYTES = 1_000_000
MAX_SOURCES = 100
ORGANIZATION_TYPES = {'Organization', 'Corporation', 'LocalBusiness', 'ProfessionalService', 'MedicalOrganization'}


def normalize_name(value):
    return ' '.join(str(value or '').casefold().split())


def validate_url(url):
    p = urlsplit(url)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None, 443):
        raise ValueError('unsupported-source-url')
    if p.fragment or len(url) > 2000:
        raise ValueError('unsupported-source-url')
    return p


class PinnedHTTPS(http.client.HTTPSConnection):
    """Connect to the vetted address while preserving TLS hostname validation."""
    def __init__(self, hostname, address):
        super().__init__(hostname, timeout=15, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        sock = socket.create_connection((self.address, 443), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def fetch_page(url):
    origin = validate_url(url).hostname
    for _ in range(4):
        parsed = validate_url(url)
        if parsed.hostname != origin:
            raise ValueError('redirect-domain-needs-review')
        addresses = sorted({item[4][0] for item in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)})
        if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
            raise ValueError('non-public-source-address')
        connection = PinnedHTTPS(parsed.hostname, addresses[0])
        try:
            path = parsed.path or '/'
            if parsed.query:
                path += '?' + parsed.query
            connection.request('GET', path, headers={'User-Agent': 'TowerSignal-CompanyEvidence/1.0', 'Accept': 'text/html', 'Accept-Encoding': 'identity'})
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                target = response.getheader('Location')
                if not target:
                    raise ValueError('invalid-redirect')
                url = urljoin(url, target)
                continue
            if response.status != 200:
                raise ValueError('http-' + str(response.status))
            if 'text/html' not in (response.getheader('Content-Type') or '').lower():
                raise ValueError('unsupported-content-type')
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError('source-too-large')
            return data.decode('utf-8', errors='replace'), url
        finally:
            connection.close()
    raise ValueError('too-many-redirects')


class StructuredDataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.capture = False
        self.parts = []
        self.documents = []
        self.contact_routes = set()

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            href = dict(attrs).get('href', '')
            if href.lower().startswith('mailto:'):
                email = unquote(href[7:].split('?')[0]).strip()
                if re.fullmatch(r'[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', email) and len(email)<=254:
                    self.contact_routes.add(('email',email.lower()))
            elif href.lower().startswith('tel:'):
                phone = unquote(href[4:]).strip()
                if re.fullmatch(r'[+0-9(). -]{7,40}',phone):
                    self.contact_routes.add(('phone',phone))
        if tag == 'script':
            self.capture = dict(attrs).get('type', '').lower() == 'application/ld+json'
            self.parts = []

    def handle_data(self, data):
        if self.capture:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.capture:
            try:
                self.documents.append(json.loads(''.join(self.parts)))
            except (ValueError, RecursionError):
                pass
            self.capture = False


def organizations(document):
    if isinstance(document, list):
        for value in document:
            yield from organizations(value)
    elif isinstance(document, dict):
        types = document.get('@type', [])
        if isinstance(types, str):
            types = [types]
        if any(t in ORGANIZATION_TYPES for t in types if isinstance(t, str)):
            yield document
        # Do not mistake nested parentOrganization or publisher for the subject company.
        yield from organizations(document.get('@graph', []))


def observations(html, expected_name):
    parser = StructuredDataParser()
    parser.feed(html)
    matches = [o for doc in parser.documents for o in organizations(doc)
               if normalize_name(o.get('name')) == normalize_name(expected_name)]
    unique = {json.dumps(o, sort_keys=True): o for o in matches}
    if not unique:
        return ('identity-unresolved' if parser.documents else 'no-structured-data'), []
    if len(unique) != 1:
        return 'identity-unresolved', []
    org = next(iter(unique.values()))
    rows = []
    for kind,value in sorted(parser.contact_routes):
        rows.append(('contact_route',{'kind':kind,'value':value}))
    legal = org.get('legalName')
    if isinstance(legal, str) and 0 < len(legal.strip()) <= 240:
        rows.append(('legal_name', legal.strip()))
    address = org.get('address')
    if isinstance(address, dict):
        address = {target: address.get(source) for target, source in [
            ('headquarters_address', 'streetAddress'), ('headquarters_city', 'addressLocality'),
            ('headquarters_region', 'addressRegion'), ('headquarters_postal_code', 'postalCode')]
            if isinstance(address.get(source), str) and 0 < len(address[source].strip()) <= 500}
        if address.get('headquarters_address'):
            # Organization address is only a proposed HQ; the reviewer must verify its meaning.
            rows.append(('headquarters', address))
    parent = org.get('parentOrganization')
    parent_name = parent.get('name') if isinstance(parent, dict) else None
    if isinstance(parent_name, str) and 0 < len(parent_name.strip()) <= 240:
        rows.append(('parent_company_name', parent_name.strip()))
    return 'observed', rows


def candidate_id(source_id, field, value):
    return hashlib.sha256(json.dumps([source_id, field, value], sort_keys=True).encode()).hexdigest()


def run(connection, fetch=fetch_page):
    from psycopg.types.json import Jsonb
    run_id = str(uuid.uuid4())
    counts = dict(checked=0, observed=0, unresolved=0, failed=0, candidate=0)
    workflow_url = None
    if os.getenv('GITHUB_REPOSITORY') and os.getenv('GITHUB_RUN_ID'):
        workflow_url = f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    # Session lock prevents overlapping manual and scheduled workers.
    if not connection.execute("SELECT pg_try_advisory_lock(731250913)").fetchone()[0]:
        raise RuntimeError('enrichment-already-running')
    try:
        connection.execute("INSERT INTO public.company_enrichment_runs(run_id,status,workflow_url) VALUES(%s,'running',%s)", (run_id, workflow_url))
        sources = connection.execute("""SELECT s.source_id,s.sales_account_id,s.source_url,s.expected_name
            FROM public.company_enrichment_sources s JOIN public.company_sales_accounts a USING(sales_account_id)
            WHERE s.enabled AND s.approved_at IS NOT NULL AND a.record_status='active'
              AND (s.last_attempt_at IS NULL OR s.last_attempt_at < now()-interval '7 days')
            ORDER BY s.last_attempt_at NULLS FIRST,s.source_id LIMIT %s""", (MAX_SOURCES,)).fetchall()
        for source_id, account_id, url, name in sources:
            counts['checked'] += 1
            try:
                html, final_url = fetch(url)
                outcome, rows = observations(html, name)
                content_hash = hashlib.sha256(html.encode()).hexdigest()
                new_candidates = 0
                with connection.transaction():
                    for field, value in rows:
                        inserted = connection.execute("""INSERT INTO public.company_enrichment_candidates
                            (candidate_id,sales_account_id,source_id,field_name,proposed_value,source_url,evidence_excerpt,content_sha256)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT(candidate_id) DO UPDATE SET last_observed_at=now(),content_sha256=excluded.content_sha256
                            RETURNING (xmax=0)""", (candidate_id(source_id,field,value),account_id,source_id,field,Jsonb(value),final_url,
                            json.dumps({'name':name,'field':field,'value':value},ensure_ascii=False)[:2500],content_hash)).fetchone()[0]
                        if inserted:
                            new_candidates += 1
                    connection.execute("""UPDATE public.company_enrichment_sources SET last_attempt_at=now(),last_success_at=now(),last_outcome=%s,last_error=NULL WHERE source_id=%s""",(outcome,source_id))
                counts['observed' if outcome=='observed' else 'unresolved'] += 1
                counts['candidate'] += new_candidates
            except Exception as error:
                counts['failed'] += 1
                # Never persist raw exception text: it may contain a URL, query or private values.
                category = str(error) if isinstance(error, ValueError) and str(error) in {
                    'unsupported-source-url','redirect-domain-needs-review','non-public-source-address',
                    'invalid-redirect','unsupported-content-type','source-too-large','too-many-redirects'} else type(error).__name__
                connection.execute("UPDATE public.company_enrichment_sources SET last_attempt_at=now(),last_outcome='failed',last_error=%s WHERE source_id=%s",(category,source_id))
        status = 'success' if not counts['failed'] else ('failed' if counts['failed']==counts['checked'] else 'partial')
        connection.execute("""UPDATE public.company_enrichment_runs SET finished_at=now(),status=%s,checked_count=%s,
            observed_count=%s,unresolved_count=%s,failed_count=%s,candidate_count=%s WHERE run_id=%s""",
            (status,counts['checked'],counts['observed'],counts['unresolved'],counts['failed'],counts['candidate'],run_id))
        return status, counts
    except BaseException:
        connection.execute("UPDATE public.company_enrichment_runs SET finished_at=now(),status='failed' WHERE run_id=%s",(run_id,))
        raise
    finally:
        connection.execute('SELECT pg_advisory_unlock(731250913)')


if __name__ == '__main__':
    import psycopg
    with psycopg.connect(os.environ['DATABASE_URL'], autocommit=True) as connection:
        status, counts = run(connection)
    print(json.dumps({'status':status,'counts':counts,'checked_at':datetime.now(timezone.utc).isoformat()}))
    if status in ('failed','partial'):
        raise SystemExit(1)
