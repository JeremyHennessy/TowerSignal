from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from toronto_market_common import read_json, request_bytes, utc_now, write_json

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data" / "toronto" / "market" / "current"
ADDRESS_POINTS_CSV = "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/abedd8bc-e3dd-4d45-8e69-79165a76e4fa/resource/64d4e54b-738f-4cd9-a9e7-8050fac8a52f/download/address-points-4326.csv"


def parse_geometry(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return None
    coords = payload.get("coordinates") if isinstance(payload, dict) else None
    if not isinstance(coords, list) or not coords:
        return None
    point = coords
    # Current Toronto 4326 CSV serializes address points as GeoJSON MultiPoint,
    # e.g. {"coordinates": [[-79.5, 43.6]], "type": "MultiPoint"}.
    while isinstance(point, list) and len(point) == 1 and isinstance(point[0], list):
        point = point[0]
    if not isinstance(point, list) or len(point) < 2:
        return None
    try:
        lon = float(point[0])
        lat = float(point[1])
    except (TypeError, ValueError):
        return None
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return None
    return lon, lat


def main() -> None:
    spine_path = MARKET / "property_spine.json"
    spine = read_json(spine_path)
    if not isinstance(spine, dict) or not isinstance(spine.get("properties"), list):
        raise RuntimeError("property_spine.json is missing")
    props = spine["properties"]
    by_id = {str(p.get("address_point_id") or ""): p for p in props if p.get("address_point_id")}
    if not by_id:
        raise RuntimeError("No Address Point IDs available for coordinate recovery")

    raw = request_bytes(ADDRESS_POINTS_CSV, timeout=240, max_bytes=350_000_000)
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig", errors="replace")))
    if "geometry" not in (reader.fieldnames or []):
        raise RuntimeError("Current Address Points CSV no longer exposes geometry column")

    matched = 0
    filled = 0
    invalid_geometry = 0
    for row in reader:
        pid = str(row.get("ADDRESS_POINT_ID") or "").strip()
        prop = by_id.get(pid)
        if prop is None:
            continue
        matched += 1
        parsed = parse_geometry(row.get("geometry"))
        if parsed is None:
            invalid_geometry += 1
            continue
        lon, lat = parsed
        prop["longitude"] = lon
        prop["latitude"] = lat
        prop["coordinate_basis"] = "CITY_ADDRESS_POINTS_4326_GEOMETRY_MULTIPOINT"
        filled += 1

    usable = sum(
        isinstance(p.get("longitude"), (int, float)) and isinstance(p.get("latitude"), (int, float))
        for p in props
    )
    if filled < 100:
        raise RuntimeError(f"Coordinate recovery unexpectedly low: {filled}")

    write_json(spine_path, spine)
    report = {
        "schema_version": "toronto-address-point-coordinate-recovery-1.0",
        "generated_at": utc_now(),
        "source": ADDRESS_POINTS_CSV,
        "source_contract": "Current 4326 CSV geometry field is GeoJSON-like MultiPoint in WGS84 order [longitude, latitude].",
        "canonical_properties": len(props),
        "target_address_point_ids": len(by_id),
        "matched_address_point_rows": matched,
        "coordinates_filled": filled,
        "invalid_or_missing_geometry": invalid_geometry,
        "properties_with_usable_coordinates_after_recovery": usable,
    }
    write_json(MARKET / "coordinate_recovery_report.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
