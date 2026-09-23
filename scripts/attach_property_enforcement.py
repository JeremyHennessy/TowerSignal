from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from attach_labor_law_decisions import attach as attach_labor_law_decisions

ROOT = Path(__file__).resolve().parents[1]


def safe_detail_path(base: Path, system_id: str) -> Path:
    safe = "".join(ch for ch in system_id if ch.isalnum() or ch in ("-", "_"))
    return base / "details" / (safe[:2] or "xx").lower() / f"{safe}.json"


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def _source_row(source: dict[str, Any], matched_count: int) -> dict[str, Any]:
    raw_count = source.get("source_record_count")
    return {
        "dataset_id": source.get("dataset_id"),
        "name": source.get("name"),
        "retrieved_at": source.get("retrieved_at"),
        "source_record_count": int(raw_count) if raw_count not in (None, "") else None,
        "source_record_count_status": source.get("source_record_count_status"),
        "source_record_count_error": source.get("source_record_count_error"),
        "source_last_updated_at": source.get("source_last_updated_at"),
        "url": source.get("url"),
        "matched_record_count": matched_count,
        "source_query_scope": source.get("source_query_scope"),
        "source_health_status": source.get("source_health_status"),
        "source_health_reasons": source.get("source_health_reasons"),
        "source_observation_start_at": source.get("source_observation_start_at"),
        "source_observation_end_at": source.get("source_observation_end_at"),
        "source_snapshot_commit": source.get("source_snapshot_commit"),
        "current_status_available": source.get("current_status_available"),
    }


def _bbl_aliases(row: dict[str, Any]) -> list[str]:
    values = row.get("bbl_aliases") if isinstance(row.get("bbl_aliases"), list) else [row.get("bbl")]
    return sorted({str(value) for value in values if value})


def _merge_hpd_alias_contexts(by_bbl: dict[str, Any], aliases: list[str]) -> tuple[dict[str, Any] | None, list[str]]:
    records_by_id: dict[str, dict[str, Any]] = {}
    matched_aliases: list[str] = []
    for bbl in aliases:
        context = by_bbl.get(bbl)
        if not isinstance(context, dict):
            continue
        matched_aliases.append(bbl)
        for record in context.get("hpd_violations") or []:
            if not isinstance(record, dict):
                continue
            identity = str(record.get("violation_id") or "")
            if identity:
                records_by_id[identity] = record
    if not records_by_id:
        return None, matched_aliases
    records = sorted(
        records_by_id.values(),
        key=lambda item: (item.get("inspection_date") or "", item.get("violation_id") or ""),
        reverse=True,
    )
    open_records = [row for row in records if row.get("is_open")]
    summary = {
        "record_count": len(records),
        "open_count": len(open_records),
        "open_class_a_count": sum(1 for row in open_records if row.get("class") == "A"),
        "open_class_b_count": sum(1 for row in open_records if row.get("class") == "B"),
        "open_class_c_count": sum(1 for row in open_records if row.get("class") == "C"),
        "latest_inspection_date": max((row.get("inspection_date") or "" for row in records), default="") or None,
    }
    return {
        "summary": summary,
        "hpd_violations": records,
        "matched_bbl_aliases": matched_aliases,
        "match_basis": "BBL_ALIAS_EXACT",
    }, matched_aliases


