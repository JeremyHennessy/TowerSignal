from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlencode

try:
    from .toronto_market_common import canonical_street_address, clean_text
except ImportError:
    from toronto_market_common import canonical_street_address, clean_text


AIC_DETAIL_BASE = "https://www.toronto.ca/city-government/planning-development/application-details/"
BUSINESS_LICENCE_DETAIL_BASE = "https://secure.toronto.ca/LicenceStatus/detail.do"
RENTSAFE_EVALUATION_BASE = "https://www.toronto.ca/community-people/housing-shelter/rental-housing-rights-information/housing-property-standards/apartment-building-standards/audits-evaluations/rentsafeto-building-evaluation-report/"
PUBLIC_NOTICE_DETAIL_BASE = "https://secure.toronto.ca/nm/api/individual/notice/"


def numeric_id(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else None
    raw = clean_text(value)
    match = re.fullmatch(r"(\d+)(?:\.0+)?", raw)
    return match.group(1) if match else None


def slug(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", "-", clean_text(value).upper()).strip("-")


def normalize_application_number(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", clean_text(value).upper())


def aic_application_url(row: dict[str, Any]) -> str | None:
    folder_rsn = numeric_id(row.get("FOLDERRSN"))
    property_rsn = numeric_id(row.get("PROPERTYRSN") or row.get("MAINPROPERTYRSN"))
    if not folder_rsn or not property_rsn:
        return None
    params = {"id": folder_rsn, "pid": property_rsn}
    title = slug(row.get("FULL_ADDRESS"))
    if title:
        params["title"] = title
    return f"{AIC_DETAIL_BASE}?{urlencode(params)}"


def development_pipeline_aic_url(
    row: dict[str, Any],
    source_rows: dict[str, list[dict[str, Any]]],
    source_address: Any,
) -> str | None:
    number = normalize_application_number(row.get("Application Number"))
    expected_address = canonical_street_address(source_address or row.get("Address"))
    if not number or not expected_address:
        return None
    candidates = []
    for app in source_rows.get("toronto_aic_applications") or []:
        if normalize_application_number(app.get("APPLICATION_NUMBER")) != number:
            continue
        if canonical_street_address(app.get("FULL_ADDRESS")) != expected_address:
            continue
        url = aic_application_url(app)
        if url:
            candidates.append(url)
    unique = sorted(set(candidates))
    return unique[0] if len(unique) == 1 else None


def business_licence_url(row: dict[str, Any]) -> str | None:
    # The City's current lookup does not display suspended/cancelled licences;
    # retain dataset fallback for those historical rows rather than constructing
    # a detail action that the publisher will not serve.
    if clean_text(row.get("Cancel Date")):
        return None
    licence = re.sub(r"[^A-Z0-9]", "", clean_text(row.get("Licence No.")).upper())
    if not licence:
        return None
    return f"{BUSINESS_LICENCE_DETAIL_BASE}?{urlencode({'licenceNo': licence})}"


def rentsafe_evaluation_url(row: dict[str, Any]) -> str | None:
    rsn = numeric_id(row.get("RSN"))
    if not rsn:
        return None
    params = {"id": rsn}
    title = slug(row.get("SITE ADDRESS"))
    if title:
        params["title"] = title
    return f"{RENTSAFE_EVALUATION_BASE}?{urlencode(params)}"


def public_notice_url(row: dict[str, Any]) -> str | None:
    notice_id = numeric_id(row.get("noticeId"))
    if not notice_id:
        return None
    return f"{PUBLIC_NOTICE_DETAIL_BASE}{notice_id}.do"


def record_action_for_source(
    source_key: str,
    row: dict[str, Any],
    source_rows: dict[str, list[dict[str, Any]]],
    link: dict[str, Any],
) -> dict[str, str | None]:
    url: str | None = None
    label: str | None = None
    if source_key == "toronto_aic_applications":
        url = aic_application_url(row)
        label = "Open AIC application" if url else None
    elif source_key == "development_pipeline":
        url = development_pipeline_aic_url(row, source_rows, link.get("source_address"))
        label = "Open AIC application" if url else None
    elif source_key == "business_licence_matches_prior_poc":
        url = business_licence_url(row)
        label = "Open licence details" if url else None
    elif source_key == "apartment_building_evaluation":
        url = rentsafe_evaluation_url(row)
        label = "Open RentSafeTO evaluation" if url else None
    elif source_key == "toronto_public_notices_exact_prior_poc":
        url = public_notice_url(row)
        label = "Open public notice" if url else None
    return {"record_url": url, "record_link_label": label}
