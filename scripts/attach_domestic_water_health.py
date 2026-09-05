from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.source_health import health_entry, validate_source_health  # noqa: E402

SOURCE_KEYS = {
    "physical": "dwt_planimetric",
    "compliance": "dwt_compliance",
    "self_reports": "dwt_self_reports",
}


def load_json(path: Path | None, default: Any) -> Any:
    if path is None or not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def safe_detail_path(base: Path, system_id: str) -> Path:
    safe = "".join(ch for ch in system_id if ch.isalnum() or ch in ("-", "_"))
    return base / "details" / (safe[:2] or "xx").lower() / f"{safe}.json"


def attach(output_dir: Path, previous_snapshot_path: Path | None = None) -> list[dict[str, Any]]:
    systems_path = output_dir / "systems.json"
    metadata_path = output_dir / "metadata.json"
    payload = load_json(systems_path, None)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Missing or malformed generated systems payload: {systems_path}")
    metadata = payload.get("metadata") or {}
    systems = payload.get("systems") or []
    entries = [
        entry
        for entry in metadata.get("source_health", [])
        if entry.get("source_key") not in set(SOURCE_KEYS.values())
    ]

    previous = load_json(previous_snapshot_path, {})
    previous_health = {
        entry.get("source_key"): entry
        for entry in previous.get("source_health", [])
        if isinstance(entry, dict)
    }
    previous_coverage = lambda key: previous_health.get(key, {}).get("coverage_percentage")

    requested = int(metadata.get("dwt_planimetric_requested_bin_count") or 0)
    physical_matched = int(metadata.get("dwt_planimetric_matched_bin_count") or 0)
    physical_features = int(metadata.get("dwt_planimetric_matched_feature_count") or 0)
    physical_attached = sum(1 for row in systems if bool(row.get("dwt_planimetric_bin_match")))

    compliance_matched = int(metadata.get("dwt_compliance_matched_bin_count") or 0)
    compliance_records = int(metadata.get("dwt_compliance_matched_record_count") or 0)
    compliance_attached = sum(1 for row in systems if int(row.get("dwt_compliance_record_count") or 0) > 0)

    self_report_matched = int(metadata.get("dwt_self_report_matched_bin_count") or 0)
    self_report_records = int(metadata.get("dwt_self_report_matched_record_count") or 0)
    self_report_attached = sum(1 for row in systems if int(row.get("dwt_self_report_record_count") or 0) > 0)

    domestic_entries = [
        health_entry(
            source_key=SOURCE_KEYS["physical"],
            dataset_id="Water_Tank_2022/FeatureServer/27",
            name="NYC OTI Planimetric 2022 Water Tanks",
            entity_unit="current cooling-tower BINs with 2022 rooftop drinking-water tank polygons",
            retrieved_record_count=physical_features,
            requested_entity_count=requested,
            normalized_entity_count=physical_matched,
            matched_entity_count=physical_matched,
            attached_entity_count=physical_attached,
            displayed_entity_count=physical_attached,
            previous_coverage_percentage=previous_coverage(SOURCE_KEYS["physical"]),
            coverage_note=(
                "Coverage is observed exact-BIN overlap between current cooling-tower buildings and the NYC OTI 2022 rooftop water-tank physical layer. "
                "A missing polygon is not evidence that a building has no current domestic-water tank."
            ),
        ),
        health_entry(
            source_key=SOURCE_KEYS["compliance"],
            dataset_id="rytv-g5ui",
            name="NYC Drinking Water Tank Inspections and Audits Compliance Results",
            entity_unit="current cooling-tower BINs with DOHMH drinking-water tank oversight records",
            retrieved_record_count=compliance_records,
            requested_entity_count=int(metadata.get("dwt_compliance_requested_bin_count") or requested),
            normalized_entity_count=compliance_records,
            matched_entity_count=compliance_matched,
            attached_entity_count=compliance_attached,
            displayed_entity_count=compliance_attached,
            previous_coverage_percentage=previous_coverage(SOURCE_KEYS["compliance"]),
            coverage_note=(
                "Coverage is observed exact-BIN prevalence of official DOHMH drinking-water tank oversight/compliance records among cooling-tower buildings, not an expected-completeness target. "
                "No match does not establish that a building has no tank or no private compliance records."
            ),
        ),
        health_entry(
            source_key=SOURCE_KEYS["self_reports"],
            dataset_id="gjm4-k24g",
            name="Self-Reported Drinking Water Tank Inspection Results",
            entity_unit="current cooling-tower BINs with certified-inspector self-reported drinking-water tank records",
            retrieved_record_count=self_report_records,
            requested_entity_count=int(metadata.get("dwt_self_report_requested_bin_count") or requested),
            normalized_entity_count=self_report_records,
            matched_entity_count=self_report_matched,
            attached_entity_count=self_report_attached,
            displayed_entity_count=self_report_attached,
            previous_coverage_percentage=previous_coverage(SOURCE_KEYS["self_reports"]),
            coverage_note=(
                "Coverage is observed exact-BIN prevalence of owner/certified-inspector annual drinking-water tank reports among cooling-tower buildings. "
                "Self-reported records remain distinct from DOHMH inspection/audit evidence and do not affect TowerSignal Priority Score."
            ),
        ),
    ]

    entries.extend(domestic_entries)
    validate_source_health(entries)
    metadata["source_health"] = entries
    payload["metadata"] = metadata
    systems_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (output_dir / "source-health.json").write_text(
        json.dumps({"generated_at": metadata.get("generated_at"), "sources": entries}, indent=2),
        encoding="utf-8",
    )

    for row in systems:
        detail_path = safe_detail_path(output_dir, str(row.get("system_id") or ""))
        detail = load_json(detail_path, None)
        if not isinstance(detail, dict):
            raise RuntimeError(f"Missing generated detail payload while attaching domestic-water source health: {row.get('system_id')}")
        detail_metadata = detail.get("metadata") or {}
        detail_metadata["source_health"] = entries
        detail["metadata"] = detail_metadata
        detail_path.write_text(json.dumps(detail, separators=(",", ":")), encoding="utf-8")

    print(json.dumps({entry["source_key"]: {
        "status": entry["status"],
        "coverage_percentage": entry["coverage_percentage"],
        "attached": entry["attached_entity_count"],
        "displayed": entry["displayed_entity_count"],
    } for entry in domestic_entries}, indent=2))
    return domestic_entries


def main() -> None:
    parser = argparse.ArgumentParser(description="Attach domestic-water source health to generated TowerSignal payload")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data")
    parser.add_argument("--previous-snapshot", type=Path)
    args = parser.parse_args()
    attach(args.output, args.previous_snapshot)


if __name__ == "__main__":
    main()
