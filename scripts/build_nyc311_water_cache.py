from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.nyc311_water import (  # noqa: E402
    CATEGORIES,
    SOURCE_DATASETS,
    SOURCE_SCOPE,
    fetch_metadata,
    iter_partition,
    normalize_request,
    utc_now,
)


def _new_property_profile(bbl: str, request: dict[str, Any]) -> dict[str, Any]:
    return {
        "bbl": bbl,
        "request_count": 0,
        "category_counts": Counter(),
        "source_counts": Counter(),
        "first_created_date": None,
        "latest_created_date": None,
        "latest_request_id": None,
        "latest_category": None,
        "latest_complaint_type": None,
        "latest_descriptor": None,
        "latest_status": None,
        "latest_incident_address": None,
        "latest_borough": None,
        "evidence_semantics": "311 reported service-request history at a source-reported BBL; not confirmation of a defect or contamination.",
    }


def _update_property_profile(profile: dict[str, Any], request: dict[str, Any]) -> None:
    profile["request_count"] += 1
    profile["category_counts"][str(request["category"])] += 1
    profile["source_counts"][str(request["source_dataset_id"])] += 1
    created_date = request.get("created_date")
    if created_date and (not profile["first_created_date"] or created_date < profile["first_created_date"]):
        profile["first_created_date"] = created_date
    if created_date and (not profile["latest_created_date"] or created_date >= profile["latest_created_date"]):
        profile["latest_created_date"] = created_date
        profile["latest_request_id"] = request.get("request_id")
        profile["latest_category"] = request.get("category")
        profile["latest_complaint_type"] = request.get("complaint_type")
        profile["latest_descriptor"] = request.get("descriptor")
        profile["latest_status"] = request.get("status")
        profile["latest_incident_address"] = request.get("incident_address")
        profile["latest_borough"] = request.get("borough")


def build(requests_path: Path, properties_path: Path, summary_path: Path, *, page_size: int) -> dict[str, Any]:
    requests_path.parent.mkdir(parents=True, exist_ok=True)
    properties_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    category_counts: Counter[str] = Counter()
    complaint_counts: Counter[str] = Counter()
    descriptor_counts: Counter[str] = Counter()
    year_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    asset_scope_counts: Counter[str] = Counter()
    properties: dict[str, dict[str, Any]] = {}
    source_health: list[dict[str, Any]] = []
    total = 0
    rows_with_bbl = 0

    with gzip.open(requests_path, "wt", encoding="utf-8", compresslevel=6) as handle:
        for source_name, dataset_id in SOURCE_DATASETS:
            metadata = fetch_metadata(source_name, dataset_id)
            expected, pages = iter_partition(metadata, page_size=page_size)
            fetched = 0
            for page in pages:
                for raw in page:
                    request = normalize_request(source_name, dataset_id, raw)
                    handle.write(json.dumps(request, separators=(",", ":")) + "\n")
                    fetched += 1
                    total += 1
                    source_counts[dataset_id] += 1
                    category_counts[str(request["category"])] += 1
                    asset_scope_counts[str(request["asset_scope"])] += 1
                    if request.get("complaint_type"):
                        complaint_counts[str(request["complaint_type"])] += 1
                    if request.get("descriptor"):
                        descriptor_counts[str(request["descriptor"])] += 1
                    year = str(request.get("created_date") or "MISSING")[:4]
                    year_counts[year] += 1
                    bbl = request.get("bbl")
                    if bbl:
                        rows_with_bbl += 1
                        profile = properties.setdefault(str(bbl), _new_property_profile(str(bbl), request))
                        _update_property_profile(profile, request)
            if fetched != expected:
                requests_path.unlink(missing_ok=True)
                raise RuntimeError(
                    f"NYC 311 source {dataset_id} count mismatch after iterator: expected {expected:,}, fetched {fetched:,}"
                )
            source_health.append(
                {
                    "source": source_name,
                    "dataset_id": dataset_id,
                    "dataset_name": metadata.dataset_name,
                    "status": "HEALTHY",
                    "source_query_scope": SOURCE_SCOPE,
                    "source_record_count": expected,
                    "fetched_record_count": fetched,
                    "pagination_complete": True,
                    "schema_valid": True,
                    "source_last_updated_at": metadata.source_last_updated_at,
                    "selected_fields": list(metadata.selected_fields),
                }
            )

    with gzip.open(properties_path, "wt", encoding="utf-8", compresslevel=6) as handle:
        for bbl in sorted(properties):
            profile = properties[bbl]
            profile["category_counts"] = dict(sorted(profile["category_counts"].items()))
            profile["source_counts"] = dict(sorted(profile["source_counts"].items()))
            handle.write(json.dumps(profile, separators=(",", ":")) + "\n")

    summary = {
        "schema_version": "1.0",
        "generated_at": utc_now(),
        "domain": "NYC_311_WATER_LEAD_SERVICE_REQUESTS",
        "source_health": source_health,
        "summary": {
            "request_count": total,
            "rows_with_bbl": rows_with_bbl,
            "unique_bbl_count": len(properties),
            "source_counts": dict(sorted(source_counts.items())),
            "category_counts": dict(sorted(category_counts.items())),
            "asset_scope_counts": dict(sorted(asset_scope_counts.items())),
            "year_counts": dict(sorted(year_counts.items())),
            "complaint_type_counts": dict(sorted(complaint_counts.items())),
            "top_descriptors": [
                {"descriptor": descriptor, "count": count}
                for descriptor, count in descriptor_counts.most_common(100)
            ],
        },
        "evidence_semantics": {
            "condition": "311 records are reported service requests. They do not by themselves confirm a building defect, contamination, lead presence or a responsible service provider.",
            "bbl": "Where present, BBL is a source-reported location identifier and supports location linkage only.",
            "public_infrastructure": "Hydrant, water-main and street-water records are explicitly separated from building/distribution drinking-water signals.",
            "lead_test_kit": "Lead kit/test-kit requests are service activity and must not be represented as evidence of lead detection.",
        },
        "categories": list(CATEGORIES),
        "requests_file": requests_path.name,
        "properties_file": properties_path.name,
    }
    summary_path.write_text(json.dumps(summary, separators=(",", ":")), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build exact-count NYC 311 water/lead service-request cache")
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--properties", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--page-size", type=int, default=50000)
    args = parser.parse_args()
    summary = build(args.requests, args.properties, args.summary, page_size=args.page_size)
    print(json.dumps(summary["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
