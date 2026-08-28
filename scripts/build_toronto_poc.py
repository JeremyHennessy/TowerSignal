from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]

CKAN_ACTION = "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/datastore_search"
PERMIT_RESOURCES = {
    "active": {
        "resource_id": "6d0229af-bc54-46de-9c2b-26759b01dd05",
        "source_url": "https://open.toronto.ca/dataset/building-permits-active-permits/",
    },
    "cleared": {
        "resource_id": "a96c0ba4-3026-402b-b09d-5b1268b8f810",
        "source_url": "https://open.toronto.ca/dataset/building-permits-cleared-permits/",
    },
}
TDSB_LIST_URLS = [
    "https://www.tdsb.on.ca/Find-your/School/By-School-Name/Elementary",
    "https://www.tdsb.on.ca/Find-your/School/By-School-Name/Secondary",
]
TDSB_FCI_URL = "https://www.tdsb.on.ca/Find-your/Schools/School-FCI/schno/{school_id}"
TDSB_SCHOOL_URL = "https://www.tdsb.on.ca/Find-your/Schools/schno/{school_id}"
TDSB_MIN_DISCOVERED_SCHOOLS = 400

QUERY_TERMS = [
    "cooling tower",
    "cooling towers",
    "evaporative condenser",
    "chiller",
    "condenser water",
    "chemical feed",
]

EQUIPMENT_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("cooling_tower", re.compile(r"\bcooling\s+towers?\b", re.I), "CONFIRMED"),
    ("evaporative_condenser", re.compile(r"\bevaporative\s+condenser(?:s)?\b", re.I), "CONFIRMED_RELATED_EQUIPMENT"),
    ("chiller", re.compile(r"\bchiller(?:s)?\b", re.I), "SUPPORTING"),
    ("condenser_water", re.compile(r"\bcondenser\s+water\b", re.I), "SUPPORTING"),
    ("chemical_feed", re.compile(r"\bchemical\s+feed\b", re.I), "SUPPORTING"),
]

