from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

DOMAIN = "NYC_LEGACY_DOB_PROJECT_CONTEXT"


def validate(path: Path, *, max_age_days: float = 1.0, require_production_volume: bool = False) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("domain") != DOMAIN:
        raise RuntimeError(f"Unexpected legacy DOB domain: {payload.get('domain')}")
    source = payload.get("source") or {}
    summary = payload.get("summary") or {}
    by_bbl = payload.get("by_bbl")
    if not isinstance(by_bbl, dict):
        raise RuntimeError("legacy DOB cache by_bbl must be an object")
    generated = datetime.fromisoformat(str(payload.get("generated_at") or "").replace("Z", "+00:00"))
    age_days = (datetime.now(timezone.utc) - generated).total_seconds() / 86400
    if age_days > max_age_days:
        raise RuntimeError(f"legacy DOB cache is stale: {age_days:.2f} days")
    if source.get("dataset_id") != "ic3t-wcy2":
        raise RuntimeError("legacy DOB cache must use authoritative dataset ic3t-wcy2")
    if int(summary.get("retained_bbl_count") or 0) != len(by_bbl):
        raise RuntimeError("legacy DOB retained BBL count does not reconcile")

    records = []
    for bbl, context in by_bbl.items():
        if len(str(bbl)) != 10 or not str(bbl).isdigit():
            raise RuntimeError(f"invalid canonical BBL in legacy DOB cache: {bbl}")
        rows = (context or {}).get("records") or []
        local_summary = (context or {}).get("summary") or {}
        if int(local_summary.get("record_count") or 0) != len(rows):
            raise RuntimeError(f"legacy DOB record count mismatch on BBL {bbl}")
        for row in rows:
            if row.get("bbl") != bbl:
                raise RuntimeError(f"legacy DOB record BBL mismatch on {bbl}")
            if row.get("match_basis") != "BOROUGH_BLOCK_LOT_TO_BBL_EXACT":
                raise RuntimeError("legacy DOB cache contains a non-exact property match")
            if row.get("relationship_boundary") != "RECORDED_DOB_APPLICANT_NOT_PROOF_OF_SERVICE_CONTRACT":
                raise RuntimeError("legacy DOB role boundary is missing")
            if not (row.get("explicit_cooling_tower_mention") or row.get("recent_relevant_project")):
                raise RuntimeError("legacy DOB cache retained a row outside the bounded production scope")
            records.append(row)

    if int(summary.get("retained_record_count") or 0) != len(records):
        raise RuntimeError("legacy DOB retained record total does not reconcile")
    explicit = sum(1 for row in records if row.get("explicit_cooling_tower_mention"))
    recent = sum(1 for row in records if row.get("recent_relevant_project"))
    if explicit != int(summary.get("explicit_cooling_tower_record_count") or 0):
        raise RuntimeError("legacy DOB explicit cooling-tower total does not reconcile")
    if recent != int(summary.get("recent_relevant_project_record_count") or 0):
        raise RuntimeError("legacy DOB recent relevant total does not reconcile")
    if require_production_volume:
        if int(source.get("requested_bbl_count") or 0) < 3000:
            raise RuntimeError("legacy DOB production cache requested too few canonical BBLs")
        if int(source.get("exact_bbl_job_count") or 0) < 100000:
            raise RuntimeError("legacy DOB production cache fetched unexpectedly few exact-BBL jobs")
        if len(records) < 1000 or explicit < 500:
            raise RuntimeError("legacy DOB production cache retained unexpectedly little bounded evidence")

    result = {
        "age_days": round(age_days, 3),
        "requested_bbl_count": int(source.get("requested_bbl_count") or 0),
        "source_matched_bbl_count": int(source.get("source_matched_bbl_count") or 0),
        "exact_bbl_job_count": int(source.get("exact_bbl_job_count") or 0),
        "retained_bbl_count": len(by_bbl),
        "retained_record_count": len(records),
        "explicit_cooling_tower_record_count": explicit,
        "recent_relevant_project_record_count": recent,
    }
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate compact legacy DOB/BIS project cache")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--max-age-days", type=float, default=1.0)
    parser.add_argument("--require-production-volume", action="store_true")
    args = parser.parse_args()
    validate(args.cache, max_age_days=args.max_age_days, require_production_volume=args.require_production_volume)


if __name__ == "__main__":
    main()
