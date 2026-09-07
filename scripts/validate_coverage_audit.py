from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_GAPS = {"DOB_NOW", "PLUTO", "HPD", "ACRIS", "NYS", "CMS", "NYC_311_HISTORICAL", "ELAP"}


def validate(report: dict[str, Any]) -> None:
    if report.get("schema_version") != "1.0":
        raise RuntimeError("Coverage audit schema_version must be 1.0")
    if not report.get("generated_at"):
        raise RuntimeError("Coverage audit generated_at is required")

    sources = report.get("standardized_coverage_sources")
    if not isinstance(sources, list) or len(sources) < 10:
        raise RuntimeError("Coverage audit must contain the current standardized source-health matrix")
    keys: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            raise RuntimeError("Coverage audit standardized source entry must be an object")
        key = str(source.get("source_key") or "")
        if not key or key in keys:
            raise RuntimeError(f"Coverage audit source_key missing or duplicated: {key!r}")
        keys.add(key)
        for field in (
            "retrieved_record_count",
            "requested_entity_count",
            "normalized_entity_count",
            "matched_entity_count",
            "attached_entity_count",
            "displayed_entity_count",
        ):
            value = source.get(field)
            if not isinstance(value, int) or value < 0:
                raise RuntimeError(f"Coverage audit {key}.{field} must be a non-negative integer")
        coverage = source.get("coverage_percentage")
        if coverage is not None and (not isinstance(coverage, (int, float)) or coverage < 0 or coverage > 100):
            raise RuntimeError(f"Coverage audit {key}.coverage_percentage is invalid")
        if source.get("integration_status") != "INTEGRATED":
            raise RuntimeError(f"Standardized source {key} must be integrated")
        if not source.get("identity_key"):
            raise RuntimeError(f"Coverage audit {key} is missing identity_key")

    artifacts = report.get("source_artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise RuntimeError("Coverage audit source_artifacts are required")
    missing = [str(item.get("artifact")) for item in artifacts if not isinstance(item, dict) or item.get("exists") is not True]
    if missing:
        raise RuntimeError("Coverage audit has missing expected generated artifacts: " + ", ".join(missing))

    gaps = report.get("gap_analysis")
    if not isinstance(gaps, list):
        raise RuntimeError("Coverage audit gap_analysis must be a list")
    gap_by_key = {str(item.get("gap_key")): item for item in gaps if isinstance(item, dict)}
    missing_gaps = sorted(REQUIRED_GAPS - set(gap_by_key))
    if missing_gaps:
        raise RuntimeError("Coverage audit missing required gap classifications: " + ", ".join(missing_gaps))
    cms = gap_by_key["CMS"]
    if cms.get("classification") != "NOT_INTEGRATED_SOURCE_CONTRACT_REQUIRED" or (cms.get("observed") or {}).get("integrated") is not False:
        raise RuntimeError("CMS must remain explicitly not integrated until an authoritative source/join contract is proven")
    historical_311 = gap_by_key["NYC_311_HISTORICAL"]
    if historical_311.get("classification") != "BOUNDED_HISTORICAL_CONTEXT_INTEGRATED" or (historical_311.get("observed") or {}).get("integrated") is not True:
        raise RuntimeError("Historical 311 must remain a bounded exact-BBL context integration after measured commercial lift")

    governance = report.get("governance") or {}
    required_false = (
        "priority_score_1_0_changed",
        "opportunity_score_authorized",
        "fuzzy_matching_used",
        "new_source_ingestion_performed",
        "ui_redesign_performed",
    )
    for key in required_false:
        if governance.get(key) is not False:
            raise RuntimeError(f"Coverage audit governance invariant failed: {key} must be false")

    nyc = report.get("nyc") or {}
    identifiers = nyc.get("identifier_coverage") or {}
    total = identifiers.get("systems")
    with_bbl = identifiers.get("with_bbl")
    missing_bbl = identifiers.get("missing_bbl")
    with_bin = identifiers.get("with_bin")
    missing_bin = identifiers.get("missing_bin")
    if not all(isinstance(value, int) and value >= 0 for value in (total, with_bbl, missing_bbl, with_bin, missing_bin)):
        raise RuntimeError("Coverage audit NYC identifier metrics are malformed")
    if with_bbl + missing_bbl != total or with_bin + missing_bin != total:
        raise RuntimeError("Coverage audit NYC identifier metrics do not reconcile")

    storage = report.get("storage_footprint") or {}
    if int(storage.get("public_data_total_bytes") or 0) <= 0 or int(storage.get("systems_json_bytes") or 0) <= 0:
        raise RuntimeError("Coverage audit storage footprint is missing generated product sizes")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate TowerSignal data completeness audit")
    parser.add_argument("--report", type=Path, default=ROOT / "public/data/coverage-audit.json")
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise RuntimeError("Coverage audit root must be an object")
    validate(report)
    print(json.dumps({
        "schema_version": report.get("schema_version"),
        "standardized_sources": len(report.get("standardized_coverage_sources") or []),
        "source_artifacts": len(report.get("source_artifacts") or []),
        "gaps": [item.get("gap_key") for item in report.get("gap_analysis") or []],
    }, indent=2))


if __name__ == "__main__":
    main()
