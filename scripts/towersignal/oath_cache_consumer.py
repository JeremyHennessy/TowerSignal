from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from towersignal.oath import normalize_ticket_number, validate_match_coverage
from towersignal.oath_cache import DEFAULT_MAX_AGE_DAYS, validate_cache


def cases_and_metadata_for_current_tickets(
    path: Path,
    current_tickets: Iterable[Any],
    *,
    max_age_days: float = DEFAULT_MAX_AGE_DAYS,
    require_production_volume: bool = True,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Project a verified durable OATH cache onto the current product ticket universe."""
    result = validate_cache(
        path,
        max_age_days=max_age_days,
        require_production_volume=require_production_volume,
    )
    requested = {
        ticket
        for value in current_tickets
        if (ticket := normalize_ticket_number(value))
    }
    cached_cases = result["cases_by_ticket"]
    cases = {ticket: cached_cases[ticket] for ticket in requested if ticket in cached_cases}
    validate_match_coverage(len(requested), len(cases))

    cache = result["cache"]
    metadata = dict(cache["oath_source"])
    scope = str(metadata.get("source_query_scope") or "OATH exact summons lifecycle")
    metadata.update(
        {
            "source_query_scope": scope + "; verified durable cache intersected to current registered-system summons",
            "requested_ticket_count": len(requested),
            "matched_ticket_count": len(cases),
            "unmatched_ticket_count": len(requested) - len(cases),
            "matched_case_count": len(cases),
            "cache_generated_at": cache.get("generated_at"),
            "cache_age_days": round(float(result["age_days"]), 4),
            "cache_ticket_universe_count": result["ticket_universe"]["count"],
            "cache_ticket_universe_sha256": result["ticket_universe"]["sha256"],
        }
    )
    return cases, metadata, result
