from __future__ import annotations

import hashlib
import re
import time
from collections import Counter
from typing import Any, Mapping

from .domestic_water import normalize_space, parse_source_date, stable_id, utc_now
from .nys_public_water import (
    LSLI_INDEX_URL,
    NysPublicWaterSourceError,
    _cell_map,
    _first_cell,
    fetch_html,
    find_table,
    parse_html,
    parse_lsli_index,
)

SCHEMA_VERSION = "1.2"
DEFAULT_REQUEST_DELAY_SECONDS = 0.15
MAX_EXPLICIT_UNAVAILABLE_DETAILS = 25

KEY_FIELDS = {
    "water system name": "pws_name",
    "pws id number": "pws_id",
    "contact name": "contact_name",
    "contact phone number": "contact_phone",
    "contact email address": "contact_email",
    "total number of service lines in the distribution system": "total_service_lines",
    "total number of identified service lines": "identified_service_lines",
    "total number of lead service lines": "lead_service_lines",
    "total number of gslrr": "gslrr_service_lines",
    "total number of non lsl": "non_lead_service_lines",
    "total number of unknown service lines": "unknown_service_lines",
}

INVENTORY_FIELDS = (
    "total_service_lines",
    "identified_service_lines",
    "lead_service_lines",
    "gslrr_service_lines",
    "non_lead_service_lines",
    "unknown_service_lines",
)

COMPONENT_REQUIRED_FIELDS = (
    "total_service_lines",
    "lead_service_lines",
    "gslrr_service_lines",
    "non_lead_service_lines",
    "unknown_service_lines",
)

METHOD_LABELS = (
    "Historical Records",
    "Field Inspection",
    "Customer Identification with Photo or other Verification",
    "Excavation",
    "Sequential Sampling",
    "Statistical Analysis/Predictive Model",
)


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", normalize_space(value).lower()).strip()


def _int(value: Any) -> int | None:
    text = normalize_space(value)
    if not text or text.upper() in {"NA", "N/A", "NONE", "-"}:
        return None
    match = re.search(r"-?\d[\d,]*", text)
    return int(match.group(0).replace(",", "")) if match else None


def _kv_rows(parser) -> dict[str, str]:
    values: dict[str, str] = {}
    for table in parser.tables:
        for row in table:
            if len(row) < 2:
                continue
            label = _key(row[0])
            value = normalize_space(row[1])
            if label and value and label not in values:
                values[label] = value
    return values


def _material_matrix(parser) -> dict[str, dict[str, Any]]:
    headers, rows = find_table(
        parser,
        ("Service Lines", "Lead", "GSL or GSLRR", "Non-Lead", "Unknown"),
    )
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        cells = _cell_map(headers, row)
        label = normalize_space(_first_cell(cells, "Service Lines"))
        if not label:
            continue
        result[label] = {
            "lead": _int(_first_cell(cells, "Lead")),
            "gsl_or_gslrr": _int(_first_cell(cells, "GSL or GSLRR")),
            "non_lead": _int(_first_cell(cells, "Non-Lead")),
            "unknown": _int(_first_cell(cells, "Unknown")),
            "raw": dict(cells),
        }
    return result


def _identification_methods(parser) -> list[dict[str, Any]]:
    headers, rows = find_table(
        parser,
        ("Identification Methods", "PWS- Side SLs", "Customer-Side SLs"),
    )
    result: list[dict[str, Any]] = []
    for row in rows:
        cells = _cell_map(headers, row)
        method = normalize_space(_first_cell(cells, "Identification Methods"))
        if not method:
            continue
        result.append({
            "method": method,
            "pws_side_count": _int(_first_cell(cells, "PWS- Side SLs")),
            "customer_side_count": _int(_first_cell(cells, "Customer-Side SLs")),
            "raw": dict(cells),
        })
    return result


