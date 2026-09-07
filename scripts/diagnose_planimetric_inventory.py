from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.fetch import SourceFetchError, fetch_count, fetch_dataset, fetch_metadata, fetch_where  # noqa: E402
from towersignal.normalize import normalize_registrations  # noqa: E402
from towersignal.planimetrics import (  # noqa: E402
    DATASET_ID as PLANIMETRIC_DATASET_ID,
    DATASET_URL as PLANIMETRIC_DATASET_URL,
    IMAGERY_YEAR,
    SOURCE_NAME as PLANIMETRIC_SOURCE_NAME,
    normalize_bin,
)

REGISTRATION_DATASET_ID = "y4fw-iqfr"
REGISTRATION_URL = "https://data.cityofnewyork.us/Health/NYC-Cooling-Tower-Registrations/y4fw-iqfr"
PLANIMETRIC_SELECT = "source_id,feature_co,sub_featur,bin,status,globalid"
PAGE_SIZE = 50000
SCHEMA_VERSION = "1.0"
BOROUGH_BY_BIN_PREFIX = {
    "1": "Manhattan",
    "2": "Bronx",
    "3": "Brooklyn",
    "4": "Queens",
    "5": "Staten Island",
}


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def fetch_complete_planimetric_inventory() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    expected = fetch_count(PLANIMETRIC_DATASET_ID)
    metadata = fetch_metadata(PLANIMETRIC_DATASET_ID)
    rows: list[dict[str, Any]] = []
    offset = 0
    while offset < expected:
        page = fetch_where(
            PLANIMETRIC_DATASET_ID,
            "1=1",
            order_by="globalid",
            select=PLANIMETRIC_SELECT,
            limit=PAGE_SIZE,
            offset=offset,
        )
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    final_count = fetch_count(PLANIMETRIC_DATASET_ID)
    if expected != len(rows) or expected != final_count:
        raise SourceFetchError(
            "Planimetric inventory changed during diagnostic pagination: "
            f"start={expected:,}, fetched={len(rows):,}, end={final_count:,}. Refusing a partial comparison."
        )
    return rows, {
        "dataset_id": PLANIMETRIC_DATASET_ID,
        "name": metadata.get("name") or PLANIMETRIC_SOURCE_NAME,
        "url": PLANIMETRIC_DATASET_URL,
        "source_record_count": expected,
        "source_last_updated_at": metadata.get("source_last_updated_at"),
        "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "imagery_year": IMAGERY_YEAR,
    }


def _borough_for_bin(bin_value: str | None) -> str:
    return BOROUGH_BY_BIN_PREFIX.get((bin_value or "")[:1], "UNKNOWN")


