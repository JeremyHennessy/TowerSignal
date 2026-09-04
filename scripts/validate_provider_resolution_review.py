from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate(path: Path, *, require_production_volume: bool) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0" or payload.get("domain") != "PROVIDER_IDENTITY_REVIEW":
        raise RuntimeError("Unexpected provider-resolution review schema/domain")
    summary = payload.get("summary")
    candidates = payload.get("alias_review_candidates")
    dec_matches = payload.get("dec_name_matches")
    if not isinstance(summary, dict) or not isinstance(candidates, list) or not isinstance(dec_matches, list):
        raise RuntimeError("Provider-resolution review payload is incomplete")
    if int(summary.get("alias_review_candidate_count") or 0) != len(candidates):
        raise RuntimeError("Alias candidate summary mismatch")
    if int(summary.get("dec_name_match_count") or 0) != len(dec_matches):
        raise RuntimeError("DEC name-match summary mismatch")
    if int(summary.get("merge_applied_count", -1)) != 0:
        raise RuntimeError("Provider-resolution review unexpectedly applied a merge")

    ids: set[str] = set()
    for row in candidates:
        candidate_id = str(row.get("candidate_id") or "")
        if not candidate_id or candidate_id in ids:
            raise RuntimeError(f"Missing/duplicate alias candidate ID: {candidate_id!r}")
        ids.add(candidate_id)
        if row.get("recommended_action") != "REVIEW" or row.get("merge_applied") is not False:
            raise RuntimeError(f"Alias candidate was auto-applied: {candidate_id}")
        if row.get("identity_confidence") != "VERIFY":
            raise RuntimeError(f"Alias candidate exceeded VERIFY confidence: {candidate_id}")
        if row.get("left_provider_id") == row.get("right_provider_id"):
            raise RuntimeError(f"Alias candidate compares a provider to itself: {candidate_id}")

    match_ids: set[str] = set()
    for row in dec_matches:
        match_id = str(row.get("match_id") or "")
        if not match_id or match_id in match_ids:
            raise RuntimeError(f"Missing/duplicate DEC name-match ID: {match_id!r}")
        match_ids.add(match_id)
        if row.get("match_method") != "NORMALIZED_NAME_EXACT":
            raise RuntimeError(f"Unexpected DEC match method: {match_id}")
        if row.get("identity_confidence") != "VERIFY" or row.get("merge_applied") is not False:
            raise RuntimeError(f"DEC name-only match was overstated: {match_id}")

    if require_production_volume:
        if int(summary.get("provider_count") or 0) < 300:
            raise RuntimeError("Implausibly small provider universe")
        if len(candidates) < 20:
            raise RuntimeError("Implausibly small alias review queue")
        if int(summary.get("providers_with_dec_name_match") or 0) < 5:
            raise RuntimeError("Implausibly small DEC/provider exact-name overlap")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate TowerSignal provider identity review queue")
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--require-production-volume", action="store_true")
    args = parser.parse_args()
    payload = validate(args.review, require_production_volume=args.require_production_volume)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
