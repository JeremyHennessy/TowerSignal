from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable, Mapping

from .fetch import _request_json
from .procurement import classify_procurement, normalize_notice, normalize_space, procurement_source_health, utc_now

DATASET_ID = "dg92-zbpx"
DATASET_NAME = "NYC City Record Online"
DATASET_PAGE = f"https://data.cityofnewyork.us/d/{DATASET_ID}"
RESOURCE_URL = f"https://data.cityofnewyork.us/resource/{DATASET_ID}.json"
METADATA_URL = f"https://data.cityofnewyork.us/api/views/{DATASET_ID}"
PAGE_SIZE = 5000
DEFAULT_AWARD_LOOKBACK_DAYS = 730

REQUIRED_FIELDS = {
    "request_id",
    "start_date",
    "end_date",
    "agency_name",
    "type_of_notice_description",
    "category_description",
    "short_title",
    "selection_method_description",
    "section_name",
    "special_case_reason_description",
    "pin",
    "due_date",
    "address_to_request",
    "contact_name",
    "contact_phone",
    "email",
    "contract_amount",
    "additional_description_1",
    "other_info_1",
    "vendor_name",
    "vendor_address",
    "printout_1",
    "document_links",
}

TEXT_FIELDS = (
    "short_title",
    "category_description",
    "additional_description_1",
    "additional_desctription_2",
    "additional_description_2",
    "additional_description_3",
    "other_info_1",
    "other_info_2",
    "other_info_3",
    "printout_1",
    "printout_2",
    "printout_3",
)

RequestJson = Callable[..., Any]


@dataclass(frozen=True)
class ScopeResult:
    name: str
    where: str
    expected_count: int
    rows: tuple[dict[str, Any], ...]
    pagination_complete: bool


def _floating_timestamp(day: date) -> str:
    return f"{day.isoformat()}T00:00:00.000"


def city_record_scopes(as_of: date, award_lookback_days: int = DEFAULT_AWARD_LOOKBACK_DAYS) -> tuple[tuple[str, str], ...]:
    if award_lookback_days <= 0:
        raise ValueError("award_lookback_days must be positive")
    open_where = (
        "type_of_notice_description = 'Solicitation' "
        f"AND due_date >= '{_floating_timestamp(as_of)}'"
    )
    award_start = as_of - timedelta(days=award_lookback_days)
    awards_where = (
        "type_of_notice_description = 'Award' "
        f"AND start_date >= '{_floating_timestamp(award_start)}'"
    )
    return (("OPEN_SOLICITATIONS", open_where), ("RECENT_AWARDS", awards_where))


def fetch_city_record_metadata(*, request_json: RequestJson = _request_json) -> dict[str, Any]:
    payload = request_json(METADATA_URL)
    if not isinstance(payload, dict):
        raise RuntimeError("City Record metadata response is not an object")
    columns = payload.get("columns")
    if not isinstance(columns, list):
        raise RuntimeError("City Record metadata response is missing columns")
    fields = {str(column.get("fieldName") or "") for column in columns if isinstance(column, dict)}
    missing = sorted(REQUIRED_FIELDS - fields)
    if missing:
        raise RuntimeError(f"City Record schema missing required API fields: {', '.join(missing)}")
    return {
        "dataset_id": DATASET_ID,
        "name": str(payload.get("name") or DATASET_NAME),
        "source_updated_at": payload.get("rowsUpdatedAt") or payload.get("publicationDate"),
        "metadata_updated_at": payload.get("metadataUpdatedAt"),
        "field_names": sorted(fields),
    }


def _fetch_count(where: str, *, request_json: RequestJson) -> int:
    payload = request_json(RESOURCE_URL, params={"$select": "count(*) AS count", "$where": where})
    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
        raise RuntimeError("City Record count query returned an unexpected shape")
    raw = payload[0].get("count")
    try:
        count = int(raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"City Record count query returned an invalid count: {raw!r}") from exc
    if count < 0:
        raise RuntimeError("City Record count query returned a negative count")
    return count


def fetch_scope(
    name: str,
    where: str,
    *,
    request_json: RequestJson = _request_json,
    page_size: int = PAGE_SIZE,
) -> ScopeResult:
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    expected = _fetch_count(where, request_json=request_json)
    rows: list[dict[str, Any]] = []
    offset = 0
    while offset < expected:
        page = request_json(
            RESOURCE_URL,
            params={
                "$where": where,
                "$order": "request_id ASC",
                "$limit": min(page_size, expected - offset),
                "$offset": offset,
            },
        )
        if not isinstance(page, list):
            raise RuntimeError(f"City Record {name} page at offset {offset} is not a list")
        if not page and offset < expected:
            raise RuntimeError(f"City Record {name} pagination ended early at {offset} of {expected}")
        for row in page:
            if not isinstance(row, dict):
                raise RuntimeError(f"City Record {name} returned a non-object row")
            rows.append(dict(row))
        offset += len(page)
        if len(page) == 0:
            break

    if len(rows) != expected:
        raise RuntimeError(f"City Record {name} pagination incomplete: expected {expected}, retrieved {len(rows)}")

    ids = [normalize_space(str(row.get("request_id") or "")) for row in rows]
    if any(not request_id for request_id in ids):
        raise RuntimeError(f"City Record {name} contains a row without request_id")
    if len(ids) != len(set(ids)):
        raise RuntimeError(f"City Record {name} contains duplicate request_id rows")

    return ScopeResult(name=name, where=where, expected_count=expected, rows=tuple(rows), pagination_complete=True)


def source_text(row: Mapping[str, Any]) -> str:
    return normalize_space(" ".join(str(row.get(field) or "") for field in TEXT_FIELDS))


