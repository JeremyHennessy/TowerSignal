from __future__ import annotations

import argparse
import io
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from pypdf import PdfReader

from toronto_market_common import (
    clean_text, is_city_of_toronto_url, read_json, request_bytes, sha256_bytes,
    utc_now, write_json,
)

ROOT = Path(__file__).resolve().parents[1]
DOC_EXTENSIONS = (".pdf",)
DOC_HINT = re.compile(r"(document|attachment|download|support|drawing|plan|study|report|noise|energy|mechanical|hvac|equipment)", re.I)
CATEGORIES = [
    ("MECHANICAL_DRAWING", re.compile(r"\b(mechanical|hvac|heating|cooling|plumbing)\b.*\b(draw|drawing|plan|schedule)\b|\bm[- ]?\d{1,3}\b", re.I | re.S)),
    ("ENERGY_STUDY", re.compile(r"\b(energy model|energy modelling|energy study|energy report|energy efficiency|green standard|tgs)\b", re.I)),
    ("NOISE_STUDY", re.compile(r"\b(noise|acoustic|acoustical|vibration)\b.*\b(study|report|assessment)\b", re.I | re.S)),
    ("PLANNING_REPORT", re.compile(r"\b(planning justification|planning rationale|planning report|planning opinion|urban design)\b", re.I)),
    ("EQUIPMENT_PLAN", re.compile(r"\b(equipment|rooftop unit|rtu|chiller|cooling tower|condenser|boiler)\b.*\b(plan|schedule|drawing|specification)\b", re.I | re.S)),
]
SIGNALS = {
    "cooling_tower": re.compile(r"\bcooling\s+towers?\b", re.I),
    "evaporative_condenser": re.compile(r"\bevaporative\s+condensers?\b", re.I),
    "chiller": re.compile(r"\bchillers?\b", re.I),
    "condenser_water": re.compile(r"\bcondenser\s+water\b", re.I),
    "water_treatment": re.compile(r"\bwater\s+treatment\b", re.I),
    "legionella": re.compile(r"\blegionella\b", re.I),
}
ROLE_RE = re.compile(
    r"\b(owner|property manager|property management|mechanical contractor|mechanical engineer|mechanical consultant|contractor|engineer|architect|consultant|applicant)\b"
    r"\s*(?:[:\-]|is|by)\s*([A-Z][A-Za-z0-9&.,'()/ \-]{2,120})",
    re.I,
)


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            self.links.append((self._href, clean_text(" ".join(self._text))))
            self._href = None
            self._text = []


def application_url(app: dict[str, Any]) -> str:
    direct = clean_text(app.get("AIC_URL"))
    if direct:
        return direct
    encrypted = clean_text(app.get("AIC_ENCRYPTED_VALUE"))
    if encrypted:
        return f"https://secure.toronto.ca/AIC/index.do?folderRsn={encrypted}"
    return ""


def discover_documents(url: str) -> tuple[list[dict[str, str]], str]:
    body = request_bytes(url, timeout=60, max_bytes=5_000_000)
    html = body.decode("utf-8", errors="replace")
    parser = LinkParser()
    parser.feed(html)
    docs: dict[str, dict[str, str]] = {}
    for href, label in parser.links:
        absolute = urljoin(url, href)
        path = urlparse(absolute).path.lower()
        if not is_city_of_toronto_url(absolute):
            continue
        if path.endswith(DOC_EXTENSIONS) or DOC_HINT.search(href) or DOC_HINT.search(label):
            if not path.endswith(DOC_EXTENSIONS) and not re.search(r"(download|document|attachment)", href, re.I):
                continue
            docs[absolute] = {"url": absolute, "label": label}
    for match in re.findall(r'''https?://[^"'<>\\\s]+?\.pdf(?:\?[^"'<>\\\s]*)?''', html, flags=re.I):
        absolute = match.replace("\\u0026", "&")
        if is_city_of_toronto_url(absolute):
            docs.setdefault(absolute, {"url": absolute, "label": ""})
    return list(docs.values()), sha256_bytes(body)


def pdf_text_and_metadata(data: bytes, max_pages: int = 250) -> tuple[str, int, str | None, list[dict[str,Any]]]:
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        chunks: list[str] = []
        excerpts: list[dict[str,Any]] = []
        pages = min(len(reader.pages), max_pages)
        for page_number,page in enumerate(reader.pages[:pages],start=1):
            try:
                page_text=page.extract_text() or "";chunks.append(page_text)
                for name,pattern in SIGNALS.items():
                    match=pattern.search(page_text)
                    if match:
                        start=max(0,match.start()-160);end=min(len(page_text),match.end()+240)
                        excerpts.append({"signal":name,"page_number":page_number,"excerpt":clean_text(page_text[start:end])[:500]})
            except Exception:
                chunks.append("")
        return "\n".join(chunks), len(reader.pages), None, excerpts[:100]
    except Exception as exc:
        return "", 0, f"{type(exc).__name__}: {exc}", []


