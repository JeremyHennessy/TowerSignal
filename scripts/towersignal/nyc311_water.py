from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterator, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_ROOT = "https://data.cityofnewyork.us"
USER_AGENT = "TowerSignal/1.0 (+https://github.com/JeremyHennessy/TowerSignal)"
SCHEMA_VERSION = "1.0"

SOURCE_DATASETS: tuple[tuple[str, str], ...] = (
    ("NYC_311_2010_2019", "76ig-c548"),
    ("NYC_311_2020_PRESENT", "erm2-nwe9"),
)

SOURCE_SCOPE = "agency='DEP' AND (complaint_type like '%Water%' OR complaint_type='Lead')"

REQUIRED_FIELDS = (
    "unique_key",
    "created_date",
    "agency",
    "complaint_type",
    "descriptor",
    "status",
    "borough",
)

DESIRED_FIELDS = (
    "unique_key",
    "created_date",
    "closed_date",
    "agency",
    "agency_name",
    "complaint_type",
    "descriptor",
    "descriptor_2",
    "location_type",
    "incident_zip",
    "incident_address",
    "street_name",
    "address_type",
    "city",
    "status",
    "resolution_description",
    "resolution_action_updated_date",
    "community_board",
    "bbl",
    "borough",
    "latitude",
    "longitude",
)

CATEGORIES = (
    "LEAD_TEST_KIT_ACTIVITY",
    "LEAD_DRINKING_WATER_REQUEST",
    "DRINKING_WATER_QUALITY",
    "WATER_SUPPLY_PRESSURE",
    "WATER_LEAK_REPORTED",
    "PUBLIC_WATER_INFRASTRUCTURE",
    "OTHER_WATER_RELATED_REQUEST",
)


class Nyc311WaterSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class Classification:
    category: str
    asset_scope: str
    reason: str
    matched_terms: tuple[str, ...]


