from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate(path: Path, *, require_production_volume: bool = False) -> dict[str, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0" or payload.get("domain") != "NYC_HISTORICAL_BUILDING_WATER_CONTEXT":
        raise RuntimeError("Unexpected historical 311 context contract")
    summary = payload.get("summary")
    profiles = payload.get("by_bbl")
    governance = payload.get("governance")
    if not isinstance(summary, dict) or not isinstance(profiles, dict) or not isinstance(governance, dict):
        raise RuntimeError("Historical 311 context payload is malformed")
    required_false = (
        "priority_score_1_0_changed",
        "current_trigger_created",
        "fuzzy_matching_used",
        "provider_or_incumbent_inference",
        "raw_historical_events_published",
    )
    if any(governance.get(key) is not False for key in required_false):
        raise RuntimeError("Historical 311 governance boundary was weakened")
    requested = int(summary.get("requested_bbl_count") or 0)
    matched = int(summary.get("matched_bbl_count") or 0)
    building_rows = int(summary.get("building_water_request_count") or 0)
    if matched != len(profiles):
        raise RuntimeError(f"Historical 311 matched BBL count mismatch: summary={matched}, profiles={len(profiles)}")
    if matched > requested:
        raise RuntimeError("Historical 311 matched more BBLs than requested")
    profile_request_total = 0
    for key, profile in profiles.items():
        if not isinstance(profile, dict) or profile.get("bbl") != key:
            raise RuntimeError(f"Historical 311 profile identity mismatch for {key}")
        if profile.get("property_link_confidence") != "CONFIRMED_SOURCE_BBL":
            raise RuntimeError(f"Historical 311 profile lacks exact-BBL evidence: {key}")
        if profile.get("evidence_semantics") != "REPORTED_SERVICE_REQUEST":
            raise RuntimeError(f"Historical 311 evidence semantics changed: {key}")
        years = profile.get("years")
        if not isinstance(years, list) or any(str(year) < "2010" or str(year) > "2024" for year in years):
            raise RuntimeError(f"Historical 311 profile contains an out-of-scope year: {key}")
        if any(field in profile for field in ("rows", "requests", "events", "raw")):
            raise RuntimeError(f"Historical 311 profile published raw event material: {key}")
        profile_request_total += int(profile.get("request_count") or 0)
    if profile_request_total != building_rows:
        raise RuntimeError(
            f"Historical 311 building-water total mismatch: profiles={profile_request_total}, summary={building_rows}"
        )
    if require_production_volume:
        if requested < 3000:
            raise RuntimeError(f"Historical 311 requested BBL population too small: {requested:,}")
        if matched < 1500:
            raise RuntimeError(f"Historical 311 matched BBL population unexpectedly low: {matched:,}")
        if building_rows < 10000:
            raise RuntimeError(f"Historical 311 building-water request population unexpectedly low: {building_rows:,}")
    return {"requested_bbl_count": requested, "matched_bbl_count": matched, "building_water_request_count": building_rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate compact NYC historical 311 context")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--require-production-volume", action="store_true")
    args = parser.parse_args()
    print(json.dumps(validate(args.cache, require_production_volume=args.require_production_volume), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
