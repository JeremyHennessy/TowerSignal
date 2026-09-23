from __future__ import annotations

import csv
import io
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from typing import Any, Callable, Iterable

from .fetch import SourceFetchError, fetch_count, fetch_metadata, fetch_where
from .planimetrics import normalize_bin
from .pluto import normalize_bbl

HPD_VIOLATIONS_DATASET_ID = "wvxf-dwi5"
HPD_VIOLATIONS_URL = "https://data.cityofnewyork.us/Housing-Development/Housing-Maintenance-Code-Violations/wvxf-dwi5"
DOB_COMPLAINTS_DATASET_ID = "eabe-havv"
DOB_COMPLAINTS_URL = "https://data.cityofnewyork.us/Housing-Development/DOB-Complaints-Received/eabe-havv"
FACADE_FILINGS_DATASET_ID = "xubg-57si"
FACADE_FILINGS_URL = "https://data.cityofnewyork.us/Housing-Development/DOB-NOW-Safety-Facades-Compliance-Filings/xubg-57si"
DOB_DISPOSITION_CODES_URL = "https://www.nyc.gov/assets/buildings/pdf/bis_complaint_disposition_codes.pdf"
DOB_BUILDING_PROFILES_METHOD_URL = "https://www.nyc.gov/assets/buildings/html/README.html"

DOB_SWO_SNAPSHOT_COMMIT = "29b7ca2d595593795c69055bfa6a39525c4c4cdd"
DOB_SWO_SNAPSHOT_COMMIT_AT = "2024-02-05T16:14:24Z"
DOB_SWO_SNAPSHOT_DATASET_ID = "NYCDOB_SWOS_ISSUED_RESCINDED_SNAPSHOT_20240205"
DOB_SWO_SNAPSHOT_URL = f"https://raw.githubusercontent.com/NYCDOB/SWOs_Issued_Rescinded/{DOB_SWO_SNAPSHOT_COMMIT}/data/SWOs_Issued_Rescinded_v2.csv"
DOB_SWO_SNAPSHOT_PAGE = f"https://github.com/NYCDOB/SWOs_Issued_Rescinded/blob/{DOB_SWO_SNAPSHOT_COMMIT}/data/SWOs_Issued_Rescinded_v2.csv"
DOB_SWO_MAP_URL = "https://www.nyc.gov/assets/buildings/html/swo-map.html"
DOB_SWO_SNAPSHOT_REQUIRED_FIELDS = {
    "Borough Name", "Complaint Number", "BIN", "Disposition Code Description",
    "Disposition Category", "Last Disposition Date", "Last Disposition Year",
    "Latitude", "Longitude", "Address", "Community Board",
}

FILTERED_PAGE_SIZE = 50000
HPD_CHUNK_SIZE = 12
BIN_CHUNK_SIZE = 100

HPD_SELECT = ",".join((
    "violationid", "buildingid", "registrationid", "boro", "block", "lot", "class",
    "inspectiondate", "approveddate", "novdescription", "novissueddate", "currentstatusid",
    "currentstatus", "currentstatusdate", "violationstatus", "rentimpairing", "bin", "bbl",
))
DOB_COMPLAINT_SELECT = ",".join((
    "complaint_number", "status", "date_entered", "house_number", "house_street", "zip_code",
    "bin", "complaint_category", "unit", "disposition_date", "disposition_code", "inspection_date", "dobrundate",
))
FACADE_SELECT = ",".join((
    "tr6_no", "control_no", "filing_type", "cycle", "bin", "house_no", "street_name", "borough",
    "block", "lot", "sequence_no", "submitted_on", "current_status", "qewi_name", "qewi_bus_name",
))

