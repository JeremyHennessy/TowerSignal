from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from towersignal.fetch import DatasetSnapshot, fetch_dataset

NYS_API_ROOT = "https://health.data.ny.gov"
NYS_COOLING_TOWER_DATASET_ID = "24a4-muw7"
NYS_COOLING_TOWER_URL = "https://health.data.ny.gov/Health/New-York-State-Cooling-Tower-Registry-Weekly-Extr/24a4-muw7"
NYS_SOURCE_REGIME = "NYS_COOLING_TOWER_REGISTRY_WEEKLY_EXTRACT"
NYS_JURISDICTION = "NEW_YORK_STATE_EXCLUDING_NYC"
NYS_LATITUDE_RANGE = (40.3, 45.2)
NYS_LONGITUDE_RANGE = (-80.0, -71.5)


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int(value: Any) -> int | None:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError, AttributeError):
        return None


def _float(value: Any) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        return None


def _date(value: Any) -> str | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return None


def _property_key(address: str | None, city: str | None, zip_code: str | None) -> str | None:
    parts = [value.casefold() if value else "" for value in (address, city, zip_code)]
    if not any(parts):
        return None
    return "|".join(parts)


def normalize_nys_coordinates(latitude_raw: Any, longitude_raw: Any) -> dict[str, Any]:
    raw_latitude = _clean(latitude_raw)
    raw_longitude = _clean(longitude_raw)
    latitude = _float(latitude_raw)
    longitude = _float(longitude_raw)
    if raw_latitude is None and raw_longitude is None:
        return {
            "latitude": None,
            "longitude": None,
            "coordinate_status": "MISSING",
            "source_latitude_raw": raw_latitude,
            "source_longitude_raw": raw_longitude,
        }
    if (
        latitude is not None
        and longitude is not None
        and NYS_LATITUDE_RANGE[0] <= latitude <= NYS_LATITUDE_RANGE[1]
        and NYS_LONGITUDE_RANGE[0] <= longitude <= NYS_LONGITUDE_RANGE[1]
    ):
        status = "VALID"
    else:
        status = "INVALID_SOURCE"
        latitude = None
        longitude = None
    return {
        "latitude": latitude,
        "longitude": longitude,
        "coordinate_status": status,
        "source_latitude_raw": raw_latitude,
        "source_longitude_raw": raw_longitude,
    }


def normalize_nys_registry(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    best: dict[str, dict[str, Any]] = {}
    duplicate_rows = 0
    missing_equipment_id_rows = 0
    for row in rows:
        equipment_id = _clean(row.get("equipment_id"))
        if not equipment_id:
            missing_equipment_id_rows += 1
            continue
        if equipment_id in best:
            duplicate_rows += 1
            # The current authoritative extract is one row per Equipment_ID. If the
            # source changes granularity later, retain a deterministic row rather than
            # silently multiplying equipment in the product.
            incumbent = best[equipment_id]
            if str(sorted(row.items())) > str(sorted(incumbent.items())):
                best[equipment_id] = row
        else:
            best[equipment_id] = row

    normalized: list[dict[str, Any]] = []
    invalid_coordinate_count = 0
    missing_coordinate_count = 0
    for equipment_id, row in best.items():
        address = _clean(row.get("equipment_street_address"))
        city = _clean(row.get("equipment_location_city"))
        zip_code = _clean(row.get("equipment_location_zip"))
        coordinates = normalize_nys_coordinates(row.get("latitude"), row.get("longitude"))
        if coordinates["coordinate_status"] == "INVALID_SOURCE":
            invalid_coordinate_count += 1
        elif coordinates["coordinate_status"] == "MISSING":
            missing_coordinate_count += 1
        normalized.append({
            "system_id": f"NYS-{equipment_id}",
            "source_equipment_id": equipment_id,
            "jurisdiction": NYS_JURISDICTION,
            "source_regime": NYS_SOURCE_REGIME,
            "address": address,
            "city": city,
            "zip": zip_code,
            "source_county": _clean(row.get("county")),
            "property_key": _property_key(address, city, zip_code),
            "property_equipment_count": 1,
            "regulation_compliance": _clean(row.get("reg_comp")),
            "ct_status": _clean(row.get("ct_status")),
            "last_update_days": _int(row.get("lastupdate")),
            "last_sampled_days": _int(row.get("last_sampled_days")),
            "latest_sample_date": _date(row.get("equipment_last_legionellla_sample_collection_date")),
            "latest_sample_result": _clean(row.get("equipment_last_legionella_test_result")),
            "operation_duration": _clean(row.get("equipment_tower_operation_duration")),
            **coordinates,
        })

    property_counts = Counter(row["property_key"] for row in normalized if row.get("property_key"))
    for row in normalized:
        if row.get("property_key"):
            row["property_equipment_count"] = int(property_counts[row["property_key"]])

    normalized.sort(key=lambda item: int(item["source_equipment_id"]) if item["source_equipment_id"].isdigit() else item["source_equipment_id"])
    return normalized, {
        "source_duplicate_equipment_rows": duplicate_rows,
        "source_missing_equipment_id_rows": missing_equipment_id_rows,
        "invalid_coordinate_equipment_count": invalid_coordinate_count,
        "missing_coordinate_equipment_count": missing_coordinate_count,
        "normalized_equipment_count": len(normalized),
        "unique_property_count": len(property_counts),
        "multi_equipment_property_count": sum(1 for count in property_counts.values() if count > 1),
        "equipment_at_multi_equipment_properties": sum(count for count in property_counts.values() if count > 1),
        "max_equipment_per_property": max(property_counts.values(), default=0),
    }


def fetch_nys_registry() -> DatasetSnapshot:
    return fetch_dataset(
        NYS_COOLING_TOWER_DATASET_ID,
        order_by="equipment_id",
        api_root=NYS_API_ROOT,
    )