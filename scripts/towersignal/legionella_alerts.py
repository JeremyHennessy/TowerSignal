from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
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
NOTIFY_TIMESTAMP_RE = re.compile(r"^(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}:\d{2})$")
ALLOWED_HOSTS = {
    "www.nyc.gov", "nyc.gov", "home4.nyc.gov", "www.health.ny.gov", "health.ny.gov", "regs.health.ny.gov",
    "a858-nycnotify.nyc.gov", "portal.311.nyc.gov",
}
LEGACY_URL_ALIASES = {
    "https://health.ny.gov/diseases/communicable/legionellosis.htm": "https://www.health.ny.gov/diseases/communicable/legionellosis/",
    "https://www.health.ny.gov/diseases/communicable/legionellosis.htm": "https://www.health.ny.gov/diseases/communicable/legionellosis/",
    "https://portal.311.nyc.gov/article/KA-02845": "https://portal.311.nyc.gov/article/?kanumber=KA-02845",
    "https://portal.311.nyc.gov/article/KA-02664": "https://portal.311.nyc.gov/article/?kanumber=KA-02664",
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
        "key": "NYC_NOTIFY_NYC",
        "agency": "NYC Emergency Management",
        "kind": "EMERGENCY_PUBLIC_HEALTH_ALERT_PAGE",
        "format": "NOTIFY_HTML",
        "url": "https://a858-nycnotify.nyc.gov/?lang=en",
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
            "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.1",
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


def _relevant(text: str) -> bool:
    return bool(LEGIONELLA_RE.search(text) or COOLING_TOWER_RE.search(text))


def _discovery_relevant(text: str) -> bool:
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


def _parse_notify_notifications(text: str) -> list[dict[str, str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    notifications: list[dict[str, str]] = []
    index = 0
    while index < len(lines):
        timestamp_match = NOTIFY_TIMESTAMP_RE.match(lines[index])
        if not timestamp_match:
            index += 1
            continue
        start = index
        index += 1
        block: list[str] = []
        while index < len(lines) and not NOTIFY_TIMESTAMP_RE.match(lines[index]):
            if lines[index].startswith("The information you want to receive"):
                break
            block.append(lines[index])
            index += 1
        title_index = next((i for i, value in enumerate(block) if value.startswith("Notify NYC -")), None)
        if title_index is None:
            continue
        title = block[title_index]
        body = " ".join(block[title_index + 1:]).strip()
        source_timestamp = lines[start]
        try:
            published_date = datetime.strptime(source_timestamp, "%m/%d/%Y %H:%M:%S").date().isoformat()
        except ValueError:
            continue
        notifications.append({
            "title": title,
            "body": body,
            "source_timestamp": source_timestamp,
            "published_date": published_date,
        })
    return notifications


def _notify_record(notification: dict[str, str], channel: dict[str, str]) -> dict[str, Any]:
    payload_text = "\n".join((notification["source_timestamp"], notification["title"], notification["body"]))
    content = payload_text.encode("utf-8")
    item_id = "notify-nyc-" + hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
    record = _record(
        url=channel["url"],
        channel=channel,
        title=notification["title"],
        text=notification["body"],
        content=content,
        content_type="text/html",
        discovered_from=channel["url"],
        item_id=item_id,
        published_date=notification["published_date"],
    )
    record["document_type"] = "NOTIFY_NYC_ALERT"
    record["source_timestamp"] = notification["source_timestamp"]
    return record


def collect() -> dict[str, Any]:
    source_snapshots: list[dict[str, Any]] = []
    discovered: dict[str, tuple[dict[str, str], str | None, str]] = {}
    items: dict[str, dict[str, Any]] = {}
    channel_urls = {_canonical_url(channel["url"]) for channel in SOURCE_CHANNELS}

    for channel in SOURCE_CHANNELS:
        content, content_type = _fetch(channel["url"])
        parsed = _parse_html(content)
        source_snapshots.append(_record(
            url=channel["url"], channel=channel, title=parsed.title, text=parsed.text,
            content=content, content_type=content_type, discovered_from=None,
        ))

        if channel.get("format") == "NOTIFY_HTML":
            for notification in _parse_notify_notifications(parsed.text):
                if not _relevant(f"{notification['title']} {notification['body']}"):
                    continue
                record = _notify_record(notification, channel)
                items[record["item_id"]] = record
            continue

        for href, label in parsed.links:
            absolute = _canonical_url(urljoin(channel["url"], href))
            if not _allowed(absolute) or absolute in channel_urls:
                continue
            if not _discovery_relevant(f"{label} {absolute}"):
                continue
            discovered.setdefault(absolute, (channel, label or None, channel["url"]))

    for seed in CURRENT_OFFICIAL_SEEDS:
        absolute = _canonical_url(seed["url"])
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
            "scope": "Official NYC Health, Notify NYC / NYC Emergency Management, NYC311, NYC Mayor's Office and NYSDOH public channels only. Notify NYC messages are parsed from the live Recent Notifications page because the historically documented RSS endpoint currently returns an empty body. HTML child-link discovery is restricted to explicit Legionnaires disease, Legionella or legionellosis references so generic cooling-tower forms are not misclassified as news/alerts.",
            "notify_history": "The live Notify NYC page exposes only recent notifications. Complete retention therefore requires frequent polling plus durable merge/history storage; this collector does not claim the current page is a complete historical archive.",
            "property_link": "This feed is not attached to a TowerSignal property merely because a building lies in an affected ZIP code. Property attribution requires an explicit published building/tower identity and a separate verified resolver.",
            "scoring": "Public-health alerts and news do not modify TowerSignal Priority Score in this build.",
            "failures": "Per-item retrieval failures are recorded and must remain visible; a failed source is never treated as an empty source.",
            "legacy_aliases": "Known obsolete official links are canonicalized only when they resolve to an already monitored current official source URL.",
        },
    }