@dataclass(frozen=True)
class SourceMetadata:
    source_name: str
    dataset_id: str
    dataset_name: str
    source_last_updated_at: str | None
    fields: tuple[str, ...]
    selected_fields: tuple[str, ...]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_space(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalize_bbl(value: Any) -> str | None:
    text = re.sub(r"\D", "", normalize_space(value))
    if len(text) == 10 and text[0] in "12345":
        return text
    return None


def parse_source_date(value: Any) -> str | None:
    text = normalize_space(value)
    if not text:
        return None
    for candidate in (text, text[:10]):
        try:
            return datetime.fromisoformat(candidate.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            pass
    for fmt in ("%m/%d/%Y", "%m/%d/%Y %I:%M:%S %p", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _terms_present(text: str, terms: Sequence[str]) -> tuple[str, ...]:
    return tuple(term for term in terms if term in text)


def classify_request(complaint_type: Any, descriptor: Any, descriptor_2: Any = None, location_type: Any = None) -> Classification:
    complaint = normalize_space(complaint_type).lower()
    detail = normalize_space(descriptor).lower()
    detail2 = normalize_space(descriptor_2).lower()
    location = normalize_space(location_type).lower()
    text = " ".join(value for value in (complaint, detail, detail2, location) if value)

    if complaint == "lead" or complaint.startswith("lead "):
        kit_terms = _terms_present(text, ("lead kit", "test kit", "lead test"))
        if kit_terms:
            return Classification(
                "LEAD_TEST_KIT_ACTIVITY",
                "BUILDING_WATER_ACTIVITY",
                "311 record is a lead test-kit/service activity; it does not prove lead is present.",
                kit_terms,
            )
        return Classification(
            "LEAD_DRINKING_WATER_REQUEST",
            "BUILDING_WATER_SIGNAL",
            "311 record is categorized by DEP as a lead-related drinking-water request; it is a reported service request, not confirmed contamination.",
            ("lead",),
        )

    quality_terms = _terms_present(
        text,
        (
            "dirty water",
            "discolor",
            "brown water",
            "black water",
            "rusty",
            "yellow water",
            "taste",
            "odor",
            "odour",
            "smell",
            "cloudy",
            "milky",
            "particle",
            "grease",
            "gasoline",
            "insect",
            "worm",
        ),
    )
    if quality_terms:
        return Classification(
            "DRINKING_WATER_QUALITY",
            "BUILDING_OR_DISTRIBUTION_SIGNAL",
            "Complaint wording describes drinking-water appearance, taste, odor or material quality; source remains a reported condition.",
            quality_terms,
        )

    supply_terms = _terms_present(text, ("no water", "low pressure", "low water pressure", "water pressure"))
    if supply_terms:
        return Classification(
            "WATER_SUPPLY_PRESSURE",
            "BUILDING_OR_DISTRIBUTION_SIGNAL",
            "Complaint wording describes missing/low-pressure water supply; the source does not establish whether the cause is internal plumbing or public distribution.",
            supply_terms,
        )

    infrastructure_terms = _terms_present(
        text,
        (
            "fire hydrant",
            "hydrant",
            "water main",
            "main break",
            "street flooding",
            "street/sidewalk",
        ),
    )
    if infrastructure_terms:
        return Classification(
            "PUBLIC_WATER_INFRASTRUCTURE",
            "PUBLIC_INFRASTRUCTURE",
            "Complaint wording points to hydrant/main/street water infrastructure rather than a building domestic-water system.",
            infrastructure_terms,
        )

    leak_terms = _terms_present(text, ("leak", "leaking"))
    if leak_terms:
        return Classification(
            "WATER_LEAK_REPORTED",
            "MIXED_LOCATION_SIGNAL",
            "A water leak is reported, but 311 wording alone does not establish whether the leak is on public infrastructure or private building plumbing.",
            leak_terms,
        )

    return Classification(
        "OTHER_WATER_RELATED_REQUEST",
        "CONTEXT_ONLY",
        "DEP complaint type contains Water but available wording is insufficient for a more specific asset classification.",
        tuple(term for term in (complaint, detail) if term),
    )


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
    raise Nyc311WaterSourceError(f"Failed to retrieve NYC 311 source after {retries} attempts: {url}: {last_error}")


def _iso_from_epoch(value: Any) -> str | None:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError):
        return None


def fetch_metadata(source_name: str, dataset_id: str) -> SourceMetadata:
    payload = _request_json(f"{API_ROOT}/api/views/{dataset_id}")
    if not isinstance(payload, dict):
        raise Nyc311WaterSourceError(f"Metadata for {dataset_id} returned a non-object payload")
    fields = tuple(
        str(column.get("fieldName"))
        for column in payload.get("columns", [])
        if isinstance(column, dict) and column.get("fieldName")
    )
    missing = [field for field in REQUIRED_FIELDS if field not in fields]
    if missing:
        raise Nyc311WaterSourceError(f"Dataset {dataset_id} missing required fields: {', '.join(missing)}")
    selected = tuple(field for field in DESIRED_FIELDS if field in fields)
    return SourceMetadata(
        source_name=source_name,
        dataset_id=dataset_id,
        dataset_name=normalize_space(payload.get("name")) or dataset_id,
        source_last_updated_at=_iso_from_epoch(payload.get("rowsUpdatedAt") or payload.get("dataUpdatedAt")),
        fields=fields,
        selected_fields=selected,
    )


def _query(dataset_id: str, params: Mapping[str, Any]) -> Any:
    return _request_json(f"{API_ROOT}/resource/{dataset_id}.json?{urlencode(params)}")


def fetch_count(dataset_id: str, *, where: str = SOURCE_SCOPE) -> int:
    payload = _query(dataset_id, {"$select": "count(*) as count", "$where": where})
    if not isinstance(payload, list) or not payload or "count" not in payload[0]:
        raise Nyc311WaterSourceError(f"Count query for {dataset_id} returned an unexpected payload")
    return int(payload[0]["count"])


def iter_partition(metadata: SourceMetadata, *, page_size: int = 50000, where: str = SOURCE_SCOPE) -> tuple[int, Iterator[list[dict[str, Any]]]]:
    expected = fetch_count(metadata.dataset_id, where=where)

    def pages() -> Iterator[list[dict[str, Any]]]:
        offset = 0
        fetched = 0
        while offset < expected:
            payload = _query(
                metadata.dataset_id,
                {
                    "$select": ",".join(metadata.selected_fields),
                    "$where": where,
                    "$order": "unique_key",
                    "$limit": page_size,
                    "$offset": offset,
                },
            )
            if not isinstance(payload, list):
                raise Nyc311WaterSourceError(f"Dataset {metadata.dataset_id} returned non-list page at offset {offset}")
            page = [row for row in payload if isinstance(row, dict)]
            if len(page) != len(payload):
                raise Nyc311WaterSourceError(f"Dataset {metadata.dataset_id} returned a non-object source row")
            fetched += len(page)
            yield page
            if len(page) < page_size:
                break
            offset += page_size
        if fetched != expected:
            raise Nyc311WaterSourceError(
                f"Dataset {metadata.dataset_id} pagination incomplete: expected {expected:,}, fetched {fetched:,}. Refusing partial snapshot."
            )

    return expected, pages()


def normalize_request(source_name: str, dataset_id: str, row: Mapping[str, Any]) -> dict[str, Any]:
    unique_key = normalize_space(row.get("unique_key"))
    classification = classify_request(
        row.get("complaint_type"),
        row.get("descriptor"),
        row.get("descriptor_2"),
        row.get("location_type"),
    )
    bbl = normalize_bbl(row.get("bbl"))
    return {
        "request_id": f"311-{dataset_id}-{unique_key}",
        "source": source_name,
        "source_dataset_id": dataset_id,
        "source_unique_key": unique_key or None,
        "created_at": normalize_space(row.get("created_date")) or None,
        "created_date": parse_source_date(row.get("created_date")),
        "closed_at": normalize_space(row.get("closed_date")) or None,
        "closed_date": parse_source_date(row.get("closed_date")),
        "agency": normalize_space(row.get("agency")) or None,
        "agency_name": normalize_space(row.get("agency_name")) or None,
        "complaint_type": normalize_space(row.get("complaint_type")) or None,
        "descriptor": normalize_space(row.get("descriptor")) or None,
        "descriptor_2": normalize_space(row.get("descriptor_2")) or None,
        "category": classification.category,
        "asset_scope": classification.asset_scope,
        "classification_reason": classification.reason,
        "classification_terms": list(classification.matched_terms),
        "evidence_type": "REPORTED_SERVICE_REQUEST",
        "condition_confirmation": "UNVERIFIED_REPORTED_CONDITION",
        "bbl": bbl,
        "property_link_confidence": "CONFIRMED_LOCATION_IDENTIFIER" if bbl else "UNLINKED",
        "location_type": normalize_space(row.get("location_type")) or None,
        "incident_zip": normalize_space(row.get("incident_zip")) or None,
        "incident_address": normalize_space(row.get("incident_address")) or None,
        "street_name": normalize_space(row.get("street_name")) or None,
        "address_type": normalize_space(row.get("address_type")) or None,
        "city": normalize_space(row.get("city")) or None,
        "borough": normalize_space(row.get("borough")) or None,
        "status": normalize_space(row.get("status")) or None,
        "resolution_description": normalize_space(row.get("resolution_description")) or None,
        "resolution_action_updated_at": normalize_space(row.get("resolution_action_updated_date")) or None,
        "community_board": normalize_space(row.get("community_board")) or None,
        "latitude": normalize_space(row.get("latitude")) or None,
        "longitude": normalize_space(row.get("longitude")) or None,
        "raw_selected": {field: row.get(field) for field in DESIRED_FIELDS if row.get(field) not in (None, "")},
    }
