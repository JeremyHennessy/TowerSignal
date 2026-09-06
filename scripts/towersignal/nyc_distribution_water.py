from __future__ import annotations

import re
from collections import Counter
from typing import Any, Mapping

from .fetch import API_ROOT, _request_json, fetch_dataset
from .procurement import normalize_space, parse_iso_date, stable_id, utc_now

SCHEMA_VERSION = "1.0"
DATASET_ID = "bkwf-xfky"
SOURCE_URL = f"https://data.cityofnewyork.us/d/{DATASET_ID}"

REQUIRED_FIELDS = (
    "sample_number",
    "sample_date",
    "sample_time",
    "sample_site",
    "sample_class",
    "residual_free_chlorine_mg_l",
    "turbidity_ntu",
    "fluoride_mg_l",
    "coliform_quanti_tray_mpn_100ml",
    "e_coli_quanti_tray_mpn_100ml",
)

MEASUREMENT_FIELDS = {
    "residual_free_chlorine": "residual_free_chlorine_mg_l",
    "turbidity": "turbidity_ntu",
    "fluoride": "fluoride_mg_l",
    "coliform": "coliform_quanti_tray_mpn_100ml",
    "e_coli": "e_coli_quanti_tray_mpn_100ml",
}


def source_schema() -> dict[str, Any]:
    metadata = _request_json(f"{API_ROOT}/api/views/{DATASET_ID}")
    if not isinstance(metadata, dict):
        raise RuntimeError("Distribution-water metadata returned a non-object payload")
    fields = {
        str(column.get("fieldName"))
        for column in metadata.get("columns", [])
        if isinstance(column, dict) and column.get("fieldName")
    }
    missing = sorted(set(REQUIRED_FIELDS) - fields)
    if missing:
        raise RuntimeError(f"Distribution-water source missing required fields: {', '.join(missing)}")
    return {
        "name": str(metadata.get("name") or DATASET_ID),
        "fields": sorted(fields),
    }


def parse_measurement(value: Any) -> dict[str, Any]:
    raw = normalize_space(value)
    if not raw:
        return {"raw": None, "numeric": None, "qualifier": "MISSING"}
    upper = raw.upper()
    if upper in {"ND", "N/D", "NON-DETECT", "NON DETECT", "NOT DETECTED"}:
        return {"raw": raw, "numeric": None, "qualifier": "ND"}

    compact = raw.replace(",", "")
    match = re.search(r"(-?\d+(?:\.\d+)?)", compact)
    numeric = float(match.group(1)) if match else None
    if compact.lstrip().startswith("<"):
        qualifier = "LT"
    elif compact.lstrip().startswith(">"):
        qualifier = "GT"
    elif numeric is not None:
        qualifier = "EQ"
    else:
        qualifier = "TEXT"
    return {"raw": raw, "numeric": numeric, "qualifier": qualifier}


def normalize_sample(row: Mapping[str, Any]) -> dict[str, Any]:
    sample_number = normalize_space(row.get("sample_number"))
    if not sample_number:
        raise RuntimeError("Distribution-water source row missing sample_number")
    measurements = {
        target: parse_measurement(row.get(source_field))
        for target, source_field in MEASUREMENT_FIELDS.items()
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "sample_id": stable_id("nyc-distribution-water", sample_number),
        "sample_number": sample_number,
        "sample_date": parse_iso_date(row.get("sample_date")),
        "sample_time": normalize_space(row.get("sample_time")) or None,
        "sample_site": normalize_space(row.get("sample_site")) or None,
        "sample_class": normalize_space(row.get("sample_class")) or None,
        "measurements": measurements,
        "property_link_confidence": "UNLINKED_SAMPLE_SITE",
        "source_dataset_id": DATASET_ID,
        "raw": dict(row),
    }


def _site_profiles(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for sample in samples:
        site = str(sample.get("sample_site") or "MISSING")
        profile = profiles.setdefault(
            site,
            {
                "sample_site": None if site == "MISSING" else site,
                "sample_count": 0,
                "sample_classes": Counter(),
                "first_sample_date": None,
                "latest_sample_date": None,
                "latest_sample_id": None,
                "latest_measurements": None,
                "property_link_confidence": "UNLINKED_SAMPLE_SITE",
            },
        )
        profile["sample_count"] += 1
        if sample.get("sample_class"):
            profile["sample_classes"][str(sample["sample_class"])] += 1
        sample_date = sample.get("sample_date")
        if sample_date:
            if not profile["first_sample_date"] or sample_date < profile["first_sample_date"]:
                profile["first_sample_date"] = sample_date
            if not profile["latest_sample_date"] or sample_date >= profile["latest_sample_date"]:
                profile["latest_sample_date"] = sample_date
                profile["latest_sample_id"] = sample["sample_id"]
                profile["latest_measurements"] = sample["measurements"]

    result: list[dict[str, Any]] = []
    for profile in profiles.values():
        counter: Counter[str] = profile.pop("sample_classes")
        profile["sample_class_counts"] = dict(sorted(counter.items()))
        result.append(profile)
    return sorted(result, key=lambda row: str(row.get("sample_site") or ""))


def build_payload(*, page_size: int = 50000) -> dict[str, Any]:
    schema = source_schema()
    snapshot = fetch_dataset(DATASET_ID, "sample_number", page_size=page_size)
    samples = [normalize_sample(row) for row in snapshot.rows]
    ids = [row["sample_id"] for row in samples]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Distribution-water sample IDs are not unique")
    sites = _site_profiles(samples)
    class_counts = Counter(str(row.get("sample_class") or "MISSING") for row in samples)
    generated_at = utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "domain": "NYC_DISTRIBUTION_DRINKING_WATER_QUALITY",
        "source": {
            "dataset_id": DATASET_ID,
            "name": schema["name"],
            "url": SOURCE_URL,
            "retrieved_at": snapshot.retrieved_at,
            "source_last_updated_at": snapshot.source_last_updated_at,
            "source_record_count": snapshot.source_record_count,
            "fetched_record_count": len(snapshot.rows),
            "pagination_complete": len(snapshot.rows) == snapshot.source_record_count,
            "schema_valid": True,
        },
        "evidence_semantics": {
            "sample_site": "NYC DEP distribution sampling-site identifier; no TowerSignal property link is inferred in this increment.",
            "measurement": "Raw source text is always retained; numeric parsing retains comparison qualifiers such as < or > rather than treating them as exact measurements.",
        },
        "summary": {
            "sample_count": len(samples),
            "sample_site_count": len(sites),
            "sample_class_counts": dict(sorted(class_counts.items())),
            "samples_with_coliform_value": sum(1 for row in samples if row["measurements"]["coliform"]["raw"] is not None),
            "samples_with_e_coli_value": sum(1 for row in samples if row["measurements"]["e_coli"]["raw"] is not None),
        },
        "sites": sites,
        "samples": samples,
    }
