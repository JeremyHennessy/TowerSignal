from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from toronto_app_sources import OFFICIAL_DATASET_URLS, _record_for_link, load_source_rows, normalize_source_link

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MARKET = ROOT / "data/toronto/market/current"
DEFAULT_REPORT = DEFAULT_MARKET / "source_semantic_audit.json"
EXPECTED_SOURCES = tuple(sorted(OFFICIAL_DATASET_URLS))


def load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Semantic/cardinality audit of Toronto property-source links")
    parser.add_argument("--market", type=Path, default=DEFAULT_MARKET)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    market = args.market
    links_payload = load(market / "property_source_links.json")
    spine = load(market / "property_spine.json")
    coverage = load(market / "coverage_report.json")
    source_rows = load_source_rows(ROOT, load)

    properties = [p for p in spine.get("properties", []) if isinstance(p, dict)]
    property_ids = {clean(p.get("property_id")) for p in properties if clean(p.get("property_id"))}
    links = [link for link in links_payload.get("links", []) if isinstance(link, dict)]

    exact_identity = Counter()
    full_payload = Counter()
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_record_properties: dict[tuple[str, str], set[str]] = defaultdict(set)
    property_source_records: dict[tuple[str, str], list[str]] = defaultdict(list)
    invalid_properties: list[dict[str, Any]] = []
    unknown_sources: list[dict[str, Any]] = []
    unresolved_source_rows: list[dict[str, Any]] = []
    missing_record_ids: list[dict[str, Any]] = []
    normalized_record_actions: dict[str, set[str]] = defaultdict(set)

    for link in links:
        source = clean(link.get("source_key"))
        pid = clean(link.get("property_id"))
        rid = clean(link.get("source_record_id"))
        row_index = link.get("source_row_index")
        identity = (pid, source, rid)
        exact_identity[identity] += 1
        full_payload[json.dumps(link, sort_keys=True, default=str)] += 1
        by_source[source].append(link)
        source_record_properties[(source, rid)].add(pid)
        property_source_records[(pid, source)].append(rid)
        if not rid:
            missing_record_ids.append({"property_id": pid, "source_key": source, "source_row_index": row_index})
        if pid not in property_ids:
            invalid_properties.append({"property_id": pid, "source_key": source, "source_record_id": rid})
        if source not in EXPECTED_SOURCES:
            unknown_sources.append({"property_id": pid, "source_key": source, "source_record_id": rid})
        if source in EXPECTED_SOURCES:
            row = _record_for_link(link, source_rows)
            if not row:
                unresolved_source_rows.append({"property_id": pid, "source_key": source, "source_record_id": rid, "source_row_index": row_index})
            normalized = normalize_source_link(link, source_rows)
            record_url = clean(normalized.get("record_url"))
            if record_url:
                normalized_record_actions[source].add(record_url)

    duplicate_identities = [
        {"property_id": key[0], "source_key": key[1], "source_record_id": key[2], "count": count}
        for key, count in exact_identity.items() if count > 1
    ]
    duplicate_payloads = [
        {"payload": json.loads(payload), "count": count}
        for payload, count in full_payload.items() if count > 1
    ]

    multi_property_records: list[dict[str, Any]] = []
    for (source, rid), pids in source_record_properties.items():
        if rid and len(pids) > 1:
            bases = sorted({clean(link.get("match_basis")) for link in by_source[source] if clean(link.get("source_record_id")) == rid})
            addresses = sorted({clean(link.get("source_address")) for link in by_source[source] if clean(link.get("source_record_id")) == rid and clean(link.get("source_address"))})
            multi_property_records.append({"source_key": source, "source_record_id": rid, "property_count": len(pids), "property_ids": sorted(pids), "match_bases": bases, "source_addresses": addresses})

    source_summary: dict[str, Any] = {}
    for source in EXPECTED_SOURCES:
        items = by_source.get(source, [])
        records = {clean(item.get("source_record_id")) for item in items if clean(item.get("source_record_id"))}
        props = {clean(item.get("property_id")) for item in items if clean(item.get("property_id"))}
        per_property = Counter(clean(item.get("property_id")) for item in items)
        per_record = Counter(clean(item.get("source_record_id")) for item in items if clean(item.get("source_record_id")))
        expected_properties = ((coverage.get("source_coverage") or {}).get(source) or {}).get("matched_canonical_properties")
        source_summary[source] = {
            "links": len(items),
            "unique_source_records": len(records),
            "unique_properties": len(props),
            "coverage_expected_properties": expected_properties,
            "coverage_property_count_matches": expected_properties is None or expected_properties == len(props),
            "max_links_per_property": max(per_property.values(), default=0),
            "max_properties_per_source_record": max(per_record.values(), default=0),
            "multi_property_source_record_count": sum(1 for count in per_record.values() if count > 1),
            "record_action_count": len(normalized_record_actions.get(source, set())),
            "dataset_url": OFFICIAL_DATASET_URLS[source],
        }

    missing_sources = sorted(set(EXPECTED_SOURCES) - set(by_source))
    unexpected_sources = sorted(set(by_source) - set(EXPECTED_SOURCES))
    link_count_declared = links_payload.get("link_count") or (links_payload.get("counts") or {}).get("source_links")
    coverage_link_count = (coverage.get("counts") or {}).get("source_links")

    findings = {
        "exact_duplicate_link_identities": len(duplicate_identities),
        "exact_duplicate_payloads": len(duplicate_payloads),
        "invalid_property_references": len(invalid_properties),
        "unknown_source_keys": len(unknown_sources),
        "missing_source_record_ids": len(missing_record_ids),
        "unresolved_source_rows": len(unresolved_source_rows),
        "multi_property_source_records": len(multi_property_records),
        "missing_expected_source_families": len(missing_sources),
        "unexpected_source_families": len(unexpected_sources),
        "coverage_count_mismatches": sum(1 for item in source_summary.values() if not item["coverage_property_count_matches"]),
    }

    hard_failures = {
        key: value for key, value in findings.items()
        if key not in {"multi_property_source_records"} and value
    }
    if isinstance(link_count_declared, int) and link_count_declared != len(links):
        hard_failures["declared_link_count_mismatch"] = {"declared": link_count_declared, "actual": len(links)}
    if isinstance(coverage_link_count, int) and coverage_link_count != len(links):
        hard_failures["coverage_link_count_mismatch"] = {"coverage": coverage_link_count, "actual": len(links)}

    report = {
        "schema_version": "toronto-source-semantic-audit-1.0",
        "generated_at": utc_now(),
        "status": "FAILED" if hard_failures else "PASSED_WITH_CARDINALITY_REVIEW" if multi_property_records else "PASSED",
        "counts": {
            "source_links": len(links),
            "source_families": len(by_source),
            "canonical_properties": len(property_ids),
            "unique_property_source_record_identities": len(exact_identity),
            "unique_source_records_across_families": len(source_record_properties),
            "record_specific_actions": sum(len(v) for v in normalized_record_actions.values()),
        },
        "findings": findings,
        "hard_failures": hard_failures,
        "sources": source_summary,
        "cardinality_review": sorted(multi_property_records, key=lambda item: (item["source_key"], item["source_record_id"])),
        "duplicate_identities": duplicate_identities[:200],
        "duplicate_payloads": duplicate_payloads[:50],
        "invalid_property_references": invalid_properties[:200],
        "unknown_sources": unknown_sources[:200],
        "missing_record_ids": missing_record_ids[:200],
        "unresolved_source_rows": unresolved_source_rows[:200],
        "missing_expected_sources": missing_sources,
        "unexpected_sources": unexpected_sources,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "counts": report["counts"], "findings": findings, "sources": source_summary}, indent=2))
    if args.strict and hard_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
