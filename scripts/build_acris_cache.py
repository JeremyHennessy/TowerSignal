from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.acris import build_recent_cache, normalize_bbl, validate_cache_file  # noqa: E402


def tower_bbls_from_snapshot(path: Path) -> set[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    systems = payload.get("systems") if isinstance(payload, dict) else None
    if not isinstance(systems, list):
        systems = payload.get("observations") if isinstance(payload, dict) else None
    if not isinstance(systems, list):
        raise RuntimeError(f"Tower history snapshot is missing systems: {path}")
    bbls = {bbl for row in systems if isinstance(row, dict) and (bbl := normalize_bbl(row.get("bbl"))) is not None}
    if len(bbls) < 1000:
        raise RuntimeError(f"Refusing to build production ACRIS cache from only {len(bbls):,} usable BBLs")
    return bbls


def build(tower_snapshot: Path, output: Path) -> dict:
    bbls = tower_bbls_from_snapshot(tower_snapshot)
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
    parser.add_argument("--tower-snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.tower_snapshot, args.output)


if __name__ == "__main__":
    main()
