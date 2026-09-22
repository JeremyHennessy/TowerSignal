from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _normalize_bbl(value: Any) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits if len(digits) == 10 and digits[0] in "12345" else None


def _safe_detail_path(base: Path, system_id: str) -> Path:
    safe = "".join(ch for ch in system_id if ch.isalnum() or ch in ("-", "_"))
    return base / "details" / (safe[:2] or "xx").lower() / f"{safe}.json"


def _aliases(system: dict[str, Any]) -> list[str]:
    values = system.get("bbl_aliases") if isinstance(system.get("bbl_aliases"), list) else [system.get("bbl")]
    return sorted({
        bbl
        for value in values
        if (bbl := _normalize_bbl(value))
    })


def _merge_profiles(profiles: dict[str, Any], aliases: list[str]) -> tuple[dict[str, Any] | None, list[str]]:
    matched = [bbl for bbl in aliases if isinstance(profiles.get(bbl), dict)]
    if not matched:
        return None, []
    category_counts: dict[str, int] = {}
    years: set[str] = set()
    request_count = 0
    first_dates: list[str] = []
    latest_dates: list[str] = []
    for bbl in matched:
        profile = profiles[bbl]
        request_count += int(profile.get("request_count") or 0)
        for category, count in (profile.get("category_counts") or {}).items():
            category_counts[str(category)] = category_counts.get(str(category), 0) + int(count or 0)
        years.update(str(year) for year in (profile.get("years") or []))
        if profile.get("first_reported_date"):
            first_dates.append(str(profile["first_reported_date"]))
        if profile.get("latest_reported_date"):
            latest_dates.append(str(profile["latest_reported_date"]))
    ordered_years = sorted(years)
    merged = {
        "bbl": aliases[0] if aliases else None,
        "request_count": request_count,
        "category_counts": dict(sorted(category_counts.items())),
        "years": ordered_years,
        "year_count": len(ordered_years),
        "first_reported_date": min(first_dates) if first_dates else None,
        "latest_reported_date": max(latest_dates) if latest_dates else None,
        "recurrent_history": request_count >= 3 and len(ordered_years) >= 2,
        "has_2024_activity": "2024" in ordered_years,
        "property_link_confidence": "CONFIRMED_EXACT_BBL_ALIAS",
        "evidence_semantics": "REPORTED_SERVICE_REQUEST",
    }
    return merged, matched


def attach(output_dir: Path, cache_path: Path) -> dict[str, int]:
    systems_path = output_dir / "systems.json"
    systems_payload = json.loads(systems_path.read_text(encoding="utf-8"))
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    if cache.get("schema_version") != "1.0" or cache.get("domain") != "NYC_HISTORICAL_BUILDING_WATER_CONTEXT":
        raise RuntimeError("Unexpected historical 311 context cache")
    systems = systems_payload.get("systems")
    profiles = cache.get("by_bbl")
    if not isinstance(systems, list) or not isinstance(profiles, dict):
        raise RuntimeError("Historical 311 attachment inputs are malformed")

    attached_systems = 0
    attached_requests = 0
    for system in systems:
        if not isinstance(system, dict):
            continue
        system_id = str(system.get("system_id") or "")
        aliases = _aliases(system)
        profile, matched_aliases = _merge_profiles(profiles, aliases)
        detail_path = _safe_detail_path(output_dir, system_id)
        if not detail_path.exists():
            raise RuntimeError(f"Missing account detail while attaching historical 311 context: {system_id}")
        detail = json.loads(detail_path.read_text(encoding="utf-8"))
        if isinstance(profile, dict):
            context = {
                "summary": profile,
                "matched_bbl_aliases": matched_aliases,
                "match_basis": "BBL_ALIAS_EXACT",
                "evidence_boundaries": cache["evidence_boundaries"],
                "source": {
                    "dataset_ids": sorted({str(row.get("dataset_id")) for row in cache.get("source_health", []) if isinstance(row, dict) and row.get("dataset_id")}),
                    "generated_at": cache.get("generated_at"),
                    "query_boundaries": cache.get("query_boundaries"),
                },
            }
            detail["nyc_historical_water_context"] = context
            attached_systems += 1
            attached_requests += int(profile.get("request_count") or 0)
        else:
            detail["nyc_historical_water_context"] = None
        detail_path.write_text(json.dumps(detail, separators=(",", ":")), encoding="utf-8")

    metadata = systems_payload.get("metadata")
    if not isinstance(metadata, dict):
        raise RuntimeError("TowerSignal systems metadata is malformed")
    metadata.update(
        {
            "nyc_historical_311_context_available": True,
            "nyc_historical_311_match_basis": "BBL_ALIAS_EXACT",
            "nyc_historical_311_requested_bbl_count": int(cache["summary"]["requested_bbl_count"]),
            "nyc_historical_311_matched_bbl_count": int(cache["summary"]["matched_bbl_count"]),
            "nyc_historical_311_systems_attached": attached_systems,
            "nyc_historical_311_attached_request_count": attached_requests,
        }
    )
    systems_payload["summary"]["systems_with_nyc_historical_water_context"] = attached_systems
    systems_path.write_text(json.dumps(systems_payload, separators=(",", ":")), encoding="utf-8")
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    report = {
        "systems_attached": attached_systems,
        "attached_request_count": attached_requests,
        "match_basis": "BBL_ALIAS_EXACT",
    }
    (output_dir / "historical-311-context-coverage.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {"systems_attached": attached_systems, "attached_request_count": attached_requests}


def main() -> None:
    parser = argparse.ArgumentParser(description="Attach compact historical NYC 311 context by exact BBL")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data")
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(attach(args.output, args.cache), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
