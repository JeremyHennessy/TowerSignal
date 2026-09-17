from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.labor_law import (  # noqa: E402
    fetch_published_labor_law_decisions,
    match_decisions_to_systems,
    merge_retained_decisions,
)

DOMAIN = "NYS_LABOR_LAW_PUBLISHED_DECISIONS"
SCHEMA_VERSION = "1.0"


def load_json(path: Path | None, default: Any) -> Any:
    if path is None or not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def build(systems_path: Path, output_path: Path, previous_path: Path | None = None) -> dict[str, Any]:
    systems_payload = load_json(systems_path, None)
    if not isinstance(systems_payload, dict):
        raise RuntimeError(f"Missing or malformed systems payload: {systems_path}")
    systems = systems_payload.get("systems") or []
    previous = load_json(previous_path, {})
    previous_decisions = previous.get("decisions") or [] if isinstance(previous, dict) else []

    current_decisions, source = fetch_published_labor_law_decisions()
    decisions = merge_retained_decisions(current_decisions, previous_decisions)
    by_system, unmatched = match_decisions_to_systems(decisions, systems)
    attached_record_count = sum(len(rows) for rows in by_system.values())
    explicit_candidate_count = sum(len(row.get("explicit_subject_property_candidates") or []) for row in decisions)
    source_health_reasons = [
        "Official Reports is complete for appellate decisions but only selected trial-court decisions",
        "Published decisions are not a comprehensive Supreme Court filing or NYSCEF docket feed",
    ]
    if source.get("retrieval_failures"):
        source_health_reasons.append(f"{len(source['retrieval_failures'])} child decision retrieval failures in current collection")
    source["source_health_status"] = "WARNING"
    source["source_health_reasons"] = source_health_reasons

    payload = {
        "schema_version": SCHEMA_VERSION,
        "domain": DOMAIN,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_systems_snapshot": {
            "schema_version": systems_payload.get("schema_version"),
            "snapshot_date": (systems_payload.get("metadata") or {}).get("snapshot_date"),
            "system_count": len(systems),
        },
        "source": source,
        "summary": {
            "current_feed_labor_law_decision_count": len(current_decisions),
            "retained_labor_law_decision_count": len(decisions),
            "explicit_subject_property_candidate_count": explicit_candidate_count,
            "matched_system_count": len(by_system),
            "attached_decision_record_count": attached_record_count,
            "unmatched_property_candidate_count": len(unmatched),
            "child_retrieval_failure_count": len(source.get("retrieval_failures") or []),
        },
        "decisions": decisions,
        "by_system": by_system,
        "unmatched_property_candidates": unmatched,
        "evidence_boundaries": {
            "coverage": "Official New York Law Reporting Bureau published-decision evidence: all appellate decisions in the monitored First/Second Department feeds and selected trial-court decisions. This is not a comprehensive filing/docket feed.",
            "property_identity": "TowerSignal attaches a decision only when decision text uses explicit subject-worksite syntax containing a street address that exactly normalizes to a current TowerSignal property address. Party names, case citations and counsel addresses are not property matches.",
            "building_level": "A property-address match is building-level litigation context and does not identify an individual cooling tower or establish cooling-tower involvement.",
            "liability": "A published decision may describe allegations, motions or rulings. Presence does not itself establish current liability, compliance status, safety condition or service opportunity.",
            "scoring": "Labor Law published-decision evidence does not modify TowerSignal Priority Score.",
            "absence": "No matching published decision is not evidence that no Labor Law litigation or filing exists.",
        },
    }
    raw = json.dumps(payload, separators=(",", ":"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(raw, encoding="utf-8")

    # The canonical Pages workflow already stages and persists the complete
    # public/data/history/segments directory only after hosted verification.
    # Mirror this source-owned durable cache into that directory so prior
    # published decisions survive RSS-window turnover without a second
    # persistence owner or any pre-verification history write.
    durable_segment = output_path.parent / "history" / "segments" / "labor-law-decisions.json"
    durable_segment.parent.mkdir(parents=True, exist_ok=True)
    durable_segment.write_text(raw, encoding="utf-8")

    print(json.dumps(payload["summary"], indent=2))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build durable official Labor Law published-decision evidence")
    parser.add_argument("--systems", type=Path, default=ROOT / "public/data/systems.json")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data/labor-law-decisions.json")
    parser.add_argument("--previous", type=Path)
    args = parser.parse_args()
    build(args.systems, args.output, args.previous)


if __name__ == "__main__":
    main()
