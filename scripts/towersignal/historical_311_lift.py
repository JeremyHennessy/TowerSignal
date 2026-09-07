from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping, Sequence

from .domestic_water_market import NYC_API_ROOT, fetch_metadata, fetch_snapshot, normalize_space
from .nyc_water_signals import normalize_311

HISTORICAL_2010_2019_DATASET = "76ig-c548"
CURRENT_2020_PRESENT_DATASET = "erm2-nwe9"
PERIODS = (
    ("HISTORICAL_2010_2019", HISTORICAL_2010_2019_DATASET, "2010-01-01T00:00:00.000", "2020-01-01T00:00:00.000"),
    ("HISTORICAL_2020_2024", CURRENT_2020_PRESENT_DATASET, "2020-01-01T00:00:00.000", "2025-01-01T00:00:00.000"),
    ("CURRENT_2025_PLUS", CURRENT_2020_PRESENT_DATASET, "2025-01-01T00:00:00.000", None),
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
    "incident_zip",
    "incident_address",
    "street_name",
    "status",
    "resolution_description",
    "bbl",
    "borough",
)


def _chunks(values: Sequence[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield list(values[start : start + size])


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def period_where(bbls: Sequence[str], start: str, end: str | None) -> str:
    if not bbls:
        raise ValueError("At least one BBL is required")
    bbl_clause = ",".join(_quote(value) for value in bbls)
    parts = ["agency='DEP'", f"bbl in ({bbl_clause})", f"created_date >= '{start}'"]
    if end:
        parts.append(f"created_date < '{end}'")
    parts.append(WATER_CLAUSE)
    return " AND ".join(parts)


def fetch_period_rows(
    *,
    dataset_id: str,
    period_name: str,
    bbls: Sequence[str],
    start: str,
    end: str | None,
    batch_size: int = 60,
    page_size: int = 5000,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    metadata = fetch_metadata(dataset_id, api_root=NYC_API_ROOT)
    fields = set(metadata["fields"])
    missing = [field for field in REQUIRED_FIELDS if field not in fields]
    if missing:
        raise RuntimeError(f"NYC 311 dataset {dataset_id} missing required fields: {', '.join(missing)}")
    selected = [field for field in DESIRED_FIELDS if field in fields]
    requested_bbls = set(bbls)
    rows_by_key: dict[str, dict[str, Any]] = {}
    source_rows = 0
    partitions = 0
    for bbl_batch in _chunks(sorted(requested_bbls), batch_size):
        partitions += 1
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
            progress_label=f"311 lift {period_name} BBL batch {partitions}",
            seek_field="unique_key",
        )
        source_rows += len(snapshot.rows)
        for raw in snapshot.rows:
            normalized = normalize_311(raw)
            request_id = str(normalized.get("request_id") or normalize_space(raw.get("unique_key")))
            if request_id in rows_by_key:
                continue
            if normalized.get("bbl") not in requested_bbls:
                raise RuntimeError(f"NYC 311 exact-BBL query returned unexpected BBL {normalized.get('bbl')!r}")
            rows_by_key[request_id] = normalized
    rows = sorted(rows_by_key.values(), key=lambda row: (str(row.get("created_date") or ""), str(row.get("request_id") or "")))
    return rows, {
        "period": period_name,
        "dataset_id": dataset_id,
        "source_last_updated_at": metadata.get("source_last_updated_at"),
        "requested_bbl_count": len(requested_bbls),
        "partition_count": partitions,
        "source_row_count": source_rows,
        "deduped_row_count": len(rows),
        "exact_bbl_only": True,
    }


def _profile(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not row.get("is_building_water_signal"):
            continue
        bbl = str(row.get("bbl") or "")
        if not bbl:
            continue
        profile = profiles.setdefault(
            bbl,
            {"request_count": 0, "category_counts": Counter(), "years": set(), "latest_date": None},
        )
        profile["request_count"] += 1
        profile["category_counts"][str(row.get("category") or "UNKNOWN")] += 1
        created = str(row.get("created_date") or "")
        if len(created) >= 4:
            profile["years"].add(created[:4])
        if created and (profile["latest_date"] is None or created > profile["latest_date"]):
            profile["latest_date"] = created
    for profile in profiles.values():
        profile["category_counts"] = dict(sorted(profile["category_counts"].items()))
        profile["years"] = sorted(profile["years"])
    return profiles


def summarize_lift(
    *,
    tower_bbls: Sequence[str],
    borough_by_bbl: Mapping[str, str],
    historical_rows: Sequence[Mapping[str, Any]],
    recent_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    historical = _profile(historical_rows)
    recent = _profile(recent_rows)
    tower_set = set(tower_bbls)
    historical_set = set(historical) & tower_set
    recent_set = set(recent) & tower_set
    historical_only = historical_set - recent_set
    recurring_historical_only = {
        bbl for bbl in historical_only
        if historical[bbl]["request_count"] >= 3 and len(historical[bbl]["years"]) >= 2
    }
    recentish_historical_only = {
        bbl for bbl in historical_only
        if str(historical[bbl].get("latest_date") or "") >= "2024-01-01"
    }
    category_counts: Counter[str] = Counter()
    borough_counts: Counter[str] = Counter()
    for bbl in historical_only:
        category_counts.update(historical[bbl]["category_counts"])
        borough_counts[str(borough_by_bbl.get(bbl) or "UNKNOWN")] += 1

    denominator = len(tower_set)
    ranked = sorted(
        historical_only,
        key=lambda bbl: (str(historical[bbl].get("latest_date") or ""), int(historical[bbl].get("request_count") or 0)),
        reverse=True,
    )
    examples = [
        {
            "bbl": bbl,
            "borough": borough_by_bbl.get(bbl),
            "historical_request_count": historical[bbl]["request_count"],
            "historical_years": historical[bbl]["years"],
            "latest_historical_date": historical[bbl]["latest_date"],
            "category_counts": historical[bbl]["category_counts"],
            "recent_2025_plus_building_signal_count": 0,
        }
        for bbl in ranked[:30]
    ]

    return {
        "tower_bbl_count": denominator,
        "tower_bbls_with_historical_building_water_signal": len(historical_set),
        "tower_bbls_with_2025_plus_building_water_signal": len(recent_set),
        "historical_only_tower_bbl_count": len(historical_only),
        "historical_only_share_of_tower_bbls": round(len(historical_only) / denominator, 6) if denominator else 0.0,
        "recurring_historical_only_tower_bbl_count": len(recurring_historical_only),
        "historical_only_with_2024_activity_count": len(recentish_historical_only),
        "historical_only_category_counts": dict(sorted(category_counts.items())),
        "historical_only_by_borough": dict(sorted(borough_counts.items())),
        "historical_only_examples": examples,
        "decision_semantics": {
            "who": "Historical-only exact-BBL building-water requests may add account context, but do not establish a current condition or current sales trigger.",
            "when": "Pre-2025 history alone is not treated as a current timing signal. 2024-only and recurrent history are measured separately for review.",
            "why": "Repeated source-reported building-water requests can explain long-run property context while remaining unverified reported conditions.",
        },
        "governance": {
            "priority_score_1_0_changed": False,
            "ui_changed": False,
            "durable_history_changed": False,
            "fuzzy_matching_used": False,
            "provider_or_incumbent_inference": False,
            "historical_311_authorized_for_production": False,
        },
    }
