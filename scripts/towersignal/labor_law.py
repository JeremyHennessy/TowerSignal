from __future__ import annotations

import hashlib
import html
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Iterable

from .fetch import SourceFetchError

LABOR_LAW_DATASET_ID = "NYS_OFFICIAL_REPORTS_LABOR_LAW_PUBLISHED_DECISIONS"
LABOR_LAW_SOURCE_URL = "https://www.nycourts.gov/reporter/RSS.shtml"
LABOR_LAW_FEEDS = {
    "APP_DIV_FIRST": "https://www.nycourts.gov/reporter/RSS/AD1st.xml",
    "APP_DIV_SECOND": "https://www.nycourts.gov/reporter/RSS/AD2d.xml",
    "SELECTED_TRIAL": "https://www.nycourts.gov/reporter/RSS/misc.xml",
}
MAX_ITEMS_PER_FEED = 80

_ADDRESS_EXPR = (
    r"\d{1,5}\s+(?:East|West|North|South|E\.?|W\.?|N\.?|S\.?)?\s*"
    r"[A-Z][A-Za-z0-9 .\'\-]{1,70}\s+"
    r"(?:Street|St\.?|Avenue|Ave\.?|Road|Rd\.?|Boulevard|Blvd\.?|Place|Pl\.?|Lane|Ln\.?|Drive|Dr\.?|Broadway)"
)
ADDRESS_RE = re.compile(r"\b" + _ADDRESS_EXPR + r"\b", re.I)
SUBJECT_ADDRESS_PATTERNS = (
    re.compile(r"(?:premises|property|building|construction\s+site|work\s*site|worksite|project)\s+(?:located\s+|situated\s+)?(?:at|on)\s+(?P<address>" + _ADDRESS_EXPR + r")\b", re.I),
    re.compile(r"(?:working|performing\s+work|employed)\s+(?:at|on)\s+(?:the\s+)?(?:premises|property|building|construction\s+site|work\s*site|worksite|project)?\s*(?:located\s+)?(?:at|on)?\s*(?P<address>" + _ADDRESS_EXPR + r")\b", re.I),
    re.compile(r"(?:accident|incident|injur(?:y|ies)|fall)\s+(?:occurred|happened|took\s+place)\s+(?:at|on)\s+(?:the\s+)?(?:premises|property|building|construction\s+site|work\s*site|worksite|project)?\s*(?:located\s+)?(?:at|on)?\s*(?P<address>" + _ADDRESS_EXPR + r")\b", re.I),
)
INDEX_RE = re.compile(r"(?:INDEX\s+NO\.?|Index\s+No\.?)\s*[:#]?\s*([0-9A-Za-z/\-]+)", re.I)
CASE_RE = re.compile(r"(?:Case\s+No\.?)\s*[:#]?\s*([0-9A-Za-z/\-]+)", re.I)
NYSCEF_RE = re.compile(r"NYSCEF\s+DOC\.\s+NO\.\s*([0-9]+)", re.I)
SECTIONS_RE = re.compile(r"Labor\s+Law\s*(?:§§?|sections?)?\s*([0-9(),\s]+)", re.I)

SUFFIXES = {
    "STREET": "ST", "ST": "ST", "AVENUE": "AVE", "AVE": "AVE",
    "ROAD": "RD", "RD": "RD", "BOULEVARD": "BLVD", "BLVD": "BLVD",
    "PLACE": "PL", "PL": "PL", "LANE": "LN", "LN": "LN",
    "DRIVE": "DR", "DR": "DR", "EAST": "E", "WEST": "W",
    "NORTH": "N", "SOUTH": "S",
}


def normalize_property_address(value: Any) -> str | None:
    text = str(value or "").upper().strip()
    if not text:
        return None
    text = re.sub(r"[^A-Z0-9 ]+", " ", text)
    tokens = [SUFFIXES.get(token, token) for token in text.split()]
    normalized = " ".join(tokens)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized or None


def normalize_publication_date(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).date().isoformat()


