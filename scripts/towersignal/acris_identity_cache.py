"""Prevent a valid but differently scoped ACRIS cache becoming false absence evidence."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from .acris import build_recent_cache, normalize_bbl, tower_bbl_hash


def property_targets(systems: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    targets: dict[str, dict[str, Any]] = {}
    for system in sorted(systems, key=lambda row: str(row.get("system_id") or "")):
        bbl = normalize_bbl(system.get("bbl"))
        if not bbl:
            continue
        aliases = set((targets.get(bbl) or {}).get("bbl_aliases") or [])
        aliases.update(value for raw in (system.get("bbl_aliases") or [bbl]) if (value := normalize_bbl(raw)))
        targets[bbl] = {
            "system_id": system.get("system_id"),
            "bin": system.get("bin"),
            "borough": system.get("borough"),
            "number": system.get("number"),
            "street": system.get("street"),
            "address": system.get("address"),
            "bbl_aliases": sorted(aliases),
        }
    return targets


def graph_digest(targets: dict[str, dict[str, Any]]) -> str:
    return hashlib.sha256(json.dumps(targets, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def ensure_alignment(
    cache: dict[str, Any] | None,
    systems: list[dict[str, Any]],
    *,
    builder: Callable[..., dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], bool]:
    targets = property_targets(systems)
    digest = graph_digest(targets)
    universe_hash = tower_bbl_hash(targets)
    if cache is not None and (cache.get("tower_bbl_universe") or {}).get("sha256") == universe_hash and cache.get("mapping_property_graph_sha256") == digest:
        return cache, False
    # No currently aligned cache: build from the exact systems being released,
    # not a separately collected registry or an older count-only property list.
    refreshed = (builder or build_recent_cache)(set(targets), property_targets=targets)
    if (refreshed.get("tower_bbl_universe") or {}).get("sha256") != universe_hash:
        raise RuntimeError("Rebuilt ACRIS cache does not match the release property universe")
    refreshed["mapping_property_graph_sha256"] = digest
    return refreshed, True
