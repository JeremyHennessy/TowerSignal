from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.building_footprints import fetch_building_footprints_by_bin  # noqa: E402
from towersignal.fetch import fetch_dataset  # noqa: E402
from towersignal.normalize import normalize_registrations  # noqa: E402
from towersignal.planimetrics import normalize_bin  # noqa: E402
from towersignal.pluto import normalize_bbl  # noqa: E402

REGISTRATION_DATASET_ID = "y4fw-iqfr"


def _norm_bbl(value: Any) -> str | None:
    bbl = normalize_bbl(value)
    return bbl.zfill(10) if bbl else None


def _values(footprints: list[dict[str, Any]], field: str) -> set[str]:
    return {
        value
        for footprint in footprints
        if (value := _norm_bbl(footprint.get(field)))
    }


def classify_known_bbl(system: dict[str, Any], footprints: list[dict[str, Any]]) -> dict[str, Any]:
    registry_bbl = _norm_bbl(system.get("bbl"))
    bin_value = normalize_bin(system.get("bin"))
    base_values = _values(footprints, "base_bbl")
    map_values = _values(footprints, "mappluto_bbl")
    base_match = bool(registry_bbl and registry_bbl in base_values)
    map_match = bool(registry_bbl and registry_bbl in map_values)

    if not footprints:
        status = "NO_FOOTPRINT_MATCH"
    elif base_match and map_match:
        status = "REGISTRY_MATCHES_BOTH"
    elif base_match:
        status = "REGISTRY_MATCHES_BASE_BBL_ONLY"
    elif map_match:
        status = "REGISTRY_MATCHES_MAPPLUTO_BBL_ONLY"
    else:
        status = "REGISTRY_MATCHES_NEITHER"

    return {
        "system_id": system.get("system_id"),
        "borough": system.get("borough"),
        "bin": bin_value,
        "registry_bbl": registry_bbl,
        "status": status,
        "base_bbls": sorted(base_values),
        "mappluto_bbls": sorted(map_values),
        "footprint_feature_count": len(footprints),
    }


def build_calibration(
    systems: list[dict[str, Any]], footprints_by_bin: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    known = [system for system in systems if _norm_bbl(system.get("bbl"))]
    rows = [
        classify_known_bbl(system, footprints_by_bin.get(normalize_bin(system.get("bin")) or "", []))
        for system in known
    ]
    counts = Counter(row["status"] for row in rows)
    by_borough: dict[str, Counter[str]] = {}
    for row in rows:
        borough = str(row.get("borough") or "UNKNOWN").upper()
        by_borough.setdefault(borough, Counter())[row["status"]] += 1

    footprint_rows = [row for row in rows if row["status"] != "NO_FOOTPRINT_MATCH"]
    base_matches = sum(
        1 for row in footprint_rows
        if row["status"] in {"REGISTRY_MATCHES_BOTH", "REGISTRY_MATCHES_BASE_BBL_ONLY"}
    )
    map_matches = sum(
        1 for row in footprint_rows
        if row["status"] in {"REGISTRY_MATCHES_BOTH", "REGISTRY_MATCHES_MAPPLUTO_BBL_ONLY"}
    )
    footprint_count = len(footprint_rows)

    neither = [row for row in rows if row["status"] == "REGISTRY_MATCHES_NEITHER"]
    base_only = [row for row in rows if row["status"] == "REGISTRY_MATCHES_BASE_BBL_ONLY"]
    map_only = [row for row in rows if row["status"] == "REGISTRY_MATCHES_MAPPLUTO_BBL_ONLY"]

    return {
        "known_registry_bbl_system_count": len(known),
        "systems_with_exact_bin_footprint": footprint_count,
        "systems_without_exact_bin_footprint": counts.get("NO_FOOTPRINT_MATCH", 0),
        "status_counts": dict(sorted(counts.items())),
        "base_bbl_matches_registry_count": base_matches,
        "base_bbl_match_percentage_when_footprint_present": round(base_matches / footprint_count * 100.0, 2) if footprint_count else 0.0,
        "mappluto_bbl_matches_registry_count": map_matches,
        "mappluto_bbl_match_percentage_when_footprint_present": round(map_matches / footprint_count * 100.0, 2) if footprint_count else 0.0,
        "borough_status": {
            borough: dict(sorted(status.items()))
            for borough, status in sorted(by_borough.items())
        },
        "base_only_examples": base_only[:50],
        "mappluto_only_examples": map_only[:50],
        "neither_examples": neither[:100],
        "decision_rule": {
            "prefer_base_bbl_if_calibrated": (
                "Only prefer published BASE_BBL for missing-registry-BBL recovery if it materially outperforms MapPLUTO BBL "
                "against systems whose registry BBL is already known, with mismatches explicitly retained for review."
            ),
            "no_address_matching": True,
            "no_fuzzy_matching": True,
            "does_not_modify_identity": True,
        },
    }


def run(output: Path) -> dict[str, Any]:
    registration = fetch_dataset(REGISTRATION_DATASET_ID, "system_id")
    systems, dedupe = normalize_registrations(registration.rows)
    known_bins = {
        bin_value
        for system in systems
        if _norm_bbl(system.get("bbl"))
        and (bin_value := normalize_bin(system.get("bin")))
    }
    footprints, footprint_meta = fetch_building_footprints_by_bin(known_bins)
    report = {
        "registration_source": {
            "dataset_id": registration.dataset_id,
            "name": registration.name,
            "source_record_count": registration.source_record_count,
            "source_last_updated_at": registration.source_last_updated_at,
            "retrieved_at": registration.retrieved_at,
            "dedupe": dedupe,
        },
        "footprint_source": footprint_meta,
        "calibration": build_calibration(systems, footprints),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["calibration"], indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate Building Footprints BBL fields against known cooling-tower registry BBLs")
    parser.add_argument("--output", type=Path, default=Path("footprint-bbl-calibration.json"))
    args = parser.parse_args()
    run(args.output)


if __name__ == "__main__":
    main()
