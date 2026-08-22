from __future__ import annotations

from typing import Any


class SourceHealthError(RuntimeError):
    pass


def _pct(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round((numerator / denominator) * 100.0, 2)


def health_entry(
    *,
    source_key: str,
    dataset_id: str,
    name: str,
    entity_unit: str,
    retrieved_record_count: int,
    requested_entity_count: int,
    normalized_entity_count: int,
    matched_entity_count: int,
    attached_entity_count: int,
    displayed_entity_count: int,
    previous_coverage_percentage: float | None = None,
    coverage_note: str,
) -> dict[str, Any]:
    coverage = _pct(matched_entity_count, requested_entity_count)
    change = None
    if coverage is not None and previous_coverage_percentage is not None:
        change = round(coverage - previous_coverage_percentage, 2)

    status = "HEALTHY"
    reasons: list[str] = []
    if retrieved_record_count <= 0:
        status = "FAILED"
        reasons.append("source returned no records")
    if matched_entity_count > 0 and attached_entity_count <= 0:
        status = "FAILED"
        reasons.append("matched entities did not attach to product records")
    if attached_entity_count > 0 and displayed_entity_count <= 0:
        status = "FAILED"
        reasons.append("attached entities are not represented in generated product output")
    if coverage is not None and previous_coverage_percentage is not None and previous_coverage_percentage > 0:
        relative = coverage / previous_coverage_percentage
        if relative < 0.5:
            status = "FAILED"
            reasons.append("coverage fell by more than 50% versus the previous verified snapshot")
        elif relative < 0.75 and status != "FAILED":
            status = "WARNING"
            reasons.append("coverage fell by more than 25% versus the previous verified snapshot")

    return {
        "source_key": source_key,
        "dataset_id": dataset_id,
        "name": name,
        "entity_unit": entity_unit,
        "retrieved_record_count": int(retrieved_record_count),
        "requested_entity_count": int(requested_entity_count),
        "normalized_entity_count": int(normalized_entity_count),
        "matched_entity_count": int(matched_entity_count),
        "attached_entity_count": int(attached_entity_count),
        "displayed_entity_count": int(displayed_entity_count),
        "coverage_percentage": coverage,
        "previous_coverage_percentage": previous_coverage_percentage,
        "coverage_change_percentage_points": change,
        "coverage_note": coverage_note,
        "status": status,
        "status_reasons": reasons,
    }


def validate_source_health(entries: list[dict[str, Any]]) -> None:
    failed = [entry for entry in entries if entry.get("status") == "FAILED"]
    if failed:
        summary = "; ".join(f"{entry['source_key']}: {', '.join(entry.get('status_reasons') or ['failed'])}" for entry in failed)
        raise SourceHealthError(f"Source-health gate failed: {summary}")