def _inventory_availability(parser, kv: Mapping[str, str]) -> dict[str, Any]:
    online_value = None
    under_50k_value = None
    for label, value in kv.items():
        if "50 000 customers or greater" in label:
            online_value = value
        elif "under 50 000 customers" in label:
            under_50k_value = value
    candidate_links = []
    for href, text in parser.links:
        href_text = normalize_space(href)
        display = normalize_space(text)
        if not href_text.lower().startswith(("http://", "https://")):
            continue
        if "health.ny.gov" in href_text.lower() or (
            "ny.gov" in href_text.lower() and "leadfree" not in href_text.lower()
        ):
            continue
        candidate_links.append({"href": href_text, "text": display or None})
    return {
        "online_posting_raw": online_value,
        "under_50000_access_raw": under_50k_value,
        "external_links": candidate_links,
    }


def _certification(parser) -> dict[str, Any]:
    for table in parser.tables:
        normalized_rows = [[_key(cell) for cell in row] for row in table]
        all_cells = {cell for row in normalized_rows for cell in row}
        if not {"name", "title", "date"}.issubset(all_cells):
            continue

        result = {"name": None, "title": None, "date": None, "raw_table": table}
        for row in table:
            if len(row) >= 2:
                left, right = normalize_space(row[0]), normalize_space(row[1])
                left_key, right_key = _key(left), _key(right)
                if left_key in {"name", "title", "date"} and right:
                    result[left_key] = parse_source_date(right) if left_key == "date" else right
                elif right_key in {"name", "title", "date"} and left:
                    result[right_key] = parse_source_date(left) if right_key == "date" else left

        if all(result.get(field) is None for field in ("name", "title", "date")):
            for index, row in enumerate(normalized_rows):
                if row[:3] == ["name", "title", "date"] and index > 0:
                    prior = table[index - 1]
                    if len(prior) >= 3:
                        result["name"] = normalize_space(prior[0]) or None
                        result["title"] = normalize_space(prior[1]) or None
                        result["date"] = parse_source_date(prior[2])
                    break
        return result
    return {"name": None, "title": None, "date": None, "raw_table": None}


def _normalized_inventory(parsed: Mapping[str, Any], *, source_url: str) -> tuple[dict[str, int], dict[str, Any], dict[str, str]]:
    missing_components = [
        field for field in COMPONENT_REQUIRED_FIELDS if parsed.get(field) is None
    ]
    if missing_components:
        raise NysPublicWaterSourceError(
            f"LSLI detail missing required inventory component fields {missing_components}: {source_url}"
        )

    source_reported = {field: parsed.get(field) for field in INVENTORY_FIELDS}
    lead = int(parsed["lead_service_lines"])
    gslrr = int(parsed["gslrr_service_lines"])
    non_lead = int(parsed["non_lead_service_lines"])
    unknown = int(parsed["unknown_service_lines"])
    total = int(parsed["total_service_lines"])
    derived_identified = lead + gslrr + non_lead

    source_identified = parsed.get("identified_service_lines")
    if source_identified is None:
        identified = derived_identified
        evidence = "DERIVED_FROM_SOURCE_COMPONENT_COUNTS"
    else:
        identified = int(source_identified)
        evidence = "SOURCE_REPORTED"
        if identified != derived_identified:
            raise NysPublicWaterSourceError(
                f"LSLI identified-line source total does not reconcile with components: {source_url}"
            )

    if total != identified + unknown:
        raise NysPublicWaterSourceError(
            f"LSLI total-line source count does not reconcile with identified + unknown: {source_url}"
        )

    inventory = {
        "total_service_lines": total,
        "identified_service_lines": identified,
        "lead_service_lines": lead,
        "gslrr_service_lines": gslrr,
        "non_lead_service_lines": non_lead,
        "unknown_service_lines": unknown,
    }
    inventory_evidence = {
        "identified_service_lines": evidence,
        "all_other_inventory_fields": "SOURCE_REPORTED",
    }
    return inventory, source_reported, inventory_evidence


