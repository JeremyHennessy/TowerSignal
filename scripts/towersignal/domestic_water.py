from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import urlencode

from .fetch import SourceFetchError, _request_json, fetch_count, fetch_metadata, fetch_where
from .planimetrics import normalize_bin

WATER_TANK_LAYER_URL = (
    "https://services6.arcgis.com/yG5s3afENB5iO9fj/ArcGIS/rest/services/"
    "Water_Tank_2022/FeatureServer/27"
)
WATER_TANK_SOURCE_KEY = "NYC_OTI_PLANIMETRICS_WATER_TANKS"
WATER_TANK_IMAGERY_YEAR = 2022
WATER_TANK_LOCATION_LEVEL = "ROOF_LEVEL"
WATER_TANK_LOCATION_BASIS = "SOURCE_FEATURE_CLASS_CAPTURE_RULE"

COMPLIANCE_DATASET_ID = "rytv-g5ui"
COMPLIANCE_DATASET_URL = (
    "https://data.cityofnewyork.us/Health/"
    "NYC-Drinking-Water-Tank-Inspections-and-Audits-Com/rytv-g5ui"
)
COMPLIANCE_SOURCE_KEY = "NYC_DOHMH_DWT_COMPLIANCE"

SELF_REPORT_DATASET_ID = "gjm4-k24g"
SELF_REPORT_DATASET_URL = (
    "https://data.cityofnewyork.us/Health/"
    "Self-Reported-Drinking-Water-Tank-Inspection-Resul/gjm4-k24g"
)
SELF_REPORT_SOURCE_KEY = "NYC_DOHMH_DWT_SELF_REPORTED_INSPECTIONS"

MATCH_BASIS = "BIN_EXACT"
FILTERED_QUERY_LIMIT = 50000
ARC_GIS_QUERY_LIMIT = 2000


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


def _iso_from_millis(value: Any) -> str | None:
    try:
        millis = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(millis / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _arcgis_error(payload: Any, context: str) -> None:
    if isinstance(payload, dict) and payload.get("error"):
        raise SourceFetchError(f"ArcGIS {context} returned an error: {payload['error']}")


def _attribute(attributes: dict[str, Any], *candidates: str) -> Any:
    lowered = {str(key).lower(): value for key, value in attributes.items()}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    return None


def _field_name(metadata: dict[str, Any], *candidates: str, required: bool = False) -> str | None:
    fields = metadata.get("fields") or []
    by_name = {str(field.get("name") or "").upper(): str(field.get("name") or "") for field in fields}
    by_alias = {str(field.get("alias") or "").upper(): str(field.get("name") or "") for field in fields}
    for candidate in candidates:
        upper = candidate.upper()
        if upper in by_name:
            return by_name[upper]
        if upper in by_alias:
            return by_alias[upper]
    if required:
        raise SourceFetchError(f"Water-tank ArcGIS layer is missing required field candidates {candidates!r}")
    return None


def _ring_area(ring: list[list[float]]) -> float:
    return sum(
        ring[index][0] * ring[index + 1][1] - ring[index + 1][0] * ring[index][1]
        for index in range(len(ring) - 1)
    ) / 2


def _point_in_ring(point: list[float], ring: list[list[float]]) -> bool:
    x, y = point
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-15) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _normalize_ring(raw: Any) -> list[list[float]]:
    if not isinstance(raw, list) or len(raw) < 4:
        raise SourceFetchError("Water-tank ArcGIS polygon contains an invalid ring")
    ring: list[list[float]] = []
    for raw_point in raw:
        if not isinstance(raw_point, (list, tuple)) or len(raw_point) < 2:
            raise SourceFetchError("Water-tank ArcGIS polygon contains an invalid coordinate")
        try:
            ring.append([float(raw_point[0]), float(raw_point[1])])
        except (TypeError, ValueError) as exc:
            raise SourceFetchError("Water-tank ArcGIS polygon contains a non-numeric coordinate") from exc
    if ring[0] != ring[-1]:
        ring.append(list(ring[0]))
    if len(ring) < 4 or abs(_ring_area(ring)) < 1e-15:
        raise SourceFetchError("Water-tank ArcGIS polygon contains a degenerate ring")
    return ring


