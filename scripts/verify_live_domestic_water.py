from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.domestic_water import (  # noqa: E402
    fetch_dwt_compliance_by_bin,
    fetch_dwt_self_reports_by_bin,
    fetch_planimetric_water_tanks_by_bin,
)
from towersignal.planimetrics import normalize_bin  # noqa: E402


def safe_detail_path(base: Path, system_id: str) -> Path:
    safe = "".join(ch for ch in system_id if ch.isalnum() or ch in ("-", "_"))
    return base / "details" / (safe[:2] or "xx").lower() / f"{safe}.json"


def canonical_physical(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "global_id": record.get("global_id"),
        "source_id": record.get("source_id"),
        "bin": record.get("bin"),
        "feature_code": record.get("feature_code"),
        "status": record.get("status"),
        "base_elevation_ft": record.get("base_elevation_ft"),
        "top_elevation_ft": record.get("top_elevation_ft"),
        "height_ft": record.get("height_ft"),
        "geometry": record.get("geometry"),
        "imagery_year": record.get("imagery_year"),
        "location_level": record.get("location_level"),
        "match_basis": record.get("match_basis"),
    }


def canonical_compliance(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "bin": record.get("bin"),
        "status": record.get("status"),
        "number_of_dwt": record.get("number_of_dwt"),
        "activity_type": record.get("activity_type"),
        "activity_year": record.get("activity_year"),
        "violation_code": record.get("violation_code"),
        "law_section": record.get("law_section"),
        "violation_text": record.get("violation_text"),
        "compliance_year": record.get("compliance_year"),
        "date_of_occurrence": record.get("date_of_occurrence"),
        "summons_number": record.get("summons_number"),
        "match_basis": record.get("match_basis"),
    }


def canonical_self_report(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "bin": record.get("bin"),
        "reporting_year": record.get("reporting_year"),
        "tank_num": record.get("tank_num"),
        "inspection_by_firm": record.get("inspection_by_firm"),
        "inspection_performed": record.get("inspection_performed"),
        "inspection_date": record.get("inspection_date"),
        "sediment_result": record.get("sediment_result"),
        "biological_growth_result": record.get("biological_growth_result"),
        "debris_insects_result": record.get("debris_insects_result"),
        "rodent_bird_result": record.get("rodent_bird_result"),
        "sample_collected": record.get("sample_collected"),
        "coliform": record.get("coliform"),
        "ecoli": record.get("ecoli"),
        "meet_standards": record.get("meet_standards"),
        "match_basis": record.get("match_basis"),
    }


def select_bins(systems: list[dict[str, Any]], field: str, sample_size: int) -> list[str]:
    selected: list[str] = []
    for row in systems:
        if not row.get(field):
            continue
        bin_value = normalize_bin(row.get("bin"))
        if not bin_value or bin_value in selected:
            continue
        selected.append(bin_value)
        if len(selected) >= sample_size:
            break
    return selected


def generated_records_by_bin(output_dir: Path, systems: list[dict[str, Any]], bins: list[str], key: str) -> dict[str, list[dict[str, Any]]]:
    wanted = set(bins)
    found: dict[str, list[dict[str, Any]]] = {}
    for row in systems:
        bin_value = normalize_bin(row.get("bin"))
        if bin_value not in wanted or bin_value in found:
            continue
        detail_path = safe_detail_path(output_dir, str(row["system_id"]))
        detail = json.loads(detail_path.read_text(encoding="utf-8"))
        context = detail.get("domestic_water") or {}
        found[bin_value] = list(context.get(key) or [])
    return found


def verify(output_dir: Path, sample_size: int) -> dict[str, Any]:
    payload = json.loads((output_dir / "systems.json").read_text(encoding="utf-8"))
    systems = payload.get("systems") or []
    if not systems:
        raise RuntimeError("Generated NYC systems payload is empty")

    physical_bins = select_bins(systems, "dwt_planimetric_bin_match", sample_size)
    compliance_bins = select_bins(systems, "dwt_compliance_record_count", sample_size)
    self_report_bins = select_bins(systems, "dwt_self_report_record_count", sample_size)

    generated_physical = generated_records_by_bin(output_dir, systems, physical_bins, "planimetric_tank_features")
    generated_compliance = generated_records_by_bin(output_dir, systems, compliance_bins, "compliance_history")
    generated_self_reports = generated_records_by_bin(output_dir, systems, self_report_bins, "self_report_history")

    live_physical, _ = fetch_planimetric_water_tanks_by_bin(physical_bins)
    live_compliance, _ = fetch_dwt_compliance_by_bin(compliance_bins)
    live_self_reports, _ = fetch_dwt_self_reports_by_bin(self_report_bins)

    checks: list[dict[str, Any]] = []
    for bin_value in physical_bins:
        generated = sorted((canonical_physical(row) for row in generated_physical.get(bin_value, [])), key=lambda row: row["global_id"] or "")
        live = sorted((canonical_physical(row) for row in live_physical.get(bin_value, [])), key=lambda row: row["global_id"] or "")
        checks.append({"source": "planimetric_water_tanks", "bin": bin_value, "pass": generated == live, "generated_count": len(generated), "live_count": len(live)})

    for bin_value in compliance_bins:
        generated = [canonical_compliance(row) for row in generated_compliance.get(bin_value, [])]
        live = [canonical_compliance(row) for row in live_compliance.get(bin_value, [])]
        checks.append({"source": "dwt_compliance", "bin": bin_value, "pass": generated == live, "generated_count": len(generated), "live_count": len(live)})

    for bin_value in self_report_bins:
        generated = [canonical_self_report(row) for row in generated_self_reports.get(bin_value, [])]
        live = [canonical_self_report(row) for row in live_self_reports.get(bin_value, [])]
        checks.append({"source": "dwt_self_reports", "bin": bin_value, "pass": generated == live, "generated_count": len(generated), "live_count": len(live)})

    failures = [check for check in checks if not check["pass"]]
    report = {
        "sample_size_per_source": sample_size,
        "physical_bins": physical_bins,
        "compliance_bins": compliance_bins,
        "self_report_bins": self_report_bins,
        "checks": checks,
        "pass": not failures,
    }
    print(json.dumps(report, indent=2))
    if failures:
        raise RuntimeError(f"Domestic-water live verification failed for {len(failures)} exact-BIN samples")
    if not physical_bins or not compliance_bins or not self_report_bins:
        raise RuntimeError("Domestic-water live verification could not find at least one generated match for each evidence family")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Independently verify generated NYC domestic-water context against live sources")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data")
    parser.add_argument("--sample-size", type=int, default=3)
    args = parser.parse_args()
    if args.sample_size <= 0:
        raise SystemExit("--sample-size must be positive")
    verify(args.output, args.sample_size)


if __name__ == "__main__":
    main()
