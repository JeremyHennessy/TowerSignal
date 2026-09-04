from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _parse_timestamp(value: Any) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise RuntimeError("Missing generated_at timestamp")
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def validate(path: Path, *, max_age_days: int, require_production_volume: bool) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0" or payload.get("domain") != "NYC_LL84_BUILDING_WATER":
        raise RuntimeError("Unexpected LL84 water cache schema/domain")

    generated = _parse_timestamp(payload.get("generated_at"))
    age_days = (datetime.now(timezone.utc) - generated).total_seconds() / 86400
    if age_days < -0.05 or age_days > max_age_days:
        raise RuntimeError(f"LL84 cache age is outside allowed range: {age_days:.2f} days")

    sources = payload.get("source_health")
    summary = payload.get("summary")
    observations = payload.get("observations")
    latest = payload.get("latest_properties")
    if not isinstance(sources, list) or len(sources) != 1 or not isinstance(summary, dict):
        raise RuntimeError("LL84 cache missing source health/summary")
    if not isinstance(observations, list) or not isinstance(latest, list):
        raise RuntimeError("LL84 cache missing observation/property collections")
    source = sources[0]
    if source.get("dataset_id") != "5zyy-y8am" or source.get("status") != "HEALTHY":
        raise RuntimeError("LL84 source health is not healthy")
    if source.get("pagination_complete") is not True or source.get("schema_valid") is not True:
        raise RuntimeError("LL84 source pagination/schema proof failed")
    if int(source.get("source_record_count") or -1) != int(source.get("fetched_record_count") or -2):
        raise RuntimeError("LL84 source count mismatch")
    if int(summary.get("observation_count") or -3) != len(observations):
        raise RuntimeError("LL84 observation summary mismatch")
    if int(summary.get("unique_epa_property_count") or -4) != len(latest):
        raise RuntimeError("LL84 property summary mismatch")

    observation_ids: set[str] = set()
    for row in observations:
        observation_id = str(row.get("observation_id") or "")
        if not observation_id or observation_id in observation_ids:
            raise RuntimeError(f"Missing/duplicate LL84 observation ID: {observation_id}")
        observation_ids.add(observation_id)
        bbls = row.get("bbls")
        bins = row.get("bins")
        if not isinstance(bbls, list) or not isinstance(bins, list):
            raise RuntimeError("LL84 identifier arrays are malformed")
        if any(len(str(bbl)) != 10 or not str(bbl).isdigit() for bbl in bbls):
            raise RuntimeError("LL84 BBL parsing emitted an invalid identifier")
        if any(len(str(bin_value)) != 7 or not str(bin_value).isdigit() for bin_value in bins):
            raise RuntimeError("LL84 BIN parsing emitted an invalid identifier")

    for row in latest:
        if row.get("latest_observation_id") not in observation_ids:
            raise RuntimeError(f"Latest property points to unknown observation {row.get('latest_observation_id')}")
        if row.get("year_over_year_delta_pct") is not None and row.get("year_over_year_delta_kgal") is None:
            raise RuntimeError("LL84 percent delta emitted without numeric delta")

    if require_production_volume:
        minimums = {
            "observation_count": 90000,
            "unique_epa_property_count": 25000,
            "rows_with_bbl": 70000,
            "rows_with_reported_water_use": 30000,
        }
        for key, minimum in minimums.items():
            if int(summary.get(key) or 0) < minimum:
                raise RuntimeError(f"Implausibly small LL84 {key}: {summary.get(key)} < {minimum}")

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate verified NYC LL84 water cache")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--max-age-days", type=int, default=1)
    parser.add_argument("--require-production-volume", action="store_true")
    args = parser.parse_args()
    payload = validate(args.cache, max_age_days=args.max_age_days, require_production_volume=args.require_production_volume)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
