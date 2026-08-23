from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.nys_registry import (  # noqa: E402
    NYS_COOLING_TOWER_DATASET_ID,
    NYS_COOLING_TOWER_URL,
    NYS_JURISDICTION,
    NYS_SOURCE_REGIME,
    fetch_nys_registry,
    normalize_nys_registry,
)

NYS_SCHEMA_VERSION = "1.0"


def build(output_dir: Path) -> dict:
    snapshot = fetch_nys_registry()
    systems, normalization = normalize_nys_registry(snapshot.rows)
    if not systems:
        raise RuntimeError("NYS cooling-tower source produced no normalized equipment records")

    source_county_counts = Counter(row.get("source_county") for row in systems if row.get("source_county"))
    status_counts = Counter(row.get("ct_status") for row in systems if row.get("ct_status"))
    compliance_counts = Counter(row.get("regulation_compliance") for row in systems if row.get("regulation_compliance"))
    result_counts = Counter(row.get("latest_sample_result") for row in systems if row.get("latest_sample_result"))
    operation_counts = Counter(row.get("operation_duration") for row in systems if row.get("operation_duration"))

    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    metadata = {
        "schema_version": NYS_SCHEMA_VERSION,
        "generated_at": generated_at,
        "jurisdiction": NYS_JURISDICTION,
        "source_regime": NYS_SOURCE_REGIME,
        "source": {
            "dataset_id": snapshot.dataset_id,
            "name": snapshot.name,
            "retrieved_at": snapshot.retrieved_at,
            "source_record_count": snapshot.source_record_count,
            "source_last_updated_at": snapshot.source_last_updated_at,
            "url": NYS_COOLING_TOWER_URL,
            "scope_note": (
                "Official NYS Department of Health weekly extract. Source documentation describes statewide coverage excluding NYC. "
                "Published county values are preserved as source provenance and are not used alone to infer NYC geography."
            ),
        },
        **normalization,
    }
    summary = {
        "registered_equipment": len(systems),
        "mapped_equipment": sum(1 for row in systems if row.get("latitude") is not None and row.get("longitude") is not None),
        "non_compliant": compliance_counts.get("Non-compliant", 0),
        "compliant": compliance_counts.get("Compliant", 0),
        "sample_required": status_counts.get("Sample_Required", 0),
        "update_required": status_counts.get("Update_Required", 0),
        "missing_legionella_result": status_counts.get("Missing Legionella Result", 0),
        "disinfection_required": status_counts.get("Disinfection Required", 0),
        "decommissioned": status_counts.get("Decommissioned", 0),
        "out_of_service": status_counts.get("Out of Service", 0),
        "multi_equipment_properties": normalization["multi_equipment_property_count"],
        "equipment_at_multi_equipment_properties": normalization["equipment_at_multi_equipment_properties"],
        "max_equipment_per_property": normalization["max_equipment_per_property"],
        "published_county_counts": dict(sorted(source_county_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "compliance_counts": dict(sorted(compliance_counts.items())),
        "sample_result_counts": dict(sorted(result_counts.items())),
        "operation_duration_counts": dict(sorted(operation_counts.items())),
    }
    payload = {"schema_version": NYS_SCHEMA_VERSION, "metadata": metadata, "summary": summary, "systems": systems}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "nys-systems.json").write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    (output_dir / "nys-metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps({
        "registered_equipment": summary["registered_equipment"],
        "mapped_equipment": summary["mapped_equipment"],
        "non_compliant": summary["non_compliant"],
        "sample_required": summary["sample_required"],
        "disinfection_required": summary["disinfection_required"],
        "multi_equipment_properties": summary["multi_equipment_properties"],
        "source_record_count": snapshot.source_record_count,
    }, indent=2))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build TowerSignal NYS cooling-tower registry payload")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data")
    args = parser.parse_args()
    build(args.output)


if __name__ == "__main__":
    main()