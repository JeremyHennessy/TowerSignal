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
    registry_bbl = registry_bbl.zfill(10) if registry_bbl else None
    bin_value = normalize_bin(system.get("bin"))
    candidates = _mappluto_candidates(footprints)
    base_context = sorted({
        value.zfill(10)
        for footprint in footprints
        if (value := normalize_bbl(footprint.get("base_bbl")))
    })
    expected_prefix = BOROUGH_CODE_BY_NAME.get(_borough(system.get("borough")))
    canonical: str | None = None
    source_dataset: str | None = None
    source_field: str | None = None
    join_key: str | None = "BIN_EXACT" if bin_value else None
    reconciliation_required = False

    if registry_bbl:
        canonical = registry_bbl
        source_dataset = "NYC_COOLING_TOWER_REGISTRATIONS"
        source_field = "bbl"
        identity_basis = "REGISTRY_SOURCE_BBL"
        status = "REGISTRY_SOURCE_BBL"

        if bin_value and footprints and len(candidates) == 1:
            candidate = next(iter(candidates))
            if expected_prefix and candidate[0] != expected_prefix:
                status = "REGISTRY_SOURCE_BBL_MAPPLUTO_BOROUGH_CONFLICT"
            elif candidate == registry_bbl:
                status = "REGISTRY_SOURCE_BBL_CONFIRMED_BY_EXACT_BIN_MAPPLUTO"
            elif registry_bbl in base_context:
                # NYC Building Footprints explicitly bridges the registry/base lot to
                # one current MapPLUTO tax lot for this exact BIN. Preserve the
                # registry value as provenance, but use the current property lot for
                # property-level enrichment.
                canonical = candidate
                identity_basis = "REGISTRY_BASE_BBL_TO_MAPPLUTO_BBL_EXACT_BIN"
                status = "RECONCILED_REGISTRY_BASE_TO_MAPPLUTO_BBL"
                source_dataset = "NYC_OTI_BUILDING_FOOTPRINTS"
                source_field = "mappluto_bbl"
                reconciliation_required = True
            else:
                status = "REGISTRY_SOURCE_BBL_MAPPLUTO_CONFLICT"
        elif bin_value and footprints and len(candidates) > 1:
            status = "REGISTRY_SOURCE_BBL_MULTIPLE_MAPPLUTO_BBLS"
        elif bin_value and footprints and len(candidates) == 0:
            status = "REGISTRY_SOURCE_BBL_NO_MAPPLUTO_BBL"
    else:
        identity_basis = "UNRESOLVED"
        source_dataset = None
        source_field = None
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
                identity_basis = "BUILDING_FOOTPRINT_MAPPLUTO_BBL_EXACT_BIN"
                source_dataset = "NYC_OTI_BUILDING_FOOTPRINTS"
                source_field = "mappluto_bbl"

    aliases = sorted({value for value in (canonical, registry_bbl) if value})

    return {
        "canonical_bbl": canonical,
        "property_bbl": canonical,
        "registry_bbl": registry_bbl,
        "bbl_aliases": aliases,
        "identity_basis": identity_basis,
        "status": status,
        "source_dataset": source_dataset,
        "source_field": source_field,
        "join_key": join_key,
        "mappluto_bbl_candidates": sorted(candidates),
        "base_bbl_context": base_context,
        "registry_base_bridge_confirmed": bool(
            registry_bbl
            and len(candidates) == 1
            and registry_bbl in base_context
            and next(iter(candidates)) != registry_bbl
        ),
        "reconciliation_required": reconciliation_required,
        "address_matching_used": False,
        "fuzzy_matching_used": False,
    }


