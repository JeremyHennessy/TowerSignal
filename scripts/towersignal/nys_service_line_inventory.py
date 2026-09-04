from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import re
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DATASET_ID = "j63k-4n92"
API_ROOT = "https://health.data.ny.gov"
RESOURCE_ROOT = f"{API_ROOT}/resource/{DATASET_ID}"
METADATA_URL = f"{API_ROOT}/api/views/{DATASET_ID}"
SOURCE_PAGE = f"{API_ROOT}/Health/New-York-State-Lead-Service-Line-Inventory/{DATASET_ID}/about_data"
USER_AGENT = "TowerSignal/1.0 (+https://github.com/JeremyHennessy/TowerSignal)"
SCHEMA_VERSION = "1.0"
MAX_BULK_ROWS = 5_000_000

SOURCE_FIELDS = (
    "locality",
    "street_address",
    "zip_code",
    "state",
    "lead_gooseneck_pigtail_or",
    "current_public_side_sl",
    "was_public_sl_material_ever",
    "public_sl_material",
    "public_sl_installation_or",
    "public_sl_size",
    "customer_sl_material",
    "customer_sl_material_1",
    "lead_solder_present",
    "building_type",
    "pou_or_poe_treatment_present",
    "customer_sl_installation",
    "customer_sl_size",
    "sl_category",
    "note",
    "location",
)

NORMALIZED_FIELDS = (
    "source_row_ordinal",
    "service_address_id",
    "locality_normalized",
    "nyc_borough",
    "public_material_normalized",
    "customer_material_normalized",
    "public_method_normalized",
    "customer_method_normalized",
    "sl_category_normalized",
    "latitude",
    "longitude",
)

NYC_LOCALITY_CODES = {
    "MN": "MANHATTAN",
    "BX": "BRONX",
    "BK": "BROOKLYN",
    "QN": "QUEENS",
    "SI": "STATEN ISLAND",
}

MATERIAL_EXACT = {
    "lead including lead lined galvanized": "LEAD",
    "lead": "LEAD",
    "copper": "COPPER",
    "plastic": "PLASTIC",
    "galvanized": "GALVANIZED",
    "galvanized iron": "GALVANIZED",
    "known other": "KNOWN_OTHER",
    "unknown but could be lead": "UNKNOWN_COULD_BE_LEAD",
    "unknown but unlikely lead": "UNKNOWN_UNLIKELY_LEAD",
    "unknown unlikely lead": "UNKNOWN_UNLIKELY_LEAD",
    "unknown": "UNKNOWN",
    "non lead": "NON_LEAD_OTHER",
}

METHOD_EXACT = {
    "records": "RECORDS",
    "not verified": "NOT_VERIFIED",
    "field inspection": "FIELD_INSPECTION",
    "field investigation": "FIELD_INSPECTION",
    "statistical analysis predictive model": "STATISTICAL_MODEL",
    "predictive modeling": "STATISTICAL_MODEL",
    "excavation": "EXCAVATION",
    "other": "OTHER",
    "customer identification with photo or other verification": "CUSTOMER_IDENTIFICATION",
    "customer identification with photo or other verification": "CUSTOMER_IDENTIFICATION",
    "sequential sampling": "SEQUENTIAL_SAMPLING",
}

CATEGORY_EXACT = {
    "lead": "LEAD",
    "non lead": "NON_LEAD",
    "gslrr": "GSLRR",
    "unknown": "UNKNOWN",
    "unknown lead status unknown": "UNKNOWN_LEAD_STATUS",
    "unknown sl": "UNKNOWN_LEAD_STATUS",
    "err 508": "SOURCE_ERROR",
    "ref": "SOURCE_ERROR",
}


class NysServiceLineSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceState:
    row_count: int
    rows_updated_at: int | None
    data_updated_at: int | None
    name: str
    fields: tuple[str, ...]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_space(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _token_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", normalize_space(value).lower()).strip()


def stable_id(prefix: str, *parts: Any) -> str:
    material = "|".join(normalize_space(part) for part in parts)
    return f"{prefix}-{hashlib.sha256(material.encode('utf-8')).hexdigest()[:20]}"


def normalize_locality(value: Any) -> str | None:
    text = normalize_space(value)
    return text.casefold() if text else None


def service_address_id(locality: Any, street_address: Any, zip_code: Any) -> str | None:
    locality_key = normalize_locality(locality)
    street_key = _token_key(street_address).upper()
    zip_key = re.sub(r"\D", "", normalize_space(zip_code))[:5]
    if not locality_key or not street_key or not zip_key:
        return None
    return stable_id("nys-lsli-address", locality_key, street_key, zip_key)


def normalize_material(value: Any) -> str:
    key = _token_key(value)
    if not key:
        return "MISSING"
    return MATERIAL_EXACT.get(key, "OTHER_RAW")


def normalize_method(value: Any) -> str:
    key = _token_key(value)
    if not key:
        return "MISSING"
    return METHOD_EXACT.get(key, "OTHER_RAW")


def normalize_category(value: Any) -> str:
    key = _token_key(value)
    if not key:
        return "MISSING"
    return CATEGORY_EXACT.get(key, "OTHER_RAW")


def parse_location(value: Any) -> tuple[float | None, float | None]:
    text = normalize_space(value)
    if not text:
        return None, None
    # Socrata CSV point values are commonly `POINT (longitude latitude)`.
    match = re.search(
        r"POINT\s*\(\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s*\)",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        longitude, latitude = float(match.group(1)), float(match.group(2))
    else:
        # Retain a deliberately narrow fallback for `(lat, lon)`/`lat,lon` exports.
        numbers = re.findall(r"-?\d+(?:\.\d+)?", text)
        if len(numbers) != 2:
            return None, None
        first, second = float(numbers[0]), float(numbers[1])
        if -90 <= first <= 90 and -180 <= second <= 180:
            latitude, longitude = first, second
        else:
            longitude, latitude = first, second
    if not (40 <= latitude <= 46 and -80 <= longitude <= -71):
        return None, None
    return latitude, longitude


def _request_json(url: str, *, retries: int = 4, timeout: int = 120) -> Any:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(2**attempt)
    raise NysServiceLineSourceError(f"Failed to retrieve NYS LSLI source: {url}: {last_error}")


def fetch_source_state() -> SourceState:
    metadata = _request_json(METADATA_URL)
    if not isinstance(metadata, dict):
        raise NysServiceLineSourceError("NYS LSLI metadata returned a non-object payload")
    fields = tuple(
        str(column.get("fieldName"))
        for column in metadata.get("columns", [])
        if isinstance(column, dict) and column.get("fieldName")
    )
    if fields != SOURCE_FIELDS:
        missing = sorted(set(SOURCE_FIELDS) - set(fields))
        extra = sorted(set(fields) - set(SOURCE_FIELDS))
        raise NysServiceLineSourceError(
            f"NYS LSLI schema drift: missing={missing}, extra={extra}, ordered_fields={fields}"
        )
    count_payload = _request_json(
        f"{RESOURCE_ROOT}.json?{urlencode({'$select': 'count(*) as count'})}"
    )
    if not isinstance(count_payload, list) or not count_payload or "count" not in count_payload[0]:
        raise NysServiceLineSourceError("NYS LSLI source count query returned unexpected payload")
    row_count = int(count_payload[0]["count"])
    return SourceState(
        row_count=row_count,
        rows_updated_at=(int(metadata["rowsUpdatedAt"]) if metadata.get("rowsUpdatedAt") is not None else None),
        data_updated_at=(int(metadata["dataUpdatedAt"]) if metadata.get("dataUpdatedAt") is not None else None),
        name=str(metadata.get("name") or DATASET_ID),
        fields=fields,
    )


def _bulk_csv_url(limit: int) -> str:
    return f"{RESOURCE_ROOT}.csv?{urlencode({'$limit': limit})}"


def download_bulk_csv(path: Path, *, expected_count: int, retries: int = 3, timeout: int = 600) -> dict[str, Any]:
    if expected_count <= 0 or expected_count > MAX_BULK_ROWS:
        raise NysServiceLineSourceError(
            f"NYS LSLI source count {expected_count:,} is outside supported coherent single-export range 1..{MAX_BULK_ROWS:,}"
        )
    url = _bulk_csv_url(MAX_BULK_ROWS)
    last_error: Exception | None = None
    for attempt in range(retries):
        sha256 = hashlib.sha256()
        byte_count = 0
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/csv"})
            with urlopen(request, timeout=timeout) as response, path.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    sha256.update(chunk)
                    byte_count += len(chunk)
            if byte_count < 10_000_000:
                raise NysServiceLineSourceError(f"NYS LSLI bulk CSV unexpectedly small: {byte_count:,} bytes")
            return {"url": url, "sha256": sha256.hexdigest(), "byte_count": byte_count}
        except (HTTPError, URLError, TimeoutError, OSError, NysServiceLineSourceError) as exc:
            last_error = exc
            path.unlink(missing_ok=True)
            if attempt + 1 < retries:
                time.sleep(2**attempt)
    raise NysServiceLineSourceError(f"Failed to retrieve coherent NYS LSLI bulk CSV: {last_error}")


def _is_yes(value: Any) -> bool:
    return _token_key(value) in {"yes", "y"}


def normalize_row(row: Mapping[str, Any], *, source_row_ordinal: int) -> dict[str, Any]:
    locality_raw = normalize_space(row.get("locality")) or None
    street_raw = normalize_space(row.get("street_address")) or None
    zip_raw = normalize_space(row.get("zip_code")) or None
    locality_code = normalize_space(locality_raw).upper()
    latitude, longitude = parse_location(row.get("location"))
    result = {field: (row.get(field) if row.get(field) not in (None, "") else None) for field in SOURCE_FIELDS}
    result.update(
        {
            "source_row_ordinal": source_row_ordinal,
            "service_address_id": service_address_id(locality_raw, street_raw, zip_raw),
            "locality_normalized": normalize_locality(locality_raw),
            "nyc_borough": NYC_LOCALITY_CODES.get(locality_code),
            "public_material_normalized": normalize_material(row.get("current_public_side_sl")),
            "customer_material_normalized": normalize_material(row.get("customer_sl_material")),
            "public_method_normalized": normalize_method(row.get("public_sl_material")),
            "customer_method_normalized": normalize_method(row.get("customer_sl_material_1")),
            "sl_category_normalized": normalize_category(row.get("sl_category")),
            "latitude": latitude,
            "longitude": longitude,
        }
    )
    return result


def process_csv(source_path: Path, output_path: Path, *, expected_count: int) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    raw_locality_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    public_material_counts: Counter[str] = Counter()
    customer_material_counts: Counter[str] = Counter()
    public_method_counts: Counter[str] = Counter()
    customer_method_counts: Counter[str] = Counter()
    borough_counts: Counter[str] = Counter()
    building_type_counts: Counter[str] = Counter()
    pou_poe_raw_counts: Counter[str] = Counter()
    parsed_rows = 0
    address_key_missing_count = 0
    location_count = 0
    note_count = 0
    pou_poe_yes_count = 0

    with source_path.open("r", encoding="utf-8-sig", errors="replace", newline="") as source_handle:
        reader = csv.DictReader(source_handle)
        if tuple(reader.fieldnames or ()) != SOURCE_FIELDS:
            raise NysServiceLineSourceError(
                f"NYS LSLI bulk CSV header mismatch: {tuple(reader.fieldnames or ())}"
            )
        with gzip.open(output_path, "wt", encoding="utf-8", newline="", compresslevel=6) as output_handle:
            writer = csv.DictWriter(output_handle, fieldnames=[*SOURCE_FIELDS, *NORMALIZED_FIELDS])
            writer.writeheader()
            for source_row_ordinal, row in enumerate(reader, start=1):
                normalized = normalize_row(row, source_row_ordinal=source_row_ordinal)
                writer.writerow(normalized)
                parsed_rows += 1

                raw_locality_counts[str(normalized.get("locality") or "MISSING")] += 1
                category_counts[str(normalized["sl_category_normalized"])] += 1
                public_material_counts[str(normalized["public_material_normalized"])] += 1
                customer_material_counts[str(normalized["customer_material_normalized"])] += 1
                public_method_counts[str(normalized["public_method_normalized"])] += 1
                customer_method_counts[str(normalized["customer_method_normalized"])] += 1
                building_type_counts[normalize_space(normalized.get("building_type")) or "MISSING"] += 1
                pou_poe_raw = normalize_space(normalized.get("pou_or_poe_treatment_present")) or "MISSING"
                pou_poe_raw_counts[pou_poe_raw] += 1
                if _is_yes(normalized.get("pou_or_poe_treatment_present")):
                    pou_poe_yes_count += 1
                if normalized.get("nyc_borough"):
                    borough_counts[str(normalized["nyc_borough"])] += 1
                if normalized.get("service_address_id") is None:
                    address_key_missing_count += 1
                if normalized.get("latitude") is not None and normalized.get("longitude") is not None:
                    location_count += 1
                if normalized.get("note") not in (None, ""):
                    note_count += 1

    if parsed_rows != expected_count:
        output_path.unlink(missing_ok=True)
        raise NysServiceLineSourceError(
            f"NYS LSLI parsed row count mismatch: expected {expected_count:,}, parsed {parsed_rows:,}"
        )

    return {
        "row_count": parsed_rows,
        "raw_locality_counts": dict(raw_locality_counts.most_common()),
        "normalized_category_counts": dict(sorted(category_counts.items())),
        "normalized_public_material_counts": dict(sorted(public_material_counts.items())),
        "normalized_customer_material_counts": dict(sorted(customer_material_counts.items())),
        "normalized_public_method_counts": dict(sorted(public_method_counts.items())),
        "normalized_customer_method_counts": dict(sorted(customer_method_counts.items())),
        "nyc_borough_row_counts": dict(sorted(borough_counts.items())),
        "building_type_counts": dict(building_type_counts.most_common()),
        "pou_poe_raw_counts": dict(pou_poe_raw_counts.most_common()),
        "pou_poe_yes_count": pou_poe_yes_count,
        "missing_service_address_id_count": address_key_missing_count,
        "rows_with_valid_nys_location": location_count,
        "rows_with_note": note_count,
    }


def build_cache(data_output: Path, summary_output: Path) -> dict[str, Any]:
    before = fetch_source_state()
    temp_path = Path(tempfile.mkstemp(prefix="towersignal-nys-lsli-", suffix=".csv")[1])
    try:
        download = download_bulk_csv(temp_path, expected_count=before.row_count)
        processed = process_csv(temp_path, data_output, expected_count=before.row_count)
    finally:
        temp_path.unlink(missing_ok=True)

    after = fetch_source_state()
    if before.row_count != after.row_count:
        data_output.unlink(missing_ok=True)
        raise NysServiceLineSourceError(
            f"NYS LSLI source row count changed during coherent snapshot: {before.row_count:,} -> {after.row_count:,}"
        )
    if before.rows_updated_at != after.rows_updated_at or before.data_updated_at != after.data_updated_at:
        data_output.unlink(missing_ok=True)
        raise NysServiceLineSourceError(
            "NYS LSLI source update timestamp changed during coherent snapshot; refusing mixed-version cache"
        )

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "domain": "NYS_ADDRESS_LEVEL_SERVICE_LINE_INVENTORY",
        "source": {
            "dataset_id": DATASET_ID,
            "name": before.name,
            "host": API_ROOT,
            "source_page": SOURCE_PAGE,
            "bulk_export_url": download["url"],
            "bulk_export_sha256": download["sha256"],
            "bulk_export_byte_count": download["byte_count"],
            "source_record_count": before.row_count,
            "source_rows_updated_at": before.rows_updated_at,
            "source_data_updated_at": before.data_updated_at,
            "before_after_count_stable": True,
            "before_after_update_timestamp_stable": True,
            "schema_valid": True,
            "source_fields": list(SOURCE_FIELDS),
        },
        "identity_semantics": {
            "pws_id": "The published line-level dataset does not contain PWSID; no PWS relationship is inferred from locality/address.",
            "service_address_id": "Deterministic normalized locality + street address + ZIP grouping key. It is intentionally non-unique because multiple service-line rows at one address are legitimate source records.",
            "source_row_ordinal": "Ordinal within the coherent bulk snapshot. It is unique only within that snapshot and must not be used as a longitudinal source identifier.",
            "duplicates": "Every source row is retained. No address or exact-row deduplication is performed in this source adapter.",
            "nyc": "NYC locality codes MN/BX/BK/QN/SI are labeled for analysis only. This adapter does not collapse the current paired-row NYC source pattern into one service line.",
        },
        "normalization_semantics": {
            "raw_preserved": "All 20 source fields are preserved in the compressed cache.",
            "materials": "Only exact/case/punctuation-normalized known material labels are mapped to canonical categories; unrecognized source text remains OTHER_RAW.",
            "methods": "Only explicit recognized verification-method labels/known spelling variants are mapped; unrecognized source text remains OTHER_RAW.",
            "metadata_warning": "Portal column names are authoritative for field selection; source metadata descriptions are not used to shift values between columns.",
        },
        "summary": processed,
        "data_file": data_output.name,
    }
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.write_text(json.dumps(summary, separators=(",", ":")), encoding="utf-8")
    return summary
