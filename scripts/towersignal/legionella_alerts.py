from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
LEGIONELLA_RE = re.compile(r"\b(legionnaires?|legionella|legionellosis)\b", re.IGNORECASE)
COOLING_TOWER_RE = re.compile(r"\bcooling\s+towers?\b", re.IGNORECASE)
DATE_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+([0-3]?\d),\s+(20\d{2})\b",
    re.IGNORECASE,
)
ALLOWED_HOSTS = {
    "www.nyc.gov", "nyc.gov", "home4.nyc.gov", "www.health.ny.gov", "health.ny.gov", "regs.health.ny.gov",
    "a858-nycnotify.nyc.gov", "portal.311.nyc.gov",
}
LEGACY_URL_ALIASES = {
    "https://health.ny.gov/diseases/communicable/legionellosis.htm": "https://www.health.ny.gov/diseases/communicable/legionellosis/",
    "https://www.health.ny.gov/diseases/communicable/legionellosis.htm": "https://www.health.ny.gov/diseases/communicable/legionellosis/",
}

SOURCE_CHANNELS = (
    {
        "key": "NYC_DOH_LEGIONNAIRES_TOPIC",
        "agency": "NYC Health Department",
        "kind": "CURRENT_PUBLIC_HEALTH_TOPIC",
        "url": "https://www.nyc.gov/site/doh/health/health-topics/legionnaires-disease.page",
    },
    {
        "key": "NYC_DOH_PROVIDER_LEGIONELLOSIS",
        "agency": "NYC Health Department",
        "kind": "PROVIDER_GUIDANCE_AND_ALERT_LINKS",
        "url": "https://www.nyc.gov/site/doh/providers/health-topics/legionnaires-disease-and-legionellosis.page",
    },
    {
        "key": "NYC_DOH_HEALTH_ALERT_NETWORK",
        "agency": "NYC Health Department",
        "kind": "HEALTH_ALERT_ARCHIVE",
        "url": "https://www.nyc.gov/site/doh/providers/resources/health-alert-network.page",
    },
    {
        "key": "NYC_DOH_PRESS_RELEASES",
        "agency": "NYC Health Department",
        "kind": "PRESS_RELEASE_INDEX",
        "url": "https://www.nyc.gov/site/doh/about/press/recent-press-releases.page",
    },
    {
        "key": "NYC_DOH_COOLING_TOWER_REQUIREMENTS",
        "agency": "NYC Health Department",
        "kind": "COOLING_TOWER_REGULATORY_AND_CLUSTER_BANNER",
        "url": "https://www.nyc.gov/site/doh/business/permits-and-licenses/cooling-towers.page",
    },
    {
        "key": "NYC_MAYOR_NEWS",
        "agency": "NYC Mayor's Office",
        "kind": "MAYORAL_NEWS_INDEX",
        "url": "https://www.nyc.gov/mayors-office/news",
    },
    {
        "key": "NYC_NOTIFY_NYC_RSS",
        "agency": "NYC Emergency Management",
        "kind": "EMERGENCY_PUBLIC_HEALTH_ALERT_FEED",
        "format": "RSS",
        "url": "https://a858-nycnotify.nyc.gov/RSS/NotifyNYC?lang=en",
    },
    {
        "key": "NYC_311_LEGIONNAIRES",
        "agency": "NYC311",
        "kind": "CURRENT_PUBLIC_INFORMATION",
        "url": "https://portal.311.nyc.gov/article/?kanumber=KA-02845",
    },
    {
        "key": "NYC_311_COOLING_TOWER",
        "agency": "NYC311",
        "kind": "COOLING_TOWER_PUBLIC_INFORMATION",
        "url": "https://portal.311.nyc.gov/article/?kanumber=KA-02664",
    },
    {
        "key": "NYSDOH_LEGIONNAIRES_TOPIC",
        "agency": "New York State Department of Health",
        "kind": "STATE_DISEASE_TOPIC",
        "url": "https://www.health.ny.gov/diseases/communicable/legionellosis/",
    },
    {
        "key": "NYSDOH_LEGIONELLA_REGULATION",
        "agency": "New York State Department of Health",
        "kind": "STATE_COOLING_TOWER_REQUIREMENTS",
        "url": "https://www.health.ny.gov/environmental/water/drinking/legionella/cooling_towers.htm",
    },
    {
        "key": "NYSDOH_PROTECTION_AGAINST_LEGIONELLA",
        "agency": "New York State Department of Health",
        "kind": "STATE_REGULATORY_HUB",
        "url": "https://www.health.ny.gov/environmental/water/drinking/legionella/",
    },
)