# Official DOB BIS Complaint Disposition Codes. The Building Profiles methodology identifies
# A3/K4/L1/V3 as Stop Work Order dispositions; the code dictionary additionally identifies
# K6/U4/U5 as SWO issuance and L2/L3 as rescission events.
SWO_DISPOSITION_CODES: dict[str, tuple[str, str]] = {
    "A3": ("ISSUED_FULL", "Full Stop Work Order Served"),
    "K4": ("ISSUED", "Cranes and Derricks – Stop Work Order (SWO) – No Associated Address"),
    "K6": ("ISSUED_PARTIAL", "Letter of Deficiency Issued with Partial SWO"),
    "L1": ("ISSUED_PARTIAL", "Partial Stop Work Order"),
    "L2": ("RESCINDED_FULL", "Stop Work Order Fully Rescinded"),
    "L3": ("RESCINDED_PARTIAL", "Stop Work Order Partially Rescinded"),
    "U4": ("ISSUED_FULL", "CSC: Full Stop Work Order Issued – On Action Complaint"),
    "U5": ("ISSUED_PARTIAL", "CSC: Partial SWO Issued – On Action Complaint"),
    "V3": ("VIOLATION_OF_ORDER", "Stop Work Order Violation Served (Non-Compliant After-Hours Work)"),
}
SWO_CODE_LIST = tuple(SWO_DISPOSITION_CODES)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _date(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        try:
            return date.fromisoformat(text[:10]).isoformat()
        except ValueError:
            pass
    if len(text) >= 8 and text[:8].isdigit():
        try:
            return datetime.strptime(text[:8], "%Y%m%d").date().isoformat()
        except ValueError:
            pass
    for pattern in ("%m/%d/%Y", "%m/%d/%Y %H:%M:%S"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _quoted(values: Iterable[str]) -> str:
    cleaned = []
    for value in values:
        if not value.isdigit():
            raise ValueError(f"Expected numeric identifier, got {value!r}")
        cleaned.append(f"'{value}'")
    return ",".join(cleaned)


def _paged_where(dataset_id: str, *, where: str, order_by: str, select: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = fetch_where(
            dataset_id,
            where=where,
            order_by=order_by,
            select=select,
            limit=FILTERED_PAGE_SIZE,
            offset=offset,
            request_timeout=120,
        )
        rows.extend(page)
        if len(page) < FILTERED_PAGE_SIZE:
            return rows
        offset += FILTERED_PAGE_SIZE
        if offset > 2_000_000:
            raise SourceFetchError(
                f"Filtered query for {dataset_id} exceeded 2,000,000 rows; refusing an unbounded property evidence result"
            )


def _source_record_count_telemetry(dataset_id: str) -> dict[str, Any]:
    """Whole-dataset counts are telemetry only and must not invalidate exact filtered evidence."""
    try:
        return {
            "source_record_count": fetch_count(dataset_id),
            "source_record_count_status": "AVAILABLE",
            "source_record_count_error": None,
        }
    except SourceFetchError as exc:
        return {
            "source_record_count": None,
            "source_record_count_status": "UNAVAILABLE_TELEMETRY",
            "source_record_count_error": str(exc),
        }


def normalize_hpd_violation(row: dict[str, Any]) -> dict[str, Any]:
    bbl = normalize_bbl(row.get("bbl"))
    if not bbl:
        raise SourceFetchError("HPD violation row lacks a valid canonical BBL")
    violation_id = _text(row.get("violationid"))
    if not violation_id:
        raise SourceFetchError(f"HPD violation row on BBL {bbl} lacks ViolationID")
    violation_status = (_text(row.get("violationstatus")) or "").upper() or None
    return {
        "violation_id": violation_id,
        "building_id": _text(row.get("buildingid")),
        "registration_id": _text(row.get("registrationid")),
        "bbl": bbl,
        "bin": normalize_bin(row.get("bin")),
        "borough": _text(row.get("boro")),
        "block": _text(row.get("block")),
        "lot": _text(row.get("lot")),
        "class": _text(row.get("class")),
        "inspection_date": _date(row.get("inspectiondate")),
        "approved_date": _date(row.get("approveddate")),
        "nov_issued_date": _date(row.get("novissueddate")),
        "description": _text(row.get("novdescription")),
        "current_status_id": _text(row.get("currentstatusid")),
        "current_status": _text(row.get("currentstatus")),
        "current_status_date": _date(row.get("currentstatusdate")),
        "violation_status": violation_status,
        "is_open": violation_status == "OPEN",
        "rent_impairing": (_text(row.get("rentimpairing")) or "").upper() == "Y",
        "source": "NYC_HPD_HOUSING_MAINTENANCE_CODE_VIOLATIONS",
        "match_basis": "BBL_EXACT",
    }


def fetch_hpd_violations_by_bbl(bbl_values: Iterable[Any], *, chunk_size: int = HPD_CHUNK_SIZE) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    requested = sorted({bbl for value in bbl_values if (bbl := normalize_bbl(value))}, key=int)
    requested_set = set(requested)
    by_bbl: dict[str, dict[str, dict[str, Any]]] = {}
    for start in range(0, len(requested), chunk_size):
        chunk = requested[start:start + chunk_size]
        if not chunk:
            continue
        rows = _paged_where(
            HPD_VIOLATIONS_DATASET_ID,
            where=f"bbl in ({_quoted(chunk)})",
            order_by="bbl,violationid",
            select=HPD_SELECT,
        )
        for row in rows:
            normalized = normalize_hpd_violation(row)
            bbl = normalized["bbl"]
            if bbl not in requested_set:
                raise SourceFetchError(f"HPD filtered query returned BBL {bbl} outside requested universe")
            by_bbl.setdefault(bbl, {})[normalized["violation_id"]] = normalized

    result: dict[str, list[dict[str, Any]]] = {}
    for bbl, keyed in by_bbl.items():
        result[bbl] = sorted(
            keyed.values(),
            key=lambda item: (item.get("inspection_date") or "", item["violation_id"]),
            reverse=True,
        )
    metadata = fetch_metadata(HPD_VIOLATIONS_DATASET_ID)
    records = [record for values in result.values() for record in values]
    count_telemetry = _source_record_count_telemetry(HPD_VIOLATIONS_DATASET_ID)
    return result, {
        "dataset_id": HPD_VIOLATIONS_DATASET_ID,
        "name": metadata.get("name") or "Housing Maintenance Code Violations",
        "url": HPD_VIOLATIONS_URL,
        "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_last_updated_at": metadata.get("source_last_updated_at"),
        **count_telemetry,
        "requested_bbl_count": len(requested),
        "matched_bbl_count": len(result),
        "matched_violation_count": len(records),
        "open_violation_count": sum(1 for record in records if record["is_open"]),
        "class_c_open_count": sum(1 for record in records if record["is_open"] and record.get("class") == "C"),
        "source_query_scope": "Exact canonical BBL subset of TowerSignal NYC cooling-tower properties; complete filtered pagination",
    }


def normalize_official_swo_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    bin_value = normalize_bin(row.get("BIN"))
    if not bin_value:
        raise SourceFetchError("Official DOB SWO snapshot row lacks a valid BIN")
    complaint_number = _text(row.get("Complaint Number"))
    if not complaint_number:
        raise SourceFetchError(f"Official DOB SWO snapshot row on BIN {bin_value} lacks complaint number")
    category = (_text(row.get("Disposition Category")) or "").upper()
    if category not in {"ACTIVE", "RESCINDED"}:
        raise SourceFetchError(f"Unexpected official DOB SWO snapshot category {category!r} for BIN {bin_value}")
    return {
        "complaint_number": complaint_number,
        "bin": bin_value,
        "borough": _text(row.get("Borough Name")),
        "address": _text(row.get("Address")),
        "community_board": _text(row.get("Community Board")),
        "disposition_description": _text(row.get("Disposition Code Description")),
        "status_at_snapshot": category,
        "last_disposition_date": _date(row.get("Last Disposition Date")),
        "last_disposition_year": _text(row.get("Last Disposition Year")),
        "latitude": _text(row.get("Latitude")),
        "longitude": _text(row.get("Longitude")),
        "source": "NYC_DOB_STOP_WORK_ORDERS_DATED_SNAPSHOT",
        "source_snapshot_commit": DOB_SWO_SNAPSHOT_COMMIT,
        "source_snapshot_committed_at": DOB_SWO_SNAPSHOT_COMMIT_AT,
        "match_basis": "BIN_EXACT",
        "current_status_claim": False,
    }


def _download_official_swo_snapshot(*, attempts: int = 4, timeout: int = 120) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(
                DOB_SWO_SNAPSHOT_URL,
                headers={"User-Agent": "TowerSignal-official-source/1.0"},
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(min(2 ** attempt, 8))
    raise SourceFetchError(f"Unable to retrieve pinned official DOB SWO snapshot: {last_error}")


def fetch_official_swo_snapshot_by_bin(
    bin_values: Iterable[Any],
    *,
    request_bytes: Callable[[], bytes] | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    requested = sorted({value for item in bin_values if (value := normalize_bin(item))}, key=int)
    requested_set = set(requested)
    raw = request_bytes() if request_bytes else _download_official_swo_snapshot()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    fields = set(reader.fieldnames or [])
    missing = sorted(DOB_SWO_SNAPSHOT_REQUIRED_FIELDS - fields)
    if missing:
        raise SourceFetchError(f"Official DOB SWO snapshot schema missing fields: {', '.join(missing)}")
    source_rows = list(reader)
    by_bin: dict[str, dict[str, dict[str, Any]]] = {}
    normalized_source: list[dict[str, Any]] = []
    for row in source_rows:
        normalized = normalize_official_swo_snapshot(row)
        normalized_source.append(normalized)
        bin_value = normalized["bin"]
        if bin_value not in requested_set:
            continue
        identity = f"{normalized['complaint_number']}:{normalized['status_at_snapshot']}:{normalized.get('last_disposition_date') or ''}"
        by_bin.setdefault(bin_value, {})[identity] = normalized

    result: dict[str, list[dict[str, Any]]] = {}
    for bin_value, keyed in by_bin.items():
        result[bin_value] = sorted(
            keyed.values(),
            key=lambda item: (item.get("last_disposition_date") or "", item["complaint_number"]),
            reverse=True,
        )
    source_dates = [row["last_disposition_date"] for row in normalized_source if row.get("last_disposition_date")]
    matched_records = [record for values in result.values() for record in values]
    return result, {
        "dataset_id": DOB_SWO_SNAPSHOT_DATASET_ID,
        "name": "NYC DOB Stop Work Orders — dated official snapshot",
        "url": DOB_SWO_SNAPSHOT_PAGE,
        "official_map_url": DOB_SWO_MAP_URL,
        "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_last_updated_at": DOB_SWO_SNAPSHOT_COMMIT_AT,
        "source_snapshot_commit": DOB_SWO_SNAPSHOT_COMMIT,
        "source_record_count": len(source_rows),
        "source_observation_start_at": min(source_dates) if source_dates else None,
        "source_observation_end_at": max(source_dates) if source_dates else None,
        "requested_bin_count": len(requested),
        "matched_bin_count": len(result),
        "matched_record_count": len(matched_records),
        "active_at_snapshot_count": sum(1 for record in matched_records if record["status_at_snapshot"] == "ACTIVE"),
        "rescinded_at_snapshot_count": sum(1 for record in matched_records if record["status_at_snapshot"] == "RESCINDED"),
        "source_health_status": "WARNING",
        "source_health_reasons": [
            "Pinned official DOB source snapshot was committed 2024-02-05 and ends at 2024-02-03; it is not a current 2026 SWO status ledger.",
            "Live NYC.gov SWO map/CSV and BIS current-status endpoints return HTTP 403 from GitHub Actions, so freshness cannot be independently proven in release automation.",
        ],
        "source_query_scope": "Complete pinned NYCDOB SWO snapshot (published two-year window), filtered to TowerSignal BINs only after retrieval; exact BIN match; ACTIVE/RESCINDED means status at the dated snapshot, not current status.",
        "current_status_available": False,
    }


def normalize_stop_work_order(row: dict[str, Any]) -> dict[str, Any]:
    bin_value = normalize_bin(row.get("bin"))
    if not bin_value:
        raise SourceFetchError("DOB SWO complaint row lacks a valid BIN")
    code = (_text(row.get("disposition_code")) or "").upper()
    if code not in SWO_DISPOSITION_CODES:
        raise SourceFetchError(f"Unexpected SWO disposition code {code!r} for BIN {bin_value}")
    event_type, disposition_text = SWO_DISPOSITION_CODES[code]
    complaint_number = _text(row.get("complaint_number"))
    if not complaint_number:
        raise SourceFetchError(f"DOB SWO row on BIN {bin_value} lacks complaint number")
    return {
        "complaint_number": complaint_number,
        "bin": bin_value,
        "complaint_status": _text(row.get("status")),
        "date_entered": _date(row.get("date_entered")),
        "inspection_date": _date(row.get("inspection_date")),
        "disposition_date": _date(row.get("disposition_date")),
        "disposition_code": code,
        "disposition_text": disposition_text,
        "event_type": event_type,
        "complaint_category": _text(row.get("complaint_category")),
        "unit": _text(row.get("unit")),
        "address": " ".join(part for part in (_text(row.get("house_number")), _text(row.get("house_street"))) if part) or None,
        "zip": _text(row.get("zip_code")),
        "source_refresh_date": _date(row.get("dobrundate")),
        "source": "NYC_DOB_COMPLAINTS_STOP_WORK_ORDER_DISPOSITIONS",
        "match_basis": "BIN_EXACT",
    }


def fetch_stop_work_orders_by_bin(bin_values: Iterable[Any], *, chunk_size: int = BIN_CHUNK_SIZE) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    requested = sorted({value for item in bin_values if (value := normalize_bin(item))}, key=int)
    requested_set = set(requested)
    codes = ",".join(f"'{code}'" for code in SWO_CODE_LIST)
    by_bin: dict[str, dict[str, dict[str, Any]]] = {}
    for start in range(0, len(requested), chunk_size):
        chunk = requested[start:start + chunk_size]
        if not chunk:
            continue
        rows = _paged_where(
            DOB_COMPLAINTS_DATASET_ID,
            where=f"bin in ({_quoted(chunk)}) AND disposition_code in ({codes})",
            order_by="bin,complaint_number",
            select=DOB_COMPLAINT_SELECT,
        )
        for row in rows:
            normalized = normalize_stop_work_order(row)
            bin_value = normalized["bin"]
            if bin_value not in requested_set:
                raise SourceFetchError(f"DOB SWO query returned BIN {bin_value} outside requested universe")
            identity = f"{normalized['complaint_number']}:{normalized['disposition_code']}:{normalized.get('disposition_date') or ''}"
            by_bin.setdefault(bin_value, {})[identity] = normalized

    result: dict[str, list[dict[str, Any]]] = {}
    for bin_value, keyed in by_bin.items():
        result[bin_value] = sorted(
            keyed.values(),
            key=lambda item: (item.get("disposition_date") or item.get("inspection_date") or item.get("date_entered") or "", item["complaint_number"]),
            reverse=True,
        )
    metadata = fetch_metadata(DOB_COMPLAINTS_DATASET_ID)
    records = [record for values in result.values() for record in values]
    return result, {
        "dataset_id": DOB_COMPLAINTS_DATASET_ID,
        "name": metadata.get("name") or "DOB Complaints Received",
        "url": DOB_COMPLAINTS_URL,
        "disposition_code_dictionary_url": DOB_DISPOSITION_CODES_URL,
        "methodology_url": DOB_BUILDING_PROFILES_METHOD_URL,
        "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_last_updated_at": metadata.get("source_last_updated_at"),
        "source_record_count": fetch_count(DOB_COMPLAINTS_DATASET_ID),
        "requested_bin_count": len(requested),
        "matched_bin_count": len(result),
        "matched_event_count": len(records),
        "issue_event_count": sum(1 for record in records if str(record["event_type"]).startswith("ISSUED")),
        "rescission_event_count": sum(1 for record in records if str(record["event_type"]).startswith("RESCINDED")),
        "source_query_scope": "Exact BIN subset of TowerSignal NYC cooling-tower buildings, restricted to official DOB SWO-related disposition codes",
        "swo_disposition_codes": SWO_DISPOSITION_CODES,
    }


def normalize_facade_filing(row: dict[str, Any]) -> dict[str, Any]:
    bin_value = normalize_bin(row.get("bin"))
    if not bin_value:
        raise SourceFetchError("DOB NOW facade filing row lacks a valid BIN")
    control_no = _text(row.get("control_no"))
    if not control_no:
        raise SourceFetchError(f"DOB NOW facade row on BIN {bin_value} lacks CONTROL_NO")
    return {
        "control_no": control_no,
        "tr6_no": _text(row.get("tr6_no")),
        "bin": bin_value,
        "filing_type": _text(row.get("filing_type")),
        "cycle": _text(row.get("cycle")),
        "sequence_no": _text(row.get("sequence_no")),
        "submitted_on": _date(row.get("submitted_on")),
        "current_status": _text(row.get("current_status")),
        "qewi_name": _text(row.get("qewi_name")),
        "qewi_business_name": _text(row.get("qewi_bus_name")),
        "address": " ".join(part for part in (_text(row.get("house_no")), _text(row.get("street_name"))) if part) or None,
        "borough": _text(row.get("borough")),
        "block": _text(row.get("block")),
        "lot": _text(row.get("lot")),
        "source": "NYC_DOB_NOW_SAFETY_FACADES_COMPLIANCE_FILINGS",
        "match_basis": "BIN_EXACT",
    }


def fetch_facade_filings_by_bin(bin_values: Iterable[Any], *, chunk_size: int = BIN_CHUNK_SIZE) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    requested = sorted({value for item in bin_values if (value := normalize_bin(item))}, key=int)
    requested_set = set(requested)
    by_bin: dict[str, dict[str, dict[str, Any]]] = {}
    for start in range(0, len(requested), chunk_size):
        chunk = requested[start:start + chunk_size]
        if not chunk:
            continue
        rows = _paged_where(
            FACADE_FILINGS_DATASET_ID,
            where=f"bin in ({_quoted(chunk)})",
            order_by="bin,submitted_on,control_no",
            select=FACADE_SELECT,
        )
        for row in rows:
            normalized = normalize_facade_filing(row)
            bin_value = normalized["bin"]
            if bin_value not in requested_set:
                raise SourceFetchError(f"Facade query returned BIN {bin_value} outside requested universe")
            identity = f"{normalized['control_no']}:{normalized.get('sequence_no') or ''}:{normalized.get('filing_type') or ''}"
            by_bin.setdefault(bin_value, {})[identity] = normalized

    result: dict[str, list[dict[str, Any]]] = {}
    for bin_value, keyed in by_bin.items():
        result[bin_value] = sorted(
            keyed.values(),
            key=lambda item: (item.get("submitted_on") or "", item["control_no"], item.get("sequence_no") or ""),
            reverse=True,
        )
    metadata = fetch_metadata(FACADE_FILINGS_DATASET_ID)
    records = [record for values in result.values() for record in values]
    status_counts: dict[str, int] = {}
    for record in records:
        status = record.get("current_status") or "UNPUBLISHED"
        status_counts[status] = status_counts.get(status, 0) + 1
    return result, {
        "dataset_id": FACADE_FILINGS_DATASET_ID,
        "name": metadata.get("name") or "DOB NOW: Safety – Facades Compliance Filings",
        "url": FACADE_FILINGS_URL,
        "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_last_updated_at": metadata.get("source_last_updated_at"),
        "source_record_count": fetch_count(FACADE_FILINGS_DATASET_ID),
        "requested_bin_count": len(requested),
        "matched_bin_count": len(result),
        "matched_filing_count": len(records),
        "status_counts": status_counts,
        "source_query_scope": "Exact BIN subset of TowerSignal NYC cooling-tower buildings; all matching DOB NOW facade compliance filings retained",
    }
