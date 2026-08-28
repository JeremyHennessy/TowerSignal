from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RECENT_DAYS = 365

SIGNAL_RANK = {
    "TDSB_COOLING_TOWER_RENEWAL": 100,
    "RECENT_SOURCE_ACTIVE_COOLING_TOWER_PERMIT": 90,
    "SOURCE_ACTIVE_COOLING_TOWER_PERMIT": 80,
    "RECENT_SOURCE_ACTIVE_MECHANICAL_PERMIT": 70,
    "SOURCE_ACTIVE_MECHANICAL_PERMIT": 65,
    "COOLING_TOWER_PROJECT_HISTORY": 60,
    "TDSB_RELATED_MECHANICAL_RENEWAL": 55,
    "HISTORICAL_MECHANICAL_PROJECT": 40,
}


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    for candidate in (text[:10], text):
        try:
            return datetime.fromisoformat(candidate.replace("Z", "+00:00")).date()
        except ValueError:
            continue
    return None


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            serialized = dict(row)
            for key, value in list(serialized.items()):
                if isinstance(value, (list, dict)):
                    serialized[key] = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
            writer.writerow(serialized)


def normalize(output_dir: Path) -> dict[str, Any]:
    evidence_path = output_dir / "evidence.json"
    properties_path = output_dir / "properties.json"
    summary_path = output_dir / "summary.json"
    evidence_payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    properties_payload = json.loads(properties_path.read_text(encoding="utf-8"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    generated_at = str(summary.get("generated_at") or "")
    as_of = parse_date(generated_at)
    if as_of is None:
        raise RuntimeError(f"Toronto POC summary has unusable generated_at: {generated_at!r}")

    evidence = evidence_payload.get("evidence") or []
    properties = properties_payload.get("properties") or []
    recent_active_tower_properties: set[str] = set()
    source_active_tower_properties: set[str] = set()

    for item in evidence:
        source_key = str(item.get("source_key") or "")
        if source_key != "toronto_building_permits_active":
            continue
        equipment_type = str(item.get("equipment_type") or "")
        event_date = parse_date(item.get("event_date"))
        days_old = (as_of - event_date).days if event_date else None
        recent = days_old is not None and 0 <= days_old <= RECENT_DAYS
        item["source_active_record"] = True
        item["event_age_days"] = days_old
        item["recent_activity_365d"] = recent
        if equipment_type == "cooling_tower":
            source_active_tower_properties.add(item["property_key"])
            item["signal_type"] = (
                "RECENT_SOURCE_ACTIVE_COOLING_TOWER_PERMIT" if recent else "SOURCE_ACTIVE_COOLING_TOWER_PERMIT"
            )
            if recent:
                recent_active_tower_properties.add(item["property_key"])
        else:
            item["signal_type"] = (
                "RECENT_SOURCE_ACTIVE_MECHANICAL_PERMIT" if recent else "SOURCE_ACTIVE_MECHANICAL_PERMIT"
            )

    evidence_by_id = {item["evidence_id"]: item for item in evidence}
    for property_item in properties:
        evidence_ids = list(property_item.get("explicit_tower_evidence_ids") or []) + list(
            property_item.get("supporting_evidence_ids") or []
        )
        signals = {
            evidence_by_id[evidence_id]["signal_type"]
            for evidence_id in evidence_ids
            if evidence_id in evidence_by_id and evidence_by_id[evidence_id].get("signal_type")
        }
        property_item["commercial_signals"] = sorted(
            signals,
            key=lambda value: (-SIGNAL_RANK.get(value, 0), value),
        )
        active_rows = [
            evidence_by_id[evidence_id]
            for evidence_id in evidence_ids
            if evidence_id in evidence_by_id and evidence_by_id[evidence_id].get("source_active_record")
        ]
        property_item["source_active_permit_record"] = bool(active_rows)
        recent_rows = [row for row in active_rows if row.get("recent_activity_365d")]
        property_item["recent_source_active_permit_activity_365d"] = bool(recent_rows)
        recent_dates = [row.get("event_date") for row in recent_rows if row.get("event_date")]
        property_item["latest_recent_permit_activity_date"] = max(recent_dates) if recent_dates else None

    counts = summary.setdefault("counts", {})
    counts.pop("active_permit_confirmed_cooling_tower_properties", None)
    counts["source_active_permit_confirmed_cooling_tower_properties"] = len(source_active_tower_properties)
    counts["recent_365d_source_active_permit_confirmed_cooling_tower_properties"] = len(
        recent_active_tower_properties
    )
    summary["permit_timing_contract"] = {
        "source_active": "Record is present in the City of Toronto Active Permits dataset; this does not by itself mean recent buying activity.",
        "recent_activity_window_days": RECENT_DAYS,
        "recent_activity": "Source-active permit record with a usable event date no more than 365 days before POC generation.",
        "old_source_active_records": "Retained as equipment/project evidence but not represented as recent activity.",
    }

    evidence_payload["metadata"] = summary
    properties_payload["metadata"] = summary
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    evidence_path.write_text(json.dumps(evidence_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    properties_path.write_text(json.dumps(properties_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    write_csv(
        output_dir / "properties.csv",
        properties,
        [
            "property_key",
            "tower_status",
            "address",
            "property_name",
            "organization",
            "geo_id",
            "equipment_types",
            "commercial_signals",
            "renewal_priorities",
            "latest_source_event_date",
            "source_active_permit_record",
            "recent_source_active_permit_activity_365d",
            "latest_recent_permit_activity_date",
            "source_keys",
            "evidence_count",
        ],
    )
    write_csv(
        output_dir / "evidence.csv",
        evidence,
        [
            "evidence_id",
            "source_key",
            "source_record_id",
            "source_status",
            "source_url",
            "property_key",
            "geo_id",
            "address",
            "property_name",
            "organization",
            "equipment_type",
            "evidence_confidence",
            "signal_type",
            "event_date",
            "event_age_days",
            "recent_activity_365d",
            "priority",
            "description",
        ],
    )
    print(
        json.dumps(
            {
                "source_active_tower_properties": len(source_active_tower_properties),
                "recent_365d_source_active_tower_properties": len(recent_active_tower_properties),
            },
            indent=2,
        )
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize Toronto POC permit source-state vs recency")
    parser.add_argument("--output", type=Path, default=ROOT / "data/toronto/poc/current")
    args = parser.parse_args()
    normalize(args.output)


if __name__ == "__main__":
    main()