# Current high-value official pages are explicit seeds so ingestion does not depend on an index
# being updated before a public-health response page is published.
CURRENT_OFFICIAL_SEEDS = (
    {
        "key": "NYC_DOH_CURRENT_CLUSTER_INITIAL",
        "agency": "NYC Health Department",
        "kind": "PRESS_RELEASE",
        "url": "https://www.nyc.gov/site/doh/about/press/pr2026/nyc-health-department-investigating-legionnaires-cluster-in-the-bronx.page",
    },
    {
        "key": "NYC_DOH_CURRENT_CLUSTER_REMEDIATION",
        "agency": "NYC Health Department",
        "kind": "PRESS_RELEASE",
        "url": "https://www.nyc.gov/site/doh/about/press/pr2026/nyc-health-department-orders-cooling-towers-to-be-cleaned-in-south-bronx.page",
    },
    {
        "key": "NYC_311_LEGIONNAIRES",
        "agency": "NYC311",
        "kind": "CURRENT_PUBLIC_INFORMATION",
        "url": "https://portal.311.nyc.gov/article/?kanumber=KA-02845",
    },
)


@dataclass
class ParsedPage:
    title: str | None
    text: str
    links: list[tuple[str, str]]


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_title = False
        self._title_parts: list[str] = []
        self._text_parts: list[str] = []
        self._anchor_href: str | None = None
        self._anchor_parts: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self._in_title = True
        if tag.lower() == "a":
            self._anchor_href = next((value for key, value in attrs if key.lower() == "href" and value), None)
            self._anchor_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False
        if tag.lower() == "a" and self._anchor_href:
            label = " ".join(" ".join(self._anchor_parts).split())
            self.links.append((self._anchor_href, label))
            self._anchor_href = None
            self._anchor_parts = []

    def handle_data(self, data: str) -> None:
        clean = " ".join(data.split())
        if not clean:
            return
        self._text_parts.append(clean)
        if self._in_title:
            self._title_parts.append(clean)
        if self._anchor_href is not None:
            self._anchor_parts.append(clean)

    def parsed(self) -> ParsedPage:
        title = " ".join(self._title_parts).strip() or None
        return ParsedPage(title=title, text="\n".join(self._text_parts), links=self.links)


def _canonical_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = "https" if parsed.scheme in {"http", "https"} else parsed.scheme
    host = parsed.netloc.lower()
    canonical = urlunparse((scheme, host, parsed.path, "", parsed.query, ""))
    return LEGACY_URL_ALIASES.get(canonical, canonical)


def _allowed(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() in ALLOWED_HOSTS


def _fetch(url: str, *, timeout: int = 60) -> tuple[bytes, str]:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml,application/xml,text/xml,text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.1",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read(), str(response.headers.get("Content-Type") or "")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Unable to retrieve official Legionella source {url}: {exc}") from exc


def _parse_html(content: bytes) -> ParsedPage:
    parser = _PageParser()
    parser.feed(content.decode("utf-8", errors="replace"))
    return parser.parsed()


def _published_date(text: str) -> str | None:
    match = DATE_RE.search(text)
    if not match:
        return None
    try:
        return datetime.strptime(" ".join(match.groups()), "%B %d %Y").date().isoformat()
    except ValueError:
        return None


def _feed_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).date().isoformat()
    except (TypeError, ValueError, OverflowError):
        return _published_date(value)


def _strip_html(value: str | None) -> str:
    if not value:
        return ""
    parser = _PageParser()
    parser.feed(value)
    return " ".join(parser.parsed().text.split())


