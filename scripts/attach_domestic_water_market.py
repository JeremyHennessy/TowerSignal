from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _normalize_bin(value: Any) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits if len(digits) == 7 else None


def safe_detail_path(base: Path, system_id: str) -> Path:
    safe = "".join(ch for ch in system_id if ch.isalnum() or ch in ("-", "_"))
    return base / "details" / (safe[:2] or "xx").lower() / f"{safe}.json"


def _property_by_exact_bin(cache: dict[str, Any]) -> dict[str, dict[str, Any]]:
    properties = cache.get("properties") or []
    result: dict[str, dict[str, Any]] = {}
    for property_profile in properties:
        if not isinstance(property_profile, dict):
            continue
        bin_value = _normalize_bin(property_profile.get("bin"))
        if not bin_value:
            continue
        if property_profile.get("building_key") != f"NYC-BIN-{bin_value}":
            continue
        if bin_value in result:
            raise RuntimeError(f"Domestic-water market cache contains duplicate exact-BIN property profile: {bin_value}")
        result[bin_value] = property_profile
    return result


def _public_property_profile(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "building_key": profile.get("building_key"),
        "bin": profile.get("bin"),
        "bbl": profile.get("bbl"),
        "address": profile.get("address"),
        "borough": profile.get("borough"),
        "zip": profile.get("zip"),
        "inspection_count": int(profile.get("inspection_count") or 0),
        "observed_tank_count": int(profile.get("observed_tank_count") or 0),
        "observed_provider_ids": list(profile.get("observed_provider_ids") or []),
        "observed_lab_ids": list(profile.get("observed_lab_ids") or []),
        "latest_inspection_date": profile.get("latest_inspection_date"),
        "latest_reporting_year": profile.get("latest_reporting_year"),
        "current_observed_provider_id": profile.get("current_observed_provider_id"),
        "current_observed_provider_raw": profile.get("current_observed_provider_raw"),
        "current_observed_lab_id": profile.get("current_observed_lab_id"),
        "current_observed_lab_raw": profile.get("current_observed_lab_raw"),
        "compliance_activity_count": int(profile.get("compliance_activity_count") or 0),
        "violation_count": int(profile.get("violation_count") or 0),
        "latest_violation_date": profile.get("latest_violation_date"),
    }


def attach(output_dir: Path, cache_path: Path) -> dict[str, Any]:
    systems_path = output_dir / "systems.json"
    metadata_path = output_dir / "metadata.json"
    if not systems_path.exists():
        raise RuntimeError(f"Base NYC systems payload is missing: {systems_path}")
    if not cache_path.exists():
        raise RuntimeError(f"Domestic-water market cache is missing: {cache_path}")

    payload = json.loads(systems_path.read_text(encoding="utf-8"))
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    if cache.get("domain") != "NY_DOMESTIC_WATER_PROVIDER_INTELLIGENCE":
        raise RuntimeError("Domestic-water market cache has unexpected domain")

    systems = payload.get("systems") or []
    metadata = payload.get("metadata") or {}
    summary = payload.get("summary") or {}
    properties_by_bin = _property_by_exact_bin(cache)

    attached = 0
    current_provider = 0
    current_lab = 0
    inspection_records = 0
    compliance_records = 0

    for row in systems:
        if not isinstance(row, dict):
            continue
        system_id = str(row.get("system_id") or "")
        bin_value = _normalize_bin(row.get("bin"))
        profile = properties_by_bin.get(bin_value) if bin_value else None
        public_profile = _public_property_profile(profile) if profile else None

        row.update({
            "dwt_market_exact_bin_match": bool(public_profile),
            "dwt_market_inspection_count": public_profile["inspection_count"] if public_profile else 0,
            "dwt_market_observed_provider_count": len(public_profile["observed_provider_ids"]) if public_profile else 0,
            "dwt_market_current_provider_id": public_profile["current_observed_provider_id"] if public_profile else None,
            "dwt_market_current_provider_raw": public_profile["current_observed_provider_raw"] if public_profile else None,
            "dwt_market_latest_inspection_date": public_profile["latest_inspection_date"] if public_profile else None,
            "dwt_market_observed_lab_count": len(public_profile["observed_lab_ids"]) if public_profile else 0,
            "dwt_market_current_lab_id": public_profile["current_observed_lab_id"] if public_profile else None,
            "dwt_market_current_lab_raw": public_profile["current_observed_lab_raw"] if public_profile else None,
            "dwt_market_compliance_activity_count": public_profile["compliance_activity_count"] if public_profile else 0,
            "dwt_market_violation_count": public_profile["violation_count"] if public_profile else 0,
            "dwt_market_latest_violation_date": public_profile["latest_violation_date"] if public_profile else None,
        })

        if public_profile:
            attached += 1
            inspection_records += public_profile["inspection_count"]
            compliance_records += public_profile["compliance_activity_count"]
            if public_profile["current_observed_provider_id"] and public_profile["current_observed_provider_raw"]:
                current_provider += 1
            if public_profile["current_observed_lab_id"] and public_profile["current_observed_lab_raw"]:
                current_lab += 1

        detail_path = safe_detail_path(output_dir, system_id)
        if not detail_path.exists():
            raise RuntimeError(f"Missing account detail while attaching domestic-water market evidence: {system_id}")
        detail = json.loads(detail_path.read_text(encoding="utf-8"))
        detail["domestic_water_market"] = None if not public_profile else {
            "property_profile": public_profile,
            "match_basis": "BIN_EXACT",
            "evidence_boundaries": {
                "provider": "The latest source-reported drinking-water-tank inspection names this firm at the exact-BIN building. It is observed service evidence, not proof of a current cooling-tower incumbent or exclusive contract.",
                "laboratory": "The latest source-reported drinking-water-tank inspection names this laboratory at the exact-BIN building. It is observed laboratory service evidence only.",
                "property_link": "Domestic-water market property evidence is attached only when the source property profile and TowerSignal account share the same exact seven-digit NYC BIN.",
            },
            "source": {
                "domain": cache.get("domain"),
                "generated_at": cache.get("generated_at"),
            },
        }
        detail_path.write_text(json.dumps(detail, separators=(",", ":")), encoding="utf-8")

    metadata.update({
        "dwt_market_cache_available": True,
        "dwt_market_cache_generated_at": cache.get("generated_at"),
        "dwt_market_match_basis": "BIN_EXACT",
        "dwt_market_source_property_count": len(cache.get("properties") or []),
        "dwt_market_exact_bin_property_count": len(properties_by_bin),
        "dwt_market_systems_attached": attached,
        "dwt_market_systems_with_current_observed_provider": current_provider,
    })
    summary.update({
        "systems_with_dwt_market_property": attached,
        "systems_with_current_observed_dwt_provider": current_provider,
        "systems_with_current_observed_dwt_lab": current_lab,
    })
    payload["metadata"] = metadata
    payload["summary"] = summary
    payload["systems"] = systems
    systems_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    report = {
        "source_property_count": len(cache.get("properties") or []),
        "exact_bin_property_count": len(properties_by_bin),
        "systems_attached": attached,
        "systems_with_current_observed_provider": current_provider,
        "systems_with_current_observed_lab": current_lab,
        "attached_inspection_record_count": inspection_records,
        "attached_compliance_activity_count": compliance_records,
        "match_basis": "BIN_EXACT",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Attach exact-BIN domestic-water provider/lab market evidence to TowerSignal accounts")
    parser.add_argument("--output", type=Path, default=ROOT / "public" / "data")
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    attach(args.output, args.cache)


if __name__ == "__main__":
    main()
