from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_timestamp(value: Any) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise RuntimeError("Missing generated_at timestamp")
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def validate(path: Path, *, max_age_days: int, require_production_volume: bool) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0":
        raise RuntimeError(f"Unexpected schema version: {payload.get('schema_version')!r}")
    generated_at = parse_timestamp(payload.get("generated_at"))
    age_days = (datetime.now(timezone.utc) - generated_at).total_seconds() / 86400
    if age_days < -0.05 or age_days > max_age_days:
        raise RuntimeError(f"Cache generated_at is outside allowed age: {age_days:.2f} days")

    summary = payload.get("summary")
    sources = payload.get("source_health")
    if not isinstance(summary, dict) or not isinstance(sources, list) or len(sources) != 6:
        raise RuntimeError("Domestic-water cache is missing summary or six source-health records")
    for source in sources:
        if not isinstance(source, dict):
            raise RuntimeError("Source-health record is not an object")
        if source.get("status") != "HEALTHY" or source.get("pagination_complete") is not True or source.get("schema_valid") is not True:
            raise RuntimeError(f"Unhealthy source: {source.get('dataset_id')}")
        if int(source.get("source_record_count") or -1) != int(source.get("fetched_record_count") or -2):
            raise RuntimeError(f"Source count mismatch for {source.get('dataset_id')}")

    collections = {
        "tank_inspection_count": "tank_inspections",
        "tank_compliance_activity_count": "tank_compliance_activities",
        "observed_provider_count": "providers",
        "observed_laboratory_count": "laboratories",
        "observed_property_count": "properties",
        "dec_7g_business_registration_count": "dec_7g_businesses",
        "dec_7g_applicator_certification_count": "dec_7g_applicators",
        "free_residential_lead_copper_sample_count": "free_residential_lead_copper_samples",
        "compliance_lead_copper_sample_count": "compliance_lead_copper_samples",
    }
    for summary_key, collection_key in collections.items():
        collection = payload.get(collection_key)
        if not isinstance(collection, list):
            raise RuntimeError(f"Missing collection {collection_key}")
        if int(summary.get(summary_key) or 0) != len(collection):
            raise RuntimeError(f"Summary mismatch for {summary_key}")

    provider_ids = {str(row.get("provider_id")) for row in payload["providers"] if row.get("provider_id")}
    for prop in payload["properties"]:
        current = prop.get("current_observed_provider_id")
        if current and str(current) not in provider_ids:
            raise RuntimeError(f"Property references unknown provider {current}")
    for provider in payload["providers"]:
        aliases = provider.get("aliases")
        if not provider.get("provider_key") or not isinstance(aliases, list) or not aliases:
            raise RuntimeError(f"Invalid provider profile {provider.get('provider_id')}")
        alias_observations = sum(int(alias.get("inspection_count") or 0) for alias in aliases if isinstance(alias, dict))
        if alias_observations != int(provider.get("inspection_count") or 0):
            raise RuntimeError(f"Provider alias count mismatch for {provider.get('provider_id')}")

    for row in payload["dec_7g_businesses"]:
        if str(row.get("category") or "").lower() != "7g" or row.get("relationship_evidence") != "QUALIFIED_PROVIDER":
            raise RuntimeError("DEC business cache contains non-7G or misrepresented evidence")
    for row in payload["dec_7g_applicators"]:
        if str(row.get("category") or "").lower() != "7g" or row.get("relationship_evidence") != "QUALIFIED_PROVIDER":
            raise RuntimeError("DEC applicator cache contains non-7G or misrepresented evidence")

    if require_production_volume:
        minimums = {
            "tank_inspection_count": 50000,
            "tank_compliance_activity_count": 20000,
            "observed_provider_count": 25,
            "observed_property_count": 3000,
            "dec_7g_business_registration_count": 50,
            "dec_7g_applicator_certification_count": 1000,
            "free_residential_lead_copper_sample_count": 40000,
            "compliance_lead_copper_sample_count": 3000,
        }
        for key, minimum in minimums.items():
            if int(summary.get(key) or 0) < minimum:
                raise RuntimeError(f"Implausibly small production {key}: {summary.get(key)} < {minimum}")

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate TowerSignal domestic-water/provider intelligence cache")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--max-age-days", type=int, default=1)
    parser.add_argument("--require-production-volume", action="store_true")
    args = parser.parse_args()
    payload = validate(args.cache, max_age_days=args.max_age_days, require_production_volume=args.require_production_volume)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