def attach(output_dir: Path, cache_path: Path) -> dict[str, int]:
    systems_path = output_dir / "systems.json"
    metadata_path = output_dir / "metadata.json"
    payload = load_json(systems_path)
    cache = load_json(cache_path)
    if cache.get("domain") != "NYC_PROPERTY_ENFORCEMENT_CONTEXT":
        raise RuntimeError("Unexpected property enforcement cache domain")
    by_bbl = cache.get("by_bbl") or {}
    by_bin = cache.get("by_bin") or {}
    if not isinstance(by_bbl, dict) or not isinstance(by_bin, dict):
        raise RuntimeError("Property enforcement cache indexes are malformed")

    attached_hpd_systems = 0
    attached_swo_systems = 0
    attached_official_swo_snapshot_systems = 0
    attached_facade_systems = 0
    for row in payload.get("systems") or []:
        aliases = _bbl_aliases(row)
        bin_value = str(row.get("bin") or "")
        hpd_context, hpd_matched_aliases = _merge_hpd_alias_contexts(by_bbl, aliases)
        bin_context = by_bin.get(bin_value) or {}
        swo_context = bin_context.get("stop_work_orders") or {}
        official_swo_context = bin_context.get("official_swo_snapshot") or {}
        facade_context = bin_context.get("facade_compliance") or {}

        hpd_summary = (hpd_context or {}).get("summary") or {}
        swo_summary = swo_context.get("summary") or {}
        official_swo_summary = official_swo_context.get("summary") or {}
        facade_summary = facade_context.get("summary") or {}

        row["hpd_violation_count"] = int(hpd_summary.get("record_count") or 0)
        row["hpd_open_violation_count"] = int(hpd_summary.get("open_count") or 0)
        row["hpd_open_class_c_count"] = int(hpd_summary.get("open_class_c_count") or 0)
        row["latest_hpd_violation_inspection_date"] = hpd_summary.get("latest_inspection_date")
        row["stop_work_order_event_count"] = int(swo_summary.get("record_count") or 0)
        row["latest_stop_work_order_event_date"] = swo_summary.get("latest_event_date")
        row["official_swo_snapshot_record_count"] = int(official_swo_summary.get("record_count") or 0)
        row["official_swo_active_at_snapshot_count"] = int(official_swo_summary.get("active_at_snapshot_count") or 0)
        row["official_swo_rescinded_at_snapshot_count"] = int(official_swo_summary.get("rescinded_at_snapshot_count") or 0)
        row["official_swo_snapshot_latest_disposition_date"] = official_swo_summary.get("latest_disposition_date")
        row["official_swo_snapshot_observation_status"] = "NO_USABLE_BIN" if not bin_value else ("MATCHED_DATED_OBSERVATION" if row["official_swo_snapshot_record_count"] else "NO_MATCH_IN_DATED_SNAPSHOT")
        row["facade_compliance_filing_count"] = int(facade_summary.get("record_count") or 0)
        row["facade_latest_status"] = facade_summary.get("latest_status")
        row["facade_latest_cycle"] = facade_summary.get("latest_cycle")
        row["facade_latest_submitted_on"] = facade_summary.get("latest_submitted_on")

        if row["hpd_violation_count"]:
            attached_hpd_systems += 1
        if row["stop_work_order_event_count"]:
            attached_swo_systems += 1
        if row["official_swo_snapshot_record_count"]:
            attached_official_swo_snapshot_systems += 1
        if row["facade_compliance_filing_count"]:
            attached_facade_systems += 1

        detail_path = safe_detail_path(output_dir, str(row["system_id"]))
        detail = load_json(detail_path)
        detail["property_enforcement_context"] = {
            "hpd_violations": hpd_context,
            "hpd_matched_bbl_aliases": hpd_matched_aliases,
            "stop_work_orders": swo_context if swo_context.get("records") else None,
            "official_swo_snapshot": {
                "summary": official_swo_summary,
                "records": official_swo_context.get("records") or [],
                "observation_status": row["official_swo_snapshot_observation_status"],
                "source": (cache.get("sources") or {}).get("official_swo_snapshot") or {},
            },
            "facade_compliance": facade_context if facade_context.get("records") else None,
            "evidence_boundaries": cache.get("evidence_semantics") or {},
            "generated_at": cache.get("generated_at"),
        }
        detail_path.write_text(json.dumps(detail, separators=(",", ":")), encoding="utf-8")

    cache_summary = cache.get("summary") or {}
    summary = payload.get("summary") or {}
    summary["systems_with_hpd_violation_context"] = attached_hpd_systems
    summary["systems_with_stop_work_order_context"] = attached_swo_systems
    summary["systems_with_official_swo_snapshot_observation"] = attached_official_swo_snapshot_systems
    summary["systems_with_facade_compliance_context"] = attached_facade_systems
    payload["summary"] = summary

    metadata = payload.get("metadata") or {}
    metadata["property_enforcement_cache_available"] = True
    metadata["property_enforcement_generated_at"] = cache.get("generated_at")
    metadata["hpd_violation_match_basis"] = "BBL_ALIAS_EXACT"
    metadata["hpd_violation_requested_bbl_count"] = int(cache_summary.get("requested_bbl_count") or 0)
    metadata["stop_work_order_match_basis"] = "BIN_EXACT"
    metadata["official_swo_snapshot_match_basis"] = "BIN_EXACT"
    metadata["official_swo_snapshot_current_status_available"] = False
    metadata["official_swo_snapshot_source_last_updated_at"] = ((cache.get("sources") or {}).get("official_swo_snapshot") or {}).get("source_last_updated_at")
    metadata["official_swo_snapshot_observation_end_at"] = ((cache.get("sources") or {}).get("official_swo_snapshot") or {}).get("source_observation_end_at")
    metadata["facade_compliance_match_basis"] = "BIN_EXACT"
    metadata["hpd_violation_count"] = int(cache_summary.get("hpd_violation_count") or 0)
    metadata["hpd_open_violation_count"] = int(cache_summary.get("hpd_open_violation_count") or 0)
    metadata["stop_work_order_event_count"] = int(cache_summary.get("swo_event_count") or 0)
    metadata["official_swo_snapshot_record_count"] = int(cache_summary.get("official_swo_snapshot_record_count") or 0)
    metadata["facade_compliance_filing_count"] = int(cache_summary.get("facade_filing_count") or 0)

    cache_sources = cache.get("sources") or {}
    dataset_ids = {"wvxf-dwi5", "eabe-havv", "NYCDOB_SWOS_ISSUED_RESCINDED_SNAPSHOT_20240205", "xubg-57si"}
    sources = [item for item in metadata.get("sources", []) if item.get("dataset_id") not in dataset_ids]
    sources.extend((
        _source_row(cache_sources.get("hpd_violations") or {}, int(cache_summary.get("hpd_violation_count") or 0)),
        _source_row(cache_sources.get("stop_work_orders") or {}, int(cache_summary.get("swo_event_count") or 0)),
        _source_row(cache_sources.get("official_swo_snapshot") or {}, int(cache_summary.get("official_swo_snapshot_record_count") or 0)),
        _source_row(cache_sources.get("facade_compliance") or {}, int(cache_summary.get("facade_filing_count") or 0)),
    ))
    metadata["sources"] = sources
    payload["metadata"] = metadata

    systems_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    labor_result = attach_labor_law_decisions(output_dir, cache_path.with_name("labor-law-decisions.json"))
    result = {
        "attached_hpd_systems": attached_hpd_systems,
        "attached_swo_systems": attached_swo_systems,
        "attached_official_swo_snapshot_systems": attached_official_swo_snapshot_systems,
        "attached_facade_systems": attached_facade_systems,
        "labor_law_attached_systems": labor_result["attached_systems"],
        "labor_law_attached_records": labor_result["attached_records"],
    }
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Attach exact-key NYC property enforcement context")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data")
    parser.add_argument("--cache", type=Path, default=ROOT / "public/data/property-enforcement.json")
    args = parser.parse_args()
    attach(args.output, args.cache)


if __name__ == "__main__":
    main()
