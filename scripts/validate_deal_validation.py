from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Expected JSON object: {path}")
    return payload


def walk_keys(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_keys(child)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate TowerSignal deal-intelligence empirical validation report")
    parser.add_argument("--report", type=Path, default=Path("public/data/deal-validation.json"))
    args = parser.parse_args()
    report = load_object(args.report)

    methodology = report.get("methodology") or {}
    summary = report.get("summary") or {}
    gate = report.get("validation_gate") or {}
    targets = report.get("targets")
    screen = report.get("screen_experiment") or {}
    hits = screen.get("hits")
    if not isinstance(targets, list) or not isinstance(hits, list):
        raise SystemExit("Deal validation report is missing targets[] or screen_experiment.hits[]")

    if methodology.get("entity_match") != "EXACT_CURATED_ALIAS_OR_EXPLICIT_SOURCE_DBA_ALIAS_ONLY_NO_FUZZY_MATCHING":
        raise SystemExit("Deal validation must use exact curated/source-declared DBA alias matching only")
    if methodology.get("monetary_values_used_in_screen") is not False:
        raise SystemExit("Deal validation relationship screen must not use monetary values")
    if methodology.get("experiment_type") != "RETROSPECTIVE_SOURCE_DATE_BACKTEST":
        raise SystemExit("Deal validation must disclose retrospective source-date methodology")

    forbidden_score_keys = [key for key in walk_keys(report) if key.lower() in {"score", "deal_score", "opportunity_score"}]
    if forbidden_score_keys:
        raise SystemExit(f"Deal validation must not emit a deal/opportunity score: {forbidden_score_keys}")

    target_ids = [str(target.get("id") or "") for target in targets if isinstance(target, dict)]
    if any(not target_id for target_id in target_ids) or len(target_ids) != len(set(target_ids)):
        raise SystemExit("Deal-validation target IDs must be present and unique")
    if int(summary.get("curated_acquisition_outcome_count") or -1) != len(targets):
        raise SystemExit("Curated outcome count does not reconcile to targets[]")

    observed = sum(
        1 for target in targets
        if isinstance(target, dict) and target.get("coverage_status") == "OBSERVED_IN_CURRENT_SOURCES"
    )
    screened = sum(
        1 for target in targets
        if isinstance(target, dict)
        and target.get("coverage_status") == "OBSERVED_IN_CURRENT_SOURCES"
        and target.get("relationship_density_screen_pass") is True
    )
    if int(summary.get("exact_observed_outcome_count") or -1) != observed:
        raise SystemExit("Observed outcome count does not reconcile to targets[]")
    if int(summary.get("observed_outcomes_passing_screen") or -1) != screened:
        raise SystemExit("Screened observed outcome count does not reconcile to targets[]")

    min_observed = int(gate.get("min_observed_outcome_targets") or 0)
    min_screened = int(gate.get("min_screened_outcome_targets") or 0)
    expected_coverage_thresholds = observed >= min_observed and screened >= min_screened
    score_authorization_locked = gate.get("score_authorization_locked") is True
    expected_gate = expected_coverage_thresholds and not score_authorization_locked

    if gate.get("coverage_thresholds_passed") is not expected_coverage_thresholds:
        raise SystemExit("Coverage-threshold result does not match pre-specified thresholds")
    if gate.get("passed") is not expected_gate:
        raise SystemExit("Validation authorization gate does not reconcile to coverage thresholds and holdout lock")
    if gate.get("opportunity_score_2_allowed") is not expected_gate:
        raise SystemExit("Opportunity Score 2.0 permission does not match validation authorization gate")
    if gate.get("home_deal_model_allowed") is not expected_gate:
        raise SystemExit("Home deal-model permission does not match validation authorization gate")
    if score_authorization_locked and not str(gate.get("score_authorization_lock_reason") or "").strip():
        raise SystemExit("Score-authorization lock must disclose a reason")

    if expected_coverage_thresholds and score_authorization_locked:
        expected_conclusion = "COVERAGE_THRESHOLDS_MET_HOLDOUT_REQUIRED"
        expected_next = "RUN_INDEPENDENT_HOLDOUT_VALIDATION"
    elif expected_gate:
        expected_conclusion = "VALIDATED_FOR_SCORE_EXPERIMENT"
        expected_next = "BUILD_SCORE_EXPERIMENT"
    else:
        expected_conclusion = "NOT_VALIDATED_CURRENT_SOURCE_COVERAGE"
        expected_next = "EXPAND_PROCUREMENT_SOURCE_COVERAGE_BEFORE_SCORING"
    if gate.get("conclusion") != expected_conclusion:
        raise SystemExit("Deal-validation conclusion does not match coverage/authorization state")
    if gate.get("recommended_next_step") != expected_next:
        raise SystemExit("Deal-validation next step does not match coverage/authorization state")

    for target in targets:
        if not isinstance(target, dict):
            raise SystemExit("Deal-validation target must be an object")
        source_url = str(target.get("primary_source_url") or "")
        if not source_url.startswith("https://"):
            raise SystemExit(f"Target is missing primary acquisition evidence URL: {target.get('id')}")
        if target.get("coverage_status") != "OBSERVED_IN_CURRENT_SOURCES" and target.get("exact_source_observation_count") not in (0, None):
            raise SystemExit(f"Unobserved target has source observation count: {target.get('id')}")

    print(json.dumps({
        "targets": len(targets),
        "observed_outcomes": observed,
        "observed_outcomes_passing_screen": screened,
        "screen_hits": len(hits),
        "coverage_thresholds_passed": expected_coverage_thresholds,
        "score_authorization_locked": score_authorization_locked,
        "gate_passed": expected_gate,
        "conclusion": gate.get("conclusion"),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