def parse_detail(html: str, *, source_url: str, expected_pws_id: str | None = None) -> dict[str, Any]:
    parser = parse_html(html)
    kv = _kv_rows(parser)

    parsed: dict[str, Any] = {}
    for source_label, target in KEY_FIELDS.items():
        value = kv.get(source_label)
        parsed[target] = _int(value) if target.endswith("_lines") else (value or None)

    pws_id = normalize_space(parsed.get("pws_id")).upper()
    if not re.fullmatch(r"NY\d{7}", pws_id):
        raise NysPublicWaterSourceError(f"LSLI detail missing valid PWS ID: {source_url}")
    if expected_pws_id and pws_id != expected_pws_id:
        raise NysPublicWaterSourceError(
            f"LSLI detail PWS mismatch: expected {expected_pws_id}, got {pws_id}: {source_url}"
        )

    inventory, source_reported_inventory, inventory_evidence = _normalized_inventory(
        parsed, source_url=source_url
    )

    methods = _identification_methods(parser)
    method_names = {_key(row["method"]) for row in methods}
    expected_methods = {_key(value) for value in METHOD_LABELS}
    if not expected_methods.issubset(method_names):
        raise NysPublicWaterSourceError(
            f"LSLI detail missing identification methods: {source_url}"
        )

    contact_present = any(
        parsed.get(field) for field in ("contact_name", "contact_phone", "contact_email")
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "detail_id": stable_id("nys-lsli-detail", pws_id),
        "pws_id": pws_id,
        "pws_name": parsed.get("pws_name"),
        "detail_status": "PARSED",
        "owner_or_operator_form_contact": {
            "name": parsed.get("contact_name"),
            "phone": parsed.get("contact_phone"),
            "email": parsed.get("contact_email"),
            "relationship_role": (
                "OWNER_OR_LICENSED_OPERATOR_OF_RECORD_FORM_CONTACT"
                if contact_present else None
            ),
            "relationship_evidence": "NYSDOH_LSLI_SECTION_II" if contact_present else None,
            "role_semantics": (
                "Source section is labeled 'Owner / Licensed Operator of Record Completing the Form'; "
                "TowerSignal does not infer whether the named contact is owner versus operator."
            ) if contact_present else None,
        },
        "inventory": inventory,
        "source_reported_inventory": source_reported_inventory,
        "inventory_evidence": inventory_evidence,
        "material_matrix": _material_matrix(parser),
        "identification_methods": methods,
        "inventory_availability": _inventory_availability(parser, kv),
        "certification": _certification(parser),
        "source_url": source_url,
        "source_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
    }


def _explicit_detail_404(exc: Exception) -> bool:
    text = str(exc).lower()
    return "http error 404" in text and "failed to retrieve nysdoh page" in text


def _unavailable_detail(index_row: Mapping[str, Any], exc: Exception) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "pws_id": str(index_row["pws_id"]),
        "pws_name": index_row.get("pws_name"),
        "principal_county_served": index_row.get("principal_county_served"),
        "detail_status": "DETAIL_UNAVAILABLE_404",
        "source_url": str(index_row["detail_url"]),
        "source_error": normalize_space(exc),
        "evidence_semantics": (
            "PWS is present in the current authoritative NYSDOH LSLI index, but the indexed "
            "detail URL returned HTTP 404 through both the primary and configured fallback hosts. "
            "No inventory values are inferred."
        ),
    }


