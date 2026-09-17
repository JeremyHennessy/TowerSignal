from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATASET_ID = "NYS_OFFICIAL_REPORTS_LABOR_LAW_PUBLISHED_DECISIONS"


def safe_detail_path(base: Path, system_id: str) -> Path:
    safe = "".join(ch for ch in system_id if ch.isalnum() or ch in ("-", "_"))
    return base / "details" / (safe[:2] or "xx").lower() / f"{safe}.json"


def load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def attach(output_dir: Path, cache_path: Path) -> dict[str, int]:
    systems_path = output_dir / "systems.json"
    metadata_path = output_dir / "metadata.json"
    payload = load(systems_path)
    cache = load(cache_path)
    if cache.get("domain") != "NYS_LABOR_LAW_PUBLISHED_DECISIONS":
        raise RuntimeError("Unexpected Labor Law cache domain")
    by_system = cache.get("by_system") or {}
    if not isinstance(by_system, dict):
        raise RuntimeError("Malformed Labor Law cache system index")

    attached_systems = 0
    attached_records = 0
    for row in payload.get("systems") or []:
        system_id = str(row.get("system_id") or "")
        records = by_system.get(system_id) or []
        row["labor_law_published_decision_count"] = len(records)
        row["labor_law_latest_published_decision_date"] = max((str(item.get("publication_date") or "") for item in records), default="") or None
        if records:
            attached_systems += 1
            attached_records += len(records)
        detail_path = safe_detail_path(output_dir, system_id)
        detail = load(detail_path)
        detail["labor_law_published_decisions"] = {
            "records": records,
            "source": cache.get("source") or {},
            "evidence_boundaries": cache.get("evidence_boundaries") or {},
            "generated_at": cache.get("generated_at"),
        }
        detail_path.write_text(json.dumps(detail, separators=(",", ":")), encoding="utf-8")

    summary = payload.get("summary") or {}
    summary["systems_with_labor_law_published_decisions"] = attached_systems
    payload["summary"] = summary

    metadata = payload.get("metadata") or {}
    metadata["labor_law_published_decisions_available"] = True
    metadata["labor_law_published_decision_match_basis"] = "PUBLISHED_DECISION_EXPLICIT_WORKSITE_ADDRESS_EXACT"
    metadata["labor_law_published_decision_count"] = int((cache.get("summary") or {}).get("retained_labor_law_decision_count") or 0)
    metadata["labor_law_published_decision_attached_system_count"] = attached_systems
    metadata["labor_law_current_filing_status_available"] = False
    source = cache.get("source") or {}
    source_row = {
        "dataset_id": DATASET_ID,
        "name": source.get("name") or "New York Official Reports — Labor Law published decisions",
        "retrieved_at": source.get("retrieved_at"),
        "source_record_count": int(source.get("source_record_count") or 0),
        "source_last_updated_at": None,
        "url": source.get("url"),
        "matched_record_count": int((cache.get("summary") or {}).get("retained_labor_law_decision_count") or 0),
        "source_query_scope": source.get("source_query_scope"),
        "source_health_status": source.get("source_health_status") or "WARNING",
        "source_health_reasons": source.get("source_health_reasons") or [],
        "current_status_available": False,
    }
    metadata["sources"] = [item for item in metadata.get("sources", []) if item.get("dataset_id") != DATASET_ID] + [source_row]
    payload["metadata"] = metadata

    systems_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    result = {"attached_systems": attached_systems, "attached_records": attached_records}
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Attach exact-property Labor Law published-decision evidence")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data")
    parser.add_argument("--cache", type=Path, default=ROOT / "public/data/labor-law-decisions.json")
    args = parser.parse_args()
    attach(args.output, args.cache)


if __name__ == "__main__":
    main()