def _fetch_bytes(url: str, *, attempts: int = 4, timeout: int = 90) -> tuple[bytes, str | None]:
    error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "TowerSignal-official-source/1.0"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read(), response.headers.get("Content-Type")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            error = exc
            if attempt < attempts:
                time.sleep(min(2 ** attempt, 8))
    raise SourceFetchError(f"Unable to retrieve official NY Courts source {url}: {error}")


def _clean_html(raw: bytes) -> str:
    decoded = raw.decode("utf-8", "ignore")
    without_tags = re.sub(r"<[^>]+>", " ", decoded)
    return html.unescape(re.sub(r"\s+", " ", without_tags)).strip()


def _stable_id(feed: str, link: str, title: str) -> str:
    return hashlib.sha256(f"{feed}|{link}|{title}".encode("utf-8")).hexdigest()[:24]


def _subject_addresses(text: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for pattern in SUBJECT_ADDRESS_PATTERNS:
        for match in pattern.finditer(text):
            raw = re.sub(r"\s+", " ", match.group("address")).strip(" ,.;")
            normalized = normalize_property_address(raw)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            left = max(0, match.start() - 120)
            right = min(len(text), match.end() + 120)
            found.append({"address": raw, "normalized_address": normalized, "context": text[left:right]})
    return found


def normalize_decision(feed: str, feed_url: str, item: dict[str, str], body: bytes, content_type: str | None) -> dict[str, Any] | None:
    text = _clean_html(body)
    if not re.search(r"Labor\s+Law", text, re.I):
        return None
    title = item.get("title", "").strip()
    link = item.get("link", "").strip()
    publication_date_raw = item.get("pub_date", "").strip()
    addresses = _subject_addresses(text)
    all_addresses = []
    for match in ADDRESS_RE.finditer(text):
        raw = re.sub(r"\s+", " ", match.group(0)).strip(" ,.;")
        normalized = normalize_property_address(raw)
        if normalized and normalized not in [row["normalized_address"] for row in all_addresses]:
            all_addresses.append({"address": raw, "normalized_address": normalized})
    subject = {row["normalized_address"] for row in addresses}
    return {
        "decision_id": _stable_id(feed, link, title),
        "feed": feed,
        "feed_url": feed_url,
        "title": title,
        "decision_url": link,
        "publication_date": normalize_publication_date(publication_date_raw),
        "publication_date_raw": publication_date_raw or None,
        "labor_law_mention_count": len(re.findall(r"Labor\s+Law", text, re.I)),
        "labor_law_sections": sorted({match.group(1).strip() for match in SECTIONS_RE.finditer(text) if match.group(1).strip()}),
        "index_numbers": sorted(set(INDEX_RE.findall(text))),
        "case_numbers": sorted(set(CASE_RE.findall(text))),
        "nyscef_document_numbers": sorted(set(NYSCEF_RE.findall(text))),
        "explicit_subject_property_candidates": addresses,
        "rejected_address_candidates": [row for row in all_addresses if row["normalized_address"] not in subject],
        "decision_content_type": content_type,
        "source": "NYS_OFFICIAL_REPORTS_PUBLISHED_DECISION",
        "evidence_class": "PUBLISHED_DECISION_PARTIAL_COVERAGE",
    }


def fetch_published_labor_law_decisions(
    *,
    max_items_per_feed: int = MAX_ITEMS_PER_FEED,
    fetcher: Callable[[str], tuple[bytes, str | None]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fetch_bytes = fetcher or _fetch_bytes
    decisions: list[dict[str, Any]] = []
    feed_rows: dict[str, Any] = {}
    retrieval_failures: list[dict[str, str]] = []
    for feed, url in LABOR_LAW_FEEDS.items():
        raw, content_type = fetch_bytes(url)
        root = ET.fromstring(raw)
        items = root.findall(".//item")
        inspected = items[:max_items_per_feed]
        labor_count = 0
        for item in inspected:
            entry = {
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "pub_date": (item.findtext("pubDate") or "").strip(),
            }
            if not entry["link"]:
                continue
            try:
                body, decision_content_type = fetch_bytes(entry["link"])
                normalized = normalize_decision(feed, url, entry, body, decision_content_type)
                if normalized:
                    decisions.append(normalized)
                    labor_count += 1
            except Exception as exc:  # fail visible but do not turn one child retrieval into a false zero
                retrieval_failures.append({"feed": feed, "decision_url": entry["link"], "error": f"{type(exc).__name__}: {exc}"})
        feed_rows[feed] = {
            "url": url,
            "content_type": content_type,
            "feed_item_count": len(items),
            "inspected_item_count": len(inspected),
            "labor_law_decision_count": labor_count,
        }
    decisions.sort(key=lambda row: (row.get("publication_date") or "", row["decision_id"]), reverse=True)
    return decisions, {
        "dataset_id": LABOR_LAW_DATASET_ID,
        "name": "New York Official Reports — Labor Law published decisions",
        "url": LABOR_LAW_SOURCE_URL,
        "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_record_count": sum(row["feed_item_count"] for row in feed_rows.values()),
        "inspected_record_count": sum(row["inspected_item_count"] for row in feed_rows.values()),
        "matched_record_count": len(decisions),
        "feed_health": feed_rows,
        "retrieval_failures": retrieval_failures,
        "source_query_scope": "Current Official Reports RSS window: all First/Second Department feed items plus selected trial-court feed items, bounded to the newest 80 per feed",
        "coverage_boundary": "Official Reports publishes all appellate decisions but only selected trial-court decisions. This is published-decision evidence, not a comprehensive Supreme Court filing or NYSCEF docket feed.",
        "current_filing_status_available": False,
    }


def merge_retained_decisions(current: list[dict[str, Any]], previous: Iterable[dict[str, Any]] = ()) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in previous:
        if isinstance(row, dict) and row.get("decision_id"):
            merged[str(row["decision_id"])] = dict(row)
    for row in current:
        merged[str(row["decision_id"])] = dict(row)
    return sorted(merged.values(), key=lambda row: (row.get("publication_date") or "", row["decision_id"]), reverse=True)


def match_decisions_to_systems(decisions: Iterable[dict[str, Any]], systems: Iterable[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    address_index: dict[str, list[dict[str, Any]]] = {}
    for system in systems:
        normalized = normalize_property_address(system.get("address"))
        if normalized:
            address_index.setdefault(normalized, []).append(system)

    by_system: dict[str, list[dict[str, Any]]] = {}
    unmatched: list[dict[str, Any]] = []
    for decision in decisions:
        matched_any = False
        for candidate in decision.get("explicit_subject_property_candidates") or []:
            normalized = candidate.get("normalized_address")
            rows = address_index.get(str(normalized), [])
            if not rows:
                unmatched.append({"decision_id": decision["decision_id"], "address": candidate.get("address"), "normalized_address": normalized, "reason": "NO_EXACT_TOWERSIGNAL_ADDRESS"})
                continue
            matched_any = True
            property_system_ids = sorted(str(row["system_id"]) for row in rows)
            for system in rows:
                by_system.setdefault(str(system["system_id"]), []).append({
                    "decision_id": decision["decision_id"],
                    "title": decision.get("title"),
                    "decision_url": decision.get("decision_url"),
                    "publication_date": decision.get("publication_date"),
                    "labor_law_sections": decision.get("labor_law_sections") or [],
                    "index_numbers": decision.get("index_numbers") or [],
                    "case_numbers": decision.get("case_numbers") or [],
                    "nyscef_document_numbers": decision.get("nyscef_document_numbers") or [],
                    "published_subject_address": candidate.get("address"),
                    "matched_normalized_address": normalized,
                    "property_system_ids": property_system_ids,
                    "match_basis": "PUBLISHED_DECISION_EXPLICIT_WORKSITE_ADDRESS_EXACT",
                    "fact_class": "CONFIRMED_FACT",
                    "evidence_confidence": "CONFIRMED",
                    "building_level_context": True,
                    "liability_claim": False,
                    "source": decision.get("source"),
                })
        if not matched_any and not (decision.get("explicit_subject_property_candidates") or []):
            unmatched.append({"decision_id": decision["decision_id"], "address": None, "normalized_address": None, "reason": "NO_EXPLICIT_SUBJECT_PROPERTY_ADDRESS"})
    for rows in by_system.values():
        rows.sort(key=lambda row: (row.get("publication_date") or "", row["decision_id"]), reverse=True)
    return by_system, unmatched
