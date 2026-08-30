from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from toronto_app_sources import valid_public_url

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "public/data/toronto-market.json"
REPORT = ROOT / "data/toronto/market/current/source_action_qa.json"
USER_AGENT = "TowerSignal-Toronto-Source-QA/1.0 (+https://github.com/JeremyHennessy/TowerSignal)"


def check_url(url: str, retries: int = 3) -> dict[str, Any]:
    last_error = None
    for attempt in range(retries):
        try:
            with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=30) as response:
                response.read(8192)
                return {"url": response.geturl(), "http_status": response.status, "status": "REACHABLE" if 200 <= response.status < 400 else "HTTP_ERROR"}
        except HTTPError as error:
            last_error = f"HTTP {error.code}"
            if error.code == 429 and attempt + 1 < retries:
                time.sleep(2 * (attempt + 1))
                continue
            return {"url": url, "http_status": error.code, "status": "HTTP_ERROR", "error": last_error}
        except (URLError, TimeoutError) as error:
            last_error = str(error)
            if attempt + 1 < retries:
                time.sleep(2 * (attempt + 1))
                continue
    return {"url": url, "http_status": None, "status": "TRANSPORT_ERROR", "error": last_error}


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify Toronto application source actions")
    parser.add_argument("--strict", action="store_true", help="Fail when any checked public action is unreachable")
    parser.add_argument("--record-sample-size", type=int, default=5, help="Deterministic record URLs checked per source family")
    args = parser.parse_args()
    payload = json.loads(PAYLOAD.read_text(encoding="utf-8"))
    catalogue = payload.get("source_catalog") or {}
    properties = payload.get("properties") or []
    if len(catalogue) != 13:
        raise RuntimeError(f"Expected 13 Toronto source families, found {len(catalogue)}")

    record_actions: dict[str, list[str]] = {}
    representative_records: dict[str, dict[str, Any]] = {}
    for prop in properties:
        for link in prop.get("source_links") or []:
            source = str(link.get("source_key") or "")
            representative_records.setdefault(source, {
                "property_id": prop.get("property_id"),
                "display_address": prop.get("display_address"),
                "source_record_id": link.get("source_record_id"),
            })
            if link.get("record_url"):
                record_actions.setdefault(source, []).append(str(link["record_url"]))

    source_results = {}
    failures = []
    checked_urls: dict[str, dict[str, Any]] = {}
    for source, item in sorted(catalogue.items()):
        dataset_url = valid_public_url(item.get("dataset_url"))
        if not dataset_url:
            raise RuntimeError(f"Invalid dataset action for {source}")
        checked_urls.setdefault(dataset_url, check_url(dataset_url))
        all_record_urls = sorted(set(record_actions.get(source) or []))
        if args.record_sample_size < 1:
            raise RuntimeError("--record-sample-size must be positive")
        if len(all_record_urls) <= args.record_sample_size:
            unique_record_urls = all_record_urls
        else:
            # Evenly sample the stable sorted set so large record collections do
            # not turn weekly QA into a bulk crawl of the publisher site.
            indexes = {round(i * (len(all_record_urls) - 1) / (args.record_sample_size - 1)) for i in range(args.record_sample_size)} if args.record_sample_size > 1 else {0}
            unique_record_urls = [all_record_urls[index] for index in sorted(indexes)]
        record_results = []
        for url in unique_record_urls:
            if valid_public_url(url) != url:
                raise RuntimeError(f"Invalid record action for {source}: {url}")
            checked_urls.setdefault(url, check_url(url))
            record_results.append(checked_urls[url])
        expected_level = "RECORD_AND_DATASET" if all_record_urls else "DATASET_FALLBACK"
        if item.get("link_level") != expected_level:
            raise RuntimeError(f"Source action level mismatch for {source}: expected {expected_level}")
        results = [checked_urls[dataset_url], *record_results]
        failures.extend({"source_key": source, **result} for result in results if result["status"] != "REACHABLE")
        source_results[source] = {
            "link_level": expected_level,
            "dataset_action": checked_urls[dataset_url],
            "record_actions": record_results,
            "available_unique_record_actions": len(all_record_urls),
            "checked_record_action_sample": len(record_results),
            "representative_source_record": representative_records.get(source),
            "fallback_message_required": expected_level == "DATASET_FALLBACK",
        }

    report = {
        "schema_version": "toronto-source-action-qa-1.0",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "PASSED" if not failures else "COMPLETED_WITH_LINK_FAILURES",
        "counts": {
            "source_families": len(source_results),
            "unique_dataset_actions": len({item["dataset_url"] for item in catalogue.values()}),
            "unique_record_actions": len({url for urls in record_actions.values() for url in urls}),
            "checked_record_action_sample": sum(len(item["record_actions"]) for item in source_results.values()),
            "checked_unique_urls": len(checked_urls),
            "failures": len(failures),
        },
        "sources": source_results,
        "failures": failures,
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "counts": report["counts"]}, indent=2))
    if args.strict and failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
