from __future__ import annotations

from collections import Counter
from typing import Any

from .planimetrics import normalize_bin
from .pluto import normalize_bbl

BOROUGH_CODE_BY_NAME = {
    "MANHATTAN": "1",
    "BRONX": "2",
    "BROOKLYN": "3",
    "QUEENS": "4",
    "STATEN ISLAND": "5",
}


def _borough(value: Any) -> str:
    text = str(value or "").strip().upper()
    aliases = {
        "MN": "MANHATTAN",
        "BX": "BRONX",
        "BK": "BROOKLYN",
        "QN": "QUEENS",
        "SI": "STATEN ISLAND",
        "STATEN ISLAND / RICHMOND": "STATEN ISLAND",
    }
    return aliases.get(text, text)


def _mappluto_candidates(footprints: list[dict[str, Any]]) -> set[str]:
    candidates: set[str] = set()
    for footprint in footprints:
        value = normalize_bbl(footprint.get("mappluto_bbl"))
        if value:
            candidates.add(value.zfill(10))
    return candidates


def resolve_system_bbl_identity(
    system: dict[str, Any],
    footprints: list[dict[str, Any]],
) -> dict[str, Any]:
    registry_bbl = normalize_bbl(system.get("bbl"))
    if registry_bbl:
        canonical = registry_bbl.zfill(10)
        return {
            "canonical_bbl": canonical,
            "registry_bbl": canonical,
            "identity_basis": "REGISTRY_SOURCE_BBL",
            "status": "REGISTRY_SOURCE_BBL",
            "source_dataset": "NYC_COOLING_TOWER_REGISTRATIONS",
            "source_field": "bbl",
            "join_key": None,
            "mappluto_bbl_candidates": [],
            "base_bbl_context": [],
            "address_matching_used": False,
            "fuzzy_matching_used": False,
        }

    bin_value = normalize_bin(system.get("bin"))
    candidates = _mappluto_candidates(footprints)
    base_context = sorted({
        value.zfill(10)
        for footprint in footprints
        if (value := normalize_bbl(footprint.get("base_bbl")))
    })
    expected_prefix = BOROUGH_CODE_BY_NAME.get(_borough(system.get("borough")))
    canonical: str | None = None

    if not bin_value:
        status = "UNRESOLVED_NO_VALID_BIN"
    elif not footprints:
        status = "UNRESOLVED_NO_FOOTPRINT_MATCH"
    elif len(candidates) == 0:
        status = "UNRESOLVED_NO_MAPPLUTO_BBL"
    elif len(candidates) > 1:
        status = "UNRESOLVED_MULTIPLE_MAPPLUTO_BBLS"
    else:
        candidate = next(iter(candidates))
        if expected_prefix and candidate[0] != expected_prefix:
            status = "UNRESOLVED_BOROUGH_PREFIX_CONFLICT"
        else:
            status = "RECOVERED_EXACT_BIN_MAPPLUTO_BBL"
            canonical = candidate

    return {
        "canonical_bbl": canonical,
        "registry_bbl": None,
        "identity_basis": "BUILDING_FOOTPRINT_MAPPLUTO_BBL_EXACT_BIN" if canonical else "UNRESOLVED",
        "status": status,
        "source_dataset": "NYC_OTI_BUILDING_FOOTPRINTS" if footprints else None,
        "source_field": "mappluto_bbl" if footprints else None,
        "join_key": "BIN_EXACT" if bin_value else None,
        "mappluto_bbl_candidates": sorted(candidates),
        "base_bbl_context": base_context,
        "address_matching_used": False,
        "fuzzy_matching_used": False,
    }


def apply_bbl_identity_recovery(
    systems: list[dict[str, Any]],
    footprints_by_bin: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    status_counts: Counter[str] = Counter()
    recovered_by_borough: Counter[str] = Counter()
    unresolved_by_borough: Counter[str] = Counter()
    source_bbl_count = 0
    recovered_count = 0
    unresolved_count = 0

    for system in systems:
        bin_value = normalize_bin(system.get("bin"))
        evidence = resolve_system_bbl_identity(system, footprints_by_bin.get(bin_value or "", []))
        system["registry_bbl"] = evidence["registry_bbl"]
        system["bbl"] = evidence["canonical_bbl"]
        system["bbl_identity_basis"] = evidence["identity_basis"]
        system["bbl_identity_status"] = evidence["status"]
        system["bbl_identity_evidence"] = evidence
        status_counts[evidence["status"]] += 1

        borough = _borough(system.get("borough")) or "UNKNOWN"
        if evidence["status"] == "REGISTRY_SOURCE_BBL":
            source_bbl_count += 1
        elif evidence["status"] == "RECOVERED_EXACT_BIN_MAPPLUTO_BBL":
            recovered_count += 1
            recovered_by_borough[borough] += 1
        else:
            unresolved_count += 1
            unresolved_by_borough[borough] += 1

    return {
        "system_count": len(systems),
        "registry_source_bbl_count": source_bbl_count,
        "recovered_bbl_count": recovered_count,
        "canonical_bbl_count": source_bbl_count + recovered_count,
        "unresolved_bbl_count": unresolved_count,
        "status_counts": dict(sorted(status_counts.items())),
        "recovered_by_borough": dict(sorted(recovered_by_borough.items())),
        "unresolved_by_borough": dict(sorted(unresolved_by_borough.items())),
        "recovery_contract": {
            "join_key": "BIN_EXACT",
            "recovery_field": "NYC_OTI_BUILDING_FOOTPRINTS.mappluto_bbl",
            "unique_candidate_required": True,
            "borough_prefix_reconciliation_required": True,
            "address_matching_used": False,
            "fuzzy_matching_used": False,
            "registry_bbl_overwrite_allowed": False,
            "base_bbl_role": "PHYSICAL_TAX_LOT_CONTEXT_ONLY",
        },
    }
