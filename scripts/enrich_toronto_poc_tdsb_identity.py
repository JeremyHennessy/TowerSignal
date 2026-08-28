from __future__ import annotations

import argparse
import csv
import html
import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
TDSB_SCHOOL_URL = "https://www.tdsb.on.ca/Find-your/Schools/schno/{school_id}"
USER_AGENT = "TowerSignal-Toronto-POC/0.1 (+https://github.com/JeremyHennessy/TowerSignal)"


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
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
        if tag in {"br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

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
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ignore_depth:
            return
        text = clean_text(data)
        if not text:
            return
        self.parts.append(text)
        if self._in_title:
            self.title_parts.append(text)

    @property
    def visible_text(self) -> str:
        text = " ".join(self.parts)
        text = re.sub(r"\s*\n\s*", "\n", text)
        return re.sub(r"[ \t]+", " ", text).strip()

    @property
    def title(self) -> str:
        return clean_text(" ".join(self.title_parts))


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", html.unescape(str(value))).strip()


def request_bytes(url: str, *, timeout: int = 45, retries: int = 3) -> bytes:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
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


def parse_page(body: bytes) -> VisibleTextParser:
    parser = VisibleTextParser()
    parser.feed(body.decode("utf-8", errors="replace"))
    return parser


def canonical_school_name(parser: VisibleTextParser, school_id: str) -> str:
    title = parser.title
    title = re.sub(r"\s*\(\s*GR\..*$", "", title, flags=re.I)
    title = re.sub(r"\s*[|\-–]\s*Toronto District School Board.*$", "", title, flags=re.I)
    title = clean_text(title)
    invalid = {"", "tdsb", "toronto district school board", "renewal needs backlog", "school fci"}
    if title.lower() in invalid:
        raise RuntimeError(f"TDSB school {school_id} canonical page did not expose a usable title: {parser.title!r}")
    return title


def canonical_address(parser: VisibleTextParser, school_id: str) -> str:
    text = parser.visible_text
    patterns = [
        re.compile(r"(?:^|\n)Address\s*:?\s*(\d{1,6}[^\n]{4,180})", re.I),
        re.compile(
            r"\b(\d{1,6}\s+[A-Za-z0-9' .-]+(?:Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Drive|Dr|Crescent|Cres|Lane|Way|Trail|Court|Ct)[^\n]{0,100})",
            re.I,
        ),
    ]
    for pattern in patterns:
        match = pattern.search(text)
        if not match:
            continue
        candidate = clean_text(match.group(1))
        candidate = re.split(
            r"\s+(?:View Website|View School|Phone|Telephone|Fax|Email|Principal|Vice-Principal|Superintendent|Ward|Grades)\b",
            candidate,
            maxsplit=1,
            flags=re.I,
        )[0]
        if re.match(r"^\d{1,6}\s+", candidate) and len(candidate) >= 8:
            return candidate
    raise RuntimeError(f"TDSB school {school_id} canonical page did not expose a usable street address")


def fetch_identity(school_id: str) -> dict[str, str]:
    source_url = TDSB_SCHOOL_URL.format(school_id=school_id)
    parser = parse_page(request_bytes(source_url))
    return {
        "school_id": school_id,
        "property_name": canonical_school_name(parser, school_id),
        "address": canonical_address(parser, school_id),
        "identity_source_url": source_url,
    }


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


def enrich(output_dir: Path) -> dict[str, Any]:
    evidence_path = output_dir / "evidence.json"
    properties_path = output_dir / "properties.json"
    summary_path = output_dir / "summary.json"
    evidence_payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    properties_payload = json.loads(properties_path.read_text(encoding="utf-8"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    evidence = evidence_payload.get("evidence") or []
    properties = properties_payload.get("properties") or []
    school_ids = sorted(
        {
            str(item.get("source_record_id"))
            for item in evidence
            if item.get("source_key") == "tdsb_facility_condition_renewal" and item.get("source_record_id")
        },
        key=int,
    )
    if not school_ids:
        raise RuntimeError("No retained TDSB schools were available for identity enrichment")

    identities: dict[str, dict[str, str]] = {}
    for school_id in school_ids:
        identities[school_id] = fetch_identity(school_id)

    for item in evidence:
        if item.get("source_key") != "tdsb_facility_condition_renewal":
            continue
        school_id = str(item.get("source_record_id"))
        identity = identities[school_id]
        item["property_name"] = identity["property_name"]
        item["address"] = identity["address"]
        source_fields = item.setdefault("source_fields", {})
        source_fields["identity_source_url"] = identity["identity_source_url"]
        source_fields["identity_match_basis"] = "EXACT_TDSB_SCHOOL_NUMBER"

    property_by_key = {item["property_key"]: item for item in properties}
    for school_id, identity in identities.items():
        property_key = f"tdsb-schno:{school_id}"
        property_item = property_by_key.get(property_key)
        if not property_item:
            raise RuntimeError(f"Missing grouped property for matched TDSB school {school_id}")
        property_item["property_name"] = identity["property_name"]
        property_item["address"] = identity["address"]

    for school_id, identity in identities.items():
        if identity["property_name"].lower() in {"renewal needs backlog", "school fci"}:
            raise RuntimeError(f"TDSB school {school_id} retained a non-canonical property name")
        if not re.match(r"^\d{1,6}\s+", identity["address"]):
            raise RuntimeError(f"TDSB school {school_id} retained an invalid address: {identity['address']!r}")

    tdsb_meta = summary.setdefault("sources", {}).setdefault("tdsb", {})
    tdsb_meta["identity_enrichment"] = {
        "matched_school_count": len(identities),
        "match_basis": "EXACT_TDSB_SCHOOL_NUMBER",
        "canonical_page_template": TDSB_SCHOOL_URL,
        "identity_failures": 0,
    }

    evidence_payload["metadata"] = summary
    properties_payload["metadata"] = summary
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    evidence_path.write_text(json.dumps(evidence_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    properties_path.write_text(json.dumps(properties_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    write_csv(
        output_dir / "properties.csv",
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
        output_dir / "evidence.csv",
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
    print(f"Canonical TDSB identity enrichment succeeded for {len(identities)} confirmed schools")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich Toronto POC TDSB properties from canonical school pages")
    parser.add_argument("--output", type=Path, default=ROOT / "data/toronto/poc/current")
    args = parser.parse_args()
    enrich(args.output)


if __name__ == "__main__":
    main()
