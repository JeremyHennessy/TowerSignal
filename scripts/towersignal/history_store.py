from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HISTORY_STORAGE_VERSION = "2.0"
SEGMENT_HARD_MAX_BYTES = 8 * 1024 * 1024
SEGMENT_GROWTH_RATIO_LIMIT = 1.75
SEGMENT_GROWTH_ABSOLUTE_ALLOWANCE = 1 * 1024 * 1024
OATH_SHARD_NAMES = ("oath_0", "oath_1")

CORE_FIELDS = (
    "system_id", "bin", "bbl", "registry_bbl", "bbl_identity_basis", "bbl_identity_status",
    "address", "borough", "zip", "date_registered",
    "active_equipment", "sample_dates", "latest_sample_date", "primary_signal",
    "signal_types", "priority_score", "evidence_confidence", "first_seen_at", "last_seen_at",
)
INSPECTION_FIELDS = ("inspection_keys", "violation_keys")
OATH_FIELDS = ("oath_cases",)
PROPERTY_FIELDS = ("pluto_owner", "building_context")
HPD_FIELDS = ("hpd_registration_id", "hpd_last_registration_date", "hpd_contacts")
SYSTEM_SEGMENTS = {
    "core": CORE_FIELDS,
    "inspections": ("system_id", *INSPECTION_FIELDS),
    "property": ("system_id", *PROPERTY_FIELDS),
    "hpd": ("system_id", *HPD_FIELDS),
}
KNOWN_SYSTEM_FIELDS = set(CORE_FIELDS) | set(INSPECTION_FIELDS) | set(OATH_FIELDS) | set(PROPERTY_FIELDS) | set(HPD_FIELDS)