def build_payload(*, request_delay_seconds: float = DEFAULT_REQUEST_DELAY_SECONDS) -> dict[str, Any]:
    index_snapshot = fetch_html(LSLI_INDEX_URL)
    index_rows = parse_lsli_index(index_snapshot.html, source_url=LSLI_INDEX_URL)
    if len({row["pws_id"] for row in index_rows}) != len(index_rows):
        raise NysPublicWaterSourceError("LSLI index contains duplicate PWS IDs")

    details: list[dict[str, Any]] = []
    unavailable_details: list[dict[str, Any]] = []
    retrieved_at = utc_now()
    for ordinal, index_row in enumerate(index_rows, start=1):
        try:
            snapshot = fetch_html(str(index_row["detail_url"]))
        except NysPublicWaterSourceError as exc:
            if not _explicit_detail_404(exc):
                raise
            unavailable_details.append(_unavailable_detail(index_row, exc))
            if len(unavailable_details) > MAX_EXPLICIT_UNAVAILABLE_DETAILS:
                raise NysPublicWaterSourceError(
                    f"LSLI detail source has more than {MAX_EXPLICIT_UNAVAILABLE_DETAILS} explicit 404 entries"
                ) from exc
        else:
            details.append(
                parse_detail(
                    snapshot.html,
                    source_url=str(index_row["detail_url"]),
                    expected_pws_id=str(index_row["pws_id"]),
                )
            )
        if request_delay_seconds > 0 and ordinal < len(index_rows):
            time.sleep(request_delay_seconds)

    method_system_counts: Counter[str] = Counter()
    for detail in details:
        for method in detail["identification_methods"]:
            if (method.get("pws_side_count") or 0) > 0 or (
                method.get("customer_side_count") or 0
            ) > 0:
                method_system_counts[str(method["method"])] += 1

    coverage_count = len(details) + len(unavailable_details)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": retrieved_at,
        "domain": "NYS_LEAD_SERVICE_LINE_INVENTORY_DETAILS",
        "source": {
            "name": "NYSDOH Lead Service Line Inventory detail pages",
            "index_url": LSLI_INDEX_URL,
            "index_record_count": len(index_rows),
            "parsed_detail_count": len(details),
            "explicit_unavailable_404_count": len(unavailable_details),
            "coverage_record_count": coverage_count,
            "coverage_complete": coverage_count == len(index_rows),
            "parsed_detail_complete": len(unavailable_details) == 0,
            "request_delay_seconds": request_delay_seconds,
        },
        "evidence_semantics": {
            "contact": "Section II source label combines owner / licensed operator of record completing the form; TowerSignal does not split that role without stronger evidence.",
            "inventory": "Lead, GSLRR, non-lead, unknown and total line counts must be source-reported. If the source omits only the aggregate identified count, TowerSignal preserves that source null and separately derives identified = lead + GSLRR + non-lead with explicit evidence metadata.",
            "unavailable": "A current-index PWS whose detail page returns authoritative HTTP 404 is retained explicitly and receives no inferred detail values.",
            "certification": "Certification fields are preserved only when structurally parseable; a blank source certification remains blank.",
        },
        "summary": {
            "index_count": len(index_rows),
            "parsed_detail_count": len(details),
            "unavailable_detail_count": len(unavailable_details),
            "details_with_derived_identified_count": sum(
                1
                for row in details
                if row["inventory_evidence"]["identified_service_lines"]
                == "DERIVED_FROM_SOURCE_COMPONENT_COUNTS"
            ),
            "details_with_form_contact": sum(
                1 for row in details if row["owner_or_operator_form_contact"]["name"]
            ),
            "systems_with_lead_lines": sum(
                1 for row in details if int(row["inventory"]["lead_service_lines"]) > 0
            ),
            "systems_with_gslrr": sum(
                1 for row in details if int(row["inventory"]["gslrr_service_lines"]) > 0
            ),
            "systems_with_unknown_lines": sum(
                1 for row in details if int(row["inventory"]["unknown_service_lines"]) > 0
            ),
            "source_reported_total_service_lines_sum": sum(
                int(row["inventory"]["total_service_lines"]) for row in details
            ),
            "identification_method_system_counts": dict(sorted(method_system_counts.items())),
        },
        "details": details,
        "unavailable_details": unavailable_details,
    }
