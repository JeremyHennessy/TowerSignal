"""Source-native HPD identities and contacts, without address guessing or sentinel joins."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from .fetch import SourceFetchError, fetch_count, fetch_metadata, fetch_where
from .hpd import (HPD_REGISTRATION_DATASET_ID, HPD_CONTACTS_DATASET_ID,
                  HPD_REGISTRATION_URL, HPD_CONTACTS_URL, REGISTRATION_SELECT,
                  CONTACT_SELECT, parts_to_bbl, normalize_contact, _registration_rank)
from .planimetrics import normalize_bin
from .pluto import normalize_bbl


def positive_id(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return str(int(text)) if text.isascii() and text.isdigit() and int(text) > 0 else None


def registration_bbl(row: dict) -> str | None:
    return parts_to_bbl(row.get("boroid"), row.get("block"), row.get("lot"))


def key_digest(values) -> str:
    return hashlib.sha256("\n".join(sorted(set(str(v) for v in values))).encode()).hexdigest()


def index_registrations(rows: list[dict]) -> dict:
    by_bbl, by_bin, identities = defaultdict(list), defaultdict(list), defaultdict(set)
    for row in rows:
        bbl = registration_bbl(row)
        bin_value = normalize_bin(row.get("bin"))
        rid = positive_id(row.get("registrationid"))
        if bbl:
            by_bbl[bbl].append(row)
        if bin_value:
            by_bin[bin_value].append(row)
        if rid:
            identities[rid].add((str(row.get("buildingid") or ""), bin_value, bbl))
    conflicts = {rid for rid, keys in identities.items() if len(keys) > 1}
    eligible_by_bin = {
        bin_value: [r for r in group if positive_id(r.get("registrationid"))
                    and positive_id(r.get("registrationid")) not in conflicts and registration_bbl(r)]
        for bin_value, group in by_bin.items()
    }
    return {"by_bbl": dict(by_bbl), "by_bin": dict(by_bin),
            "eligible_by_bin": eligible_by_bin, "conflicting_registration_ids": conflicts}


def fetch_registration_snapshot() -> dict:
    before = fetch_metadata(HPD_REGISTRATION_DATASET_ID)
    expected = fetch_count(HPD_REGISTRATION_DATASET_ID)
    rows = []
    for offset in range(0, expected, 50000):
        rows.extend(fetch_where(HPD_REGISTRATION_DATASET_ID, "1=1",
                    "registrationid,buildingid,:id", REGISTRATION_SELECT, offset=offset))
    after = fetch_metadata(HPD_REGISTRATION_DATASET_ID)
    if len(rows) != expected or before.get("source_last_updated_at") != after.get("source_last_updated_at"):
        raise SourceFetchError("HPD registration snapshot changed or is incomplete; not negative evidence")
    index = index_registrations(rows)
    index["source"] = {**after, "source_record_count": expected,
        "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "registration_identity_sha256": hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}
    return index


def select_registration(system: dict, index: dict) -> tuple[dict | None, str]:
    bin_value = normalize_bin(system.get("bin"))
    bbl = normalize_bbl(system.get("bbl"))
    # Prefer the building's own registration. Do not replace a current empty
    # registration with an older contact-bearing one.
    exact = index["by_bin"].get(bin_value, []) if bin_value else []
    if exact:
        properties = {registration_bbl(r) for r in exact if registration_bbl(r)}
        if len(properties) != 1:
            return None, "AMBIGUOUS_HPD_BUILDING_PROPERTY"
        candidates, basis = exact, "BIN_EXACT"
    else:
        candidates, basis = index["by_bbl"].get(bbl, []) if bbl else [], "BBL_PARCEL_EXACT"
    if not candidates:
        return None, "NO_REGISTRATION_ON_CHECKED_KEYS" if bin_value or bbl else "IDENTITY_UNRESOLVED"
    row = max(candidates, key=lambda r: (_registration_rank(r), str(r.get("buildingid") or "")))
    rid = positive_id(row.get("registrationid"))
    if rid is None:
        return row, "UNUSABLE_SOURCE_REGISTRATION_ID"
    if rid in index["conflicting_registration_ids"]:
        return row, "COLLIDING_SOURCE_REGISTRATION_ID"
    return row, basis


def assemble_contacts(systems: list[dict], index: dict, rows: list[dict]) -> dict[str, dict]:
    by_id = defaultdict(list)
    for row in rows:
        rid = positive_id(row.get("registrationid"))
        if rid and rid not in index["conflicting_registration_ids"]:
            by_id[rid].append(normalize_contact(row))
    result = {}
    for system in systems:
        row, basis = select_registration(system, index)
        sid = str(system["system_id"])
        if row is None:
            result[sid] = {"registration": None, "status": basis}
            continue
        rid = positive_id(row.get("registrationid"))
        safe = basis in {"BIN_EXACT", "BBL_PARCEL_EXACT"}
        contacts = by_id.get(rid, []) if safe else []
        contacts = sorted({json.dumps(c, sort_keys=True): c for c in contacts}.values(),
                          key=lambda c: (c.get("type") or "", c.get("registration_contact_id") or ""))
        status = ("MATCHED" if contacts else "VERIFIED_EMPTY_CONTACTS") if safe else basis
        result[sid] = {"status": status, "registration": {
            "registration_id": rid,
            "source_registration_id_raw": row.get("registrationid"),
            "building_id": str(row.get("buildingid") or "") or None,
            "source_bin": normalize_bin(row.get("bin")),
            "source_bbl": registration_bbl(row),
            "last_registration_date": str(row.get("lastregistrationdate") or "")[:10] or None,
            "contacts": contacts, "lookup_status": status,
            "match_basis": basis if safe else None,
            "property_identity_agrees": registration_bbl(row) in (system.get("bbl_aliases") or [system.get("bbl")]),
            "source": "NYC_HPD_MULTIPLE_DWELLING_REGISTRATION",
        }}
    return result


def fetch_contacts_for_systems(systems: list[dict], index: dict) -> tuple[dict, dict]:
    ids = set()
    for system in systems:
        row, basis = select_registration(system, index)
        if row and basis in {"BIN_EXACT", "BBL_PARCEL_EXACT"}:
            ids.add(positive_id(row.get("registrationid")))
    ids = sorted(ids, key=int)
    rows = []
    for start in range(0, len(ids), 250):
        batch = ids[start:start + 250]
        found = fetch_where(HPD_CONTACTS_DATASET_ID, f"registrationid in ({','.join(batch)})",
                            "registrationid,type,registrationcontactid", CONTACT_SELECT)
        if len(found) >= 50000 or any(positive_id(r.get("registrationid")) not in batch for r in found):
            raise SourceFetchError("HPD contact lookup hit row cap or returned an unrequested registration")
        rows.extend(found)
    by_system = assemble_contacts(systems, index, rows)
    source, contacts_meta = index["source"], fetch_metadata(HPD_CONTACTS_DATASET_ID)
    bbls = {s["bbl"] for s in systems if s.get("bbl")}
    bins = {v for s in systems if (v := normalize_bin(s.get("bin")))}
    return by_system, {
        "registration_dataset_id": HPD_REGISTRATION_DATASET_ID,
        "registration_name": source["name"], "registration_url": HPD_REGISTRATION_URL,
        "registration_source_record_count": source["source_record_count"],
        "registration_source_last_updated_at": source.get("source_last_updated_at"),
        "contacts_dataset_id": HPD_CONTACTS_DATASET_ID,
        "contacts_name": contacts_meta["name"], "contacts_url": HPD_CONTACTS_URL,
        "contacts_source_record_count": fetch_count(HPD_CONTACTS_DATASET_ID),
        "contacts_source_last_updated_at": contacts_meta.get("source_last_updated_at"),
        "retrieved_at": source["retrieved_at"], "requested_bbl_count": len(bbls),
        "requested_assigned_bin_count": len(bins), "queried_registration_id_count": len(ids),
        "queried_registration_ids_sha256": key_digest(ids), "queried_bbls_sha256": key_digest(bbls),
        "queried_bins_sha256": key_digest(bins),
        "registration_identity_sha256": source["registration_identity_sha256"],
        "matched_registration_bbl_count": len({s.get("bbl") for s in systems if by_system[str(s["system_id"])]["registration"] and s.get("bbl")}),
        "matched_contact_bbl_count": len({s.get("bbl") for s in systems if by_system[str(s["system_id"])]["status"] == "MATCHED" and s.get("bbl")}),
        "matched_contact_record_count": len(rows),
        "source_query_scope": "Complete stable HPD identity snapshot; assigned BIN first, canonical BBL parcel second; positive unique registration IDs only",
    }