USER_AGENT = "TowerSignal-Toronto-POC/0.1 (+https://github.com/JeremyHennessy/TowerSignal)"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def request_bytes(url: str, *, timeout: int = 45, retries: int = 3) -> bytes:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json,text/html,application/xhtml+xml,*/*;q=0.8",
                    "Accept-Language": "en-CA,en;q=0.9",
                },
            )
            with urlopen(request, timeout=timeout) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed to retrieve {url}: {last_error}")


def request_json(url: str) -> dict[str, Any]:
    payload = json.loads(request_bytes(url).decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object from {url}")
    return payload


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def value_for(record: dict[str, Any], *candidate_names: str) -> Any:
    normalized = {normalize_key(str(key)): value for key, value in record.items()}
    for name in candidate_names:
        if normalize_key(name) in normalized:
            return normalized[normalize_key(name)]
    return None


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", html.unescape(str(value))).strip()


def normalized_address(value: str) -> str:
    value = clean_text(value).upper()
    value = re.sub(r"[^A-Z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def permit_address(record: dict[str, Any]) -> str:
    direct = clean_text(value_for(record, "address", "site_address", "location"))
    if direct:
        return direct
    parts = [
        clean_text(value_for(record, "street_num", "street_number", "street_no")),
        clean_text(value_for(record, "street_name")),
        clean_text(value_for(record, "street_type")),
        clean_text(value_for(record, "street_direction", "street_dir")),
    ]
    return " ".join(part for part in parts if part)


def property_key_for(*, geo_id: str, address: str, fallback: str) -> str:
    if geo_id:
        return f"toronto-geoid:{geo_id.strip()}"
    normalized = normalized_address(address)
    if normalized:
        digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]
        return f"toronto-address:{digest}"
    return fallback


def source_record_id(record: dict[str, Any], source_status: str) -> str:
    for names in (
        ("permit_num", "permit_number"),
        ("application_num", "application_number"),
        ("_id", "id"),
    ):
        value = clean_text(value_for(record, *names))
        if value:
            revision = clean_text(value_for(record, "revision_num", "revision_number"))
            return f"{source_status}:{value}:{revision}" if revision else f"{source_status}:{value}"
    digest = hashlib.sha1(json.dumps(record, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:20]
    return f"{source_status}:sha1:{digest}"


def record_search_text(record: dict[str, Any]) -> str:
    preferred_names = [
        "description",
        "work",
        "work_description",
        "permit_type",
        "permit_category",
        "current_use",
        "proposed_use",
        "structure_type",
    ]
    preferred_values = [clean_text(value_for(record, name)) for name in preferred_names]
    preferred = " | ".join(value for value in preferred_values if value)
    if preferred:
        return preferred
    return " | ".join(clean_text(value) for value in record.values() if value is not None)


def classify_equipment(text: str) -> list[tuple[str, str]]:
    matches: list[tuple[str, str]] = []
    for equipment_type, pattern, confidence in EQUIPMENT_PATTERNS:
        if pattern.search(text):
            matches.append((equipment_type, confidence))
    return matches


def permit_event_date(record: dict[str, Any]) -> str | None:
    for name in (
        "completed_date",
        "completion_date",
        "issued_date",
        "permit_issued_date",
        "application_date",
    ):
        value = clean_text(value_for(record, name))
        if value:
            return value
    return None


def fetch_ckan_records(resource_id: str, query: str) -> tuple[list[dict[str, Any]], int]:
    records: list[dict[str, Any]] = []
    offset = 0
    limit = 1000
    total: int | None = None
    while total is None or offset < total:
        params = urlencode({"resource_id": resource_id, "q": query, "limit": limit, "offset": offset})
        payload = request_json(f"{CKAN_ACTION}?{params}")
        if payload.get("success") is not True:
            raise RuntimeError(f"Toronto CKAN query failed for resource {resource_id!r}, q={query!r}")
        result = payload.get("result") or {}
        batch = result.get("records") or []
        if not isinstance(batch, list):
            raise RuntimeError("Toronto CKAN response records were not a list")
        total = int(result.get("total") or 0)
        records.extend(item for item in batch if isinstance(item, dict))
        offset += len(batch)
        if not batch:
            break
    return records, int(total or 0)


def extract_permit_evidence(retrieved_at: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    evidence_by_id: dict[str, dict[str, Any]] = {}
    source_meta: dict[str, Any] = {}
    for source_status, resource in PERMIT_RESOURCES.items():
        source_query_totals: dict[str, int] = {}
        source_unique_records: set[str] = set()
        for query in QUERY_TERMS:
            records, total = fetch_ckan_records(resource["resource_id"], query)
            source_query_totals[query] = total
            for record in records:
                record_id = source_record_id(record, source_status)
                source_unique_records.add(record_id)
                text = record_search_text(record)
                equipment_matches = classify_equipment(text)
                if not equipment_matches:
                    continue
                address = permit_address(record)
                geo_id = clean_text(value_for(record, "geo_id", "geoid"))
                postal_code = clean_text(value_for(record, "postal", "postal_code"))
                permit_number = clean_text(value_for(record, "permit_num", "permit_number"))
                status = clean_text(value_for(record, "status", "permit_status")) or source_status.upper()
                for equipment_type, confidence in equipment_matches:
                    if equipment_type == "cooling_tower":
                        signal_type = "ACTIVE_COOLING_TOWER_PERMIT" if source_status == "active" else "COOLING_TOWER_PROJECT_HISTORY"
                    elif source_status == "active":
                        signal_type = "ACTIVE_MECHANICAL_PERMIT"
                    else:
                        signal_type = "HISTORICAL_MECHANICAL_PROJECT"
                    evidence_id = f"permit:{record_id}:{equipment_type}"
                    evidence_by_id[evidence_id] = {
                        "evidence_id": evidence_id,
                        "jurisdiction": "TORONTO_ON",
                        "source_key": f"toronto_building_permits_{source_status}",
                        "source_record_id": record_id,
                        "source_status": source_status,
                        "source_url": resource["source_url"],
                        "retrieved_at": retrieved_at,
                        "property_key": property_key_for(
                            geo_id=geo_id,
                            address=address,
                            fallback=f"permit:{record_id}",
                        ),
                        "geo_id": geo_id or None,
                        "address": address or None,
                        "postal_code": postal_code or None,
                        "organization": None,
                        "equipment_type": equipment_type,
                        "evidence_confidence": confidence,
                        "signal_type": signal_type,
                        "event_date": permit_event_date(record),
                        "priority": None,
                        "description": text,
                        "source_fields": {
                            "permit_number": permit_number or None,
                            "revision_number": clean_text(value_for(record, "revision_num", "revision_number")) or None,
                            "permit_type": clean_text(value_for(record, "permit_type")) or None,
                            "status": status,
                            "application_date": clean_text(value_for(record, "application_date")) or None,
                            "issued_date": clean_text(value_for(record, "issued_date")) or None,
                            "completed_date": clean_text(value_for(record, "completed_date")) or None,
                            "current_use": clean_text(value_for(record, "current_use")) or None,
                            "proposed_use": clean_text(value_for(record, "proposed_use")) or None,
                        },
                    }
        source_meta[source_status] = {
            "resource_id": resource["resource_id"],
            "source_url": resource["source_url"],
            "query_terms": QUERY_TERMS,
            "query_totals": source_query_totals,
            "unique_records_returned_across_queries": len(source_unique_records),
        }
    return list(evidence_by_id.values()), source_meta


class RowTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[str] = []
        self._row_depth = 0
        self._row_parts: list[str] = []
        self.visible_parts: list[str] = []
        self.title_parts: list[str] = []
        self._in_title = False
        self._ignore_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"}:
            self._ignore_depth += 1
            return
        if self._ignore_depth:
            return
        if tag == "title":
            self._in_title = True
        if tag == "tr":
            self._row_depth += 1
            if self._row_depth == 1:
                self._row_parts = []
        if tag in {"br", "p", "div", "li", "td", "th", "h1", "h2", "h3"}:
            self.visible_parts.append("\n")
            if self._row_depth:
                self._row_parts.append(" | ")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"}:
            if self._ignore_depth:
                self._ignore_depth -= 1
            return
        if self._ignore_depth:
            return
        if tag == "title":
            self._in_title = False
        if tag == "tr" and self._row_depth:
            self._row_depth -= 1
            if self._row_depth == 0:
                row = clean_text(" ".join(self._row_parts).replace(" |  | ", " | "))
                if row:
                    self.rows.append(row)
                self._row_parts = []
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3"}:
            self.visible_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ignore_depth:
            return
        text = clean_text(data)
        if not text:
            return
        self.visible_parts.append(text)
        if self._in_title:
            self.title_parts.append(text)
        if self._row_depth:
            self._row_parts.append(text)

    @property
    def visible_text(self) -> str:
        text = " ".join(self.visible_parts)
        text = re.sub(r"\s*\n\s*", "\n", text)
        return re.sub(r"[ \t]+", " ", text).strip()

    @property
    def title(self) -> str:
        return clean_text(" ".join(self.title_parts))


def parse_html_page(body: bytes) -> RowTextParser:
    parser = RowTextParser()
    parser.feed(body.decode("utf-8", errors="replace"))
    return parser


def discover_tdsb_school_ids() -> tuple[list[str], dict[str, int]]:
    school_ids: set[str] = set()
    counts: dict[str, int] = {}
    patterns = [
        re.compile(r"schno/(\d{3,5})", re.I),
        re.compile(r"schno=(\d{3,5})", re.I),
    ]
    for url in TDSB_LIST_URLS:
        body = request_bytes(url)
        page = body.decode("utf-8", errors="replace")
        discovered: set[str] = set()
        for pattern in patterns:
            discovered.update(pattern.findall(page))
        counts[url] = len(discovered)
        school_ids.update(discovered)
    if len(school_ids) < TDSB_MIN_DISCOVERED_SCHOOLS:
        raise RuntimeError(
            f"TDSB school discovery returned only {len(school_ids)} unique school IDs; "
            f"minimum fail-closed threshold is {TDSB_MIN_DISCOVERED_SCHOOLS}."
        )
    return sorted(school_ids, key=int), counts


def extract_priority(text: str) -> str | None:
    match = re.search(r"\b(Urgent|High|Medium|Low)\b", text, flags=re.I)
    return match.group(1).upper() if match else None


def extract_school_name(parser: RowTextParser, school_id: str) -> str:
    title = parser.title
    if title:
        title = re.sub(r"\s*[|\-–]\s*Toronto District School Board.*$", "", title, flags=re.I)
        title = re.sub(r"\s*[|\-–]\s*TDSB.*$", "", title, flags=re.I)
        title = re.sub(r"\s*School FCI\s*", " ", title, flags=re.I)
        title = clean_text(title)
        if title and title.lower() not in {"tdsb", "toronto district school board"}:
            return title
    for line in parser.visible_text.splitlines():
        line = clean_text(line)
        if line and len(line) < 140 and "facility condition" not in line.lower() and "renewal" not in line.lower():
            return line
    return f"TDSB school {school_id}"


def extract_address(text: str) -> str | None:
    patterns = [
        re.compile(r"\bAddress\s*:?\s*([^\n]{5,160})", re.I),
        re.compile(r"\b(\d{1,6}\s+[A-Za-z0-9' .-]+(?:Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Drive|Dr|Crescent|Cres|Lane|Way|Trail|Court|Ct))\b", re.I),
    ]
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            candidate = clean_text(match.group(1))
            candidate = re.split(r"\s+(?:Phone|Telephone|Fax|Ward|Grades|Principal)\b", candidate, maxsplit=1, flags=re.I)[0]
            if candidate:
                return candidate
    return None


def relevant_rows(parser: RowTextParser) -> list[tuple[str, str, str]]:
    rows = parser.rows or parser.visible_text.splitlines()
    matches: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for raw_row in rows:
        row = clean_text(raw_row)
        if not row:
            continue
        for equipment_type, pattern, confidence in EQUIPMENT_PATTERNS:
            if pattern.search(row):
                key = (equipment_type, row.lower())
                if key not in seen:
                    seen.add(key)
                    matches.append((equipment_type, confidence, row))
    return matches


def fetch_tdsb_school_fci(school_id: str) -> tuple[str, RowTextParser]:
    url = TDSB_FCI_URL.format(school_id=school_id)
    return school_id, parse_html_page(request_bytes(url, timeout=45, retries=3))


def extract_tdsb_evidence(retrieved_at: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    school_ids, discovery_counts = discover_tdsb_school_ids()
    evidence: list[dict[str, Any]] = []
    fetch_failures: list[dict[str, str]] = []
    matched_school_count = 0
    cooling_tower_school_count = 0

    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {executor.submit(fetch_tdsb_school_fci, school_id): school_id for school_id in school_ids}
        for future in as_completed(futures):
            school_id = futures[future]
            try:
                _, parser = future.result()
            except Exception as exc:  # keep per-school failure visible; aggregate gate below
                fetch_failures.append({"school_id": school_id, "error": str(exc)[:500]})
                continue

            rows = relevant_rows(parser)
            has_cooling_tower = any(equipment_type == "cooling_tower" for equipment_type, _, _ in rows)
            if not has_cooling_tower:
                continue
            matched_school_count += 1
            cooling_tower_school_count += 1
            school_name = extract_school_name(parser, school_id)
            address = extract_address(parser.visible_text)
            property_key = f"tdsb-schno:{school_id}"

            # Once a school is explicitly confirmed by a cooling-tower renewal row, retain
            # related chiller/condenser/chemical-feed rows as supporting account intelligence.
            for index, (equipment_type, confidence, row) in enumerate(rows):
                priority = extract_priority(row)
                signal_type = "TDSB_COOLING_TOWER_RENEWAL" if equipment_type == "cooling_tower" else "TDSB_RELATED_MECHANICAL_RENEWAL"
                evidence_id = f"tdsb:{school_id}:{equipment_type}:{index}"
                evidence.append(
                    {
                        "evidence_id": evidence_id,
                        "jurisdiction": "TORONTO_ON",
                        "source_key": "tdsb_facility_condition_renewal",
                        "source_record_id": school_id,
                        "source_status": "2025_FCI",
                        "source_url": TDSB_FCI_URL.format(school_id=school_id),
                        "retrieved_at": retrieved_at,
                        "property_key": property_key,
                        "geo_id": None,
                        "address": address,
                        "postal_code": None,
                        "organization": "Toronto District School Board",
                        "property_name": school_name,
                        "equipment_type": equipment_type,
                        "evidence_confidence": confidence,
                        "signal_type": signal_type,
                        "event_date": None,
                        "priority": priority,
                        "description": row,
                        "source_fields": {
                            "school_id": school_id,
                            "school_page_url": TDSB_SCHOOL_URL.format(school_id=school_id),
                        },
                    }
                )

    failure_rate = len(fetch_failures) / len(school_ids) if school_ids else 1.0
    if failure_rate > 0.10:
        raise RuntimeError(
            f"TDSB FCI retrieval failed for {len(fetch_failures)}/{len(school_ids)} schools "
            f"({failure_rate:.1%}); fail-closed threshold is 10%."
        )

    meta = {
        "source_url": "https://www.tdsb.on.ca/Community/Planning/School-Facilities/Facility-Condition-Index",
        "list_urls": TDSB_LIST_URLS,
        "discovery_counts_by_page": discovery_counts,
        "unique_school_ids_discovered": len(school_ids),
        "school_pages_failed": len(fetch_failures),
        "school_page_failure_rate": round(failure_rate, 6),
        "matched_confirmed_cooling_tower_schools": cooling_tower_school_count,
        "matched_schools_with_retained_related_rows": matched_school_count,
        "fetch_failures": fetch_failures,
    }
    return evidence, meta


def signal_rank(signal: str) -> int:
    return {
        "TDSB_COOLING_TOWER_RENEWAL": 100,
        "ACTIVE_COOLING_TOWER_PERMIT": 90,
        "ACTIVE_MECHANICAL_PERMIT": 70,
        "COOLING_TOWER_PROJECT_HISTORY": 60,
        "TDSB_RELATED_MECHANICAL_RENEWAL": 55,
        "HISTORICAL_MECHANICAL_PROJECT": 40,
    }.get(signal, 0)


def build_properties(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in evidence:
        grouped.setdefault(item["property_key"], []).append(item)

    properties: list[dict[str, Any]] = []
    for property_key, items in grouped.items():
        confirmed_tower = any(
            item["equipment_type"] == "cooling_tower" and item["evidence_confidence"] == "CONFIRMED"
            for item in items
        )
        addresses = [item.get("address") for item in items if item.get("address")]
        names = [item.get("property_name") for item in items if item.get("property_name")]
        organizations = [item.get("organization") for item in items if item.get("organization")]
        geo_ids = [item.get("geo_id") for item in items if item.get("geo_id")]
        source_keys = sorted({item["source_key"] for item in items})
        equipment_types = sorted({item["equipment_type"] for item in items})
        signals = sorted({item["signal_type"] for item in items}, key=lambda value: (-signal_rank(value), value))
        priorities = sorted({item["priority"] for item in items if item.get("priority")})
        explicit_tower_evidence = [item["evidence_id"] for item in items if item["equipment_type"] == "cooling_tower"]
        supporting_evidence = [item["evidence_id"] for item in items if item["equipment_type"] != "cooling_tower"]
        event_dates = [item["event_date"] for item in items if item.get("event_date")]
        properties.append(
            {
                "property_key": property_key,
                "jurisdiction": "TORONTO_ON",
                "tower_status": "CONFIRMED" if confirmed_tower else "NO_TOWER_ASSERTION",
                "address": addresses[0] if addresses else None,
                "property_name": names[0] if names else None,
                "organization": organizations[0] if organizations else None,
                "geo_id": geo_ids[0] if geo_ids else None,
                "equipment_types": equipment_types,
                "commercial_signals": signals,
                "renewal_priorities": priorities,
                "latest_source_event_date": max(event_dates) if event_dates else None,
                "source_keys": source_keys,
                "evidence_count": len(items),
                "explicit_tower_evidence_ids": explicit_tower_evidence,
                "supporting_evidence_ids": supporting_evidence,
            }
        )

    properties.sort(
        key=lambda item: (
            0 if item["tower_status"] == "CONFIRMED" else 1,
            -max((signal_rank(signal) for signal in item["commercial_signals"]), default=0),
            item.get("address") or item.get("property_name") or item["property_key"],
        )
    )
    return properties


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            serialized = dict(row)
            for key, value in list(serialized.items()):
                if isinstance(value, (list, dict)):
                    serialized[key] = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
            writer.writerow(serialized)


def validate_outputs(evidence: list[dict[str, Any]], properties: list[dict[str, Any]], source_meta: dict[str, Any]) -> None:
    if not source_meta.get("permits", {}).get("active") or not source_meta.get("permits", {}).get("cleared"):
        raise RuntimeError("Both active and cleared Toronto permit sources are required")
    if source_meta.get("tdsb", {}).get("unique_school_ids_discovered", 0) < TDSB_MIN_DISCOVERED_SCHOOLS:
        raise RuntimeError("TDSB discovery threshold was not met")
    if len({item["evidence_id"] for item in evidence}) != len(evidence):
        raise RuntimeError("Duplicate evidence_id values detected")
    if len({item["property_key"] for item in properties}) != len(properties):
        raise RuntimeError("Duplicate property_key values detected")
    for item in properties:
        if item["tower_status"] == "CONFIRMED" and not item["explicit_tower_evidence_ids"]:
            raise RuntimeError(f"Confirmed property has no explicit tower evidence: {item['property_key']}")
        if item["tower_status"] != "CONFIRMED" and item["explicit_tower_evidence_ids"]:
            raise RuntimeError(f"Unconfirmed property contains explicit tower evidence: {item['property_key']}")


def build(output_dir: Path) -> dict[str, Any]:
    retrieved_at = utc_now()
    permit_evidence, permit_meta = extract_permit_evidence(retrieved_at)
    tdsb_evidence, tdsb_meta = extract_tdsb_evidence(retrieved_at)
    evidence = permit_evidence + tdsb_evidence
    evidence.sort(key=lambda item: (item["property_key"], item["source_key"], item["evidence_id"]))
    properties = build_properties(evidence)
    source_meta = {"permits": permit_meta, "tdsb": tdsb_meta}
    validate_outputs(evidence, properties, source_meta)

    confirmed = [item for item in properties if item["tower_status"] == "CONFIRMED"]
    confirmed_from_permits = {
        item["property_key"]
        for item in evidence
        if item["source_key"].startswith("toronto_building_permits_")
        and item["equipment_type"] == "cooling_tower"
        and item["evidence_confidence"] == "CONFIRMED"
    }
    confirmed_from_tdsb = {
        item["property_key"]
        for item in evidence
        if item["source_key"] == "tdsb_facility_condition_renewal"
        and item["equipment_type"] == "cooling_tower"
        and item["evidence_confidence"] == "CONFIRMED"
    }
    active_tower_properties = {
        item["property_key"]
        for item in evidence
        if item["signal_type"] == "ACTIVE_COOLING_TOWER_PERMIT"
    }

    summary = {
        "schema_version": "toronto-poc-0.1",
        "generated_at": retrieved_at,
        "jurisdiction": "TORONTO_ON",
        "status": "EXPERIMENTAL_POC",
        "evidence_contract": {
            "confirmed_tower": "Only public-source text explicitly matching cooling tower/cooling towers.",
            "related_equipment": "Evaporative condenser is confirmed related equipment but is not relabeled as a cooling tower.",
            "supporting": "Chiller, condenser-water, and chemical-feed references are supporting commercial/mechanical context only.",
            "absence": "No matching record is not evidence that a property lacks a cooling tower.",
        },
        "counts": {
            "evidence_rows": len(evidence),
            "unique_properties_with_any_retained_evidence": len(properties),
            "confirmed_cooling_tower_properties": len(confirmed),
            "confirmed_cooling_tower_properties_from_permits": len(confirmed_from_permits),
            "confirmed_cooling_tower_properties_from_tdsb": len(confirmed_from_tdsb),
            "active_permit_confirmed_cooling_tower_properties": len(active_tower_properties),
            "properties_with_no_tower_assertion_but_related_supporting_evidence": len(properties) - len(confirmed),
        },
        "sources": source_meta,
        "query_terms": QUERY_TERMS,
    }

    temp_dir = output_dir.parent / f".{output_dir.name}.tmp"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    (temp_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (temp_dir / "evidence.json").write_text(json.dumps({"metadata": summary, "evidence": evidence}, indent=2, ensure_ascii=False), encoding="utf-8")
    (temp_dir / "properties.json").write_text(json.dumps({"metadata": summary, "properties": properties}, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(
        temp_dir / "properties.csv",
        properties,
        [
            "property_key",
            "tower_status",
            "address",
            "property_name",
            "organization",
            "geo_id",
            "equipment_types",
            "commercial_signals",
            "renewal_priorities",
            "latest_source_event_date",
            "source_keys",
            "evidence_count",
        ],
    )
    write_csv(
        temp_dir / "evidence.csv",
        evidence,
        [
            "evidence_id",
            "source_key",
            "source_record_id",
            "source_status",
            "source_url",
            "property_key",
            "geo_id",
            "address",
            "property_name",
            "organization",
            "equipment_type",
            "evidence_confidence",
            "signal_type",
            "event_date",
            "priority",
            "description",
        ],
    )

    if output_dir.exists():
        shutil.rmtree(output_dir)
    temp_dir.rename(output_dir)
    print(json.dumps(summary["counts"], indent=2))
    print(f"Toronto POC generated at {retrieved_at}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build isolated TowerSignal Toronto public-record POC")
    parser.add_argument("--output", type=Path, default=ROOT / "data/toronto/poc/current")
    args = parser.parse_args()
    build(args.output)


if __name__ == "__main__":
    main()
