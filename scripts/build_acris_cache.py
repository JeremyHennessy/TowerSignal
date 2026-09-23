from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.acris import build_recent_cache, normalize_bbl, validate_cache_file  # noqa: E402
from towersignal.bbl_identity import apply_bbl_identity_recovery  # noqa: E402
from towersignal.building_footprints import fetch_building_footprints_by_bin  # noqa: E402
from towersignal.fetch import fetch_dataset  # noqa: E402
from towersignal.hpd_identity import fetch_registration_snapshot  # noqa: E402
from towersignal.acris_identity_cache import property_targets as build_property_targets, graph_digest  # noqa: E402
from towersignal.normalize import normalize_registrations  # noqa: E402

REGISTRATION_DATASET_ID = "y4fw-iqfr"


def _tower_bbls(systems: list[dict[str, Any]], source: str) -> set[str]:
    bbls = {bbl for row in systems if (bbl := normalize_bbl(row.get("bbl"))) is not None}
    if len(bbls) < 1000:
        raise RuntimeError(f"Refusing to build production ACRIS cache from only {len(bbls):,} usable BBLs in {source}")
    return bbls


def tower_bbls_from_snapshot(path: Path) -> set[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    systems = payload.get("systems") if isinstance(payload, dict) else None
    if not isinstance(systems, list):
        systems = payload.get("observations") if isinstance(payload, dict) else None
    if not isinstance(systems, list):
        raise RuntimeError(f"Tower history snapshot is missing systems: {path}")
    return _tower_bbls([row for row in systems if isinstance(row, dict)], str(path))


def reconciled_current_systems() -> list[dict[str, Any]]:
    snapshot = fetch_dataset(REGISTRATION_DATASET_ID, "system_id")
    systems, _ = normalize_registrations(snapshot.rows)
    if len(systems) < 3500:
        raise RuntimeError(
            f"Refusing to build production ACRIS cache from only {len(systems):,} normalized current systems"
        )

    bins = {str(system.get("bin")) for system in systems if system.get("bin")}
    footprints_by_bin, _ = fetch_building_footprints_by_bin(bins)
    hpd_index = fetch_registration_snapshot()
    identity_meta = apply_bbl_identity_recovery(systems, footprints_by_bin, hpd_index["eligible_by_bin"])
    if identity_meta["canonical_bbl_count"] < 1000:
        raise RuntimeError(
            "Refusing to build ACRIS cache from an implausibly small reconciled property-BBL universe"
        )
    return systems


def property_targets_from_systems(systems: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return build_property_targets(systems)


def tower_bbls_from_current_registrations() -> set[str]:
    systems = reconciled_current_systems()
    return _tower_bbls(
        systems,
        f"current NYC registry {REGISTRATION_DATASET_ID} after exact-BIN property-BBL reconciliation",
    )


def build(tower_snapshot: Path | None, output: Path) -> dict:
    if tower_snapshot:
        bbls = tower_bbls_from_snapshot(tower_snapshot)
        payload = json.loads(tower_snapshot.read_text(encoding="utf-8"))
        property_targets = property_targets_from_systems(payload.get("systems") or payload.get("observations") or [])
    else:
        systems = reconciled_current_systems()
        bbls = _tower_bbls(
            systems,
            f"current NYC registry {REGISTRATION_DATASET_ID} after exact-BIN property-BBL reconciliation",
        )
        property_targets = property_targets_from_systems(systems)
    cache = build_recent_cache(bbls, property_targets=property_targets)
    cache["mapping_property_graph_sha256"] = graph_digest(property_targets)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(cache, separators=(",", ":")), encoding="utf-8")
    result = validate_cache_file(output, require_production_volume=True)
    metrics = cache["metrics"]
    print(json.dumps({
        "cache_bytes": result["size_bytes"],
        "requested_tower_bbl_count": metrics["requested_tower_bbl_count"],
        "tower_bbls_with_recent_relevant_acris": metrics["tower_bbls_with_recent_relevant_acris"],
        "matched_recent_document_count": metrics["matched_recent_document_count"],
        "party_row_count": metrics["party_row_count"],
        "alias_bbl_document_link_count": metrics.get("alias_bbl_document_link_count", 0),
        "condo_address_document_link_count": metrics.get("condo_address_document_link_count", 0),
        "condo_rollup_property_count": metrics.get("condo_rollup_property_count", 0),
        "total_seconds": metrics["total_seconds"],
    }, indent=2))
    return cache


def main() -> None:
    parser = argparse.ArgumentParser(description="Build verified bounded ACRIS cache for TowerSignal")
    parser.add_argument(
        "--tower-snapshot",
        type=Path,
        help="Optional historical snapshot override. By default the current NYC registrations feed defines the cache universe.",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.tower_snapshot, args.output)


if __name__ == "__main__":
    main()
