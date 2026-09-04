from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.nyc311_water import CATEGORIES, SOURCE_DATASETS, normalize_bbl  # noqa: E402

ALLOWED_DATASET_IDS = {dataset_id for _, dataset_id in SOURCE_DATASETS}


def validate(requests_path: Path, properties_path: Path, summary_path: Path, *, max_age_days: int, require_production_volume: bool) -> dict:
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0" or payload.get("domain") != "NYC_311_WATER_LEAD_SERVICE_REQUESTS":
        raise RuntimeError("Unexpected 311 cache schema/domain")
    generated = datetime.fromisoformat(str(payload.get("generated_at") or "").replace("Z", "+00:00"))
    age_days = (datetime.now(timezone.utc) - generated).total_seconds() / 86400
    if age_days < -0.05 or age_days > max_age_days:
        raise RuntimeError(f"311 cache age is outside allowed range: {age_days:.2f} days")

    source_health = payload.get("source_health")
    summary = payload.get("summary")
    if not isinstance(source_health, list) or len(source_health) != len(SOURCE_DATASETS) or not isinstance(summary, dict):
        raise RuntimeError("311 cache missing source health/summary")

    expected_by_source: dict[str, int] = {}
    for source in source_health:
        if not isinstance(source, dict):
            raise RuntimeError("Malformed source-health row")
        dataset_id = str(source.get("dataset_id") or "")
        if dataset_id not in ALLOWED_DATASET_IDS:
            raise RuntimeError(f"Unexpected source dataset {dataset_id}")
        expected = int(source.get("source_record_count") or -1)
        fetched = int(source.get("fetched_record_count") or -2)
        if source.get("status") != "HEALTHY" or source.get("pagination_complete") is not True or source.get("schema_valid") is not True or expected != fetched:
            raise RuntimeError(f"Source proof failed for {dataset_id}")
        expected_by_source[dataset_id] = expected

    source_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    bbl_counts: Counter[str] = Counter()
    request_ids: set[str] = set()
    rows_with_bbl = 0
    request_count = 0
    with gzip.open(requests_path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            request_id = str(row.get("request_id") or "")
            if not request_id or request_id in request_ids:
                raise RuntimeError(f"Missing/duplicate request ID: {request_id}")
            request_ids.add(request_id)
            dataset_id = str(row.get("source_dataset_id") or "")
            category = str(row.get("category") or "")
            if dataset_id not in ALLOWED_DATASET_IDS or category not in CATEGORIES:
                raise RuntimeError("Unexpected dataset/category in 311 artifact")
            if row.get("evidence_type") != "REPORTED_SERVICE_REQUEST" or row.get("condition_confirmation") != "UNVERIFIED_REPORTED_CONDITION":
                raise RuntimeError("311 evidence boundary changed")
            bbl = row.get("bbl")
            if bbl:
                if normalize_bbl(bbl) != str(bbl) or row.get("property_link_confidence") != "CONFIRMED_LOCATION_IDENTIFIER":
                    raise RuntimeError(f"Invalid BBL/link evidence: {bbl}")
                rows_with_bbl += 1
                bbl_counts[str(bbl)] += 1
            request_count += 1
            source_counts[dataset_id] += 1
            category_counts[category] += 1

    if request_count != int(summary.get("request_count") or -1) or rows_with_bbl != int(summary.get("rows_with_bbl") or -1):
        raise RuntimeError("311 request/BBL summary mismatch")
    if dict(sorted(source_counts.items())) != summary.get("source_counts") or dict(sorted(category_counts.items())) != summary.get("category_counts"):
        raise RuntimeError("311 source/category summary mismatch")
    for dataset_id, expected in expected_by_source.items():
        if source_counts[dataset_id] != expected:
            raise RuntimeError(f"311 artifact source count mismatch for {dataset_id}")

    property_count = 0
    seen_bbls: set[str] = set()
    with gzip.open(properties_path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            bbl = str(row.get("bbl") or "")
            if normalize_bbl(bbl) != bbl or bbl in seen_bbls:
                raise RuntimeError(f"Invalid/duplicate property BBL: {bbl}")
            seen_bbls.add(bbl)
            if int(row.get("request_count") or 0) != bbl_counts[bbl]:
                raise RuntimeError(f"Property request count mismatch for {bbl}")
            categories = row.get("category_counts")
            if not isinstance(categories, dict) or sum(int(value) for value in categories.values()) != bbl_counts[bbl]:
                raise RuntimeError(f"Property category counts do not sum for {bbl}")
            property_count += 1

    if property_count != int(summary.get("unique_bbl_count") or -1) or property_count != len(bbl_counts):
        raise RuntimeError("311 property artifact count mismatch")

    if require_production_volume:
        floors = {
            "request_count": (request_count, 100000),
            "historical_requests": (source_counts.get("76ig-c548", 0), 50000),
            "current_requests": (source_counts.get("erm2-nwe9", 0), 25000),
            "rows_with_bbl": (rows_with_bbl, 20000),
            "unique_bbl_count": (property_count, 10000),
        }
        for name, (actual, minimum) in floors.items():
            if actual < minimum:
                raise RuntimeError(f"Implausibly small {name}: {actual:,} < {minimum:,}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate NYC 311 water service-request cache")
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--properties", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--max-age-days", type=int, default=1)
    parser.add_argument("--require-production-volume", action="store_true")
    args = parser.parse_args()
    payload = validate(args.requests, args.properties, args.summary, max_age_days=args.max_age_days, require_production_volume=args.require_production_volume)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