def _compact(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_json(path: Path, payload: Any) -> tuple[int, str]:
    raw = _compact(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return len(raw), _sha256_bytes(raw)


def _segment_entry(path: str, size: int, digest: str, record_count: int | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {"path": path, "bytes": size, "sha256": digest}
    if record_count is not None:
        entry["record_count"] = record_count
    return entry


def _system_ids(rows: list[dict[str, Any]]) -> list[str]:
    ids = [str(row.get("system_id") or "") for row in rows]
    if any(not value for value in ids):
        raise RuntimeError("History snapshot contains a system without system_id")
    if len(ids) != len(set(ids)):
        raise RuntimeError("History snapshot contains duplicate system_id values")
    return ids


def _write_system_segment(
    history_dir: Path,
    name: str,
    rows: list[dict[str, Any]],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "history_storage_version": HISTORY_STORAGE_VERSION,
        "history_schema_version": snapshot.get("history_schema_version"),
        "observed_at": snapshot.get("observed_at"),
        "segment": name,
        "systems": rows,
    }
    relative = f"segments/{name}.json"
    size, digest = _write_json(history_dir / relative, payload)
    return _segment_entry(relative, size, digest, len(rows))


def write_segmented_snapshot(history_dir: Path, snapshot: dict[str, Any]) -> dict[str, Any]:
    systems = snapshot.get("systems")
    if not isinstance(systems, list):
        raise RuntimeError("History snapshot systems must be a list")
    system_rows = [dict(row) for row in systems if isinstance(row, dict)]
    if len(system_rows) != len(systems):
        raise RuntimeError("History snapshot systems must contain objects only")
    ids = _system_ids(system_rows)

    for row in system_rows:
        unknown = sorted(set(row) - KNOWN_SYSTEM_FIELDS)
        if unknown:
            raise RuntimeError(
                f"History segmentation does not own new durable fields for {row.get('system_id')}: {unknown}. "
                "Assign them to an explicit segment before persisting."
            )

    segment_root = history_dir / "segments"
    segment_root.mkdir(parents=True, exist_ok=True)
    segment_entries: dict[str, dict[str, Any]] = {}

    for name, fields in SYSTEM_SEGMENTS.items():
        rows: list[dict[str, Any]] = []
        for row in system_rows:
            if name == "core":
                segment_row = {key: row.get(key) for key in fields if key in row}
            else:
                segment_row = {key: row.get(key) for key in fields}
            rows.append(segment_row)
        segment_entries[name] = _write_system_segment(history_dir, name, rows, snapshot)

    # OATH is the largest current source-owned state. Keep every System ID in
    # each shard, but split each system's ordered case list by stable list index.
    # The index is retained in the storage representation so reconstruction can
    # reproduce the exact original list order without changing history meaning.
    oath_shard_rows: dict[str, list[dict[str, Any]]] = {name: [] for name in OATH_SHARD_NAMES}
    for row in system_rows:
        cases = row.get("oath_cases") or []
        if not isinstance(cases, list):
            raise RuntimeError(f"History oath_cases must be a list for {row.get('system_id')}")
        indexed_by_shard: dict[str, list[list[Any]]] = {name: [] for name in OATH_SHARD_NAMES}
        for index, case in enumerate(cases):
            shard = OATH_SHARD_NAMES[index % len(OATH_SHARD_NAMES)]
            indexed_by_shard[shard].append([index, case])
        for shard in OATH_SHARD_NAMES:
            oath_shard_rows[shard].append({
                "system_id": row["system_id"],
                "oath_cases_indexed": indexed_by_shard[shard],
            })
    for shard in OATH_SHARD_NAMES:
        segment_entries[shard] = _write_system_segment(history_dir, shard, oath_shard_rows[shard], snapshot)

    dob_payload = {
        "history_storage_version": HISTORY_STORAGE_VERSION,
        "history_schema_version": snapshot.get("history_schema_version"),
        "observed_at": snapshot.get("observed_at"),
        "segment": "dob",
        "dob_history_initialized": bool(snapshot.get("dob_history_initialized")),
        "dob_by_bbl": snapshot.get("dob_by_bbl") or {},
    }
    dob_size, dob_digest = _write_json(segment_root / "dob.json", dob_payload)
    segment_entries["dob"] = _segment_entry("segments/dob.json", dob_size, dob_digest, len(dob_payload["dob_by_bbl"]))

    health_payload = {
        "history_storage_version": HISTORY_STORAGE_VERSION,
        "history_schema_version": snapshot.get("history_schema_version"),
        "observed_at": snapshot.get("observed_at"),
        "segment": "source_health",
        "source_health": snapshot.get("source_health") or [],
    }
    health_size, health_digest = _write_json(segment_root / "source-health.json", health_payload)
    segment_entries["source_health"] = _segment_entry("segments/source-health.json", health_size, health_digest, len(health_payload["source_health"]))

    manifest = {
        "history_storage_version": HISTORY_STORAGE_VERSION,
        "history_schema_version": snapshot.get("history_schema_version"),
        "history_started_at": snapshot.get("history_started_at"),
        "observed_at": snapshot.get("observed_at"),
        "system_count": len(ids),
        "segments": segment_entries,
    }
    _write_json(history_dir / "latest.json", manifest)
    return manifest


def _load_verified_segment(history_dir: Path, name: str, entry: dict[str, Any]) -> dict[str, Any]:
    relative = str(entry.get("path") or "")
    if not relative or relative.startswith("/") or ".." in Path(relative).parts:
        raise RuntimeError(f"Invalid history segment path for {name}: {relative!r}")
    path = history_dir / relative
    if not path.exists():
        raise RuntimeError(f"History segment missing: {path}")
    raw = path.read_bytes()
    expected_size = int(entry.get("bytes") or -1)
    expected_digest = str(entry.get("sha256") or "")
    if len(raw) != expected_size:
        raise RuntimeError(f"History segment size mismatch for {name}: expected {expected_size}, got {len(raw)}")
    if _sha256_bytes(raw) != expected_digest:
        raise RuntimeError(f"History segment checksum mismatch for {name}")
    payload = json.loads(raw)
    if not isinstance(payload, dict) or payload.get("history_storage_version") != HISTORY_STORAGE_VERSION:
        raise RuntimeError(f"History segment contract invalid for {name}")
    if payload.get("segment") != name:
        raise RuntimeError(f"History segment identity mismatch: expected {name}, got {payload.get('segment')}")
    return payload


def _validated_system_rows(name: str, payload: dict[str, Any], ids: list[str]) -> list[dict[str, Any]]:
    rows = payload.get("systems")
    if not isinstance(rows, list):
        raise RuntimeError(f"History {name} segment systems must be a list")
    segment_rows = [dict(row) for row in rows if isinstance(row, dict)]
    if len(segment_rows) != len(rows):
        raise RuntimeError(f"History {name} segment systems must contain objects only")
    segment_ids = _system_ids(segment_rows)
    if set(segment_ids) != set(ids):
        raise RuntimeError(f"History {name} segment system IDs do not reconcile to core")
    return segment_rows


def reconstruct_segmented_snapshot(history_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("history_storage_version") != HISTORY_STORAGE_VERSION:
        raise RuntimeError(f"Unsupported history storage version: {manifest.get('history_storage_version')}")
    segment_entries = manifest.get("segments")
    if not isinstance(segment_entries, dict):
        raise RuntimeError("Segmented history manifest is missing segments")
    required = set(SYSTEM_SEGMENTS) | set(OATH_SHARD_NAMES) | {"dob", "source_health"}
    missing = sorted(required - set(segment_entries))
    if missing:
        raise RuntimeError(f"Segmented history manifest missing segments: {missing}")

    loaded = {
        name: _load_verified_segment(history_dir, name, dict(segment_entries[name]))
        for name in required
    }
    core_rows = loaded["core"].get("systems")
    if not isinstance(core_rows, list):
        raise RuntimeError("Core history segment systems must be a list")
    core = [dict(row) for row in core_rows if isinstance(row, dict)]
    ids = _system_ids(core)
    if int(manifest.get("system_count") or -1) != len(ids):
        raise RuntimeError("Segmented history manifest system_count does not match core segment")
    by_id = {row["system_id"]: row for row in core}

    for name in ("inspections", "property", "hpd"):
        for row in _validated_system_rows(name, loaded[name], ids):
            system_id = row.pop("system_id")
            by_id[system_id].update(row)

    oath_indexed_by_system: dict[str, dict[int, Any]] = {system_id: {} for system_id in ids}
    for shard in OATH_SHARD_NAMES:
        for row in _validated_system_rows(shard, loaded[shard], ids):
            system_id = str(row.get("system_id"))
            indexed = row.get("oath_cases_indexed")
            if not isinstance(indexed, list):
                raise RuntimeError(f"History {shard} oath_cases_indexed must be a list for {system_id}")
            for item in indexed:
                if not isinstance(item, list) or len(item) != 2 or not isinstance(item[0], int) or item[0] < 0:
                    raise RuntimeError(f"History {shard} has invalid OATH index record for {system_id}")
                index, case = item
                if index in oath_indexed_by_system[system_id]:
                    raise RuntimeError(f"Duplicate OATH list index {index} across shards for {system_id}")
                oath_indexed_by_system[system_id][index] = case
    for system_id in ids:
        indexed = oath_indexed_by_system[system_id]
        expected_indexes = list(range(len(indexed)))
        actual_indexes = sorted(indexed)
        if actual_indexes != expected_indexes:
            raise RuntimeError(f"OATH shard indexes are not contiguous for {system_id}: {actual_indexes[:10]}")
        by_id[system_id]["oath_cases"] = [indexed[index] for index in expected_indexes]

    dob = loaded["dob"]
    health = loaded["source_health"]
    snapshot = {
        "history_schema_version": manifest.get("history_schema_version"),
        "history_started_at": manifest.get("history_started_at"),
        "observed_at": manifest.get("observed_at"),
        "dob_history_initialized": bool(dob.get("dob_history_initialized")),
        "dob_by_bbl": dob.get("dob_by_bbl") or {},
        "systems": [by_id[system_id] for system_id in ids],
        "source_health": health.get("source_health") or [],
    }
    return snapshot


def load_history_snapshot(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"History snapshot must be an object: {path}")
    if payload.get("history_storage_version") == HISTORY_STORAGE_VERSION:
        return reconstruct_segmented_snapshot(path.parent, payload)
    return payload
