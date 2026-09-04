from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any, Mapping, Sequence

from towersignal.domestic_water import NYC_API_ROOT, fetch_snapshot, parse_source_date, source_health, stable_id

SCHEMA_VERSION = "1.0"
DATASET_ID = "5zyy-y8am"

IDENTITY_FIELDS = (
    "report_year",
    "property_id",
    "property_name",
    "nyc_borough_block_and_lot",
    "nyc_building_identification",
    "address_1",
    "city",
    "postal_code",
    "borough",
    "primary_property_type_self",
    "property_gfa_calculated_1",
)
WATER_FIELDS = (
    "metered_areas_water",
    "water_use_all_water_sources",
    "indoor_water_use_all_water",
    "outdoor_water_use_all_water",
    "municipally_supplied_potable",
    "municipally_supplied_potable_1",
    "municipally_supplied_potable_2",
    "municipally_supplied_potable_3",
    "estimated_values_water",
    "alert_water_meter_has_less",
    "estimated_data_flag_1",
    "last_modified_date_water",
)
SELECT_FIELDS = IDENTITY_FIELDS + WATER_FIELDS


def parse_number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    text = str(value).strip().replace(",", "")
    if not text or text.upper() in {"N/A", "NA", "NOT AVAILABLE", "NONE", "NULL"}:
        return None
    text = text.replace("%", "")
    try:
        return float(text)
    except ValueError:
        return None


def extract_bbls(value: Any) -> list[str]:
    text = str(value or "")
    candidates = re.findall(r"(?<!\d)[1-5]\d{9}(?!\d)", text)
    return list(dict.fromkeys(candidates))


def extract_bins(value: Any) -> list[str]:
    text = str(value or "")
    candidates = re.findall(r"(?<!\d)[1-5]\d{6}(?!\d)", text)
    return list(dict.fromkeys(candidates))


def normalize_row(row: Mapping[str, Any]) -> dict[str, Any]:
    report_year = str(row.get("report_year") or "").strip() or None
    property_id = str(row.get("property_id") or "").strip() or None
    bbls = extract_bbls(row.get("nyc_borough_block_and_lot"))
    bins = extract_bins(row.get("nyc_building_identification"))

    potable_total = parse_number(row.get("municipally_supplied_potable_1"))
    mixed = parse_number(row.get("municipally_supplied_potable"))
    all_water = parse_number(row.get("water_use_all_water_sources"))
    indoor = parse_number(row.get("municipally_supplied_potable_2"))
    outdoor = parse_number(row.get("municipally_supplied_potable_3"))
    effective_potable = potable_total if potable_total is not None else mixed

    selected_raw = {field: row.get(field) for field in SELECT_FIELDS if row.get(field) not in (None, "")}
    return {
        "observation_id": stable_id("ll84-water", property_id, report_year),
        "report_year": report_year,
        "epa_property_id": property_id,
        "property_name": str(row.get("property_name") or "").strip() or None,
        "address": str(row.get("address_1") or "").strip() or None,
        "city": str(row.get("city") or "").strip() or None,
        "postal_code": str(row.get("postal_code") or "").strip() or None,
        "borough": str(row.get("borough") or "").strip() or None,
        "property_type": str(row.get("primary_property_type_self") or "").strip() or None,
        "building_gfa_sqft": parse_number(row.get("property_gfa_calculated_1")),
        "bbls": bbls,
        "bins": bins,
        "property_link_confidence": "CONFIRMED_IDENTIFIER" if (bbls or bins) else "UNLINKED",
        "metered_areas_water": str(row.get("metered_areas_water") or "").strip() or None,
        "water_use_all_sources_kgal": all_water,
        "indoor_water_use_all_sources_kgal": parse_number(row.get("indoor_water_use_all_water")),
        "outdoor_water_use_all_sources_kgal": parse_number(row.get("outdoor_water_use_all_water")),
        "municipal_potable_mixed_kgal": mixed,
        "municipal_potable_total_kgal": potable_total,
        "municipal_potable_indoor_kgal": indoor,
        "municipal_potable_outdoor_kgal": outdoor,
        "effective_municipal_potable_kgal": effective_potable,
        "has_reported_water_use": any(value is not None for value in (all_water, effective_potable, indoor, outdoor)),
        "estimated_values_water": str(row.get("estimated_values_water") or "").strip() or None,
        "estimated_municipal_water_flag": str(row.get("estimated_data_flag_1") or "").strip() or None,
        "water_meter_short_year_alert": str(row.get("alert_water_meter_has_less") or "").strip() or None,
        "water_meter_last_modified_date": parse_source_date(row.get("last_modified_date_water")),
        "source_dataset_id": DATASET_ID,
        "raw_selected": selected_raw,
    }