def normalize_arcgis_polygon(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not isinstance(value.get("rings"), list) or not value["rings"]:
        raise SourceFetchError("Water-tank ArcGIS feature is missing polygon rings")
    rings = [_normalize_ring(raw) for raw in value["rings"]]
    if len(rings) == 1:
        return {"type": "Polygon", "coordinates": [rings[0]]}

    # ArcGIS polygons use clockwise exterior rings and counter-clockwise holes.
    exteriors = [ring for ring in rings if _ring_area(ring) < 0]
    holes = [ring for ring in rings if _ring_area(ring) > 0]
    if not exteriors:
        raise SourceFetchError("Water-tank ArcGIS polygon has multiple rings but no clockwise exterior ring")

    polygons: list[list[list[list[float]]]] = [[outer] for outer in exteriors]
    for hole in holes:
        containers = [
            (index, abs(_ring_area(outer)))
            for index, outer in enumerate(exteriors)
            if _point_in_ring(hole[0], outer)
        ]
        if not containers:
            raise SourceFetchError("Water-tank ArcGIS polygon contains an unassigned interior ring")
        container_index = min(containers, key=lambda item: item[1])[0]
        polygons[container_index].append(hole)

    if len(polygons) == 1:
        return {"type": "Polygon", "coordinates": polygons[0]}
    return {"type": "MultiPolygon", "coordinates": polygons}


def normalize_water_tank_feature(feature: dict[str, Any]) -> dict[str, Any]:
    attributes = feature.get("attributes")
    if not isinstance(attributes, dict):
        raise SourceFetchError("Water-tank ArcGIS feature is missing attributes")
    bin_value = normalize_bin(_attribute(attributes, "BIN"))
    if not bin_value:
        raise SourceFetchError("Water-tank ArcGIS feature is missing a valid numeric BIN")
    global_id = _string_or_none(_attribute(attributes, "GlobalID", "GLOBALID"))
    if not global_id:
        raise SourceFetchError(f"Water-tank ArcGIS feature for BIN {bin_value} is missing GlobalID")
    return {
        "global_id": global_id,
        "source_id": _string_or_none(_attribute(attributes, "SOURCE_ID")),
        "bin": bin_value,
        "feature_code": _string_or_none(_attribute(attributes, "FEATURE_CODE", "FEAT_CODE")),
        "status": _string_or_none(_attribute(attributes, "STATUS")),
        "base_elevation_ft": _float_or_none(_attribute(attributes, "BASE_ELEVATION", "BASE_ELEV")),
        "top_elevation_ft": _float_or_none(_attribute(attributes, "TOP_ELEVATION", "TOP_ELEV")),
        "height_ft": _float_or_none(_attribute(attributes, "HEIGHT")),
        "geometry": normalize_arcgis_polygon(feature.get("geometry")),
        "source": WATER_TANK_SOURCE_KEY,
        "match_basis": MATCH_BASIS,
        "feature_identity_basis": "GLOBALID",
        "imagery_year": WATER_TANK_IMAGERY_YEAR,
        "location_level": WATER_TANK_LOCATION_LEVEL,
        "location_basis": WATER_TANK_LOCATION_BASIS,
    }


def fetch_planimetric_water_tanks_by_bin(
    bin_values: Iterable[Any],
    *,
    batch_size: int = 150,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    requested_bins = sorted({value for item in bin_values if (value := normalize_bin(item))}, key=int)
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    layer_metadata_url = f"{WATER_TANK_LAYER_URL}?{urlencode({'f': 'json'})}"
    layer_metadata = _request_json(layer_metadata_url)
    _arcgis_error(layer_metadata, "water-tank layer metadata")
    if not isinstance(layer_metadata, dict):
        raise SourceFetchError("Water-tank ArcGIS layer metadata returned an unexpected payload")

    bin_field = _field_name(layer_metadata, "BIN", required=True)
    global_id_field = _string_or_none(layer_metadata.get("globalIdField")) or _field_name(
        layer_metadata, "GlobalID", required=True
    )

    count_params = {"f": "json", "where": "1=1", "returnCountOnly": "true"}
    count_payload = _request_json(f"{WATER_TANK_LAYER_URL}/query?{urlencode(count_params)}")
    _arcgis_error(count_payload, "water-tank count query")
    if not isinstance(count_payload, dict) or count_payload.get("count") is None:
        raise SourceFetchError("Water-tank ArcGIS count query returned an unexpected payload")
    source_record_count = int(count_payload["count"])

    by_bin: dict[str, list[dict[str, Any]]] = {}
    requested_set = set(requested_bins)
    seen_global_ids: set[str] = set()

    for start in range(0, len(requested_bins), batch_size):
        chunk = requested_bins[start:start + batch_size]
        query_params = {
            "f": "json",
            "where": f"{bin_field} IN ({','.join(chunk)})",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": "4326",
            "orderByFields": f"{bin_field},{global_id_field}",
            "resultRecordCount": str(ARC_GIS_QUERY_LIMIT),
        }
        payload = _request_json(f"{WATER_TANK_LAYER_URL}/query?{urlencode(query_params)}")
        _arcgis_error(payload, "water-tank exact-BIN query")
        if not isinstance(payload, dict) or not isinstance(payload.get("features"), list):
            raise SourceFetchError("Water-tank ArcGIS exact-BIN query returned an unexpected payload")
        if payload.get("exceededTransferLimit"):
            raise SourceFetchError(
                "Water-tank ArcGIS exact-BIN query exceeded the transfer limit; refusing a truncated result"
            )
        if len(payload["features"]) >= ARC_GIS_QUERY_LIMIT:
            raise SourceFetchError(
                "Water-tank ArcGIS exact-BIN query reached the configured row limit; refusing a potentially truncated result"
            )
        for raw_feature in payload["features"]:
            normalized = normalize_water_tank_feature(raw_feature)
            bin_value = normalized["bin"]
            if bin_value not in requested_set:
                raise SourceFetchError(
                    f"Water-tank ArcGIS filtered query returned BIN {bin_value} outside the requested exact-BIN universe"
                )
            global_id = normalized["global_id"]
            if global_id in seen_global_ids:
                raise SourceFetchError(f"Duplicate water-tank ArcGIS GlobalID: {global_id}")
            seen_global_ids.add(global_id)
            by_bin.setdefault(bin_value, []).append(normalized)

    for features in by_bin.values():
        features.sort(key=lambda item: item["global_id"])

    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    editing_info = layer_metadata.get("editingInfo") if isinstance(layer_metadata.get("editingInfo"), dict) else {}
    metadata = {
        "name": layer_metadata.get("name") or "WATER_TANK",
        "retrieved_at": retrieved_at,
        "source_record_count": source_record_count,
        "source_last_updated_at": _iso_from_millis(editing_info.get("lastEditDate")),
        "url": WATER_TANK_LAYER_URL,
        "source_query_scope": "Exact BIN 2022 rooftop water-tank polygons for the current TowerSignal NYC cooling-tower registry universe",
        "requested_bin_count": len(requested_bins),
        "matched_bin_count": len(by_bin),
        "matched_feature_count": sum(len(features) for features in by_bin.values()),
        "match_basis": MATCH_BASIS,
        "feature_identity_basis": "GLOBALID",
        "imagery_year": WATER_TANK_IMAGERY_YEAR,
        "location_level": WATER_TANK_LOCATION_LEVEL,
        "location_basis": WATER_TANK_LOCATION_BASIS,
    }
    return by_bin, metadata


def normalize_compliance_row(row: dict[str, Any]) -> dict[str, Any]:
    bin_value = normalize_bin(row.get("bin"))
    if not bin_value:
        raise SourceFetchError("DOHMH drinking-water compliance row is missing a valid numeric BIN")
    return {
        "bin": bin_value,
        "house": _string_or_none(row.get("house")),
        "street_name": _string_or_none(row.get("street_name")),
        "zip_code": _string_or_none(row.get("zip_code")),
        "borough": _string_or_none(row.get("borough")),
        "status": _string_or_none(row.get("status")),
        "number_of_dwt": _int_or_none(row.get("number_of_dwt")),
        "activity_type": _string_or_none(row.get("activity_type")),
        "activity_year": _string_or_none(row.get("activity_year")),
        "violation_code": _string_or_none(row.get("violation_code")),
        "law_section": _string_or_none(row.get("law_section")),
        "violation_text": _string_or_none(row.get("violation_text")),
        "compliance_year": _string_or_none(row.get("compliance_year")),
        "date_of_occurrence": _string_or_none(row.get("date_of_occurrence")),
        "summons_number": _string_or_none(row.get("summons_number")),
        "source": COMPLIANCE_SOURCE_KEY,
        "match_basis": MATCH_BASIS,
    }


def normalize_self_report_row(row: dict[str, Any]) -> dict[str, Any]:
    bin_value = normalize_bin(row.get("bin"))
    if not bin_value:
        raise SourceFetchError("DOHMH self-reported drinking-water inspection row is missing a valid numeric BIN")
    return {
        "bin": bin_value,
        "borough": _string_or_none(row.get("borough")),
        "zip": _string_or_none(row.get("zip")),
        "house_num": _string_or_none(row.get("house_num")),
        "street_name": _string_or_none(row.get("street_name")),
        "block": _string_or_none(row.get("block")),
        "lot": _string_or_none(row.get("lot")),
        "reporting_year": _string_or_none(row.get("reporting_year")),
        "tank_num": _string_or_none(row.get("tank_num")),
        "inspection_by_firm": _string_or_none(row.get("inspection_by_firm")),
        "inspection_performed": _string_or_none(row.get("inspection_performed")),
        "inspection_date": _string_or_none(row.get("inspection_date")),
        "sediment_result": _string_or_none(row.get("si_result_sediment")),
        "biological_growth_result": _string_or_none(row.get("si_result_biological_growth")),
        "debris_insects_result": _string_or_none(row.get("si_result_debris_insects")),
        "rodent_bird_result": _string_or_none(row.get("si_result_rodent_bird")),
        "sample_collected": _string_or_none(row.get("sample_collected")),
        "coliform": _string_or_none(row.get("coliform")),
        "ecoli": _string_or_none(row.get("ecoli")),
        "meet_standards": _string_or_none(row.get("meet_standards")),
        "latitude": _float_or_none(row.get("latitude")),
        "longitude": _float_or_none(row.get("longitude")),
        "bbl": _string_or_none(row.get("bbl")),
        "nta": _string_or_none(row.get("nta")),
        "source": SELF_REPORT_SOURCE_KEY,
        "match_basis": MATCH_BASIS,
    }


def _exact_bin_where(bin_values: list[str]) -> str:
    return "bin in (" + ",".join(f"'{value}'" for value in bin_values) + ")"


def _fetch_socrata_by_bin(
    dataset_id: str,
    dataset_url: str,
    source_name_fallback: str,
    bin_values: Iterable[Any],
    normalizer,
    *,
    batch_size: int = 150,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    requested_bins = sorted({value for item in bin_values if (value := normalize_bin(item))}, key=int)
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    source_record_count = fetch_count(dataset_id)
    source_metadata = fetch_metadata(dataset_id)
    requested_set = set(requested_bins)
    by_bin: dict[str, list[dict[str, Any]]] = {}

    for start in range(0, len(requested_bins), batch_size):
        chunk = requested_bins[start:start + batch_size]
        rows = fetch_where(dataset_id, _exact_bin_where(chunk), order_by="bin")
        if len(rows) >= FILTERED_QUERY_LIMIT:
            raise SourceFetchError(
                f"{dataset_id} exact-BIN query reached the filtered-query row limit; refusing a potentially truncated result"
            )
        for raw in rows:
            normalized = normalizer(raw)
            bin_value = normalized["bin"]
            if bin_value not in requested_set:
                raise SourceFetchError(
                    f"{dataset_id} filtered query returned BIN {bin_value} outside the requested exact-BIN universe"
                )
            by_bin.setdefault(bin_value, []).append(normalized)

    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    metadata = {
        "dataset_id": dataset_id,
        "name": source_metadata.get("name") or source_name_fallback,
        "retrieved_at": retrieved_at,
        "source_record_count": source_record_count,
        "source_last_updated_at": source_metadata.get("source_last_updated_at"),
        "url": dataset_url,
        "source_query_scope": "Exact BIN records for the current TowerSignal NYC cooling-tower registry universe",
        "requested_bin_count": len(requested_bins),
        "matched_bin_count": len(by_bin),
        "matched_record_count": sum(len(records) for records in by_bin.values()),
        "match_basis": MATCH_BASIS,
    }
    return by_bin, metadata


def fetch_dwt_compliance_by_bin(
    bin_values: Iterable[Any], *, batch_size: int = 150
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    by_bin, metadata = _fetch_socrata_by_bin(
        COMPLIANCE_DATASET_ID,
        COMPLIANCE_DATASET_URL,
        "NYC Drinking Water Tank Inspections and Audits Compliance Results",
        bin_values,
        normalize_compliance_row,
        batch_size=batch_size,
    )
    for records in by_bin.values():
        records.sort(
            key=lambda item: (
                item.get("compliance_year") or "",
                item.get("activity_year") or "",
                item.get("date_of_occurrence") or "",
                item.get("summons_number") or "",
            ),
            reverse=True,
        )
    return by_bin, metadata


def fetch_dwt_self_reports_by_bin(
    bin_values: Iterable[Any], *, batch_size: int = 150
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    by_bin, metadata = _fetch_socrata_by_bin(
        SELF_REPORT_DATASET_ID,
        SELF_REPORT_DATASET_URL,
        "Self-Reported Drinking Water Tank Inspection Results",
        bin_values,
        normalize_self_report_row,
        batch_size=batch_size,
    )
    for records in by_bin.values():
        records.sort(
            key=lambda item: (
                item.get("reporting_year") or "",
                item.get("inspection_date") or "",
                item.get("tank_num") or "",
            ),
            reverse=True,
        )
    return by_bin, metadata


def summarize_domestic_water(
    planimetric_tanks: list[dict[str, Any]],
    compliance_history: list[dict[str, Any]],
    self_report_history: list[dict[str, Any]],
) -> dict[str, Any]:
    latest_compliance = compliance_history[0] if compliance_history else None
    latest_self_report = self_report_history[0] if self_report_history else None
    return {
        "planimetric_tank_count": len(planimetric_tanks),
        "compliance_record_count": len(compliance_history),
        "self_report_record_count": len(self_report_history),
        "latest_status": latest_compliance.get("status") if latest_compliance else None,
        "latest_reported_dwt_count": latest_compliance.get("number_of_dwt") if latest_compliance else None,
        "latest_activity_type": latest_compliance.get("activity_type") if latest_compliance else None,
        "latest_activity_year": latest_compliance.get("activity_year") if latest_compliance else None,
        "latest_compliance_year": latest_compliance.get("compliance_year") if latest_compliance else None,
        "violation_record_count": sum(
            1
            for record in compliance_history
            if record.get("violation_code") or record.get("summons_number") or record.get("violation_text")
        ),
        "latest_self_report_inspection_date": latest_self_report.get("inspection_date") if latest_self_report else None,
        "latest_self_report_reporting_year": latest_self_report.get("reporting_year") if latest_self_report else None,
        "latest_self_report_meet_standards": latest_self_report.get("meet_standards") if latest_self_report else None,
    }
