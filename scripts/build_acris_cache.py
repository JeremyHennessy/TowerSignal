from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.acris import build_recent_cache, normalize_bbl, validate_cache_file  # noqa: E402
from towersignal.fetch import fetch_dataset  # noqa: E402
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


def tower_bbls_from_current_registrations() -> set[str]:
    snapshot = fetch_dataset(REGISTRATION_DATASET_ID, "system_id")
    systems, _ = normalize_registrations(snapshot.rows)
    if len(systems) < 3500:
        raise RuntimeError(
            f"Refusing to build production ACRIS cache from only {len(systems):,} normalized current systems"
        )
    return _tower_bbls(systems, f"current NYC registry {REGISTRATION_DATASET_ID}")


def build(tower_snapshot: Path | None, output: Path) -> dict:
    bbls = tower_bbls_from_snapshot(tower_snapshot) if tower_snapshot else tower_bbls_from_current_registrations()
    cache = build_recent_cache(bbls)
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
