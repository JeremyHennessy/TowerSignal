from __future__ import annotations

import hashlib
import json
from typing import Any


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def row_fingerprint(record: dict[str, Any]) -> str:
    """Deterministic identity fallback for source rows without a publisher row ID."""
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def stable_source_record_id(source: str, record: dict[str, Any]) -> str:
    source = clean(source)
    if not source:
        raise ValueError("source key is required")

    if source == "chemtrac_history":
        year = clean(record.get("_towersignal_reporting_year"))
        row_id = clean(record.get("_id"))
        if year and row_id:
            return f"{source}:year:{year}:id:{row_id}"
        resource_id = clean(record.get("_towersignal_source_resource_id"))
        if resource_id and row_id:
            return f"{source}:resource:{resource_id}:id:{row_id}"

    for key in ("_id", "OBJECTID", "id", "APPLICATION_NUMBER", "FOLDERRSN", "RSN", "document_number", "noticeId"):
        value = clean(record.get(key))
        if value:
            return f"{source}:id:{value}"

    return f"{source}:sha256:{row_fingerprint(record)}"


def find_source_record(source: str, source_record_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    source = clean(source)
    record_id = clean(source_record_id)
    prefix = f"{source}:"
    if not source or not record_id.startswith(prefix):
        return {}
    tail = record_id[len(prefix):]

    if tail.startswith("year:"):
        parts = tail.split(":")
        if len(parts) == 4 and parts[0] == "year" and parts[2] == "id":
            year, row_id = parts[1], parts[3]
            return next((row for row in rows if clean(row.get("_towersignal_reporting_year")) == year and clean(row.get("_id")) == row_id), {})

    if tail.startswith("resource:"):
        parts = tail.split(":")
        if len(parts) == 4 and parts[0] == "resource" and parts[2] == "id":
            resource_id, row_id = parts[1], parts[3]
            return next((row for row in rows if clean(row.get("_towersignal_source_resource_id")) == resource_id and clean(row.get("_id")) == row_id), {})

    if tail.startswith("id:"):
        wanted = tail[3:]
        for row in rows:
            for key in ("_id", "OBJECTID", "id", "APPLICATION_NUMBER", "FOLDERRSN", "RSN", "document_number", "noticeId"):
                if clean(row.get(key)) == wanted:
                    return row
        return {}

    if tail.startswith("sha256:"):
        wanted = tail[7:]
        return next((row for row in rows if row_fingerprint(row) == wanted), {})

    # Backward compatibility for pre-contract persisted links. Prefer the stable
    # portion when possible; index fallback is intentionally last.
    if source == "toronto_public_notices_exact_prior_poc":
        wanted = tail.rsplit(":", 1)[-1]
        return next((row for row in rows if clean(row.get("noticeId")) == wanted), {})

    if source == "tobids_awarded_contracts_exact_document_address_prior_poc":
        wanted = tail.rsplit(":", 1)[-1]
        return next((row for row in rows if clean(row.get("source_record_id")) == wanted or clean(row.get("document_number")) == wanted or clean(row.get("Document Number")) == wanted), {})

    parts = tail.rsplit(":", 1)
    if len(parts) == 2:
        legacy_id, legacy_index = parts
        if legacy_id not in {"", "row"}:
            candidates = []
            for row in rows:
                if any(clean(row.get(key)) == legacy_id for key in ("_id", "OBJECTID", "id", "APPLICATION_NUMBER", "FOLDERRSN", "RSN", "document_number", "noticeId")):
                    candidates.append(row)
            if len(candidates) == 1:
                return candidates[0]
        try:
            index = int(legacy_index)
        except ValueError:
            return {}
        if 0 <= index < len(rows):
            return rows[index]

    return {}
