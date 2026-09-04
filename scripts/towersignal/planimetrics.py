from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from .fetch import SourceFetchError, fetch_count, fetch_metadata, fetch_where

DATASET_ID = "x748-37q7"
DATASET_URL = "https://data.cityofnewyork.us/City-Government/NYC-Planimetric-Database-Cooling-Towers/x748-37q7"
SOURCE_NAME = "NYC Planimetric Database: Cooling Towers"
SOURCE_KEY = "NYC_OTI_PLANIMETRICS_COOLING_TOWERS"
MATCH_BASIS = "BIN_EXACT"
IMAGERY_YEAR = 2022
SELECT_FIELDS = "the_geom,source_id,feature_co,sub_featur,bin,status,globalid"


def normalize_bin(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits or None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_geometry(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SourceFetchError("Plan imetric cooling-tower row is missing GeoJSON geometry")
    geometry_type = value.get("type")
    coordinates = value.get("coordinates")
    if geometry_type not in {"Polygon", "MultiPolygon"} or not isinstance(coordinates, list) or not coordinates:
        raise SourceFetchError(f"Unexpected Planimetric cooling-tower geometry: {geometry_type!r}")
    return {"type": geometry_type, "coordinates": coordinates}


def normalize_planimetric_row(row: dict[str, Any]) -> dict[str, Any]:
    bin_value = normalize_bin(row.get("bin"))
    if not bin_value:
        raise SourceFetchError("Plan imetric cooling-tower row is missing BIN")
    source_id = _string_or_none(row.get("source_id"))
    global_id = _string_or_none(row.get("globalid"))
    if not source_id and not global_id:
        raise SourceFetchError(f"Plan imetric cooling-tower row for BIN {bin_value} has no source identifier")
    return {
        "source_id": source_id,
        "global_id": global_id,
        "bin": bin_value,
        "feature_code": _string_or_none(row.get("feature_co")),
        "sub_feature_code": _string_or_none(row.get("sub_featur")),
        "status": _string_or_none(row.get("status")),
        "geometry": _normalize_geometry(row.get("the_geom")),
        "source": SOURCE_KEY,
        "match_basis": MATCH_BASIS,
        "imagery_year": IMAGERY_YEAR,
    }


def fetch_planimetric_towers_by_bin(
    bin_values: Iterable[Any],
    *,
    batch_size: int = 75,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    requested_bins = sorted({value for item in bin_values if (value := normalize_bin(item))}, key=int)
    source_record_count = fetch_count(DATASET_ID)
    source_metadata = fetch_metadata(DATASET_ID)
    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    by_bin: dict[str, list[dict[str, Any]]] = {}
    seen_feature_ids: set[str] = set()
    requested_set = set(requested_bins)

    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    for start in range(0, len(requested_bins), batch_size):
        chunk = requested_bins[start:start + batch_size]
        where = f"bin in ({','.join(chunk)})"
        rows = fetch_where(
            DATASET_ID,
            where,
            order_by="bin,source_id",
            select=SELECT_FIELDS,
        )
        for raw in rows:
            feature = normalize_planimetric_row(raw)
            bin_value = feature["bin"]
            if bin_value not in requested_set:
                raise SourceFetchError(
                    f"Plan imetric filtered query returned BIN {bin_value} outside the requested exact-BIN universe"
                )
            feature_identity = feature["source_id"] or feature["global_id"]
            assert feature_identity is not None
            if feature_identity in seen_feature_ids:
                raise SourceFetchError(f"Duplicate Planimetric cooling-tower feature identifier: {feature_identity}")
            seen_feature_ids.add(feature_identity)
            by_bin.setdefault(bin_value, []).append(feature)

    for features in by_bin.values():
        features.sort(key=lambda item: (item.get("source_id") or "", item.get("global_id") or ""))

    matched_feature_count = sum(len(features) for features in by_bin.values())
    metadata = {
        "dataset_id": DATASET_ID,
        "name": source_metadata.get("name") or SOURCE_NAME,
        "retrieved_at": retrieved_at,
        "source_record_count": source_record_count,
        "source_last_updated_at": source_metadata.get("source_last_updated_at"),
        "url": DATASET_URL,
        "source_query_scope": "Exact BIN matches for the current TowerSignal NYC cooling-tower registry universe",
        "requested_bin_count": len(requested_bins),
        "matched_bin_count": len(by_bin),
        "matched_feature_count": matched_feature_count,
        "match_basis": MATCH_BASIS,
        "imagery_year": IMAGERY_YEAR,
    }
    return by_bin, metadata