def classify_document(label: str, url: str, text: str) -> list[str]:
    haystack = f"{label}\n{url}\n{text[:250000]}"
    categories = [name for name, pattern in CATEGORIES if pattern.search(haystack)]
    return categories or ["OTHER"]


def role_candidates(text: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for match in ROLE_RE.finditer(text[:500000]):
        role = clean_text(match.group(1)).upper().replace(" ", "_")
        name = clean_text(match.group(2).split("\n")[0])
        name = re.split(r"\s{2,}|\b(?:Address|Tel|Phone|Email|Date|Project)\b", name, maxsplit=1, flags=re.I)[0].strip(" -,:;")
        if len(name) < 3 or len(name) > 120:
            continue
        key = (role, name.upper())
        if key in seen:
            continue
        seen.add(key)
        found.append({"role": role, "name": name, "basis": "EXTRACTED_DOCUMENT_TEXT_PATTERN"})
        if len(found) >= 25:
            break
    return found


def process_document(doc: dict[str, str]) -> dict[str, Any]:
    url = doc["url"]
    result: dict[str, Any] = {"url": url, "label": doc.get("label") or ""}
    try:
        data = request_bytes(url, timeout=120, max_bytes=60_000_000)
        result["sha256"] = sha256_bytes(data)
        result["bytes"] = len(data)
        if data[:5] != b"%PDF-":
            result.update({"parse_status": "NOT_PDF", "categories": ["OTHER"]})
            return result
        text, page_count, error, excerpts = pdf_text_and_metadata(data)
        result["page_count"] = page_count
        result["text_chars_extracted"] = len(text)
        result["parse_status"] = ("SCANNED_OR_IMAGE_ONLY" if error is None and page_count and not clean_text(text) else "PARSED") if error is None else ("ENCRYPTED" if "encrypt" in error.lower() else "CORRUPT_OR_UNREADABLE")
        if error:
            result["parse_error"] = error
        result["categories"] = classify_document(result["label"], url, text)
        result["signal_counts"] = {name: len(pattern.findall(text)) for name, pattern in SIGNALS.items()}
        result["evidence_excerpts"] = excerpts
        result["extraction_confidence"] = "TEXT_EXTRACTED" if clean_text(text) else "OCR_REQUIRED"
        result["role_candidates"] = role_candidates(text)
        return result
    except Exception as exc:
        error=f"{type(exc).__name__}: {exc}";status="OVERSIZED_SKIPPED" if "exceeded" in error.lower() else "FETCH_ERROR"
        result.update({"parse_status": status, "error": error, "categories": []})
        return result


def process_application(app: dict[str, Any]) -> dict[str, Any]:
    url = application_url(app)
    output = {
        "objectid": app.get("OBJECTID"),
        "application_number": app.get("APPLICATION_NUMBER"),
        "folder_rsn": app.get("FOLDERRSN"),
        "full_address": app.get("FULL_ADDRESS"),
        "application_type": app.get("APPLICATION_TYPE"),
        "aic_url": url or None,
        "document_count": 0,
        "documents": [],
    }
    if not url:
        output["page_status"] = "NO_AIC_URL"
        return output
    # The current AIC detail page is only a JavaScript shell. Supporting-document
    # metadata is returned by api.toronto.ca/aic/getapplicationattachments after
    # a per-session reCAPTCHA token. Do not misreport the shell as a successfully
    # scanned document page and do not bypass that access control.
    parsed_url=urlparse(url)
    if parsed_url.path.lower()=="/aic/index.do" and (parsed_url.hostname or "").lower() in {"app.toronto.ca","secure.toronto.ca"}:
        output["page_status"] = "ATTACHMENT_API_RECAPTCHA_REQUIRED"
        output["access_limitation"] = {
            "api": "https://api.toronto.ca/aic/getapplicationattachments",
            "evidence": "Official AIC client main1.0.0.js POSTs folderRsn with a g-recaptcha-response token.",
            "next_path": "Obtain an official bulk/API access agreement or permission for a reproducible non-interactive feed.",
        }
        return output
    if parsed_url.path.lower()=="/developmentapplications/associatedapplicationslist.do":
        output["page_status"]="LEGACY_REDIRECT_NO_ATTACHMENT_CATALOGUE"
        output["access_limitation"]={"evidence":"Representative legacy endpoint redirects to the generic current AIC landing page without document metadata.","next_path":"Retain catalogue identity; use an official attachment feed when available."}
        return output
    try:
        docs, page_hash = discover_documents(url)
        output["page_status"] = "FETCHED"
        output["page_sha256"] = page_hash
        output["document_count"] = len(docs)
        output["documents"] = [process_document(doc) for doc in docs]
    except Exception as exc:
        output["page_status"] = "FETCH_ERROR"
        output["page_error"] = f"{type(exc).__name__}: {exc}"
    return output


def build(market: Path, shard_index: int, shard_count: int, max_applications: int, workers: int) -> dict[str, Any]:
    app_path = market / "open_licensed" / "toronto_aic_applications.json"
    payload = read_json(app_path)
    apps = [a for a in (payload or {}).get("applications", []) if isinstance(a, dict)]
    selected = [a for a in apps if int(a.get("OBJECTID") or 0) % shard_count == shard_index]
    if max_applications > 0:
        selected = selected[:max_applications]

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(process_application, app): app for app in selected}
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda r: int(r.get("objectid") or 0))

    documents = [d for app in results for d in app.get("documents", [])]
    important = [d for d in documents if any(c != "OTHER" for c in d.get("categories", []))]
    signal_docs = [d for d in documents if any((d.get("signal_counts") or {}).values())]
    summary = {
        "schema_version": "toronto-aic-corpus-shard-0.1",
        "generated_at": utc_now(),
        "shard_index": shard_index,
        "shard_count": shard_count,
        "applications_total_source": len(apps),
        "applications_in_shard": len(selected),
        "application_pages_attempted": len(selected),
        "application_pages_fetched": sum(1 for r in results if r.get("page_status") == "FETCHED"),
        "application_page_fetch_errors": sum(1 for r in results if r.get("page_status") == "FETCH_ERROR"),
        "application_attachment_api_gated": sum(1 for r in results if r.get("page_status") == "ATTACHMENT_API_RECAPTCHA_REQUIRED"),
        "application_legacy_redirects_without_attachment_catalogue": sum(1 for r in results if r.get("page_status") == "LEGACY_REDIRECT_NO_ATTACHMENT_CATALOGUE"),
        "documents_discovered": len(documents),
        "documents_parsed": sum(1 for d in documents if d.get("parse_status") == "PARSED"),
        "documents_scanned_or_image_only": sum(1 for d in documents if d.get("parse_status") == "SCANNED_OR_IMAGE_ONLY"),
        "documents_encrypted": sum(1 for d in documents if d.get("parse_status") == "ENCRYPTED"),
        "documents_corrupt_or_unreadable": sum(1 for d in documents if d.get("parse_status") == "CORRUPT_OR_UNREADABLE"),
        "documents_oversized_skipped": sum(1 for d in documents if d.get("parse_status") == "OVERSIZED_SKIPPED"),
        "documents_not_pdf": sum(1 for d in documents if d.get("parse_status") == "NOT_PDF"),
        "documents_fetch_errors": sum(1 for d in documents if d.get("parse_status") == "FETCH_ERROR"),
        "target_document_count": len(important),
        "documents_with_mechanical_signals": len(signal_docs),
        "document_contract": {
            "scope": "Supporting-document links discoverable from each official AIC application page; City-of-Toronto-hosted document URLs only.",
            "raw_document_persistence": "Raw PDFs are processed in-memory and are not committed to Git.",
            "tower_semantics": "Document signals are evidence candidates; this extractor does not change the existing confirmed-tower field.",
            "ocr": "No OCR in this pass. Image-only/scanned PDFs can have zero extracted text and are reported as such.",
        },
        "applications": results,
    }
    out = market / "work" / f"aic_corpus_shard_{shard_index}.json"
    write_json(out, summary)
    print(json.dumps({k: summary[k] for k in summary if k not in {"applications", "document_contract"}}, indent=2))
    return summary


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--market", type=Path, default=ROOT / "data/toronto/market/current")
    p.add_argument("--shard-index", type=int, required=True)
    p.add_argument("--shard-count", type=int, required=True)
    p.add_argument("--max-applications", type=int, default=0)
    p.add_argument("--workers", type=int, default=6)
    args = p.parse_args()
    build(args.market, args.shard_index, args.shard_count, args.max_applications, args.workers)


if __name__ == "__main__":
    main()