def build_diagnostic(
    systems: list[dict[str, Any]],
    physical_rows: list[dict[str, Any]],
    *,
    registration_source: dict[str, Any],
    planimetric_source: dict[str, Any],
) -> dict[str, Any]:
    regulatory_by_bin: dict[str, list[dict[str, Any]]] = {}
    systems_without_bin = 0
    for system in systems:
        bin_value = normalize_bin(system.get("bin"))
        if not bin_value:
            systems_without_bin += 1
            continue
        regulatory_by_bin.setdefault(bin_value, []).append(system)

    physical_by_bin: dict[str, list[dict[str, Any]]] = {}
    physical_without_bin = 0
    seen_global_ids: set[str] = set()
    duplicate_global_ids: list[str] = []
    sub_feature_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    for row in physical_rows:
        global_id = _text(row.get("globalid"))
        if not global_id:
            raise SourceFetchError("Planimetric inventory row is missing GlobalID; stable feature reconciliation is impossible")
        if global_id in seen_global_ids:
            duplicate_global_ids.append(global_id)
        seen_global_ids.add(global_id)
        sub_feature_counts[_text(row.get("sub_featur")) or "UNKNOWN"] += 1
        status_counts[_text(row.get("status")) or "UNKNOWN"] += 1
        bin_value = normalize_bin(row.get("bin"))
        if not bin_value:
            physical_without_bin += 1
            continue
        physical_by_bin.setdefault(bin_value, []).append(row)

    if duplicate_global_ids:
        raise SourceFetchError(f"Duplicate Planimetric GlobalID values: {duplicate_global_ids[:5]}")

    regulatory_bins = set(regulatory_by_bin)
    physical_bins = set(physical_by_bin)
    matched_bins = regulatory_bins & physical_bins
    regulatory_only_bins = regulatory_bins - physical_bins
    physical_only_bins = physical_bins - regulatory_bins

    matched_system_count = sum(len(regulatory_by_bin[bin_value]) for bin_value in matched_bins)
    regulatory_only_system_count = sum(len(regulatory_by_bin[bin_value]) for bin_value in regulatory_only_bins)
    matched_feature_count = sum(len(physical_by_bin[bin_value]) for bin_value in matched_bins)
    physical_only_feature_count = sum(len(physical_by_bin[bin_value]) for bin_value in physical_only_bins)

    def bin_borough_counts(values: set[str]) -> dict[str, int]:
        counts = Counter(_borough_for_bin(value) for value in values)
        return dict(sorted(counts.items()))

    multi_feature_bins = {
        bin_value: len(rows)
        for bin_value, rows in physical_by_bin.items()
        if len(rows) > 1
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "diagnostic": "NYC_PLANIMETRIC_COOLING_TOWER_INVENTORY_RECONCILIATION",
        "sources": {
            "regulatory": registration_source,
            "physical": planimetric_source,
        },
        "identity_contract": {
            "regulatory_system_identity": "system_id",
            "property_reconciliation_key": "BIN_EXACT",
            "physical_feature_identity": "globalid",
            "address_matching_used": False,
            "fuzzy_matching_used": False,
        },
        "summary": {
            "regulatory_system_count": len(systems),
            "regulatory_systems_without_valid_bin": systems_without_bin,
            "regulatory_unique_bin_count": len(regulatory_bins),
            "physical_feature_count": len(physical_rows),
            "physical_features_without_valid_bin": physical_without_bin,
            "physical_unique_bin_count": len(physical_bins),
            "matched_exact_bin_count": len(matched_bins),
            "matched_regulatory_system_count": matched_system_count,
            "matched_physical_feature_count": matched_feature_count,
            "regulatory_bins_without_physical_match": len(regulatory_only_bins),
            "regulatory_systems_without_physical_match": regulatory_only_system_count,
            "physical_bins_without_regulatory_match": len(physical_only_bins),
            "physical_features_without_regulatory_match": physical_only_feature_count,
            "physical_bins_with_multiple_features": len(multi_feature_bins),
        },
        "borough_breakdown": {
            "matched_bins": bin_borough_counts(matched_bins),
            "regulatory_only_bins": bin_borough_counts(regulatory_only_bins),
            "physical_only_bins": bin_borough_counts(physical_only_bins),
            "basis": "NYC BIN borough-prefix convention; no address matching",
        },
        "physical_source_profile": {
            "sub_feature_counts": dict(sorted(sub_feature_counts.items())),
            "status_counts": dict(sorted(status_counts.items())),
            "multi_feature_bin_examples": dict(sorted(multi_feature_bins.items(), key=lambda item: (-item[1], item[0]))[:25]),
        },
        "mismatch_examples": {
            "regulatory_only_bins": sorted(regulatory_only_bins, key=int)[:50],
            "physical_only_bins": sorted(physical_only_bins, key=int)[:50],
        },
        "evidence_boundaries": [
            "A Planimetric feature without a current regulatory match is a verification candidate, not evidence of an illegal, unregistered, or noncompliant cooling tower.",
            "A current regulatory record without a 2022 Planimetric match is not evidence that the tower does not physically exist.",
            "Planimetric imagery vintage is 2022 and must not be interpreted as a current operating-status observation.",
            "Building-level BIN reconciliation does not establish a one-to-one relationship between a physical feature and a specific regulatory System ID when multiple systems share a BIN.",
        ],
        "recommendation": {
            "inventory_qa": "SUPPORTED_FOR_EXACT_BIN_VERIFICATION",
            "priority_score_change": False,
            "production_ui_change": False,
            "durable_history_change": False,
            "next_step": "Use mismatch populations only for non-scoring inventory QA/field verification. Evaluate commercial lift separately before creating any new prospect trigger.",
        },
    }


def run(output: Path) -> dict[str, Any]:
    registration_snapshot = fetch_dataset(REGISTRATION_DATASET_ID, "system_id")
    systems, _ = normalize_registrations(registration_snapshot.rows)
    physical_rows, physical_source = fetch_complete_planimetric_inventory()
    report = build_diagnostic(
        systems,
        physical_rows,
        registration_source={
            "dataset_id": registration_snapshot.dataset_id,
            "name": registration_snapshot.name,
            "url": REGISTRATION_URL,
            "source_record_count": registration_snapshot.source_record_count,
            "source_last_updated_at": registration_snapshot.source_last_updated_at,
            "retrieved_at": registration_snapshot.retrieved_at,
        },
        planimetric_source=physical_source,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile current NYC cooling-tower registrations with the complete 2022 Planimetric inventory")
    parser.add_argument("--output", type=Path, default=Path("planimetric-inventory-diagnostic.json"))
    args = parser.parse_args()
    run(args.output)


if __name__ == "__main__":
    main()
