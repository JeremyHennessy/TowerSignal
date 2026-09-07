from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def safe_detail_path(base: Path, system_id: str) -> Path:
    safe = "".join(ch for ch in system_id if ch.isalnum() or ch in ("-", "_"))
    return base / "details" / (safe[:2] or "xx").lower() / f"{safe}.json"


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def attach(output_dir: Path, cache_path: Path) -> dict[str, int]:
    systems_path = output_dir / "systems.json"
    metadata_path = output_dir / "metadata.json"
    payload = load_json(systems_path)
    cache = load_json(cache_path)
    if cache.get("domain") != "NYC_LEGACY_DOB_PROJECT_CONTEXT":
        raise RuntimeError("Unexpected legacy DOB project cache domain")
    by_bbl = cache.get("by_bbl") or {}
    if not isinstance(by_bbl, dict):
        raise RuntimeError("Legacy DOB project cache by_bbl is malformed")

    systems = payload.get("systems") or []
    attached_systems = 0
    attached_records = 0
    explicit_systems = 0
    recent_relevant_systems = 0
    for row in systems:
        bbl = str(row.get("bbl") or "")
        context = by_bbl.get(bbl)
        summary = (context or {}).get("summary") or {}
        count = int(summary.get("record_count") or 0)
        explicit = int(summary.get("explicit_cooling_tower_count") or 0)
        recent = int(summary.get("recent_relevant_project_count") or 0)
        row["legacy_dob_project_record_count"] = count
        row["legacy_dob_explicit_cooling_tower_count"] = explicit
        row["legacy_dob_recent_relevant_project_count"] = recent
        row["latest_legacy_dob_activity_date"] = summary.get("latest_activity_date") if count else None
        if count:
            attached_systems += 1
            attached_records += count
        if explicit:
            explicit_systems += 1
        if recent:
            recent_relevant_systems += 1

        detail_path = safe_detail_path(output_dir, str(row["system_id"]))
        detail = load_json(detail_path)
        if context:
            detail["legacy_dob_project_context"] = {
                "summary": summary,
                "records": context.get("records") or [],
                "evidence_boundaries": cache.get("evidence_semantics") or {},
                "source": cache.get("source") or {},
                "generated_at": cache.get("generated_at"),
                "as_of": cache.get("as_of"),
            }
        else:
            detail["legacy_dob_project_context"] = None
        detail_path.write_text(json.dumps(detail, separators=(",", ":")), encoding="utf-8")

    summary = payload.get("summary") or {}
    summary["systems_with_legacy_dob_project_context"] = attached_systems
    summary["systems_with_legacy_dob_explicit_cooling_tower_context"] = explicit_systems
    summary["systems_with_recent_relevant_legacy_dob_projects"] = recent_relevant_systems
    payload["summary"] = summary

    metadata = payload.get("metadata") or {}
    source = cache.get("source") or {}
    metadata["legacy_dob_project_cache_available"] = True
    metadata["legacy_dob_project_match_basis"] = "BBL_EXACT"
    metadata["legacy_dob_project_requested_bbl_count"] = int(source.get("requested_bbl_count") or 0)
    metadata["legacy_dob_project_source_matched_bbl_count"] = int(source.get("source_matched_bbl_count") or 0)
    metadata["legacy_dob_project_exact_bbl_job_count"] = int(source.get("exact_bbl_job_count") or 0)
    metadata["legacy_dob_project_retained_bbl_count"] = int((cache.get("summary") or {}).get("retained_bbl_count") or 0)
    metadata["legacy_dob_project_retained_record_count"] = int((cache.get("summary") or {}).get("retained_record_count") or 0)
    sources = [item for item in metadata.get("sources", []) if item.get("dataset_id") != "ic3t-wcy2"]
    sources.append({
        "dataset_id": "ic3t-wcy2",
        "name": source.get("name") or "DOB Job Application Filings",
        "retrieved_at": cache.get("generated_at"),
        "source_record_count": int(source.get("source_record_count") or 0),
        "source_last_updated_at": source.get("source_last_updated_at"),
        "url": source.get("url"),
        "matched_record_count": int((cache.get("summary") or {}).get("retained_record_count") or 0),
        "source_query_scope": "Exact canonical BBLs; retained explicit cooling-tower text plus recent mechanical/boiler/plumbing/equipment project records only",
    })
    metadata["sources"] = sources
    payload["metadata"] = metadata

    systems_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    result = {
        "attached_systems": attached_systems,
        "attached_records": attached_records,
        "explicit_systems": explicit_systems,
        "recent_relevant_systems": recent_relevant_systems,
    }
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Attach bounded exact-BBL legacy DOB/BIS project context")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data")
    parser.add_argument("--cache", type=Path, default=ROOT / "public/data/legacy-dob-projects.json")
    args = parser.parse_args()
    attach(args.output, args.cache)


if __name__ == "__main__":
    main()
