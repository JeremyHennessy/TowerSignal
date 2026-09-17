from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Labor Law cache must be a JSON object")
    return payload


def validate(path: Path) -> dict[str, int]:
    payload = load(path)
    if payload.get("domain") != "NYS_LABOR_LAW_PUBLISHED_DECISIONS":
        raise RuntimeError("Unexpected Labor Law cache domain")
    source = payload.get("source") or {}
    summary = payload.get("summary") or {}
    decisions = payload.get("decisions") or []
    by_system = payload.get("by_system") or {}
    boundaries = payload.get("evidence_boundaries") or {}
    if not isinstance(decisions, list) or not isinstance(by_system, dict):
        raise RuntimeError("Malformed Labor Law cache indexes")
    if int(source.get("source_record_count") or 0) <= 0:
        raise RuntimeError("Official Reports feeds returned no records")
    if source.get("current_filing_status_available") is not False:
        raise RuntimeError("Labor Law source must not claim current/comprehensive filing status")
    if "not a comprehensive" not in str(boundaries.get("coverage") or "").lower():
        raise RuntimeError("Labor Law coverage boundary is missing")
    if "does not modify" not in str(boundaries.get("scoring") or "").lower():
        raise RuntimeError("Labor Law scoring boundary is missing")

    ids: set[str] = set()
    for row in decisions:
        decision_id = str(row.get("decision_id") or "")
        if not decision_id or decision_id in ids:
            raise RuntimeError(f"Missing or duplicate Labor Law decision_id: {decision_id!r}")
        ids.add(decision_id)
        if not row.get("decision_url") or not row.get("title"):
            raise RuntimeError(f"Labor Law decision {decision_id} lacks title/link")
        if row.get("evidence_class") != "PUBLISHED_DECISION_PARTIAL_COVERAGE":
            raise RuntimeError(f"Labor Law decision {decision_id} has unexpected evidence class")

    attached = 0
    for system_id, rows in by_system.items():
        if not system_id or not isinstance(rows, list):
            raise RuntimeError("Malformed Labor Law system attachment")
        for row in rows:
            attached += 1
            if row.get("decision_id") not in ids:
                raise RuntimeError(f"Attached Labor Law decision missing from retained cache: {row.get('decision_id')}")
            if row.get("match_basis") != "PUBLISHED_DECISION_EXPLICIT_WORKSITE_ADDRESS_EXACT":
                raise RuntimeError("Labor Law attachment is not explicit-address exact")
            if row.get("building_level_context") is not True or row.get("liability_claim") is not False:
                raise RuntimeError("Labor Law evidence boundaries were not preserved on attachment")
            if not row.get("published_subject_address") or not row.get("matched_normalized_address"):
                raise RuntimeError("Labor Law attachment lacks explicit source address")

    expected_attached = int(summary.get("attached_decision_record_count") or 0)
    if attached != expected_attached:
        raise RuntimeError(f"Labor Law attached count mismatch: {attached} != {expected_attached}")
    if int(summary.get("matched_system_count") or 0) != len(by_system):
        raise RuntimeError("Labor Law matched-system count mismatch")

    result = {"decision_count": len(decisions), "matched_system_count": len(by_system), "attached_record_count": attached}
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Labor Law published-decision evidence")
    parser.add_argument("--cache", type=Path, default=ROOT / "public/data/labor-law-decisions.json")
    args = parser.parse_args()
    validate(args.cache)


if __name__ == "__main__":
    main()