def _xml_text(node: ET.Element, child_name: str) -> str | None:
    child = node.find(child_name)
    if child is not None and child.text:
        return child.text.strip() or None
    return None


def _parse_rss(content: bytes, source_url: str) -> list[dict[str, str | None]]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise RuntimeError(f"Notify NYC RSS returned invalid XML: {exc}") from exc
    items: list[dict[str, str | None]] = []
    rss_items = root.findall(".//item")
    if not rss_items:
        raise RuntimeError("Notify NYC RSS returned no <item> elements")
    for item in rss_items:
        title = _xml_text(item, "title")
        description = _strip_html(_xml_text(item, "description"))
        link = _xml_text(item, "link")
        guid = _xml_text(item, "guid")
        published = _feed_date(_xml_text(item, "pubDate"))
        items.append({
            "title": title,
            "description": description,
            "link": _canonical_url(urljoin(source_url, link)) if link else _canonical_url(source_url),
            "guid": guid,
            "published_date": published,
        })
    return items


def _relevant(text: str) -> bool:
    return bool(LEGIONELLA_RE.search(text) or COOLING_TOWER_RE.search(text))


def _discovery_relevant(text: str) -> bool:
    # Child-link discovery is intentionally narrower than source-channel relevance.
    # Generic cooling-tower forms/templates are not public-health news or alerts.
    return bool(LEGIONELLA_RE.search(text))


def _record(
    *,
    url: str,
    channel: dict[str, str],
    title: str | None,
    text: str | None,
    content: bytes,
    content_type: str,
    discovered_from: str | None,
    item_id: str | None = None,
    published_date: str | None = None,
) -> dict[str, Any]:
    canonical_url = _canonical_url(url)
    is_pdf = "pdf" in content_type.lower() or urlparse(canonical_url).path.lower().endswith(".pdf")
    match_text = f"{title or ''} {text or ''} {canonical_url}"
    return {
        "item_id": item_id or hashlib.sha256(canonical_url.encode("utf-8")).hexdigest(),
        "url": canonical_url,
        "title": title,
        "agency": channel["agency"],
        "channel_key": channel["key"],
        "channel_kind": channel["kind"],
        "document_type": "PDF" if is_pdf else "HTML",
        "published_date": published_date or _published_date(match_text),
        "discovered_from": discovered_from,
        "content_sha256": hashlib.sha256(content).hexdigest(),
        "content_bytes": len(content),
        "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "match_terms": {
            "legionella": bool(LEGIONELLA_RE.search(match_text)),
            "cooling_tower": bool(COOLING_TOWER_RE.search(match_text)),
        },
    }


def _rss_record(item: dict[str, str | None], channel: dict[str, str], source_url: str) -> dict[str, Any]:
    payload_text = "\n".join(part for part in (item.get("title"), item.get("description"), item.get("guid")) if part)
    content = payload_text.encode("utf-8")
    identity = "|".join(part for part in (item.get("guid"), item.get("published_date"), item.get("title"), item.get("link")) if part)
    item_id = "notify-nyc-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()
    record = _record(
        url=item.get("link") or source_url,
        channel=channel,
        title=item.get("title"),
        text=item.get("description"),
        content=content,
        content_type="application/rss+xml",
        discovered_from=source_url,
        item_id=item_id,
        published_date=item.get("published_date"),
    )
    record["document_type"] = "RSS_ITEM"
    return record


