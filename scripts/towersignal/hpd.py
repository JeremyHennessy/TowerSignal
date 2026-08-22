from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from towersignal.fetch import fetch_count, fetch_metadata, fetch_where
from towersignal.pluto import normalize_bbl

HPD_REGISTRATION_DATASET_ID = "tesw-yqqr"
HPD_CONTACTS_DATASET_ID = "feu5-w2e2"
HPD_REGISTRATION_URL = "https://data.cityofnewyork.us/Housing-Development/Multiple-Dwelling-Registrations/tesw-yqqr"
HPD_CONTACTS_URL = "https://data.cityofnewyork.us/Housing-Development/Registration-Contacts/feu5-w2e2"

REGISTRATION_SELECT = ",".join((
    "registrationid",
    "buildingid",
    "boroid",
    "boro",
    "block",
    "lot",
    "bin",
    "lastregistrationdate",
))
CONTACT_SELECT = ",".join((
    "registrationcontactid",
    "registrationid",
    "type",
    "contactdescription",
    "corporationname",
    "title",
    "firstname",
    "middleinitial",
    "lastname",
    "businesshousenumber",
    "businessstreetname",
    "businessapartment",
    "businesscity",
    "businessstate",
    "businesszip",
))


def bbl_parts(value: Any) -> tuple[int, int, int] | None:
    normalized = normalize_bbl(value)
    if normalized is None:
        return None
    padded = normalized.zfill(10)
    if len(padded) != 10:
        return None
    borough = int(padded[0])
    block = int(padded[1:6])
    lot = int(padded[6:10])
    if borough not in {1, 2, 3, 4, 5} or block <= 0 or lot <= 0:
        return None
    return borough, block, lot


def parts_to_bbl(borough: Any, block: Any, lot: Any) -> str | None:
    try:
        borough_i = int(float(borough))
        block_i = int(float(block))
        lot_i = int(float(lot))
    except (TypeError, ValueError):
        return None
    if borough_i not in {1, 2, 3, 4, 5} or block_i <= 0 or lot_i <= 0:
        return None
    return f"{borough_i}{block_i:05d}{lot_i:04d}"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _date_only(value: Any) -> str | None:
    text = _text(value)
    if text is None:
        return None
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    return text


def _person_name(row: dict[str, Any]) -> str | None:
    parts = [_text(row.get("firstname")), _text(row.get("middleinitial")), _text(row.get("lastname"))]
    name = " ".join(part for part in parts if part)
    return name or None


def _business_address(row: dict[str, Any]) -> str | None:
    line1 = " ".join(part for part in (_text(row.get("businesshousenumber")), _text(row.get("businessstreetname"))) if part)
    apartment = _text(row.get("businessapartment"))
    if apartment:
        line1 = f"{line1}, {apartment}" if line1 else apartment
    locality = ", ".join(part for part in (_text(row.get("businesscity")), _text(row.get("businessstate"))) if part)
    zip_code = _text(row.get("businesszip"))
    if zip_code:
        locality = f"{locality} {zip_code}".strip()
    return ", ".join(part for part in (line1 or None, locality or None) if part) or None


def normalize_contact(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "registration_contact_id": _text(row.get("registrationcontactid")),
        "type": _text(row.get("type")),
        "description": _text(row.get("contactdescription")),
        "corporation_name": _text(row.get("corporationname")),
        "person_name": _person_name(row),
        "title": _text(row.get("title")),
        "business_address": _business_address(row),
        "source": "NYC_HPD_REGISTRATION_CONTACTS",
    }


def _registration_rank(row: dict[str, Any]) -> tuple[str, int]:
    return (_date_only(row.get("lastregistrationdate")) or "", int(float(row.get("registrationid") or 0)))


