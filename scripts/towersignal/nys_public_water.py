from __future__ import annotations

import re
import time
from collections import Counter
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

from towersignal.domestic_water_market import USER_AGENT, normalize_space, parse_source_date, stable_id, utc_now

SCHEMA_VERSION = "1.0"
PWS_CONTACTS_INDEX_URL = "https://www.health.ny.gov/environmental/water/drinking/pws_contacts/map_pws_contacts.htm"
CERTIFIED_OPERATORS_URL = "https://www.health.ny.gov/environmental/water/drinking/operate/certified_operators/new_york_certified_operators.htm"
LSLI_INDEX_URL = "https://www.health.ny.gov/environmental/water/drinking/service_line/"
VIOLATIONS_INDEX_URL = "https://www.health.ny.gov/environmental/water/drinking/violations/2025/map_violations_2025.htm"
COMPLIANCE_REPORT_URL = "https://www.health.ny.gov/environmental/water/drinking/violations/2025/2025_compliance_report.htm"

PWS_ID_RE = re.compile(r"\bNY\d{7}\b", re.I)


class NysPublicWaterSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class HtmlSnapshot:
    url: str
    html: str
    retrieved_at: str


class _HtmlTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self.links: list[tuple[str, str]] = []
        self.title = ""
        self.headings: list[str] = []
        self._table_depth = 0
        self._current_table: list[list[str]] | None = None
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None
        self._link_href: str | None = None
        self._link_text: list[str] | None = None
        self._title_text: list[str] | None = None
        self._heading_text: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs_dict = {key.lower(): value for key, value in attrs}
        if tag == "a":
            href = attrs_dict.get("href")
            if href:
                self._link_href = href
                self._link_text = []
        if tag == "title":
            self._title_text = []
        if tag in {"h1", "h2"}:
            self._heading_text = []
        if tag == "table":
            self._table_depth += 1
            if self._table_depth == 1:
                self._current_table = []
        elif tag == "tr" and self._table_depth and self._current_table is not None:
            self._current_row = []
        elif tag in {"td", "th"} and self._current_row is not None:
            self._current_cell = []
        elif tag == "br" and self._current_cell is not None:
            self._current_cell.append("\n")

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._current_cell.append(data)
        if self._link_text is not None:
            self._link_text.append(data)
        if self._title_text is not None:
            self._title_text.append(data)
        if self._heading_text is not None:
            self._heading_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"} and self._current_cell is not None and self._current_row is not None:
            raw = "".join(self._current_cell)
            lines = [normalize_space(part) for part in raw.splitlines() if normalize_space(part)]
            self._current_row.append("\n".join(lines))
            self._current_cell = None
        elif tag == "tr" and self._current_row is not None and self._current_table is not None:
            if any(normalize_space(cell) for cell in self._current_row):
                self._current_table.append(self._current_row)
            self._current_row = None
        elif tag == "table" and self._table_depth:
            if self._table_depth == 1 and self._current_table is not None:
                self.tables.append(self._current_table)
                self._current_table = None
            self._table_depth -= 1
        if tag == "a" and self._link_href is not None:
            self.links.append((self._link_href, normalize_space("".join(self._link_text or []))))
            self._link_href = None
            self._link_text = None
        if tag == "title" and self._title_text is not None:
            self.title = normalize_space("".join(self._title_text))
            self._title_text = None
        if tag in {"h1", "h2"} and self._heading_text is not None:
            heading = normalize_space("".join(self._heading_text))
            if heading:
                self.headings.append(heading)
            self._heading_text = None


def parse_html(html: str) -> _HtmlTableParser:
    parser = _HtmlTableParser()
    parser.feed(html)
    parser.close()
    return parser


def _fallback_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc.lower() == "www.health.ny.gov":
        return urlunparse(parsed._replace(netloc="healthweb-back.health.ny.gov"))
    return url


