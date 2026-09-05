from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SOURCE_FIELDS = (
    "locality", "street_address", "zip_code", "state",
    "lead_gooseneck_pigtail_or", "current_public_side_sl",
    "was_public_sl_material_ever", "public_sl_material",
    "public_sl_installation_or", "public_sl_size", "customer_sl_material",
    "customer_sl_material_1", "lead_solder_present", "building_type",
    "pou_or_poe_treatment_present", "customer_sl_installation",
    "customer_sl_size", "sl_category", "note", "location",
)
NORMALIZED_FIELDS = (
    "source_row_ordinal", "service_address_id", "locality_normalized", "nyc_borough",
    "public_material_normalized", "customer_material_normalized",
    "public_method_normalized", "customer_method_normalized",
    "sl_category_normalized", "latitude", "longitude",
)
ALLOWED_MATERIAL = {
    "LEAD", "COPPER", "PLASTIC", "GALVANIZED", "KNOWN_OTHER",
    "UNKNOWN_COULD_BE_LEAD", "UNKNOWN_UNLIKELY_LEAD", "UNKNOWN",
    "NON_LEAD_OTHER", "OTHER_RAW", "MISSING",
}
ALLOWED_METHOD = {
    "RECORDS", "NOT_VERIFIED", "FIELD_INSPECTION", "STATISTICAL_MODEL",
    "EXCAVATION", "OTHER", "CUSTOMER_IDENTIFICATION", "SEQUENTIAL_SAMPLING",
    "OTHER_RAW", "MISSING",
}
ALLOWED_CATEGORY = {
    "LEAD", "NON_LEAD", "GSLRR", "UNKNOWN", "UNKNOWN_LEAD_STATUS",
    "SOURCE_ERROR", "OTHER_RAW", "MISSING",
}
NYC = {"MN": "MANHATTAN", "BX": "BRONX", "BK": "BROOKLYN", "QN": "QUEENS", "SI": "STATEN ISLAND"}


def _yes(value: str | None) -> bool:
    return str(value or "").strip().casefold() in {"yes", "y"}


