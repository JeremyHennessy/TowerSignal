from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal import PRIORITY_MODEL_VERSION, SCHEMA_VERSION  # noqa: E402
from towersignal.fetch import fetch_dataset  # noqa: E402
from towersignal.inspections import aggregate_inspections  # noqa: E402
from towersignal.normalize import normalize_registrations  # noqa: E402
from towersignal.scoring import priority_score  # noqa: E402
from towersignal.signals import build_signals  # noqa: E402
from towersignal.validate import validate_generated, validate_normalized, validate_sources  # noqa: E402

REGISTRATION_ID = "y4fw-iqfr"
INSPECTION_ID = "f9wb-g8mb"


def load_rules() -> dict:
    return json.loads((ROOT / "config/rules/nyc.json").read_text(encoding="utf-8"))


def safe_detail_path(base: Path, system_id: str) -> Path:
    safe = "".join(ch for ch in system_id if ch.isalnum() or ch in ("-", "_"))
    prefix = (safe[:2] or "xx").lower()
    target = base / prefix / f"{safe}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def build(output_dir: Path) -> dict:
    rules = load_rules()
    registration_snapshot = fetch_dataset(REGISTRATION_ID, "system_id")
    inspection_snapshot = fetch_dataset(INSPECTION_ID, "system_id,inspection_date")
    validate_sources(registration_snapshot.rows, inspection_snapshot.rows)

    systems, dedupe_meta = normalize_registrations(registration_snapshot.rows)
    snapshot_date = datetime.now(ZoneInfo("America/New_York")).date()
    validate_normalized(systems, snapshot_date)
    inspections_by_system = aggregate_inspections(inspection_snapshot.rows)

    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    sources = [
        {
            "dataset_id": registration_snapshot.dataset_id,
            "name": registration_snapshot.name,
            "retrieved_at": registration_snapshot.retrieved_at,
            "source_record_count": registration_snapshot.source_record_count,
            "source_last_updated_at": registration_snapshot.source_last_updated_at,
            "url": "https://data.cityofnewyork.us/Health/NYC-Cooling-Tower-Registrations/y4fw-iqfr",
        },
        {
            "dataset_id": inspection_snapshot.dataset_id,
            "name": inspection_snapshot.name,
            "retrieved_at": inspection_snapshot.retrieved_at,
            "source_record_count": inspection_snapshot.source_record_count,
            "source_last_updated_at": inspection_snapshot.source_last_updated_at,
            "url": "https://data.cityofnewyork.us/Health/NYC-Cooling-Tower-System-Inspection-Results/f9wb-g8mb",
        },
    ]
    metadata = {
        "generated_at": generated_at,
        "snapshot_date": snapshot_date.isoformat(),
        "sources": sources,
        "normalized_system_count": len(systems),
        "source_duplicate_registration_rows": dedupe_meta["source_duplicate_rows"],
        "source_missing_registration_system_id_rows": dedupe_meta["source_missing_system_id_rows"],
        "rules_version": rules["rules_version"],
        "priority_model_version": PRIORITY_MODEL_VERSION,
    }

    summary_rows = []
    detail_dir = output_dir / "details"
    if detail_dir.exists():
        for old in detail_dir.rglob("*.json"):
            old.unlink()
    detail_dir.mkdir(parents=True, exist_ok=True)

    gap_count = 0
    recent_violation_count = 0
    active_equipment_total = 0

    for system in systems:
        inspections = inspections_by_system.get(system["system_id"], [])
        signal_state = build_signals(system, inspections, rules, snapshot_date)
        scoring = priority_score(system, signal_state)
        signals = signal_state["signals"]
        signal_types = [signal["type"] for signal in signals]
        if "POTENTIAL_SAMPLING_GAP" in signal_types:
            gap_count += 1
        if signal_state["recent_confirmed_violation"]:
            recent_violation_count += 1
        active_equipment_total += int(system.get("active_equipment") or 0)

        primary = next(
            (candidate for candidate in (
                "CONFIRMED_RECENT_VIOLATION",
                "POTENTIAL_SAMPLING_GAP",
                "NO_PUBLIC_SAMPLE_DATE",
                "MULTIPLE_ACTIVE_EQUIPMENT",
                "RECENT_NYC_HEALTH_INSPECTION",
            ) if candidate in signal_types),
            "NO_CURRENT_SIGNAL",
        )
        if primary == "CONFIRMED_RECENT_VIOLATION":
            evidence_confidence = "CONFIRMED"
        elif primary in {"POTENTIAL_SAMPLING_GAP", "NO_PUBLIC_SAMPLE_DATE"}:
            evidence_confidence = "VERIFY"
        else:
            evidence_confidence = "STRONG_SIGNAL"

        latest_inspection = signal_state["latest_inspection"]
        row = {
            "system_id": system["system_id"],
            "bin": system["bin"],
            "bbl": system["bbl"],
            "address": system["address"],
            "borough": system["borough"],
            "zip": system["zip"],
            "active_equipment": system["active_equipment"],
            "latitude": system["latitude"],
            "longitude": system["longitude"],
            "latest_sample_date": system["latest_sample_date"],
            "days_since_latest_sample": signal_state["days_since_latest_sample"],
            "latest_inspection_date": latest_inspection.get("inspection_date") if latest_inspection else None,
            "latest_inspection_type": latest_inspection.get("inspection_type") if latest_inspection else None,
            "confirmed_violation": signal_state["confirmed_violation"],
            "recent_confirmed_violation": signal_state["recent_confirmed_violation"],
            "violation_types": signal_state["violation_types"],
            "signal_types": signal_types,
            "primary_signal": primary,
            "evidence_confidence": evidence_confidence,
            "priority_score": scoring["score"],
            "score_components": scoring["components"],
        }
        summary_rows.append(row)

        detail = {
            "schema_version": SCHEMA_VERSION,
            "metadata": metadata,
            "identity": {
                "system_id": system["system_id"],
                "bin": system["bin"],
                "bbl": system["bbl"],
                "address": system["address"],
                "borough": system["borough"],
                "zip": system["zip"],
                "active_equipment": system["active_equipment"],
                "latitude": system["latitude"],
                "longitude": system["longitude"],
            },
            "sample_history": {
                "source_raw": system["sampledates_raw"],
                "dates": system["sample_dates"],
                "malformed_values": system["malformed_sample_values"],
                "latest_sample_date": system["latest_sample_date"],
                "previous_sample_date": system["previous_sample_date"],
                "latest_sample_interval_days": system["latest_sample_interval_days"],
                "intervals_days": system["sample_intervals_days"],
                "sample_count": system["sample_count"],
            },
            "signals": signals,
            "inspection_history": inspections,
            "scoring": scoring,
        }
        safe_detail_path(detail_dir, system["system_id"]).write_text(json.dumps(detail, separators=(",", ":")), encoding="utf-8")

    summary_rows.sort(key=lambda item: (-item["priority_score"], item.get("borough") or "", item.get("address") or ""))
    payload = {
        "schema_version": SCHEMA_VERSION,
        "metadata": metadata,
        "summary": {
            "registered_systems": len(summary_rows),
            "active_equipment": active_equipment_total,
            "potential_sampling_gaps": gap_count,
            "recent_confirmed_violations": recent_violation_count,
        },
        "systems": summary_rows,
    }
    validate_generated(payload)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "systems.json").write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    print(f"Generated {len(summary_rows):,} systems at {generated_at}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build TowerSignal static NYC data")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data")
    args = parser.parse_args()
    build(args.output)


if __name__ == "__main__":
    main()
