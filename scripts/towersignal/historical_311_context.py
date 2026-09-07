from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from .domestic_water_market import NYC_API_ROOT, fetch_metadata, fetch_snapshot, normalize_space
from .nyc_water_signals import normalize_311

HISTORICAL_2010_2019_DATASET = "76ig-c548"
CURRENT_2020_PRESENT_DATASET = "erm2-nwe9"
HISTORICAL_PERIODS = (
    ("2010_2019", HISTORICAL_2010_2019_DATASET, "2010-01-01T00:00:00.000", "2020-01-01T00:00:00.000"),
    ("2020_2024", CURRENT_2020_PRESENT_DATASET, "2020-01-01T00:00:00.000", "2025-01-01T00:00:00.000"),
)
WATER_CLAUSE = (
    "(lower(complaint_type) like '%water%' OR lower(descriptor) like '%water%' OR "
    "lower(descriptor_2) like '%water%' OR lower(complaint_type) like '%lead%' OR "
    "lower(descriptor) like '%lead%' OR lower(descriptor_2) like '%lead%')"
)
REQUIRED_FIELDS = ("unique_key", "created_date", "agency", "complaint_type", "descriptor", "bbl", "borough")
DESIRED_FIELDS = (
    "unique_key",
    "created_date",
    "closed_date",
    "agency",
    "agency_name",
    "complaint_type",
    "descriptor",
    "descriptor_2",
    "bbl",
    "borough",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _chunks(values: Sequence[str], size: int) -> list[list[str]]:
    if size <= 0:
        raise ValueError("batch size must be positive")
    return [list(values[start : start + size]) for start in range(0, len(values), size)]


def period_where(bbls: Sequence[str], start: str, end: str) -> str:
    if not bbls:
        raise ValueError("At least one exact BBL is required")
    return " AND ".join(
        (
            "agency='DEP'",
            f"bbl in ({','.join(_quote(value) for value in bbls)})",
            f"created_date >= '{start}'",
            f"created_date < '{end}'",
            WATER_CLAUSE,
        )
    )


def _empty_profile() -> dict[str, Any]:
    return {
        "request_count": 0,
        "category_counts": Counter(),
        "years": set(),
        "first_reported_date": None,
        "latest_reported_date": None,
    }


def _add_request(profile: dict[str, Any], row: Mapping[str, Any]) -> None:
    profile["request_count"] += 1
    profile["category_counts"][str(row.get("category") or "UNKNOWN")] += 1
    created = normalize_space(row.get("created_date"))
    if len(created) >= 4:
        profile["years"].add(created[:4])
    if created and (profile["first_reported_date"] is None or created < profile["first_reported_date"]):
        profile["first_reported_date"] = created
    if created and (profile["latest_reported_date"] is None or created > profile["latest_reported_date"]):
        profile["latest_reported_date"] = created


def _finalize_profile(bbl: str, profile: dict[str, Any]) -> dict[str, Any]:
    years = sorted(profile["years"])
    request_count = int(profile["request_count"])
    return {
        "bbl": bbl,
        "request_count": request_count,
        "category_counts": dict(sorted(profile["category_counts"].items())),
        "years": years,
        "year_count": len(years),
        "first_reported_date": profile["first_reported_date"],
        "latest_reported_date": profile["latest_reported_date"],
        "recurrent_history": request_count >= 3 and len(years) >= 2,
        "has_2024_activity": "2024" in years,
        "property_link_confidence": "CONFIRMED_SOURCE_BBL",
        "evidence_semantics": "REPORTED_SERVICE_REQUEST",
    }


def build_historical_context(
    bbls: Sequence[str],
    *,
    batch_size: int = 200,
    page_size: int = 5000,
) -> dict[str, Any]:
    requested = sorted(set(str(value) for value in bbls if len(str(value)) == 10 and str(value)[0] in "12345"))
    profiles: dict[str, dict[str, Any]] = {}
    seen_request_ids: set[str] = set()
    source_health: list[dict[str, Any]] = []
    total_source_rows = 0
    total_building_rows = 0

    for period_name, dataset_id, start, end in HISTORICAL_PERIODS:
        metadata = fetch_metadata(dataset_id, api_root=NYC_API_ROOT)
        fields = set(metadata["fields"])
        missing = [field for field in REQUIRED_FIELDS if field not in fields]
        if missing:
            raise RuntimeError(f"NYC 311 dataset {dataset_id} missing required fields: {', '.join(missing)}")
        selected = [field for field in DESIRED_FIELDS if field in fields]
        period_source_rows = 0
        period_building_rows = 0
        partitions = _chunks(requested, batch_size)
        for index, bbl_batch in enumerate(partitions, start=1):
            snapshot = fetch_snapshot(
                dataset_id,
                api_root=NYC_API_ROOT,
                order_by="unique_key",
                required_fields=REQUIRED_FIELDS,
                where=period_where(bbl_batch, start, end),
                select=",".join(selected),
                page_size=page_size,
                minimum_page_size=250,
                allow_count_fallback=False,
                progress_label=f"historical 311 {period_name} exact-BBL batch {index}",
                seek_field="unique_key",
            )
            period_source_rows += len(snapshot.rows)
            batch_set = set(bbl_batch)
            for raw in snapshot.rows:
                normalized = normalize_311(raw)
                bbl = str(normalized.get("bbl") or "")
                if bbl not in batch_set:
                    raise RuntimeError(f"Historical 311 exact-BBL query returned unexpected BBL {bbl!r}")
                request_id = str(normalized.get("request_id") or normalize_space(raw.get("unique_key")))
                if not request_id or request_id in seen_request_ids:
                    continue
                seen_request_ids.add(request_id)
                if normalized.get("is_building_water_signal") is not True:
                    continue
                period_building_rows += 1
                _add_request(profiles.setdefault(bbl, _empty_profile()), normalized)
        total_source_rows += period_source_rows
        total_building_rows += period_building_rows
        source_health.append(
            {
                "period": period_name,
                "dataset_id": dataset_id,
                "source_last_updated_at": metadata.get("source_last_updated_at"),
                "requested_bbl_count": len(requested),
                "partition_count": len(partitions),
                "source_row_count": period_source_rows,
                "building_water_row_count": period_building_rows,
                "exact_bbl_only": True,
            }
        )

    by_bbl = {bbl: _finalize_profile(bbl, profile) for bbl, profile in sorted(profiles.items())}
    recurrent_count = sum(1 for profile in by_bbl.values() if profile["recurrent_history"])
    activity_2024_count = sum(1 for profile in by_bbl.values() if profile["has_2024_activity"])
    return {
        "schema_version": "1.0",
        "domain": "NYC_HISTORICAL_BUILDING_WATER_CONTEXT",
        "generated_at": utc_now(),
        "query_boundaries": {
            "start": "2010-01-01",
            "end_exclusive": "2025-01-01",
            "agency": "DEP",
            "property_match": "EXACT_BBL_ONLY",
            "scope": "Source-reported DEP water/lead service requests classified as building-water signals and aggregated immediately by exact TowerSignal BBL.",
        },
        "summary": {
            "requested_bbl_count": len(requested),
            "matched_bbl_count": len(by_bbl),
            "source_row_count": total_source_rows,
            "building_water_request_count": total_building_rows,
            "recurrent_bbl_count": recurrent_count,
            "bbls_with_2024_activity": activity_2024_count,
        },
        "by_bbl": by_bbl,
        "source_health": source_health,
        "evidence_boundaries": {
            "historical_not_current": "2010-2024 requests are historical reported conditions, not evidence of a current condition or current sales trigger.",
            "property_link": "Only an exact source BBL matching a current TowerSignal property is retained.",
            "raw_rows": "Raw historical 311 events are not published in the production cache or durable history.",
            "provider": "311 history does not identify a service provider or incumbent contractor.",
        },
        "governance": {
            "priority_score_1_0_changed": False,
            "current_trigger_created": False,
            "fuzzy_matching_used": False,
            "provider_or_incumbent_inference": False,
            "raw_historical_events_published": False,
        },
    }