def fetch_hpd_contacts_by_bbl(bbl_values: Iterable[str], chunk_size: int = 100) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    requested = sorted({bbl for value in bbl_values if (bbl := normalize_bbl(value)) is not None}, key=int)
    requested_parts = [(bbl, bbl_parts(bbl)) for bbl in requested]
    requested_parts = [(bbl, parts) for bbl, parts in requested_parts if parts is not None]

    latest_registration_by_bbl: dict[str, dict[str, Any]] = {}
    for start in range(0, len(requested_parts), chunk_size):
        chunk = requested_parts[start : start + chunk_size]
        clauses = [f"(boroid={borough} and block={block} and lot={lot})" for _, (borough, block, lot) in chunk]
        if not clauses:
            continue
        rows = fetch_where(
            HPD_REGISTRATION_DATASET_ID,
            where=" or ".join(clauses),
            order_by="lastregistrationdate desc,registrationid desc",
            select=REGISTRATION_SELECT,
        )
        expected = {bbl for bbl, _ in chunk}
        for row in rows:
            bbl = parts_to_bbl(row.get("boroid"), row.get("block"), row.get("lot"))
            if bbl is None or bbl not in expected:
                continue
            existing = latest_registration_by_bbl.get(bbl)
            if existing is None or _registration_rank(row) > _registration_rank(existing):
                latest_registration_by_bbl[bbl] = row

    registration_ids = sorted({str(row["registrationid"]).strip() for row in latest_registration_by_bbl.values() if row.get("registrationid")})
    contacts_by_registration: dict[str, list[dict[str, Any]]] = {}
    contact_row_count = 0
    for start in range(0, len(registration_ids), 250):
        batch = registration_ids[start : start + 250]
        if not batch:
            continue
        rows = fetch_where(
            HPD_CONTACTS_DATASET_ID,
            where=f"registrationid in ({','.join(batch)})",
            order_by="registrationid,type,registrationcontactid",
            select=CONTACT_SELECT,
        )
        contact_row_count += len(rows)
        expected = set(batch)
        for row in rows:
            registration_id = str(row.get("registrationid") or "").strip()
            if registration_id not in expected:
                continue
            contacts_by_registration.setdefault(registration_id, []).append(normalize_contact(row))

    result: dict[str, dict[str, Any]] = {}
    for bbl, registration in latest_registration_by_bbl.items():
        registration_id = str(registration.get("registrationid") or "").strip()
        contacts = contacts_by_registration.get(registration_id, [])
        contacts.sort(key=lambda item: (item.get("type") or "", item.get("corporation_name") or item.get("person_name") or ""))
        result[bbl] = {
            "registration_id": registration_id or None,
            "building_id": _text(registration.get("buildingid")),
            "last_registration_date": _date_only(registration.get("lastregistrationdate")),
            "contacts": contacts,
            "source": "NYC_HPD_MULTIPLE_DWELLING_REGISTRATION",
        }

    registration_metadata = fetch_metadata(HPD_REGISTRATION_DATASET_ID)
    contact_metadata = fetch_metadata(HPD_CONTACTS_DATASET_ID)
    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return result, {
        "registration_dataset_id": HPD_REGISTRATION_DATASET_ID,
        "registration_name": registration_metadata["name"],
        "registration_url": HPD_REGISTRATION_URL,
        "registration_source_record_count": fetch_count(HPD_REGISTRATION_DATASET_ID),
        "registration_source_last_updated_at": registration_metadata.get("source_last_updated_at"),
        "contacts_dataset_id": HPD_CONTACTS_DATASET_ID,
        "contacts_name": contact_metadata["name"],
        "contacts_url": HPD_CONTACTS_URL,
        "contacts_source_record_count": fetch_count(HPD_CONTACTS_DATASET_ID),
        "contacts_source_last_updated_at": contact_metadata.get("source_last_updated_at"),
        "retrieved_at": retrieved_at,
        "requested_bbl_count": len(requested),
        "matched_registration_bbl_count": len(result),
        "matched_contact_bbl_count": sum(1 for item in result.values() if item["contacts"]),
        "matched_contact_record_count": contact_row_count,
        "source_query_scope": "Exact BBL subset of cooling-tower properties, then exact HPD registration_id contact lookup",
    }