def apply_bbl_identity_recovery(
    systems: list[dict[str, Any]],
    footprints_by_bin: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    status_counts: Counter[str] = Counter()
    recovered_by_borough: Counter[str] = Counter()
    reconciled_by_borough: Counter[str] = Counter()
    unresolved_by_borough: Counter[str] = Counter()
    source_bbl_count = 0
    recovered_count = 0
    reconciled_count = 0
    unresolved_count = 0
    conflict_count = 0

    for system in systems:
        bin_value = normalize_bin(system.get("bin"))
        evidence = resolve_system_bbl_identity(system, footprints_by_bin.get(bin_value or "", []))
        system["registry_bbl"] = evidence["registry_bbl"]
        system["property_bbl"] = evidence["property_bbl"]
        system["bbl_aliases"] = evidence["bbl_aliases"]
        system["bbl"] = evidence["canonical_bbl"]
        system["bbl_identity_basis"] = evidence["identity_basis"]
        system["bbl_identity_status"] = evidence["status"]
        system["bbl_identity_evidence"] = evidence
        status_counts[evidence["status"]] += 1

        borough = _borough(system.get("borough")) or "UNKNOWN"
        if evidence["status"] in {
            "REGISTRY_SOURCE_BBL",
            "REGISTRY_SOURCE_BBL_CONFIRMED_BY_EXACT_BIN_MAPPLUTO",
            "REGISTRY_SOURCE_BBL_NO_MAPPLUTO_BBL",
        }:
            source_bbl_count += 1
        elif evidence["status"] == "RECONCILED_REGISTRY_BASE_TO_MAPPLUTO_BBL":
            source_bbl_count += 1
            reconciled_count += 1
            reconciled_by_borough[borough] += 1
        elif evidence["status"] == "RECOVERED_EXACT_BIN_MAPPLUTO_BBL":
            recovered_count += 1
            recovered_by_borough[borough] += 1
        elif evidence["canonical_bbl"] is None:
            unresolved_count += 1
            unresolved_by_borough[borough] += 1
        else:
            # A registry BBL remains usable for provenance/enrichment when an
            # exact-BIN MapPLUTO relationship is ambiguous or conflicts, but the
            # disagreement must stay explicit for audit/review.
            source_bbl_count += 1
            conflict_count += 1

        # Fail closed on the exact defect this resolver is designed to prevent:
        # a registry/base BBL bridged by exact BIN to exactly one different
        # MapPLUTO lot must always use that MapPLUTO lot as property identity.
        if evidence["registry_base_bridge_confirmed"]:
            candidates = evidence["mappluto_bbl_candidates"]
            if (
                evidence["status"] != "RECONCILED_REGISTRY_BASE_TO_MAPPLUTO_BBL"
                or len(candidates) != 1
                or evidence["canonical_bbl"] != candidates[0]
            ):
                raise RuntimeError(
                    f"Exact-BIN registry/base-to-MapPLUTO bridge was not reconciled for system "
                    f"{system.get('system_id')}: {evidence}"
                )

    return {
        "system_count": len(systems),
        "registry_source_bbl_count": source_bbl_count,
        "reconciled_registry_bbl_count": reconciled_count,
        "recovered_bbl_count": recovered_count,
        "canonical_bbl_count": sum(1 for system in systems if normalize_bbl(system.get("bbl")) is not None),
        "unresolved_bbl_count": unresolved_count,
        "explicit_conflict_count": conflict_count,
        "status_counts": dict(sorted(status_counts.items())),
        "reconciled_by_borough": dict(sorted(reconciled_by_borough.items())),
        "recovered_by_borough": dict(sorted(recovered_by_borough.items())),
        "unresolved_by_borough": dict(sorted(unresolved_by_borough.items())),
        "recovery_contract": {
            "join_key": "BIN_EXACT",
            "recovery_field": "NYC_OTI_BUILDING_FOOTPRINTS.mappluto_bbl",
            "unique_candidate_required": True,
            "borough_prefix_reconciliation_required": True,
            "address_matching_used": False,
            "fuzzy_matching_used": False,
            "registry_bbl_preserved_as_provenance": True,
            "historical_bbl_aliases": "Canonical property BBL plus distinct registry/base BBL; aliases are exact identifiers, never fuzzy matches.",
            "registry_bbl_reconciliation_rule": (
                "When the exact-BIN footprint has one MapPLUTO BBL, the registry BBL "
                "equals footprint base_bbl, and the MapPLUTO BBL differs, use the "
                "MapPLUTO BBL as current property identity while preserving registry_bbl."
            ),
            "base_bbl_role": "REGISTRY_OR_PHYSICAL_BASE_LOT_CONTEXT",
        },
    }

