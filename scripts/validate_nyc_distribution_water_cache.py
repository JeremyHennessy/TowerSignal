from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ALLOWED_QUALIFIERS = {"MISSING", "ND", "LT", "GT", "EQ", "TEXT"}
MEASUREMENTS = {"residual_free_chlorine", "turbidity", "fluoride", "coliform", "e_coli"}


def validate(path: Path, *, max_age_days: int, require_production_volume: bool) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0" or payload.get("domain") != "NYC_DISTRIBUTION_DRINKING_WATER_QUALITY":
        raise RuntimeError("Unexpected NYC distribution-water cache schema/domain")
    generated = datetime.fromisoformat(str(payload.get("generated_at") or "").replace("Z", "+00:00"))
    age_days = (datetime.now(timezone.utc) - generated).total_seconds() / 86400
    if age_days < -0.05 or age_days > max_age_days:
        raise RuntimeError(f"Distribution-water cache age is {age_days:.2f} days")

    source = payload.get("source")
    summary = payload.get("summary")
    samples = payload.get("samples")
    sites = payload.get("sites")
    if not isinstance(source, dict) or not isinstance(summary, dict) or not isinstance(samples, list) or not isinstance(sites, list):
        raise RuntimeError("Distribution-water cache missing source/summary/samples/sites")
    expected = int(source.get("source_record_count") or -1)
    if source.get("pagination_complete") is not True or source.get("schema_valid") is not True:
        raise RuntimeError("Distribution-water source pagination/schema proof failed")
    if expected != int(source.get("fetched_record_count") or -2) or expected != len(samples):
        raise RuntimeError("Distribution-water exact source count mismatch")
    if int(summary.get("sample_count") or -3) != len(samples) or int(summary.get("sample_site_count") or -4) != len(sites):
        raise RuntimeError("Distribution-water summary count mismatch")

    ids: set[str] = set()
    for sample in samples:
        sample_id = str(sample.get("sample_id") or "")
        if not sample_id or sample_id in ids:
            raise RuntimeError(f"Missing/duplicate distribution-water sample ID: {sample_id!r}")
        ids.add(sample_id)
        if sample.get("property_link_confidence") != "UNLINKED_SAMPLE_SITE":
            raise RuntimeError(f"Distribution sample was promoted to property evidence: {sample_id}")
        measurements = sample.get("measurements")
        if not isinstance(measurements, dict) or set(measurements) != MEASUREMENTS:
            raise RuntimeError(f"Distribution sample measurement schema mismatch: {sample_id}")
        for name, measurement in measurements.items():
            if not isinstance(measurement, dict) or measurement.get("qualifier") not in ALLOWED_QUALIFIERS:
                raise RuntimeError(f"Invalid {name} measurement: {sample_id}")
            if measurement.get("qualifier") == "MISSING" and measurement.get("raw") is not None:
                raise RuntimeError(f"Missing measurement retained non-null raw value: {sample_id}")

    site_names = [str(site.get("sample_site") or "MISSING") for site in sites]
    if len(site_names) != len(set(site_names)):
        raise RuntimeError("Distribution-water site profiles are not unique")
    if sum(int(site.get("sample_count") or 0) for site in sites) != len(samples):
        raise RuntimeError("Distribution-water site profile sample counts do not reconcile")
    for site in sites:
        if site.get("property_link_confidence") != "UNLINKED_SAMPLE_SITE":
            raise RuntimeError("Distribution-water site was promoted to property evidence")

    if require_production_volume:
        if expected < 150000:
            raise RuntimeError(f"Implausibly small distribution-water source: {expected:,}")
        if len(sites) < 100:
            raise RuntimeError(f"Implausibly few distribution sampling sites: {len(sites):,}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate NYC DEP distribution drinking-water quality cache")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--max-age-days", type=int, default=1)
    parser.add_argument("--require-production-volume", action="store_true")
    args = parser.parse_args()
    payload = validate(args.cache, max_age_days=args.max_age_days, require_production_volume=args.require_production_volume)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
