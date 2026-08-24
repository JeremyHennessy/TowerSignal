from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.source_health import health_entry, validate_source_health  # noqa: E402

ACRIS_SOURCE_KEY = "acris_recent"
WARNING_AGE_DAYS = 3.0
FAIL_AGE_DAYS = 30.0


def safe_detail_path(base: Path, system_id: str) -> Path:
    safe = "".join(ch for ch in system_id if ch.isalnum() or ch in ("-", "_"))
    return base / "details" / (safe[:2] or "xx").lower() / f"{safe}.json"


def _age_days(value: str | None) -> float | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() / 86400.0)


def _missing_entry(requested_bbl_count: int) -> dict[str, Any]:
    return {
        "source_key": ACRIS_SOURCE_KEY,
        "dataset_id": "ACRIS-VERIFIED-CACHE",
        "name": "NYC ACRIS recent property activity cache",
        "entity_unit": "cooling-tower BBLs with relevant ACRIS activity in the bounded window",
        "retrieved_record_count": 0,
        "requested_entity_count": requested_bbl_count,
        "normalized_entity_count": 0,
        "matched_entity_count": 0,
        "attached_entity_count": 0,
        "displayed_entity_count": 0,
        "coverage_percentage": None,
        "previous_coverage_percentage": None,
        "coverage_change_percentage_points": None,
        "coverage_note": "Verified ACRIS cache is temporarily unavailable. TowerSignal remains published from its other verified sources; ACRIS timing context is omitted rather than inferred.",
        "status": "WARNING",
        "status_reasons": ["verified ACRIS cache unavailable for this snapshot"],
    }


def attach(output_dir: Path) -> dict[str, Any]:
    systems_path = output_dir / "systems.json"
    metadata_path = output_dir / "metadata.json"
    payload = json.loads(systems_path.read_text(encoding="utf-8"))
    metadata = payload.get("metadata") or {}
    systems = payload.get("systems") or []
    entries = [entry for entry in metadata.get("source_health", []) if entry.get("source_key") != ACRIS_SOURCE_KEY]

    requested = int(metadata.get("acris_requested_bbl_count") or 0)
    cache_available = bool(metadata.get("acris_cache_available"))
    if not cache_available:
        acris_entry = _missing_entry(requested)
    else:
        matched_bbls = int(metadata.get("acris_matched_bbl_count") or 0)
        matched_documents = int(metadata.get("acris_matched_document_count") or 0)
        attached = sum(1 for row in systems if int(row.get("acris_recent_document_count") or 0) > 0)
        acris_entry = health_entry(
            source_key=ACRIS_SOURCE_KEY,
            dataset_id="bnx9-e6tj+8h5j-fqxa+636b-3b5g",
            name="NYC ACRIS recent property activity cache",
            entity_unit="cooling-tower BBLs with relevant ACRIS activity in the bounded window",
            retrieved_record_count=matched_documents,
            requested_entity_count=requested,
            normalized_entity_count=matched_bbls,
            matched_entity_count=matched_bbls,
            attached_entity_count=attached,
            displayed_entity_count=attached,
            previous_coverage_percentage=None,
            coverage_note=(
                "Coverage is observed 365-day relevant-document activity prevalence across exact cooling-tower BBLs, not a source-completeness target. "
                "A BBL without a cached match is not evidence that no property transaction or filing ever occurred."
            ),
        )
        reasons = list(acris_entry.get("status_reasons") or [])
        age = _age_days(metadata.get("acris_cache_generated_at"))
        if age is None:
            acris_entry["status"] = "FAILED"
            reasons.append("verified cache generation time is missing or invalid")
        elif age > FAIL_AGE_DAYS:
            acris_entry["status"] = "FAILED"
            reasons.append(f"verified cache is {age:.1f} days old, above the {FAIL_AGE_DAYS:.0f}-day hard limit")
        elif age > WARNING_AGE_DAYS and acris_entry["status"] != "FAILED":
            acris_entry["status"] = "WARNING"
            reasons.append(f"verified cache is {age:.1f} days old")
        if metadata.get("acris_cache_universe_aligned") is False and acris_entry["status"] != "FAILED":
            acris_entry["status"] = "WARNING"
            reasons.append("cache BBL universe differs from the current NYC tower snapshot; unmatched new BBLs await the next cache refresh")
        acris_entry["status_reasons"] = reasons

    entries.append(acris_entry)
    validate_source_health(entries)
    metadata["source_health"] = entries
    payload["metadata"] = metadata
    systems_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (output_dir / "source-health.json").write_text(json.dumps({"generated_at": metadata.get("generated_at"), "sources": entries}, indent=2), encoding="utf-8")

    for row in systems:
        detail_path = safe_detail_path(output_dir, str(row.get("system_id") or ""))
        detail = json.loads(detail_path.read_text(encoding="utf-8"))
        detail_metadata = detail.get("metadata") or {}
        detail_metadata["source_health"] = entries
        detail["metadata"] = detail_metadata
        detail_path.write_text(json.dumps(detail, separators=(",", ":")), encoding="utf-8")

    print(json.dumps({
        "source_key": ACRIS_SOURCE_KEY,
        "status": acris_entry["status"],
        "coverage_percentage": acris_entry["coverage_percentage"],
        "attached": acris_entry["attached_entity_count"],
        "displayed": acris_entry["displayed_entity_count"],
        "reasons": acris_entry["status_reasons"],
    }, indent=2))
    return acris_entry


def main() -> None:
    parser = argparse.ArgumentParser(description="Attach ACRIS verified-cache source health to generated TowerSignal payload")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data")
    args = parser.parse_args()
    attach(args.output)


if __name__ == "__main__":
    main()
