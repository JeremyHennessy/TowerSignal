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
ALLOWED_HOSTS = {"www.nyc.gov", "nyc.gov", "home4.nyc.gov", "www.health.ny.gov", "health.ny.gov", "regs.health.ny.gov"}

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
    return urlunparse((scheme, host, parsed.path, "", parsed.query, ""))


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
    # Child-link discovery is intentionally narrower than source-channel relevance.
    # Generic cooling-tower forms/templates are not public-health news or alerts.
    return bool(LEGIONELLA_RE.search(text))


def _record(*, url: str, channel: dict[str, str], title: str | None, text: str | None, content: bytes, content_type: str, discovered_from: str | None) -> dict[str, Any]:
    is_pdf = "pdf" in content_type.lower() or urlparse(url).path.lower().endswith(".pdf")
    match_text = f"{title or ''} {text or ''} {url}"
    return {
        "url": _canonical_url(url),
        "title": title,
        "agency": channel["agency"],
        "channel_key": channel["key"],
        "channel_kind": channel["kind"],
        "document_type": "PDF" if is_pdf else "HTML",
        "published_date": _published_date(match_text),
        "discovered_from": discovered_from,
        "content_sha256": hashlib.sha256(content).hexdigest(),
        "content_bytes": len(content),
        "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "match_terms": {
            "legionella": bool(LEGIONELLA_RE.search(match_text)),
            "cooling_tower": bool(COOLING_TOWER_RE.search(match_text)),
        },
    }


def collect() -> dict[str, Any]:
    source_snapshots: list[dict[str, Any]] = []
    discovered: dict[str, tuple[dict[str, str], str | None, str]] = {}

    for channel in SOURCE_CHANNELS:
        content, content_type = _fetch(channel["url"])
        parsed = _parse_html(content)
        source_snapshots.append(_record(
            url=channel["url"], channel=channel, title=parsed.title, text=parsed.text,
            content=content, content_type=content_type, discovered_from=None,
        ))
        for href, label in parsed.links:
            absolute = _canonical_url(urljoin(channel["url"], href))
            if not _allowed(absolute):
                continue
            if not _discovery_relevant(f"{label} {absolute}"):
                continue
            discovered.setdefault(absolute, (channel, label or None, channel["url"]))

    for seed in CURRENT_OFFICIAL_SEEDS:
        discovered.setdefault(_canonical_url(seed["url"]), (seed, None, seed["url"]))

    items: dict[str, dict[str, Any]] = {}
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
        items[url] = _record(
            url=url, channel=channel, title=title, text=text, content=content,
            content_type=content_type, discovered_from=discovered_from,
        )

    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    ordered_items = sorted(
        items.values(),
        key=lambda item: (item.get("published_date") or "", item.get("title") or "", item["url"]),
        reverse=True,
    )
    return {
        "schema_version": "1.0",
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
            "nys_health_item_count": sum(1 for item in ordered_items if item.get("agency") == "New York State Department of Health"),
            "mayor_office_item_count": sum(1 for item in ordered_items if item.get("agency") == "NYC Mayor's Office"),
        },
        "evidence_semantics": {
            "scope": "Official NYC Health, NYC Mayor's Office and NYSDOH public channels only. Child-link discovery is restricted to explicit Legionnaires disease, Legionella or legionellosis references so generic cooling-tower forms are not misclassified as news/alerts.",
            "property_link": "This feed is not attached to a TowerSignal property merely because a building lies in an affected ZIP code. Property attribution requires an explicit published building/tower identity and a separate verified resolver.",
            "scoring": "Public-health alerts and news do not modify TowerSignal Priority Score in this build.",
            "failures": "Per-item retrieval failures are recorded and must remain visible; a failed source is never treated as an empty source.",
        },
    }
