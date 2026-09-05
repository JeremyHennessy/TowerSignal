from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.domestic_water import (  # noqa: E402
    COMPLIANCE_DATASET_ID,
    SELF_REPORT_DATASET_ID,
    WATER_TANK_LAYER_URL,
    fetch_dwt_compliance_by_bin,
    fetch_dwt_self_reports_by_bin,
    fetch_planimetric_water_tanks_by_bin,
    summarize_domestic_water,
)
from towersignal.planimetrics import normalize_bin  # noqa: E402

WATER_TANK_DATASET_ID = "Water_Tank_2022/FeatureServer/27"


def safe_detail_path(base: Path, system_id: str) -> Path:
    safe = "".join(ch for ch in system_id if ch.isalnum() or ch in ("-", "_"))
    return base / "details" / (safe[:2] or "xx").lower() / f"{safe}.json"


def _source_entry(metadata: dict, *, dataset_id: str) -> dict:
    entry = {
        "dataset_id": dataset_id,
        "name": metadata["name"],
        "retrieved_at": metadata["retrieved_at"],
        "source_record_count": metadata["source_record_count"],
        "source_query_scope": metadata["source_query_scope"],
        "source_last_updated_at": metadata.get("source_last_updated_at"),
        "url": metadata["url"],
    }
    if "matched_feature_count" in metadata:
        entry["matched_record_count"] = metadata["matched_feature_count"]
    elif "matched_record_count" in metadata:
        entry["matched_record_count"] = metadata["matched_record_count"]
    return entry


def _replace_sources(sources: list[dict], replacements: list[dict]) -> list[dict]:
    replace_ids = {source["dataset_id"] for source in replacements}
    retained = [source for source in sources if source.get("dataset_id") not in replace_ids]
    return retained + replacements


