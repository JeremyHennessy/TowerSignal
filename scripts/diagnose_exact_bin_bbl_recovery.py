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
BOROUGH_CODE_BY_NAME = {
    "MANHATTAN": "1",
    "BRONX": "2",
    "BROOKLYN": "3",
    "QUEENS": "4",
    "STATEN ISLAND": "5",
}


def _borough(value: Any) -> str:
    text = str(value or "UNKNOWN").strip().upper() or "UNKNOWN"
    aliases = {
        "MN": "MANHATTAN",
        "BX": "BRONX",
        "BK": "BROOKLYN",
        "QN": "QUEENS",
        "SI": "STATEN ISLAND",
        "STATEN ISLAND / RICHMOND": "STATEN ISLAND",
    }
    return aliases.get(text, text)


def _footprint_bbl_candidates(footprints: list[dict[str, Any]]) -> set[str]:
    candidates: set[str] = set()
    for footprint in footprints:
        for field in ("base_bbl", "mappluto_bbl"):
            value = normalize_bbl(footprint.get(field))
            if value:
                candidates.add(value.zfill(10))
    return candidates


def classify_recovery(
    system: dict[str, Any], footprints: list[dict[str, Any]]
) -> dict[str, Any]:
    borough = _borough(system.get("borough"))
    bin_value = normalize_bin(system.get("bin"))
    candidates = _footprint_bbl_candidates(footprints)
    expected_prefix = BOROUGH_CODE_BY_NAME.get(borough)

    if not bin_value:
        status = "NO_VALID_BIN"
    elif not footprints:
        status = "NO_FOOTPRINT_MATCH"
    elif not candidates:
        status = "NO_PUBLISHED_FOOTPRINT_BBL"
    elif len(candidates) > 1:
        status = "CONFLICTING_FOOTPRINT_BBLS"
    else:
        candidate = next(iter(candidates))
        if expected_prefix and candidate[0] != expected_prefix:
            status = "BOROUGH_PREFIX_CONFLICT"
        else:
            status = "UNAMBIGUOUS_EXACT_BIN_RECOVERY"

    return {
        "system_id": system.get("system_id"),
        "borough": borough,
        "bin": bin_value,
        "address": system.get("address"),
        "status": status,
        "candidate_bbls": sorted(candidates),
        "footprint_feature_count": len(footprints),
        "evidence_basis": "NYC_OTI_BUILDING_FOOTPRINTS; BIN_EXACT; PUBLISHED_BASE_BBL_OR_MAPPLUTO_BBL",
    }


def build_report(
    systems: list[dict[str, Any]], footprints_by_bin: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    missing_bbl = [system for system in systems if not normalize_bbl(system.get("bbl"))]
    rows: list[dict[str, Any]] = []
    for system in missing_bbl:
        bin_value = normalize_bin(system.get("bin"))
        rows.append(classify_recovery(system, footprints_by_bin.get(bin_value or "", [])))

    status_counts = Counter(row["status"] for row in rows)
    borough_status: dict[str, Counter[str]] = {}
    for row in rows:
        borough_status.setdefault(row["borough"], Counter())[row["status"]] += 1

    recoverable = [row for row in rows if row["status"] == "UNAMBIGUOUS_EXACT_BIN_RECOVERY"]
    unresolved = [row for row in rows if row["status"] != "UNAMBIGUOUS_EXACT_BIN_RECOVERY"]
    return {
        "missing_registry_bbl_system_count": len(rows),
        "unambiguous_exact_bin_recovery_count": len(recoverable),
        "unresolved_count": len(unresolved),
        "recovery_percentage": round(len(recoverable) / len(rows) * 100.0, 2) if rows else 100.0,
        "status_counts": dict(sorted(status_counts.items())),
        "borough_status": {
            borough: dict(sorted(counts.items()))
            for borough, counts in sorted(borough_status.items())
        },
        "recoverable_examples": recoverable[:50],
        "unresolved_examples": unresolved[:100],
        "identity_contract": {
            "join_key": "BIN_EXACT",
            "recovery_value": "UNIQUE_PUBLISHED_BUILDING_FOOTPRINT_BASE_BBL_OR_MAPPLUTO_BBL",
            "address_matching_used": False,
            "fuzzy_matching_used": False,
            "borough_prefix_must_reconcile": True,
            "conflicts_remain_unresolved": True,
        },
        "recommendation": {
            "production_identity_repair_candidate": bool(recoverable),
            "priority_score_change": False,
            "ui_change": False,
            "rule": (
                "Promote only UNAMBIGUOUS_EXACT_BIN_RECOVERY rows into canonical BBL identity. "
                "Never choose among conflicting footprint BBLs and never substitute address matching."
            ),
        },
    }


def run(output: Path) -> dict[str, Any]:
    registration = fetch_dataset(REGISTRATION_DATASET_ID, "system_id")
    systems, dedupe = normalize_registrations(registration.rows)
    missing_bins = {
        bin_value
        for system in systems
        if not normalize_bbl(system.get("bbl"))
        and (bin_value := normalize_bin(system.get("bin")))
    }
    footprints, footprint_meta = fetch_building_footprints_by_bin(missing_bins)
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
        "summary": build_report(systems, footprints),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose exact-BIN recovery of missing cooling-tower registry BBLs")
    parser.add_argument("--output", type=Path, default=Path("exact-bin-bbl-recovery.json"))
    args = parser.parse_args()
    run(args.output)


if __name__ == "__main__":
    main()