def fetch_html(url: str, *, retries: int = 3, timeout: int = 90) -> HtmlSnapshot:
    attempts: list[str] = [url]
    fallback = _fallback_url(url)
    if fallback != url:
        attempts.append(fallback)
    last_error: Exception | None = None
    for candidate in attempts:
        for attempt in range(retries):
            try:
                request = Request(candidate, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
                with urlopen(request, timeout=timeout) as response:
                    charset = response.headers.get_content_charset() or "utf-8"
                    html = response.read().decode(charset, errors="replace")
                if "<html" not in html.lower() and "<table" not in html.lower():
                    raise NysPublicWaterSourceError(f"Non-HTML response from {candidate}")
                return HtmlSnapshot(url=url, html=html, retrieved_at=utc_now())
            except (HTTPError, URLError, TimeoutError, UnicodeError, NysPublicWaterSourceError) as exc:
                last_error = exc
                if attempt + 1 < retries:
                    time.sleep(2**attempt)
    raise NysPublicWaterSourceError(f"Failed to retrieve NYSDOH page after fallback/retries: {url}: {last_error}")


def _normalized_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", normalize_space(value).lower()).strip()


def find_table(parser: _HtmlTableParser, required_headers: Sequence[str]) -> tuple[list[str], list[list[str]]]:
    required = [_normalized_header(value) for value in required_headers]
    for table in parser.tables:
        for index, row in enumerate(table[:5]):
            headers = [_normalized_header(cell) for cell in row]
            if all(any(req == header or req in header for header in headers) for req in required):
                return row, table[index + 1 :]
    raise NysPublicWaterSourceError(f"Required table not found: {', '.join(required_headers)}")


def _cell_map(headers: Sequence[str], row: Sequence[str]) -> dict[str, str]:
    return {_normalized_header(header): row[index] if index < len(row) else "" for index, header in enumerate(headers)}


def _first_cell(cells: Mapping[str, str], *names: str) -> str:
    for name in names:
        normalized = _normalized_header(name)
        for header, value in cells.items():
            if normalized == header or normalized in header:
                if normalize_space(value):
                    return value
    return ""


def _discover_links(html: str, index_url: str, predicate: Any) -> list[str]:
    parser = parse_html(html)
    links = {urljoin(index_url, href) for href, _ in parser.links if predicate(urljoin(index_url, href))}
    return sorted(links)


def discover_pws_contact_pages(index_html: str) -> list[str]:
    return _discover_links(
        index_html,
        PWS_CONTACTS_INDEX_URL,
        lambda url: urlparse(url).path.lower().endswith("_contacts.htm") and "map_pws_contacts" not in url.lower(),
    )


def discover_violation_pages(index_html: str) -> list[str]:
    def predicate(url: str) -> bool:
        path = urlparse(url).path.lower()
        base = path.rsplit("/", 1)[-1]
        return path.endswith("_compliance_report.htm") and base != "2025_compliance_report.htm"

    return _discover_links(index_html, VIOLATIONS_INDEX_URL, predicate)


def _pws_id(value: Any) -> str | None:
    match = PWS_ID_RE.search(normalize_space(value).upper())
    return match.group(0).upper() if match else None


def _int_value(value: Any) -> int | None:
    digits = re.sub(r"[^0-9]", "", normalize_space(value))
    return int(digits) if digits else None


def parse_pws_contact_page(html: str, *, source_url: str) -> list[dict[str, Any]]:
    parser = parse_html(html)
    headers, rows = find_table(parser, ("Public Water Supply Name", "PWS ID", "System Type", "Total Population", "Contact Information"))
    records: list[dict[str, Any]] = []
    source_heading = next((heading for heading in parser.headings if "Public" in heading and "Water" in heading), parser.title)
    for row in rows:
        cells = _cell_map(headers, row)
        pws_id = _pws_id(_first_cell(cells, "PWS ID"))
        if not pws_id:
            continue
        contact_raw = _first_cell(cells, "Contact Information")
        contact_lines = [normalize_space(line) for line in contact_raw.splitlines() if normalize_space(line)]
        records.append({
            "pws_id": pws_id,
            "pws_name": normalize_space(_first_cell(cells, "Public Water Supply Name")) or None,
            "system_type": normalize_space(_first_cell(cells, "System Type")) or None,
            "total_population": _int_value(_first_cell(cells, "Total Population")),
            "contact_information_raw": contact_raw or None,
            "contact_name_raw": contact_lines[0] if contact_lines else None,
            "contact_address_raw": "\n".join(contact_lines[1:]) if len(contact_lines) > 1 else None,
            "relationship_role": "CONTACT_FOR_PWS" if contact_raw else None,
            "relationship_evidence": "NYSDOH_PWS_DIRECTORY" if contact_raw else None,
            "operator_assignment_confidence": "NOT_PROOF_OF_OPERATOR_ROLE" if contact_raw else None,
            "source_area": source_heading or None,
            "source_url": source_url,
        })
    if not records:
        raise NysPublicWaterSourceError(f"No PWS contact rows parsed from {source_url}")
    return records


def parse_certified_operators(html: str, *, source_url: str = CERTIFIED_OPERATORS_URL) -> list[dict[str, Any]]:
    parser = parse_html(html)
    headers, rows = find_table(parser, ("County", "Name", "Certification", "Expiration", "Level Descriptions"))
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        cells = _cell_map(headers, row)
        certification = _pws_id(_first_cell(cells, "Certification"))
        if not certification:
            continue
        profile = grouped.setdefault(certification, {
            "operator_id": stable_id("nys-water-operator", certification),
            "certification_number": certification,
            "name": normalize_space(_first_cell(cells, "Name")) or None,
            "counties": set(),
            "expiration_date": parse_source_date(_first_cell(cells, "Expiration")),
            "levels": set(),
            "relationship_evidence": "QUALIFIED_OPERATOR",
            "pws_assignment_confidence": "UNLINKED_TO_PWS",
            "source_url": source_url,
        })
        county = normalize_space(_first_cell(cells, "County"))
        level = normalize_space(_first_cell(cells, "Level Descriptions"))
        if county:
            profile["counties"].add(county)
        if level:
            profile["levels"].add(level)
    result: list[dict[str, Any]] = []
    for profile in grouped.values():
        profile["counties"] = sorted(profile["counties"])
        profile["levels"] = sorted(profile["levels"])
        result.append(profile)
    if not result:
        raise NysPublicWaterSourceError("No certified operator rows parsed")
    return sorted(result, key=lambda item: str(item["certification_number"]))


def parse_lsli_index(html: str, *, source_url: str = LSLI_INDEX_URL) -> list[dict[str, Any]]:
    parser = parse_html(html)
    headers, rows = find_table(parser, ("PWS ID Number", "PWS Name", "Principal County Served"))
    result: list[dict[str, Any]] = []
    for row in rows:
        cells = _cell_map(headers, row)
        pws_id = _pws_id(_first_cell(cells, "PWS ID Number"))
        if not pws_id:
            continue
        result.append({
            "pws_id": pws_id,
            "pws_name": normalize_space(_first_cell(cells, "PWS Name")) or None,
            "principal_county_served": normalize_space(_first_cell(cells, "Principal County Served")) or None,
            "lead_service_line_inventory_required": True,
            "detail_url": urljoin(source_url.rstrip("/") + "/", f"{pws_id}.htm"),
            "source_url": source_url,
        })
    if not result:
        raise NysPublicWaterSourceError("No lead service line inventory index rows parsed")
    return result


def parse_violation_page(html: str, *, source_url: str) -> list[dict[str, Any]]:
    parser = parse_html(html)
    headers, rows = find_table(parser, ("Name (PWS ID)", "Type", "Violation Type", "Contaminant(s)", "Months Covered", "Status"))
    source_heading = next((heading for heading in parser.headings if "Compliance Report" in heading), parser.title)
    result: list[dict[str, Any]] = []
    for row in rows:
        cells = _cell_map(headers, row)
        name_cell = _first_cell(cells, "Name (PWS ID)")
        pws_id = _pws_id(name_cell)
        if not pws_id:
            continue
        pws_name = normalize_space(PWS_ID_RE.sub("", name_cell).replace("()", "").strip(" ()")) or None
        violation_type = normalize_space(_first_cell(cells, "Violation Type")) or None
        contaminants = normalize_space(_first_cell(cells, "Contaminant(s)")) or None
        months = normalize_space(_first_cell(cells, "Months Covered")) or None
        status = normalize_space(_first_cell(cells, "Status")) or None
        result.append({
            "violation_id": stable_id("nys-pws-violation", "2025", pws_id, violation_type, contaminants, months, status, source_url),
            "calendar_year": 2025,
            "pws_id": pws_id,
            "pws_name": pws_name,
            "system_type": normalize_space(_first_cell(cells, "Type")) or None,
            "violation_type": violation_type,
            "contaminants": contaminants,
            "months_covered": months,
            "status": status,
            "source_area": source_heading or None,
            "source_url": source_url,
        })
    return result


def build_pws_profiles(contact_records: Sequence[Mapping[str, Any]], lsli_records: Sequence[Mapping[str, Any]], violations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for record in contact_records:
        pws_id = str(record["pws_id"])
        profile = grouped.setdefault(pws_id, {
            "pws_id": pws_id,
            "names": Counter(),
            "system_types": Counter(),
            "populations": Counter(),
            "contacts": [],
            "source_areas": set(),
            "lead_service_line_inventory_required": False,
            "lead_service_line_inventory_principal_county": None,
            "lead_service_line_inventory_detail_url": None,
            "violation_count_2025": 0,
            "violation_status_counts_2025": Counter(),
            "violation_type_counts_2025": Counter(),
        })
        if record.get("pws_name"):
            profile["names"][str(record["pws_name"])] += 1
        if record.get("system_type"):
            profile["system_types"][str(record["system_type"])] += 1
        if record.get("total_population") is not None:
            profile["populations"][int(record["total_population"])] += 1
        if record.get("source_area"):
            profile["source_areas"].add(str(record["source_area"]))
        contact_raw = normalize_space(record.get("contact_information_raw"))
        if contact_raw and all(normalize_space(existing.get("contact_information_raw")) != contact_raw for existing in profile["contacts"]):
            profile["contacts"].append({
                "contact_name_raw": record.get("contact_name_raw"),
                "contact_address_raw": record.get("contact_address_raw"),
                "contact_information_raw": record.get("contact_information_raw"),
                "relationship_role": "CONTACT_FOR_PWS",
                "operator_assignment_confidence": "NOT_PROOF_OF_OPERATOR_ROLE",
                "source_url": record.get("source_url"),
            })
    for record in lsli_records:
        pws_id = str(record["pws_id"])
        profile = grouped.get(pws_id)
        if not profile:
            continue
        profile["lead_service_line_inventory_required"] = True
        profile["lead_service_line_inventory_principal_county"] = record.get("principal_county_served")
        profile["lead_service_line_inventory_detail_url"] = record.get("detail_url")
    for record in violations:
        profile = grouped.get(str(record["pws_id"]))
        if not profile:
            continue
        profile["violation_count_2025"] += 1
        if record.get("status"):
            profile["violation_status_counts_2025"][str(record["status"])] += 1
        if record.get("violation_type"):
            profile["violation_type_counts_2025"][str(record["violation_type"])] += 1
    result: list[dict[str, Any]] = []
    for profile in grouped.values():
        names: Counter[str] = profile.pop("names")
        system_types: Counter[str] = profile.pop("system_types")
        populations: Counter[int] = profile.pop("populations")
        profile["pws_name"] = names.most_common(1)[0][0] if names else None
        profile["observed_name_variants"] = [{"value": value, "count": count} for value, count in names.most_common()]
        profile["system_type"] = system_types.most_common(1)[0][0] if system_types else None
        profile["observed_system_type_variants"] = [{"value": value, "count": count} for value, count in system_types.most_common()]
        profile["total_population"] = populations.most_common(1)[0][0] if populations else None
        profile["observed_population_variants"] = [{"value": value, "count": count} for value, count in populations.most_common()]
        profile["source_areas"] = sorted(profile["source_areas"])
        profile["contact_count"] = len(profile["contacts"])
        profile["violation_status_counts_2025"] = dict(sorted(profile["violation_status_counts_2025"].items()))
        profile["violation_type_counts_2025"] = dict(sorted(profile["violation_type_counts_2025"].items()))
        result.append(profile)
    return sorted(result, key=lambda item: str(item["pws_id"]))


def build_payload() -> dict[str, Any]:
    generated_at = utc_now()
    pws_index = fetch_html(PWS_CONTACTS_INDEX_URL)
    pws_pages = discover_pws_contact_pages(pws_index.html)
    if len(pws_pages) < 50:
        raise NysPublicWaterSourceError(f"Implausibly few PWS contact pages discovered: {len(pws_pages)}")
    contact_records: list[dict[str, Any]] = []
    for url in pws_pages:
        snapshot = fetch_html(url)
        contact_records.extend(parse_pws_contact_page(snapshot.html, source_url=url))

    operator_snapshot = fetch_html(CERTIFIED_OPERATORS_URL)
    operators = parse_certified_operators(operator_snapshot.html)

    lsli_snapshot = fetch_html(LSLI_INDEX_URL)
    lsli_records = parse_lsli_index(lsli_snapshot.html)

    violation_index = fetch_html(VIOLATIONS_INDEX_URL)
    violation_pages = discover_violation_pages(violation_index.html)
    if len(violation_pages) < 50:
        raise NysPublicWaterSourceError(f"Implausibly few 2025 violation pages discovered: {len(violation_pages)}")
    violations: list[dict[str, Any]] = []
    for url in violation_pages:
        snapshot = fetch_html(url)
        violations.extend(parse_violation_page(snapshot.html, source_url=url))

    profiles = build_pws_profiles(contact_records, lsli_records, violations)
    pws_ids = {row["pws_id"] for row in profiles}
    lsli_ids = {row["pws_id"] for row in lsli_records}
    violation_ids = {row["pws_id"] for row in violations}
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "domain": "NYS_PUBLIC_WATER_SYSTEMS",
        "source_year": 2026,
        "violation_calendar_year": 2025,
        "evidence_semantics": {
            "pws_contacts": "NYSDOH directory contacts are CONTACT_FOR_PWS only. A listed contact is not automatically an owner, operator, laboratory or service contractor.",
            "certified_operators": "Certification is QUALIFIED_OPERATOR evidence only; the statewide list does not assign the operator to a PWS.",
            "lsli_index": "Index proves that a PWS is subject to the lead service line inventory requirement. Detail pages are a later source for owner/licensed-operator-of-record evidence.",
            "violations": "2025 NYSDOH violation rows are compliance observations tied by authoritative PWSID.",
        },
        "summary": {
            "pws_contact_page_count": len(pws_pages),
            "pws_contact_record_count": len(contact_records),
            "pws_system_count": len(profiles),
            "pws_system_type_counts": dict(sorted(Counter(str(row.get("system_type") or "UNKNOWN") for row in profiles).items())),
            "certified_operator_count": len(operators),
            "lsli_required_system_count": len(lsli_records),
            "lsli_matched_pws_count": len(pws_ids & lsli_ids),
            "lsli_unmatched_pws_count": len(lsli_ids - pws_ids),
            "violation_page_count": len(violation_pages),
            "violation_count_2025": len(violations),
            "systems_with_violations_2025": len(violation_ids),
            "violation_matched_pws_count": len(pws_ids & violation_ids),
            "violation_unmatched_pws_count": len(violation_ids - pws_ids),
            "violation_status_counts_2025": dict(sorted(Counter(str(row.get("status") or "UNKNOWN") for row in violations).items())),
        },
        "source_health": [
            {"source": "NYSDOH_PWS_DIRECTORY", "status": "HEALTHY", "index_url": PWS_CONTACTS_INDEX_URL, "retrieved_at": pws_index.retrieved_at, "page_count": len(pws_pages), "record_count": len(contact_records), "pagination_complete": True, "schema_valid": True},
            {"source": "NYSDOH_CERTIFIED_OPERATORS", "status": "HEALTHY", "url": CERTIFIED_OPERATORS_URL, "retrieved_at": operator_snapshot.retrieved_at, "record_count": len(operators), "pagination_complete": True, "schema_valid": True},
            {"source": "NYSDOH_LSLI_INDEX", "status": "HEALTHY", "url": LSLI_INDEX_URL, "retrieved_at": lsli_snapshot.retrieved_at, "record_count": len(lsli_records), "pagination_complete": True, "schema_valid": True},
            {"source": "NYSDOH_2025_VIOLATIONS", "status": "HEALTHY", "index_url": VIOLATIONS_INDEX_URL, "report_url": COMPLIANCE_REPORT_URL, "retrieved_at": violation_index.retrieved_at, "page_count": len(violation_pages), "record_count": len(violations), "pagination_complete": True, "schema_valid": True},
        ],
        "pws_systems": profiles,
        "pws_contacts": contact_records,
        "certified_operators": operators,
        "lsli_index": lsli_records,
        "violations_2025": violations,
    }
