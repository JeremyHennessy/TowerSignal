from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Mapping, Sequence

from towersignal.domestic_water_market import normalize_company_key, normalize_space, stable_id, utc_now

SCHEMA_VERSION = "1.0"

TOKEN_EQUIVALENTS = {
    "BROS": "BROTHERS",
    "BROTHER": "BROTHERS",
    "BROTHERS": "BROTHERS",
    "INTL": "INTERNATIONAL",
}

# Terms that can indicate a genuinely different business/service line. Their presence
# never blocks review, but prevents a typo-style candidate from being promoted to the
# strongest review class solely on string similarity.
DISTINGUISHING_TERMS = {
    "LINING",
    "LAB",
    "LABORATORY",
    "LABORATORIES",
    "PLUMBING",
    "HEATING",
    "ENVIRONMENTAL",
    "MANAGEMENT",
    "SERVICES",
    "SERVICE",
}


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(token for token in normalize_space(value).upper().split() if token)


def _equivalent_tokens(value: str) -> tuple[str, ...]:
    return tuple(TOKEN_EQUIVALENTS.get(token, token) for token in _tokens(value))


def _compact(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", normalize_space(value).upper())


def _differentiators(value: str) -> set[str]:
    return set(_equivalent_tokens(value)) & DISTINGUISHING_TERMS


def candidate_pair(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any] | None:
    left_key = normalize_space(left.get("provider_key"))
    right_key = normalize_space(right.get("provider_key"))
    if not left_key or not right_key or left_key == right_key:
        return None

    left_tokens = set(_equivalent_tokens(left_key))
    right_tokens = set(_equivalent_tokens(right_key))
    compact_left = _compact(left_key)
    compact_right = _compact(right_key)
    ratio = SequenceMatcher(None, left_key, right_key).ratio()
    compact_ratio = SequenceMatcher(None, compact_left, compact_right).ratio() if compact_left and compact_right else 0.0
    union = left_tokens | right_tokens
    token_jaccard = len(left_tokens & right_tokens) / len(union) if union else 0.0
    subset = bool(left_tokens and right_tokens and (left_tokens < right_tokens or right_tokens < left_tokens))
    equivalent = _equivalent_tokens(left_key) == _equivalent_tokens(right_key)
    differentiators_differ = _differentiators(left_key) != _differentiators(right_key)

    candidate_type: str | None = None
    reason: str | None = None
    review_priority = "LOW"

    if equivalent or compact_left == compact_right:
        candidate_type = "FORMAT_OR_TOKEN_EQUIVALENT"
        reason = "Names become identical after spacing/token-equivalence normalization."
        review_priority = "HIGH"
    elif max(ratio, compact_ratio) >= 0.94 and min(len(compact_left), len(compact_right)) >= 8 and not differentiators_differ:
        candidate_type = "PROBABLE_TYPO_VARIANT"
        reason = "Very high character similarity without a changed service-line differentiator."
        review_priority = "HIGH"
    elif token_jaccard >= 0.67 and max(ratio, compact_ratio) >= 0.80 and not differentiators_differ:
        candidate_type = "PROBABLE_NAMING_VARIANT"
        reason = "High token overlap and character similarity."
        review_priority = "MEDIUM"
    elif subset and len(left_tokens & right_tokens) >= 1:
        candidate_type = "SHORT_FORM_OR_RELATED_NAME"
        reason = "One normalized token set is a strict subset of the other; relationship requires evidence."
        review_priority = "MEDIUM"

    if candidate_type is None:
        return None

    left_buildings = int(left.get("observed_building_count") or 0)
    right_buildings = int(right.get("observed_building_count") or 0)
    dominant = left if left_buildings >= right_buildings else right
    secondary = right if dominant is left else left

    return {
        "candidate_id": stable_id("provider-review", left_key, right_key),
        "left_provider_id": left.get("provider_id"),
        "left_provider_key": left_key,
        "left_observed_building_count": left_buildings,
        "right_provider_id": right.get("provider_id"),
        "right_provider_key": right_key,
        "right_observed_building_count": right_buildings,
        "candidate_type": candidate_type,
        "review_priority": review_priority,
        "reason": reason,
        "character_similarity": round(ratio, 4),
        "compact_similarity": round(compact_ratio, 4),
        "token_jaccard": round(token_jaccard, 4),
        "differentiating_terms_changed": differentiators_differ,
        "suggested_canonical_provider_id": dominant.get("provider_id"),
        "suggested_canonical_provider_key": dominant.get("provider_key"),
        "secondary_provider_id": secondary.get("provider_id"),
        "recommended_action": "REVIEW",
        "merge_applied": False,
        "identity_confidence": "VERIFY",
    }


def build_alias_review_queue(providers: Sequence[Mapping[str, Any]], *, minimum_buildings: int = 2) -> list[dict[str, Any]]:
    eligible = [row for row in providers if int(row.get("observed_building_count") or 0) >= minimum_buildings]
    result: list[dict[str, Any]] = []
    for index, left in enumerate(eligible):
        for right in eligible[index + 1 :]:
            candidate = candidate_pair(left, right)
            if candidate is not None:
                result.append(candidate)
    priority_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    return sorted(
        result,
        key=lambda row: (
            priority_rank.get(str(row.get("review_priority")), 9),
            -max(int(row.get("left_observed_building_count") or 0), int(row.get("right_observed_building_count") or 0)),
            str(row.get("candidate_id")),
        ),
    )


def build_dec_name_matches(providers: Sequence[Mapping[str, Any]], dec_businesses: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    dec_by_key: dict[str, list[Mapping[str, Any]]] = {}
    for row in dec_businesses:
        key = normalize_company_key(row.get("provider_name") or row.get("provider_key"))
        if key:
            dec_by_key.setdefault(key, []).append(row)

    result: list[dict[str, Any]] = []
    for provider in providers:
        provider_key = normalize_company_key(provider.get("provider_key"))
        if not provider_key:
            continue
        for dec in dec_by_key.get(provider_key, []):
            result.append({
                "match_id": stable_id("provider-dec-name-match", provider.get("provider_id"), dec.get("registration_number")),
                "provider_id": provider.get("provider_id"),
                "provider_key": provider.get("provider_key"),
                "observed_building_count": int(provider.get("observed_building_count") or 0),
                "dec_provider_name": dec.get("provider_name"),
                "dec_registration_number": dec.get("registration_number"),
                "dec_registration_expiration_date": dec.get("registration_expiration_date"),
                "match_method": "NORMALIZED_NAME_EXACT",
                "identity_confidence": "VERIFY",
                "relationship_evidence": "CROSS_SOURCE_NAME_MATCH_ONLY",
                "qualification_scope": dec.get("qualification_scope"),
                "merge_applied": False,
            })
    return sorted(result, key=lambda row: (-int(row["observed_building_count"]), str(row["provider_key"]), str(row["dec_registration_number"])))


def build_resolution_payload(domestic_water_cache: Mapping[str, Any]) -> dict[str, Any]:
    providers = domestic_water_cache.get("providers")
    dec_businesses = domestic_water_cache.get("dec_7g_businesses")
    if not isinstance(providers, list) or not isinstance(dec_businesses, list):
        raise RuntimeError("Domestic-water cache is missing providers or DEC 7G businesses")

    alias_candidates = build_alias_review_queue(providers)
    dec_matches = build_dec_name_matches(providers, dec_businesses)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "domain": "PROVIDER_IDENTITY_REVIEW",
        "source_cache_generated_at": domestic_water_cache.get("generated_at"),
        "evidence_semantics": {
            "alias_candidates": "String/token similarity is a review lead only. No identity merge is applied.",
            "dec_matches": "Exact normalized-name matches across DOHMH observations and DEC registrations remain VERIFY because name-only evidence is not authoritative identity proof.",
            "market_share": "No market-share metric is calculated until provider identities and denominator rules are approved.",
        },
        "summary": {
            "provider_count": len(providers),
            "alias_review_candidate_count": len(alias_candidates),
            "high_priority_alias_candidate_count": sum(1 for row in alias_candidates if row["review_priority"] == "HIGH"),
            "dec_name_match_count": len(dec_matches),
            "providers_with_dec_name_match": len({str(row["provider_id"]) for row in dec_matches}),
            "merge_applied_count": 0,
        },
        "alias_review_candidates": alias_candidates,
        "dec_name_matches": dec_matches,
    }