def collect() -> dict[str, Any]:
    source_snapshots: list[dict[str, Any]] = []
    discovered: dict[str, tuple[dict[str, str], str | None, str]] = {}
    items: dict[str, dict[str, Any]] = {}
    channel_urls = {_canonical_url(channel["url"]) for channel in SOURCE_CHANNELS}

    for channel in SOURCE_CHANNELS:
        content, content_type = _fetch(channel["url"])
        if channel.get("format") == "RSS":
            feed_items = _parse_rss(content, channel["url"])
            feed_text = "\n".join(
                f"{item.get('title') or ''} {item.get('description') or ''}"
                for item in feed_items
            )
            source_snapshots.append(_record(
                url=channel["url"], channel=channel, title="Notify NYC RSS", text=feed_text,
                content=content, content_type=content_type, discovered_from=None,
            ))
            for item in feed_items:
                if not _relevant(f"{item.get('title') or ''} {item.get('description') or ''}"):
                    continue
                record = _rss_record(item, channel, channel["url"])
                items[record["item_id"]] = record
            continue

        parsed = _parse_html(content)
        source_snapshots.append(_record(
            url=channel["url"], channel=channel, title=parsed.title, text=parsed.text,
            content=content, content_type=content_type, discovered_from=None,
        ))
        for href, label in parsed.links:
            absolute = _canonical_url(urljoin(channel["url"], href))
            if not _allowed(absolute) or absolute in channel_urls:
                continue
            if not _discovery_relevant(f"{label} {absolute}"):
                continue
            discovered.setdefault(absolute, (channel, label or None, channel["url"]))

    for seed in CURRENT_OFFICIAL_SEEDS:
        absolute = _canonical_url(seed["url"])
        if absolute not in items:
            discovered.setdefault(absolute, (seed, None, seed["url"]))

    errors: list[dict[str, str]] = []
    for url, (channel, link_label, discovered_from) in sorted(discovered.items()):
        try:
            content, content_type = _fetch(url)
        except RuntimeError as exc:
            errors.append({"url": url, "error": str(exc)})
            continue
        is_pdf = "pdf" in content_type.lower() or urlparse(url).path.lower().endswith(".pdf")
        if is_pdf:
            title = link_label
            text = link_label or ""
        else:
            parsed = _parse_html(content)
            title = parsed.title or link_label
            text = parsed.text
        if not _relevant(f"{title or ''} {text} {url}"):
            continue
        record = _record(
            url=url, channel=channel, title=title, text=text, content=content,
            content_type=content_type, discovered_from=discovered_from,
        )
        items[record["item_id"]] = record

    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    ordered_items = sorted(
        items.values(),
        key=lambda item: (item.get("published_date") or "", item.get("title") or "", item["item_id"]),
        reverse=True,
    )
    return {
        "schema_version": "1.1",
        "domain": "LEGIONELLA_PUBLIC_HEALTH_ALERTS",
        "generated_at": generated_at,
        "source_channels": source_snapshots,
        "items": ordered_items,
        "errors": errors,
        "summary": {
            "source_channel_count": len(source_snapshots),
            "discovered_relevant_item_count": len(ordered_items),
            "retrieval_error_count": len(errors),
            "nyc_health_item_count": sum(1 for item in ordered_items if item.get("agency") == "NYC Health Department"),
            "nyc_emergency_management_item_count": sum(1 for item in ordered_items if item.get("agency") == "NYC Emergency Management"),
            "nyc_311_item_count": sum(1 for item in ordered_items if item.get("agency") == "NYC311"),
            "nys_health_item_count": sum(1 for item in ordered_items if item.get("agency") == "New York State Department of Health"),
            "mayor_office_item_count": sum(1 for item in ordered_items if item.get("agency") == "NYC Mayor's Office"),
        },
        "evidence_semantics": {
            "scope": "Official NYC Health, Notify NYC / NYC Emergency Management, NYC311, NYC Mayor's Office and NYSDOH public channels only. Notify NYC messages are ingested from its official RSS feed; HTML child-link discovery is restricted to explicit Legionnaires disease, Legionella or legionellosis references so generic cooling-tower forms are not misclassified as news/alerts.",
            "property_link": "This feed is not attached to a TowerSignal property merely because a building lies in an affected ZIP code. Property attribution requires an explicit published building/tower identity and a separate verified resolver.",
            "scoring": "Public-health alerts and news do not modify TowerSignal Priority Score in this build.",
            "failures": "Per-item retrieval failures are recorded and must remain visible; a failed source is never treated as an empty source.",
            "legacy_aliases": "Known obsolete official links are canonicalized only when they resolve to an already monitored current official source URL.",
        },
    }
