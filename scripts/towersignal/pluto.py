from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from towersignal.fetch import fetch_count, fetch_metadata, fetch_where

PLUTO_DATASET_ID = "64uk-42ks"
PLUTO_URL = "https://data.cityofnewyork.us/City-Government/Primary-Land-Use-Tax-Lot-Output-PLUTO-/64uk-42ks"
PLUTO_SELECT = ",".join((
    "bbl",
    "ownername",
    "landuse",
    "bldgclass",
    "lotarea",
    "bldgarea",
    "numfloors",
    "unitsres",
    "unitstotal",
    "yearbuilt",
    "yearalter1",
    "yearalter2",
))


def normalize_bbl(value: Any) -> str | None:
    if value is None:
        return None
    text = "".join(ch for ch in str(value).strip() if ch.isdigit())
    if not text:
        return None
    try:
        numeric = int(text)
    except ValueError:
        return None
    if numeric <= 0:
        return None
    return str(numeric)


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_pluto_record(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "bbl": normalize_bbl(row.get("bbl")),
        "owner_name": _text(row.get("ownername")),
        "land_use": _text(row.get("landuse")),
        "building_class": _text(row.get("bldgclass")),
        "lot_area_sqft": _number(row.get("lotarea")),
        "building_area_sqft": _number(row.get("bldgarea")),
        "floors": _number(row.get("numfloors")),
        "residential_units": _integer(row.get("unitsres")),
        "total_units": _integer(row.get("unitstotal")),
        "year_built": _integer(row.get("yearbuilt")),
        "year_altered_1": _integer(row.get("yearalter1")),
        "year_altered_2": _integer(row.get("yearalter2")),
        "source": "NYC_DCP_PLUTO",
    }


def fetch_pluto_by_bbl(bbl_values: set[str], chunk_size: int = 200) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    requested = sorted({bbl for value in bbl_values if (bbl := normalize_bbl(value)) is not None}, key=int)
    records: dict[str, dict[str, Any]] = {}

    for start in range(0, len(requested), chunk_size):
        chunk = requested[start : start + chunk_size]
        if not chunk:
            continue
        where = f"bbl in ({','.join(chunk)})"
        rows = fetch_where(PLUTO_DATASET_ID, where=where, order_by="bbl", select=PLUTO_SELECT)
        for row in rows:
            normalized = normalize_pluto_record(row)
            bbl = normalized["bbl"]
            if bbl is not None:
                records[bbl] = normalized

    metadata = fetch_metadata(PLUTO_DATASET_ID)
    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return records, {
        "dataset_id": PLUTO_DATASET_ID,
        "name": metadata["name"],
        "retrieved_at": retrieved_at,
        "source_record_count": fetch_count(PLUTO_DATASET_ID),
        "source_query_scope": f"BBL exact-match subset for {len(requested):,} registered cooling-tower systems with usable BBLs",
        "source_last_updated_at": metadata.get("source_last_updated_at"),
        "url": PLUTO_URL,
        "requested_bbl_count": len(requested),
        "matched_bbl_count": len(records),
    }
