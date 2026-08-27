from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any, Iterable, Mapping, Sequence

from .procurement import normalize_company_name, normalize_space, parse_iso_date

DEAL_VALIDATION_SCHEMA_VERSION = "1.0"
SPECIALIZED_DEAL_CATEGORIES = frozenset({
    "COOLING_TOWER_MAINTENANCE",
    "COOLING_TOWER_CLEANING",
    "COOLING_TOWER_REPAIR",
    "COOLING_TOWER_REPLACEMENT",
    "WATER_TREATMENT",
    "COOLING_WATER_TREATMENT",
    "BOILER_WATER_TREATMENT",
    "LEGIONELLA_TESTING",
    "LEGIONELLA_REMEDIATION",
    "WATER_MANAGEMENT_PLAN",
    "WATER_TREATMENT_CHEMICALS",
    "CONDENSER_WATER",
})
IN_MARKET_SCOPE_RELATIONS = frozenset({"NYC_CORE", "NYC_METRO_ADJACENT"})


def strict_vendor_key(value: str | None) -> str:
    return normalize_company_name(value, strip_legal_suffixes=False)


def _as_date(value: Any) -> date | None:
    parsed = parse_iso_date(value)
    return date.fromisoformat(parsed) if parsed else None


def source_observation_date(row: Mapping[str, Any]) -> date | None:
    """Return source-reported historical evidence date without retrieval-time leakage."""
    fields = (
        ("notice_start_date", "due_date", "notice_end_date")
        if row.get("source") == "NYC_CITY_RECORD"
        else ("start_date", "award_date", "registration_date")
    )
    for field in fields:
        parsed = _as_date(row.get(field))
        if parsed:
            return parsed
    return None


def _buyer(row: Mapping[str, Any]) -> str:
    return normalize_space(str(row.get("buyer_name") or row.get("agency") or ""))


def relationship_metrics(rows: Sequence[Mapping[str, Any]], *, cutoff: date) -> dict[str, Any]:
    dated: list[tuple[date, Mapping[str, Any]]] = []
    undated = 0
    for row in rows:
        observed = source_observation_date(row)
        if observed is None:
            undated += 1
            continue
        if observed <= cutoff:
            dated.append((observed, row))

    buyers = [_buyer(row) for _, row in dated if _buyer(row)]
    buyer_counts = Counter(buyers)
    categories = sorted({
        normalize_space(str(row.get("service_category") or ""))
        for _, row in dated
        if normalize_space(str(row.get("service_category") or ""))
    })
    specialized = sum(
        1
        for _, row in dated
        if normalize_space(str(row.get("service_category") or "")) in SPECIALIZED_DEAL_CATEGORIES
    )

    active = 0
    expiring_12m = 0
    for _, row in dated:
        start = _as_date(row.get("start_date") or row.get("notice_start_date"))
        end = _as_date(row.get("amended_end_date") or row.get("end_date") or row.get("notice_end_date"))
        if (start is None or start <= cutoff) and (end is None or end >= cutoff):
            active += 1
            if end and end <= cutoff + timedelta(days=365):
                expiring_12m += 1

    first_evidence = min((observed for observed, _ in dated), default=None)
    repeat_buyer_count = sum(1 for count in buyer_counts.values() if count > 1)
    known_buyer_observations = sum(buyer_counts.values())
    concentration = (
        max(buyer_counts.values()) / known_buyer_observations
        if known_buyer_observations
        else None
    )

    screen_pass = (
        len(dated) >= 2
        and len(buyer_counts) >= 2
        and repeat_buyer_count >= 1
        and specialized >= 1
    )

    return {
        "pre_cutoff_observation_count": len(dated),
        "undated_observation_count": undated,
        "public_buyer_count": len(buyer_counts),
        "repeat_buyer_count": repeat_buyer_count,
        "specialized_service_observation_count": specialized,
        "service_categories": categories,
        "active_at_cutoff_count": active,
        "contracts_expiring_12m_from_cutoff": expiring_12m,
        "customer_concentration_by_observation_count": (
            round(concentration, 4) if concentration is not None else None
        ),
        "first_source_reported_evidence_date": first_evidence.isoformat() if first_evidence else None,
        "lead_days_to_outcome_or_anchor": (cutoff - first_evidence).days if first_evidence else None,
        "relationship_density_screen_pass": screen_pass,
    }