def source_document_url(value: Any) -> str | None:
    if isinstance(value, Mapping):
        return normalize_space(str(value.get("url") or value.get("href") or "")) or None
    return normalize_space(str(value or "")) or None


def normalize_city_record_row(row: Mapping[str, Any], *, retrieved_at: str, scope: str) -> dict[str, Any]:
    request_id = normalize_space(str(row.get("request_id") or ""))
    if not request_id:
        raise ValueError("City Record row is missing request_id")
    notice_type = normalize_space(str(row.get("type_of_notice_description") or "")) or None
    text = source_text(row)
    notice = normalize_notice(
        source="NYC_CITY_RECORD",
        source_record_id=request_id,
        notice_id=request_id,
        title=normalize_space(str(row.get("short_title") or "")) or None,
        procurement_text=text or None,
        retrieved_at=retrieved_at,
        raw=row,
        agency=normalize_space(str(row.get("agency_name") or "")) or None,
        notice_type=notice_type,
        procurement_category=normalize_space(str(row.get("category_description") or "")) or None,
        selection_method=normalize_space(str(row.get("selection_method_description") or "")) or None,
        pin=normalize_space(str(row.get("pin") or "")) or None,
        due_date=row.get("due_date"),
        notice_start_date=row.get("start_date"),
        notice_end_date=row.get("end_date"),
        contact_name=normalize_space(str(row.get("contact_name") or "")) or None,
        contact_phone=normalize_space(str(row.get("contact_phone") or "")) or None,
        amount=row.get("contract_amount"),
        status="OPEN" if scope == "OPEN_SOLICITATIONS" else "AWARDED" if scope == "RECENT_AWARDS" else None,
        source_url=source_document_url(row.get("document_links")) or DATASET_PAGE,
    )
    notice.update(
        {
            "scope": scope,
            "vendor_raw": normalize_space(str(row.get("vendor_name") or "")) or None,
            "vendor_address": normalize_space(str(row.get("vendor_address") or "")) or None,
            "contact_email": normalize_space(str(row.get("email") or "")) or None,
            "address_to_request": normalize_space(str(row.get("address_to_request") or "")) or None,
            "section_name": normalize_space(str(row.get("section_name") or "")) or None,
            "special_case_reason": normalize_space(str(row.get("special_case_reason_description") or "")) or None,
            "amount_evidence": "SOURCE_REPORTED_UNVALIDATED" if row.get("contract_amount") not in (None, "") else None,
            "company_id": None,
            "company_match_confidence": "UNRESOLVED" if normalize_space(str(row.get("vendor_name") or "")) else None,
        }
    )
    return notice


def build_city_record_payload(
    *,
    as_of: date,
    award_lookback_days: int = DEFAULT_AWARD_LOOKBACK_DAYS,
    request_json: RequestJson = _request_json,
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    retrieved_at = retrieved_at or utc_now()
    metadata = fetch_city_record_metadata(request_json=request_json)
    metadata["total_dataset_count"] = _fetch_count("1=1", request_json=request_json)
    scope_results = [
        fetch_scope(name, where, request_json=request_json)
        for name, where in city_record_scopes(as_of, award_lookback_days)
    ]

    normalized: list[dict[str, Any]] = []
    classification_counts: dict[str, int] = {}
    scoped_record_count = 0
    for scope in scope_results:
        scoped_record_count += len(scope.rows)
        for row in scope.rows:
            classified = classify_procurement(row.get("short_title"), source_text(row), row.get("category_description"))
            if classified.service_category == "UNRELATED":
                continue
            item = normalize_city_record_row(row, retrieved_at=retrieved_at, scope=scope.name)
            normalized.append(item)
            classification_counts[item["service_category"]] = classification_counts.get(item["service_category"], 0) + 1

    normalized.sort(key=lambda item: (item.get("due_date") or item.get("notice_start_date") or "", item["procurement_id"]), reverse=True)
    relevant_awards = [item for item in normalized if item.get("scope") == "RECENT_AWARDS"]
    unresolved_vendor_count = sum(1 for item in relevant_awards if item.get("vendor_raw"))
    health = procurement_source_health(
        source="NYC_CITY_RECORD",
        last_success=retrieved_at,
        last_attempt=retrieved_at,
        record_count=scoped_record_count,
        relevant_record_count=len(normalized),
        normalized_contract_count=0,
        normalized_notice_count=len(normalized),
        resolved_company_count=0,
        unresolved_vendor_count=unresolved_vendor_count,
        facility_link_count=0,
        exact_tower_link_count=0,
        pagination_complete=all(scope.pagination_complete for scope in scope_results),
        schema_valid=True,
        freshness="CURRENT",
    )

    metadata.update(
        {
            "dataset_page": DATASET_PAGE,
            "retrieved_at": retrieved_at,
            "as_of_date": as_of.isoformat(),
            "award_lookback_days": award_lookback_days,
            "scopes": [
                {
                    "name": scope.name,
                    "where": scope.where,
                    "record_count": len(scope.rows),
                    "pagination_complete": scope.pagination_complete,
                }
                for scope in scope_results
            ],
        }
    )

    return {
        "schema_version": "1.0",
        "generated_at": retrieved_at,
        "source": metadata,
        "summary": {
            "scoped_record_count": scoped_record_count,
            "relevant_record_count": len(normalized),
            "open_relevant_opportunities": sum(1 for item in normalized if item.get("scope") == "OPEN_SOLICITATIONS"),
            "recent_relevant_awards": len(relevant_awards),
            "unresolved_vendor_count": unresolved_vendor_count,
            "classification_counts": dict(sorted(classification_counts.items())),
        },
        "source_health": health,
        "notices": normalized,
    }
