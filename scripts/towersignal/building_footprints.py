from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from .fetch import SourceFetchError, fetch_count, fetch_metadata, fetch_where
from .planimetrics import normalize_bin

DATASET_ID = "5zhs-2jue"
DATASET_URL = "https://data.cityofnewyork.us/City-Government/BUILDING/5zhs-2jue"
SOURCE_NAME = "BUILDING"
SOURCE_KEY = "NYC_OTI_BUILDING_FOOTPRINTS"
MATCH_BASIS = "BIN_EXACT"
SELECT_FIELDS = (
    "the_geom,name,bin,doitt_id,shape_area,base_bbl,objectid,construction_year,feature_code,"
    "geom_source,ground_elevation,height_roof,last_edited_date,last_status_type,mappluto_bbl"
)
FILTERED_QUERY_LIMIT = 50000


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _normalize_geometry(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SourceFetchError("NYC building-footprint row is missing GeoJSON geometry")
    geometry_type = value.get("type")
    coordinates = value.get("coordinates")
    if geometry_type not in {"Polygon", "MultiPolygon"} or not isinstance(coordinates, list) or not coordinates:
        raise SourceFetchError(f"Unexpected NYC building-footprint geometry: {geometry_type!r}")
    return {"type": geometry_type, "coordinates": coordinates}


def normalize_building_footprint_row(row: dict[str, Any]) -> dict[str, Any]:
    bin_value = normalize_bin(row.get("bin"))
    if not bin_value:
        raise SourceFetchError("NYC building-footprint row is missing a valid numeric BIN")
    doitt_id = _string_or_none(row.get("doitt_id"))
    object_id = _string_or_none(row.get("objectid"))
    if not doitt_id and not object_id:
        raise SourceFetchError(f"NYC building-footprint row for BIN {bin_value} has no DOITT_ID or OBJECTID")
    return {
        "bin": bin_value,
        "name": _string_or_none(row.get("name")),
        "doitt_id": doitt_id,
        "object_id": object_id,
        "shape_area": _float_or_none(row.get("shape_area")),
        "base_bbl": _string_or_none(row.get("base_bbl")),
        "mappluto_bbl": _string_or_none(row.get("mappluto_bbl")),
        "construction_year": _int_or_none(row.get("construction_year")),
        "feature_code": _string_or_none(row.get("feature_code")),
        "geometry_source": _string_or_none(row.get("geom_source")),
        "ground_elevation_ft": _float_or_none(row.get("ground_elevation")),
        "height_roof_ft": _float_or_none(row.get("height_roof")),
        "last_edited_date": _string_or_none(row.get("last_edited_date")),
        "last_status_type": _string_or_none(row.get("last_status_type")),
        "geometry": _normalize_geometry(row.get("the_geom")),
        "source": SOURCE_KEY,
        "match_basis": MATCH_BASIS,
        "feature_identity_basis": "DOITT_ID" if doitt_id else "OBJECTID",
    }


def feature_identity(feature: dict[str, Any]) -> str:
    doitt_id = _string_or_none(feature.get("doitt_id"))
    if doitt_id:
        return f"DOITT:{doitt_id}"
    object_id = _string_or_none(feature.get("object_id"))
    if object_id:
        return f"OBJECTID:{object_id}"
    raise SourceFetchError("Normalized NYC building footprint has no usable identity")


def fetch_building_footprints_by_bin(
    bin_values: Iterable[Any],
    *,
    batch_size: int = 150,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    requested_bins = sorted({value for item in bin_values if (value := normalize_bin(item))}, key=int)
    source_record_count = fetch_count(DATASET_ID)
    source_metadata = fetch_metadata(DATASET_ID)
    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    by_bin: dict[str, list[dict[str, Any]]] = {}
    requested_set = set(requested_bins)
    seen_feature_ids: set[str] = set()

    for start in range(0, len(requested_bins), batch_size):
        chunk = requested_bins[start:start + batch_size]
        where = f"bin in ({','.join(chunk)})"
        rows = fetch_where(
            DATASET_ID,
            where,
            order_by="bin,doitt_id,objectid",
            select=SELECT_FIELDS,
        )
        if len(rows) >= FILTERED_QUERY_LIMIT:
            raise SourceFetchError(
                "NYC building-footprint exact-BIN query reached the filtered-query row limit; refusing a potentially truncated result"
            )
        for raw in rows:
            footprint = normalize_building_footprint_row(raw)
            bin_value = footprint["bin"]
            if bin_value not in requested_set:
                raise SourceFetchError(
                    f"NYC building-footprint filtered query returned BIN {bin_value} outside the requested exact-BIN universe"
                )
            identity = feature_identity(footprint)
            if identity in seen_feature_ids:
                raise SourceFetchError(f"Duplicate NYC building-footprint feature identity: {identity}")
            seen_feature_ids.add(identity)
            by_bin.setdefault(bin_value, []).append(footprint)

    for footprints in by_bin.values():
        footprints.sort(key=feature_identity)

    matched_feature_count = sum(len(features) for features in by_bin.values())
    metadata = {
        "dataset_id": DATASET_ID,
        "name": source_metadata.get("name") or SOURCE_NAME,
        "retrieved_at": retrieved_at,
        "source_record_count": source_record_count,
        "source_last_updated_at": source_metadata.get("source_last_updated_at"),
        "url": DATASET_URL,
        "source_query_scope": "Exact BIN building footprints for the current TowerSignal NYC cooling-tower registry universe",
        "requested_bin_count": len(requested_bins),
        "matched_bin_count": len(by_bin),
        "matched_feature_count": matched_feature_count,
        "match_basis": MATCH_BASIS,
    }
    return by_bin, metadata