def build_deal_validation(
    procurement_rows: Iterable[Mapping[str, Any]],
    cohort: Mapping[str, Any],
    *,
    generated_at: str,
) -> dict[str, Any]:
    rows = [dict(row) for row in procurement_rows if normalize_space(str(row.get("vendor_raw") or ""))]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = strict_vendor_key(str(row.get("vendor_raw") or ""))
        if key:
            grouped[key].append(row)

    targets_raw = cohort.get("targets")
    if not isinstance(targets_raw, list) or not targets_raw:
        raise ValueError("Deal-validation cohort must contain targets[]")

    alias_to_target: dict[str, str] = {}
    targets: list[dict[str, Any]] = []
    for raw_target in targets_raw:
        if not isinstance(raw_target, Mapping):
            raise ValueError("Deal-validation target must be an object")
        target_id = normalize_space(str(raw_target.get("id") or ""))
        canonical_name = normalize_space(str(raw_target.get("canonical_name") or ""))
        outcome_date = _as_date(raw_target.get("outcome_date"))
        aliases = raw_target.get("aliases")
        if not target_id or not canonical_name or outcome_date is None or not isinstance(aliases, list) or not aliases:
            raise ValueError(f"Invalid deal-validation target: {target_id or canonical_name or '(unknown)'}")

        alias_keys = {strict_vendor_key(str(alias)) for alias in aliases if strict_vendor_key(str(alias))}
        for alias_key in alias_keys:
            previous = alias_to_target.get(alias_key)
            if previous and previous != target_id:
                raise ValueError(f"Exact cohort alias is assigned to multiple targets: {alias_key}")
            alias_to_target[alias_key] = target_id

        matched_aliases = sorted(alias_keys & set(grouped))
        matched_rows = [row for alias_key in matched_aliases for row in grouped[alias_key]]
        source_scope_relation = normalize_space(str(raw_target.get("source_scope_relation") or ""))
        if matched_aliases:
            coverage_status = "OBSERVED_IN_CURRENT_SOURCES"
        elif source_scope_relation in IN_MARKET_SCOPE_RELATIONS:
            coverage_status = "IN_MARKET_NOT_OBSERVED"
        else:
            coverage_status = "OUTSIDE_CURRENT_NYC_PROCUREMENT_SCOPE"

        target_metrics = relationship_metrics(matched_rows, cutoff=outcome_date)
        target = {
            "id": target_id,
            "canonical_name": canonical_name,
            "outcome_date": outcome_date.isoformat(),
            "acquirer": normalize_space(str(raw_target.get("acquirer") or "")) or None,
            "outcome_type": normalize_space(str(raw_target.get("outcome_type") or "")) or None,
            "primary_source_url": normalize_space(str(raw_target.get("primary_source_url") or "")) or None,
            "source_scope_relation": source_scope_relation,
            "market": normalize_space(str(raw_target.get("market") or "")) or None,
            "matched_alias_keys": matched_aliases,
            "coverage_status": coverage_status,
            "exact_source_observation_count": len(matched_rows),
            "external_pre_outcome_evidence": list(raw_target.get("external_pre_outcome_evidence") or []),
            **target_metrics,
        }
        targets.append(target)

    screen_config = cohort.get("screen_experiment") or {}
    screen_cutoff = _as_date(screen_config.get("cutoff_date"))
    if screen_cutoff is None:
        raise ValueError("Deal-validation screen_experiment.cutoff_date is required")

    screen_hits: list[dict[str, Any]] = []
    for vendor_key, vendor_rows in sorted(grouped.items()):
        vendor_metrics = relationship_metrics(vendor_rows, cutoff=screen_cutoff)
        if not vendor_metrics["relationship_density_screen_pass"]:
            continue
        target_id = alias_to_target.get(vendor_key)
        screen_hits.append({
            "strict_vendor_key": vendor_key,
            "curated_acquisition_target_id": target_id,
            "classification": (
                "CURATED_ACQUISITION_OUTCOME"
                if target_id
                else "NO_CURATED_OUTCOME_COMPARISON"
            ),
            **vendor_metrics,
        })

    observed_outcomes = sum(target["coverage_status"] == "OBSERVED_IN_CURRENT_SOURCES" for target in targets)
    observed_screened_outcomes = sum(
        target["coverage_status"] == "OBSERVED_IN_CURRENT_SOURCES"
        and target["relationship_density_screen_pass"]
        for target in targets
    )
    outcome_screen_hits = sum(hit["curated_acquisition_target_id"] is not None for hit in screen_hits)
    comparison_hits = len(screen_hits) - outcome_screen_hits

    gate = cohort.get("validation_gate") or {}
    min_observed = int(gate.get("min_observed_outcome_targets") or 3)
    min_screened = int(gate.get("min_screened_outcome_targets") or 2)
    gate_passed = observed_outcomes >= min_observed and observed_screened_outcomes >= min_screened

    in_market_misses = sum(target["coverage_status"] == "IN_MARKET_NOT_OBSERVED" for target in targets)
    outside_scope = sum(target["coverage_status"] == "OUTSIDE_CURRENT_NYC_PROCUREMENT_SCOPE" for target in targets)

    return {
        "schema_version": DEAL_VALIDATION_SCHEMA_VERSION,
        "generated_at": generated_at,
        "cohort_curated_as_of": cohort.get("curated_as_of"),
        "methodology": {
            "experiment_type": "RETROSPECTIVE_SOURCE_DATE_BACKTEST",
            "historical_observation_caveat": (
                "Current procurement snapshots are filtered by source-reported dates; this does not prove "
                "TowerSignal possessed each record on that historical date."
            ),
            "entity_match": "EXACT_CURATED_ALIAS_ONLY_NO_FUZZY_MATCHING",
            "monetary_values_used_in_screen": False,
            "specialized_categories": sorted(SPECIALIZED_DEAL_CATEGORIES),
            "relationship_density_screen": {
                "min_pre_cutoff_observations": 2,
                "min_public_buyers": 2,
                "min_repeat_buyers": 1,
                "min_specialized_service_observations": 1,
            },
            "comparison_semantics": (
                "Screen hits without a curated acquisition outcome are comparison candidates, not proven non-acquired companies."
            ),
        },
        "summary": {
            "curated_acquisition_outcome_count": len(targets),
            "exact_observed_outcome_count": observed_outcomes,
            "exact_outcome_coverage": round(observed_outcomes / len(targets), 4),
            "in_market_not_observed_count": in_market_misses,
            "outside_current_nyc_procurement_scope_count": outside_scope,
            "observed_outcomes_passing_screen": observed_screened_outcomes,
            "screen_experiment_hit_count": len(screen_hits),
            "screen_hits_with_curated_acquisition_outcome": outcome_screen_hits,
            "screen_hits_without_curated_outcome": comparison_hits,
            "curated_positive_fraction_of_screen_hits": (
                round(outcome_screen_hits / len(screen_hits), 4) if screen_hits else None
            ),
        },
        "validation_gate": {
            "min_observed_outcome_targets": min_observed,
            "min_screened_outcome_targets": min_screened,
            "passed": gate_passed,
            "conclusion": (
                "VALIDATED_FOR_SCORE_EXPERIMENT"
                if gate_passed
                else "NOT_VALIDATED_CURRENT_SOURCE_COVERAGE"
            ),
            "opportunity_score_2_allowed": gate_passed,
            "home_deal_model_allowed": gate_passed,
            "recommended_next_step": (
                "BUILD_SCORE_EXPERIMENT"
                if gate_passed
                else "EXPAND_PROCUREMENT_SOURCE_COVERAGE_BEFORE_SCORING"
            ),
        },
        "targets": targets,
        "screen_experiment": {
            "anchor_target_id": screen_config.get("anchor_target_id"),
            "cutoff_date": screen_cutoff.isoformat(),
            "hits": screen_hits,
        },
    }