def latest_by_property(observations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in observations:
        property_id = str(row.get("epa_property_id") or "").strip()
        if property_id:
            grouped[property_id].append(row)

    latest: list[dict[str, Any]] = []
    for property_id, rows in grouped.items():
        ordered = sorted(rows, key=lambda item: str(item.get("report_year") or ""), reverse=True)
        current = ordered[0]
        prior = ordered[1] if len(ordered) > 1 else None
        current_use = current.get("effective_municipal_potable_kgal")
        prior_use = prior.get("effective_municipal_potable_kgal") if prior else None
        delta = None
        delta_pct = None
        if isinstance(current_use, (int, float)) and isinstance(prior_use, (int, float)):
            delta = float(current_use) - float(prior_use)
            if float(prior_use) != 0:
                delta_pct = (delta / float(prior_use)) * 100.0
        latest.append({
            "epa_property_id": property_id,
            "latest_report_year": current.get("report_year"),
            "latest_observation_id": current.get("observation_id"),
            "bbls": list(current.get("bbls") or []),
            "bins": list(current.get("bins") or []),
            "address": current.get("address"),
            "borough": current.get("borough"),
            "property_type": current.get("property_type"),
            "latest_municipal_potable_kgal": current_use,
            "prior_report_year": prior.get("report_year") if prior else None,
            "prior_municipal_potable_kgal": prior_use,
            "year_over_year_delta_kgal": delta,
            "year_over_year_delta_pct": delta_pct,
            "latest_water_meter_modified_date": current.get("water_meter_last_modified_date"),
            "latest_estimated_values_water": current.get("estimated_values_water"),
            "latest_water_meter_short_year_alert": current.get("water_meter_short_year_alert"),
            "observation_count": len(rows),
            "property_link_confidence": current.get("property_link_confidence"),
        })
    return sorted(latest, key=lambda item: str(item["epa_property_id"]))


def build_payload(*, page_size: int = 50000) -> dict[str, Any]:
    snapshot = fetch_snapshot(
        DATASET_ID,
        api_root=NYC_API_ROOT,
        order_by="report_year,property_id",
        required_fields=SELECT_FIELDS,
        select=",".join(SELECT_FIELDS),
        page_size=page_size,
    )
    observations = [normalize_row(row) for row in snapshot.rows]
    latest = latest_by_property(observations)
    year_counts = Counter(str(row.get("report_year") or "MISSING") for row in observations)
    rows_with_bbl = sum(1 for row in observations if row["bbls"])
    rows_with_bin = sum(1 for row in observations if row["bins"])
    rows_with_water = sum(1 for row in observations if row["has_reported_water_use"])
    latest_with_water = sum(1 for row in latest if row["latest_municipal_potable_kgal"] is not None)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": snapshot.retrieved_at,
        "domain": "NYC_LL84_BUILDING_WATER",
        "source_health": [source_health(snapshot, normalized_count=len(observations))],
        "summary": {
            "observation_count": len(observations),
            "unique_epa_property_count": len(latest),
            "rows_with_bbl": rows_with_bbl,
            "rows_with_bin": rows_with_bin,
            "rows_with_reported_water_use": rows_with_water,
            "latest_properties_with_municipal_potable_use": latest_with_water,
            "report_year_counts": dict(sorted(year_counts.items())),
        },
        "evidence_semantics": {
            "property_identity": "BBL/BIN values are source-reported LL84 identifiers. Multiple values are preserved as arrays and never collapsed to one assumed asset.",
            "water_use": "Annual source-reported benchmarking values in thousand gallons; missing/not-available values remain null.",
            "year_over_year": "Computed only when the same EPA property ID has numeric current and prior municipal potable-water observations.",
            "scope": "LL84 covered properties only; not all NYC buildings.",
        },
        "latest_properties": latest,
        "observations": observations,
    }