def build(output_dir: Path) -> dict:
    systems_path = output_dir / "systems.json"
    metadata_path = output_dir / "metadata.json"
    if not systems_path.exists():
        raise RuntimeError(f"Base NYC systems payload is missing: {systems_path}")

    payload = json.loads(systems_path.read_text(encoding="utf-8"))
    systems = payload.get("systems") or []
    metadata = payload.get("metadata") or {}
    summary = payload.get("summary") or {}
    if not isinstance(systems, list) or not systems:
        raise RuntimeError("Base NYC systems payload contains no systems")

    bin_values = {
        normalized
        for row in systems
        if (normalized := normalize_bin(row.get("bin")))
    }

    planimetric_by_bin, planimetric_meta = fetch_planimetric_water_tanks_by_bin(bin_values)
    compliance_by_bin, compliance_meta = fetch_dwt_compliance_by_bin(bin_values)
    self_reports_by_bin, self_report_meta = fetch_dwt_self_reports_by_bin(bin_values)

    replacements = [
        _source_entry(planimetric_meta, dataset_id=WATER_TANK_DATASET_ID),
        _source_entry(compliance_meta, dataset_id=COMPLIANCE_DATASET_ID),
        _source_entry(self_report_meta, dataset_id=SELF_REPORT_DATASET_ID),
    ]
    metadata["sources"] = _replace_sources(list(metadata.get("sources") or []), replacements)

    metadata.update({
        "dwt_planimetric_requested_bin_count": planimetric_meta["requested_bin_count"],
        "dwt_planimetric_matched_bin_count": planimetric_meta["matched_bin_count"],
        "dwt_planimetric_matched_feature_count": planimetric_meta["matched_feature_count"],
        "dwt_planimetric_match_basis": planimetric_meta["match_basis"],
        "dwt_planimetric_feature_identity_basis": planimetric_meta["feature_identity_basis"],
        "dwt_planimetric_imagery_year": planimetric_meta["imagery_year"],
        "dwt_compliance_requested_bin_count": compliance_meta["requested_bin_count"],
        "dwt_compliance_matched_bin_count": compliance_meta["matched_bin_count"],
        "dwt_compliance_matched_record_count": compliance_meta["matched_record_count"],
        "dwt_compliance_match_basis": compliance_meta["match_basis"],
        "dwt_self_report_requested_bin_count": self_report_meta["requested_bin_count"],
        "dwt_self_report_matched_bin_count": self_report_meta["matched_bin_count"],
        "dwt_self_report_matched_record_count": self_report_meta["matched_record_count"],
        "dwt_self_report_match_basis": self_report_meta["match_basis"],
    })

    systems_with_planimetric = 0
    systems_with_compliance = 0
    systems_with_self_reports = 0
    systems_with_any_domestic_water = 0

    for row in systems:
        system_id = str(row.get("system_id") or "")
        bin_value = normalize_bin(row.get("bin"))
        planimetric_tanks = planimetric_by_bin.get(bin_value, []) if bin_value else []
        compliance_history = compliance_by_bin.get(bin_value, []) if bin_value else []
        self_report_history = self_reports_by_bin.get(bin_value, []) if bin_value else []
        domestic_summary = summarize_domestic_water(planimetric_tanks, compliance_history, self_report_history)

        row.update({
            "dwt_planimetric_bin_match": bool(planimetric_tanks),
            "dwt_planimetric_tank_count": len(planimetric_tanks),
            "dwt_compliance_record_count": len(compliance_history),
            "dwt_self_report_record_count": len(self_report_history),
            "dwt_latest_status": domestic_summary["latest_status"],
            "dwt_latest_reported_tank_count": domestic_summary["latest_reported_dwt_count"],
            "dwt_latest_activity_type": domestic_summary["latest_activity_type"],
            "dwt_latest_activity_year": domestic_summary["latest_activity_year"],
            "dwt_latest_self_report_inspection_date": domestic_summary["latest_self_report_inspection_date"],
            "dwt_violation_record_count": domestic_summary["violation_record_count"],
        })

        if planimetric_tanks:
            systems_with_planimetric += 1
        if compliance_history:
            systems_with_compliance += 1
        if self_report_history:
            systems_with_self_reports += 1
        if planimetric_tanks or compliance_history or self_report_history:
            systems_with_any_domestic_water += 1

        detail_path = safe_detail_path(output_dir, system_id)
        if not detail_path.exists():
            raise RuntimeError(f"Missing account detail while attaching domestic water data: {system_id}")
        detail = json.loads(detail_path.read_text(encoding="utf-8"))
        detail["domestic_water"] = {
            "summary": domestic_summary,
            "planimetric_tank_features": planimetric_tanks,
            "compliance_history": compliance_history,
            "self_report_history": self_report_history,
            "evidence_boundaries": {
                "planimetric": "2022 rooftop physical observation from NYC OTI Planimetrics; exact BIN building attachment; not current operating-status evidence.",
                "compliance": "NYC Health Department oversight/compliance records attached by exact BIN; record presence and absence are not a complete current-condition certification.",
                "self_report": "Annual inspection data self-reported by a certified inspector on behalf of the building owner; values are preserved as source-reported evidence.",
            },
        }
        detail["metadata"] = metadata
        detail_path.write_text(json.dumps(detail, separators=(",", ":")), encoding="utf-8")

    summary.update({
        "systems_with_dwt_planimetric_match": systems_with_planimetric,
        "systems_with_dwt_compliance": systems_with_compliance,
        "systems_with_dwt_self_reports": systems_with_self_reports,
        "systems_with_any_domestic_water_context": systems_with_any_domestic_water,
    })
    payload["metadata"] = metadata
    payload["summary"] = summary
    payload["systems"] = systems

    systems_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    report = {
        "requested_registry_bins": len(bin_values),
        "planimetric": {
            "source": WATER_TANK_LAYER_URL,
            "matched_bins": planimetric_meta["matched_bin_count"],
            "matched_features": planimetric_meta["matched_feature_count"],
            "systems_attached": systems_with_planimetric,
        },
        "compliance": {
            "dataset_id": COMPLIANCE_DATASET_ID,
            "matched_bins": compliance_meta["matched_bin_count"],
            "matched_records": compliance_meta["matched_record_count"],
            "systems_attached": systems_with_compliance,
        },
        "self_reports": {
            "dataset_id": SELF_REPORT_DATASET_ID,
            "matched_bins": self_report_meta["matched_bin_count"],
            "matched_records": self_report_meta["matched_record_count"],
            "systems_attached": systems_with_self_reports,
        },
        "systems_with_any_domestic_water_context": systems_with_any_domestic_water,
    }
    (output_dir / "domestic-water-coverage.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Attach exact-BIN NYC domestic-water intelligence to TowerSignal accounts")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data")
    args = parser.parse_args()
    build(args.output)


if __name__ == "__main__":
    main()
