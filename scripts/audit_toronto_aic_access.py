from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

try:
    from .toronto_record_actions import aic_application_url, normalize_application_number, numeric_id
except ImportError:
    from toronto_record_actions import aic_application_url, normalize_application_number, numeric_id

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data/toronto/market/current"
WAREHOUSE = ROOT / "data/toronto/warehouse/current"
REPORT = MARKET / "aic_targeted_access_audit.json"
DETAIL_BASE = "https://www.toronto.ca/city-government/planning-development/application-details/"
ATTACHMENTS_API = "https://api.toronto.ca/aic/getapplicationattachments"
USER_AGENT = "TowerSignal-AIC-Access-Audit/1.0 (+https://github.com/JeremyHennessy/TowerSignal)"
DOC_RE = re.compile(r"(?:https?://[^\"'<>\s]+|href=[\"']([^\"']+))[\"']?", re.I)
DOC_HINT = re.compile(r"\.(?:pdf|docx?|xlsx?|zip)(?:$|[?#])|(?:document|attachment|download)", re.I)


def load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected object: {path}")
    return payload


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def fetch(url: str, *, method: str = "GET", body: bytes | None = None, headers: dict[str, str] | None = None, max_bytes: int = 2_000_000) -> dict[str, Any]:
    request_headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/json,*/*;q=0.8", **(headers or {})}
    try:
        with urlopen(Request(url, data=body, method=method, headers=request_headers), timeout=45) as response:
            data = response.read(max_bytes)
            return {
                "status": "REACHABLE",
                "http_status": response.status,
                "final_url": response.geturl(),
                "content_type": response.headers.get("Content-Type"),
                "body": data.decode("utf-8", errors="replace"),
            }
    except HTTPError as exc:
        try:
            data = exc.read(max_bytes)
        except Exception:
            data = b""
        return {"status": "HTTP_ERROR", "http_status": exc.code, "final_url": url, "body": data.decode("utf-8", errors="replace")}
    except (URLError, TimeoutError) as exc:
        return {"status": "TRANSPORT_ERROR", "http_status": None, "final_url": url, "error": str(exc), "body": ""}


def city_document_urls(html: str, base_url: str) -> list[str]:
    urls: set[str] = set()
    for href in re.findall(r"href=[\"']([^\"']+)[\"']", html, flags=re.I):
        absolute = urljoin(base_url, href.replace("&amp;", "&"))
        parsed = urlparse(absolute)
        if parsed.scheme == "https" and (parsed.hostname or "").lower().endswith("toronto.ca") and DOC_HINT.search(absolute):
            urls.add(absolute)
    for absolute in re.findall(r"https://[^\"'<>\s]+", html, flags=re.I):
        parsed = urlparse(absolute)
        if (parsed.hostname or "").lower().endswith("toronto.ca") and DOC_HINT.search(absolute):
            urls.add(absolute.replace("&amp;", "&"))
    return sorted(urls)


def flatten_city_urls(value: Any) -> set[str]:
    output: set[str] = set()
    if isinstance(value, str):
        for url in re.findall(r"https://[^\s<>\"']+", value):
            parsed = urlparse(url)
            if (parsed.hostname or "").lower().endswith("toronto.ca"):
                output.add(url.rstrip(".,);"))
    elif isinstance(value, dict):
        for item in value.values():
            output.update(flatten_city_urls(item))
    elif isinstance(value, list):
        for item in value:
            output.update(flatten_city_urls(item))
    return output


def main() -> None:
    aic_payload = load(MARKET / "open_licensed/toronto_aic_applications.json")
    applications = [row for row in aic_payload.get("applications", []) if isinstance(row, dict)]
    notices_payload = load(WAREHOUSE / "open_licensed/toronto_public_notices.json")
    notices = [row for row in notices_payload.get("planning_notices", []) if isinstance(row, dict)]
    if not applications:
        raise RuntimeError("AIC application catalogue missing")

    notice_numbers = {
        normalize_application_number(value)
        for notice in notices
        for value in (notice.get("planningApplicationNumbers") or [])
        if normalize_application_number(value)
    }
    sortable = sorted(
        [app for app in applications if aic_application_url(app)],
        key=lambda app: (normalize_application_number(app.get("APPLICATION_NUMBER")), clean(app.get("FOLDERRSN"))),
    )
    linked = [app for app in sortable if normalize_application_number(app.get("APPLICATION_NUMBER")) in notice_numbers]
    unlinked = [app for app in sortable if normalize_application_number(app.get("APPLICATION_NUMBER")) not in notice_numbers]
    sample: list[dict[str, Any]] = []
    seen: set[str] = set()
    for app in [*linked[:6], *unlinked[:6]]:
        key = clean(app.get("FOLDERRSN"))
        if key and key not in seen:
            seen.add(key)
            sample.append(app)

    detail_results = []
    direct_documents: set[str] = set()
    for app in sample:
        url = aic_application_url(app)
        if not url:
            continue
        result = fetch(url)
        docs = city_document_urls(result.get("body") or "", url) if result["status"] == "REACHABLE" else []
        direct_documents.update(docs)
        detail_results.append({
            "application_number": app.get("APPLICATION_NUMBER"),
            "folder_rsn": app.get("FOLDERRSN"),
            "property_rsn": app.get("PROPERTYRSN") or app.get("MAINPROPERTYRSN"),
            "full_address": app.get("FULL_ADDRESS"),
            "detail_url": url,
            "http_status": result.get("http_status"),
            "status": result.get("status"),
            "direct_city_document_urls": docs,
        })

    # One standard unauthenticated request documents the public transport
    # boundary. No reCAPTCHA token is fabricated, solved, replayed, or bypassed.
    probe_app = sample[0] if sample else sortable[0]
    folder_rsn = numeric_id(probe_app.get("FOLDERRSN"))
    api_probe = None
    if folder_rsn:
        body = json.dumps({"folderRsn": int(folder_rsn)}).encode("utf-8")
        probe = fetch(ATTACHMENTS_API, method="POST", body=body, headers={"Content-Type": "application/json"}, max_bytes=200_000)
        api_probe = {
            "folder_rsn": folder_rsn,
            "http_status": probe.get("http_status"),
            "status": probe.get("status"),
            "response_excerpt": clean(probe.get("body"))[:500],
            "recaptcha_token_supplied": False,
        }

    notice_document_records: list[dict[str, Any]] = []
    notice_documents: set[str] = set()
    for notice in notices:
        numbers = {normalize_application_number(value) for value in (notice.get("planningApplicationNumbers") or []) if normalize_application_number(value)}
        if not numbers:
            continue
        urls = flatten_city_urls(notice.get("backgroundInformationList")) | flatten_city_urls(notice.get("otherReferenceList"))
        urls = {url for url in urls if DOC_HINT.search(url)}
        if not urls:
            continue
        notice_documents.update(urls)
        notice_document_records.append({
            "notice_id": notice.get("noticeId"),
            "application_numbers": sorted(numbers),
            "document_urls": sorted(urls),
        })

    document_checks = []
    for url in sorted(notice_documents)[:20]:
        result = fetch(url, max_bytes=4096)
        document_checks.append({"url": url, "status": result.get("status"), "http_status": result.get("http_status"), "final_url": result.get("final_url")})

    blocked_statuses = {400, 401, 403, 429}
    api_blocked = bool(api_probe and api_probe.get("http_status") in blocked_statuses)
    status = "PARTIAL_OPEN_DOCUMENT_DISCOVERY" if direct_documents or notice_documents else "BLOCKED_EXTERNAL_ACCESS_CONTROL"
    report = {
        "schema_version": "toronto-aic-targeted-access-audit-1.0",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": status,
        "catalogue_records": len(applications),
        "applications_with_current_detail_url": len(sortable),
        "sample_size": len(detail_results),
        "sample_detail_pages_reachable": sum(item["status"] == "REACHABLE" for item in detail_results),
        "direct_documents_discovered_on_detail_pages": len(direct_documents),
        "public_notice_records_with_city_documents": len(notice_document_records),
        "public_notice_city_document_urls": len(notice_documents),
        "attachment_api_probe": api_probe,
        "attachment_api_access_control_observed": api_blocked,
        "detail_results": detail_results,
        "direct_document_urls": sorted(direct_documents),
        "public_notice_document_records": notice_document_records[:200],
        "public_notice_document_checks": document_checks,
        "evidence_contract": {
            "no_recaptcha_bypass": True,
            "direct_aic_documents": "Count only City-hosted document URLs directly exposed by the public AIC detail HTML.",
            "public_notice_documents": "Count as lawful City public-document alternatives linked by exact municipal application number; do not relabel them AIC supporting documents unless the City explicitly identifies them as such.",
            "absence_warning": "No discovered document is not evidence that an application has no supporting documents.",
        },
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in {"detail_results", "direct_document_urls", "public_notice_document_records", "public_notice_document_checks"}}, indent=2))


if __name__ == "__main__":
    main()
