from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from .normalize import NYC_LATITUDE_RANGE, NYC_LONGITUDE_RANGE

EXPECTED_REGISTRATION_FIELDS = {
    "bin", "system_id", "date_registered", "number", "street", "borough", "zip", "sampledates", "activeequipment"
}
EXPECTED_INSPECTION_FIELDS = {
    "bin", "system_id", "address", "borough", "zip_code", "status", "active_equip", "inspection_date",
    "violation_code", "law_section", "violation_text", "violation_type", "citation_text", "summons_number", "inspection_type"
}
VALID_BOROUGHS = {"BRONX", "BROOKLYN", "MANHATTAN", "QUEENS", "STATEN ISLAND"}
VALID_COORDINATE_STATUSES = {"VALID", "MISSING", "INVALID_SOURCE"}


class DataValidationError(RuntimeError):
    pass


def _require_fields(rows: list[dict[str, Any]], required: set[str], name: str) -> None:
    observed = set().union(*(row.keys() for row in rows[:500])) if rows else set()
    missing = required - observed
    if missing:
        raise DataValidationError(f"{name} source schema is missing required fields: {sorted(missing)}")


def validate_sources(registrations: list[dict[str, Any]], inspections: list[dict[str, Any]]) -> None:
    if len(registrations) < 3500:
        raise DataValidationError(f"Registration source row count is implausibly low: {len(registrations):,}")
    if len(inspections) < 50000:
        raise DataValidationError(f"Inspection source row count is implausibly low: {len(inspections):,}")
    _require_fields(registrations, EXPECTED_REGISTRATION_FIELDS, "registration")
    _require_fields(inspections, EXPECTED_INSPECTION_FIELDS, "inspection")

    populated_ids = sum(1 for row in registrations if str(row.get("system_id") or "").strip())
    if populated_ids / len(registrations) < 0.98:
        raise DataValidationError("system_id is not populated for at least 98% of registration rows")

    boroughs = Counter(str(row.get("borough") or "").strip().upper() for row in registrations)
    unexpected = {borough for borough, count in boroughs.items() if borough and borough not in VALID_BOROUGHS and count > 5}
    if unexpected:
        raise DataValidationError(f"Unexpected borough values exceed tolerance: {sorted(unexpected)}")


def validate_normalized(systems: list[dict[str, Any]], snapshot_date: date) -> None:
    ids = [item["system_id"] for item in systems]
    if len(ids) != len(set(ids)):
        raise DataValidationError("Duplicate canonical system_id values remain after normalization")
    if len(systems) < 3500:
        raise DataValidationError(f"Normalized system count is implausibly low: {len(systems):,}")

    invalid_coordinate_count = sum(1 for system in systems if system.get("coordinate_status") == "INVALID_SOURCE")
    invalid_coordinate_limit = max(25, int(len(systems) * 0.02))
    if invalid_coordinate_count > invalid_coordinate_limit:
        raise DataValidationError(
            f"Invalid source coordinates exceed tolerance: {invalid_coordinate_count:,} systems; limit {invalid_coordinate_limit:,}"
        )

    for system in systems:
        status = system.get("coordinate_status")
        if status not in VALID_COORDINATE_STATUSES:
            raise DataValidationError(f"Unknown coordinate status for system {system['system_id']}: {status}")
        lat = system.get("latitude")
        lon = system.get("longitude")
        if status == "VALID":
            if lat is None or not NYC_LATITUDE_RANGE[0] <= lat <= NYC_LATITUDE_RANGE[1]:
                raise DataValidationError(f"Invalid normalized NYC latitude for system {system['system_id']}: {lat}")
            if lon is None or not NYC_LONGITUDE_RANGE[0] <= lon <= NYC_LONGITUDE_RANGE[1]:
                raise DataValidationError(f"Invalid normalized NYC longitude for system {system['system_id']}: {lon}")
        elif lat is not None or lon is not None:
            raise DataValidationError(f"Unusable coordinates were not quarantined for system {system['system_id']}")

        latest = system.get("latest_sample_date")
        if latest:
            parsed = date.fromisoformat(latest)
            if parsed > snapshot_date:
                raise DataValidationError(f"Future public sample date for system {system['system_id']}: {latest}")


def validate_generated(payload: dict[str, Any]) -> None:
    required = {"schema_version", "metadata", "summary", "systems"}
    if not required.issubset(payload):
        raise DataValidationError(f"Generated JSON missing keys: {sorted(required - payload.keys())}")
    if payload["metadata"]["normalized_system_count"] != len(payload["systems"]):
        raise DataValidationError("Generated metadata/system count mismatch")
    if len({item["system_id"] for item in payload["systems"]}) != len(payload["systems"]):
        raise DataValidationError("Generated systems contain duplicate system_id values")
