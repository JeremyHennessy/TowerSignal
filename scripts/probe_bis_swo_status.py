from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://a810-bisweb.nyc.gov/bisweb/PropertyProfileOverviewServlet"
USER_AGENT = "Mozilla/5.0 (compatible; TowerSignalSourceProbe/1.0; +https://github.com/JeremyHennessy/TowerSignal)"


def visible_text(html: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def probe(bin_number: str, *, timeout: int) -> dict:
    query = urlencode({"bin": bin_number, "go4": " GO ", "requestid": "0"})
    url = f"{BASE_URL}?{query}"
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
            status_code = response.status
            content_type = response.headers.get("Content-Type")
    except Exception as exc:  # Source-contract probe must preserve the failure verbatim.
        return {
            "bin": bin_number,
            "url": url,
            "retrieved_at": retrieved_at,
            "retrieval_status": "UNAVAILABLE",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }

    html = raw.decode("utf-8", errors="replace")
    text = visible_text(html)
    upper = text.upper()
    page_contract_ok = "PROPERTY PROFILE OVERVIEW" in upper and bin_number in re.sub(r"\D", "", upper)
    if "PARTIAL STOP WORK ORDER EXISTS ON THIS PROPERTY" in upper:
        observed_banner = "PARTIAL"
    elif "STOP WORK ORDER EXISTS ON THIS PROPERTY" in upper:
        observed_banner = "FULL_OR_UNQUALIFIED"
    else:
        observed_banner = "NO_BANNER_OBSERVED"

    return {
        "bin": bin_number,
        "url": url,
        "retrieved_at": retrieved_at,
        "retrieval_status": "RETRIEVED" if page_contract_ok else "UNVERIFIED_PAGE",
        "http_status": status_code,
        "content_type": content_type,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "observed_banner": observed_banner,
        "property_profile_contract_observed": page_contract_ok,
        "source_boundary": "NO_BANNER_OBSERVED is not equivalent to NO_ACTIVE_SWO until the current BIS contract is validated.",
        "text_sample": text[:500],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only bounded probe of DOB BIS property-profile SWO banners")
    parser.add_argument("bins", nargs="+", help="Exact seven-digit NYC BIN values")
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--delay", type=float, default=2.0)
    args = parser.parse_args()

    results = []
    for index, value in enumerate(args.bins):
        bin_number = re.sub(r"\D", "", value)
        if len(bin_number) != 7:
            raise SystemExit(f"Invalid BIN: {value}")
        if index:
            time.sleep(args.delay)
        result = probe(bin_number, timeout=args.timeout)
        results.append(result)
        print(json.dumps(result, sort_keys=True), flush=True)

    print(json.dumps({
        "summary": {
            "requested": len(results),
            "retrieved": sum(item.get("retrieval_status") == "RETRIEVED" for item in results),
            "unavailable": sum(item.get("retrieval_status") == "UNAVAILABLE" for item in results),
            "full_or_unqualified_banner": sum(item.get("observed_banner") == "FULL_OR_UNQUALIFIED" for item in results),
            "partial_banner": sum(item.get("observed_banner") == "PARTIAL" for item in results),
            "no_banner_observed": sum(item.get("observed_banner") == "NO_BANNER_OBSERVED" for item in results),
        },
        "results": results,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