def validate(data_path: Path, summary_path: Path, *, max_age_days: int, require_production_volume: bool) -> dict:
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0" or payload.get("domain") != "NYS_ADDRESS_LEVEL_SERVICE_LINE_INVENTORY":
        raise RuntimeError("Unexpected NYS address-level service-line cache schema/domain")
    generated = datetime.fromisoformat(str(payload.get("generated_at") or "").replace("Z", "+00:00"))
    age_days = (datetime.now(timezone.utc) - generated).total_seconds() / 86400
    if age_days < -0.05 or age_days > max_age_days:
        raise RuntimeError(f"NYS line-level cache age is {age_days:.2f} days")

    source = payload.get("source")
    summary = payload.get("summary")
    identity = payload.get("identity_semantics")
    if not isinstance(source, dict) or not isinstance(summary, dict) or not isinstance(identity, dict):
        raise RuntimeError("NYS line-level cache missing source/summary/identity semantics")
    expected = int(source.get("source_record_count") or -1)
    if source.get("schema_valid") is not True or source.get("before_after_count_stable") is not True or source.get("before_after_update_timestamp_stable") is not True:
        raise RuntimeError("NYS line-level coherent source snapshot proof failed")
    if int(summary.get("row_count") or -2) != expected:
        raise RuntimeError("NYS line-level summary/source row count mismatch")
    if len(str(source.get("bulk_export_sha256") or "")) != 64:
        raise RuntimeError("NYS line-level bulk export hash missing")
    if "does not contain PWSID" not in str(identity.get("pws_id") or ""):
        raise RuntimeError("NYS line-level no-PWSID evidence boundary missing")

    expected_header = [*SOURCE_FIELDS, *NORMALIZED_FIELDS]
    material_public: Counter[str] = Counter()
    material_customer: Counter[str] = Counter()
    method_public: Counter[str] = Counter()
    method_customer: Counter[str] = Counter()
    category: Counter[str] = Counter()
    boroughs: Counter[str] = Counter()
    row_count = 0
    missing_address = 0
    location_count = 0
    note_count = 0
    pou_yes = 0

    with gzip.open(data_path, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if list(reader.fieldnames or []) != expected_header:
            raise RuntimeError("NYS line-level compressed cache header mismatch")
        if "pws_id" in (reader.fieldnames or []):
            raise RuntimeError("NYS line-level cache unexpectedly invented a PWS ID field")
        for expected_ordinal, row in enumerate(reader, start=1):
            row_count += 1
            if int(row.get("source_row_ordinal") or 0) != expected_ordinal:
                raise RuntimeError(f"NYS line-level source ordinal gap at row {expected_ordinal:,}")
            public_material = str(row.get("public_material_normalized") or "")
            customer_material = str(row.get("customer_material_normalized") or "")
            public_method = str(row.get("public_method_normalized") or "")
            customer_method = str(row.get("customer_method_normalized") or "")
            sl_category = str(row.get("sl_category_normalized") or "")
            if public_material not in ALLOWED_MATERIAL or customer_material not in ALLOWED_MATERIAL:
                raise RuntimeError(f"Invalid normalized material at source row {expected_ordinal:,}")
            if public_method not in ALLOWED_METHOD or customer_method not in ALLOWED_METHOD:
                raise RuntimeError(f"Invalid normalized verification method at source row {expected_ordinal:,}")
            if sl_category not in ALLOWED_CATEGORY:
                raise RuntimeError(f"Invalid normalized SL category at source row {expected_ordinal:,}")
            material_public[public_material] += 1
            material_customer[customer_material] += 1
            method_public[public_method] += 1
            method_customer[customer_method] += 1
            category[sl_category] += 1

            locality = str(row.get("locality") or "").strip().upper()
            borough = str(row.get("nyc_borough") or "").strip()
            expected_borough = NYC.get(locality, "")
            if borough != expected_borough:
                raise RuntimeError(f"NYS line-level NYC locality mapping mismatch at row {expected_ordinal:,}")
            if borough:
                boroughs[borough] += 1
            address_id = str(row.get("service_address_id") or "")
            if not address_id:
                missing_address += 1
            elif not address_id.startswith("nys-lsli-address-"):
                raise RuntimeError(f"Invalid service-address grouping key at row {expected_ordinal:,}")
            lat = str(row.get("latitude") or "").strip()
            lon = str(row.get("longitude") or "").strip()
            if bool(lat) != bool(lon):
                raise RuntimeError(f"Partial normalized coordinate pair at row {expected_ordinal:,}")
            if lat and lon:
                latitude, longitude = float(lat), float(lon)
                if not (40 <= latitude <= 46 and -80 <= longitude <= -71):
                    raise RuntimeError(f"Normalized coordinate outside NY bounds at row {expected_ordinal:,}")
                location_count += 1
            if str(row.get("note") or ""):
                note_count += 1
            if _yes(row.get("pou_or_poe_treatment_present")):
                pou_yes += 1

    if row_count != expected:
        raise RuntimeError(f"NYS line-level compressed cache row count mismatch: {row_count:,} != {expected:,}")
    checks = {
        "normalized_public_material_counts": dict(sorted(material_public.items())),
        "normalized_customer_material_counts": dict(sorted(material_customer.items())),
        "normalized_public_method_counts": dict(sorted(method_public.items())),
        "normalized_customer_method_counts": dict(sorted(method_customer.items())),
        "normalized_category_counts": dict(sorted(category.items())),
        "nyc_borough_row_counts": dict(sorted(boroughs.items())),
    }
    for key, actual in checks.items():
        if summary.get(key) != actual:
            raise RuntimeError(f"NYS line-level summary mismatch for {key}")
    scalar_checks = {
        "missing_service_address_id_count": missing_address,
        "rows_with_valid_nys_location": location_count,
        "rows_with_note": note_count,
        "pou_poe_yes_count": pou_yes,
    }
    for key, actual in scalar_checks.items():
        if int(summary.get(key) or 0) != actual:
            raise RuntimeError(f"NYS line-level summary mismatch for {key}")

    if require_production_volume:
        if expected < 4_000_000:
            raise RuntimeError(f"Implausibly small NYS line-level source: {expected:,}")
        if location_count < 3_500_000:
            raise RuntimeError(f"Implausibly few georeferenced NYS line rows: {location_count:,}")
        if sum(boroughs.values()) < 1_000_000:
            raise RuntimeError(f"Implausibly few NYC-coded source rows: {sum(boroughs.values()):,}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate coherent NYSDOH address-level service-line cache")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--max-age-days", type=int, default=1)
    parser.add_argument("--require-production-volume", action="store_true")
    args = parser.parse_args()
    payload = validate(args.data, args.summary, max_age_days=args.max_age_days, require_production_volume=args.require_production_volume)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
