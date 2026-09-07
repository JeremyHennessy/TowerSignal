from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.history_store import HISTORY_STORAGE_VERSION, validate_segmented_storage  # noqa: E402

HARD_MAX_BYTES = 25 * 1024 * 1024
GROWTH_RATIO_LIMIT = 1.75
GROWTH_ABSOLUTE_ALLOWANCE = 2 * 1024 * 1024


def _is_segmented_manifest(path: Path) -> bool:
    with path.open("rb") as handle:
        prefix = handle.read(8192)
    marker_compact = f'"history_storage_version":"{HISTORY_STORAGE_VERSION}"'.encode()
    marker_spaced = f'"history_storage_version": "{HISTORY_STORAGE_VERSION}"'.encode()
    return marker_compact in prefix or marker_spaced in prefix


def validate_history_size(current_path: Path, previous_path: Path | None = None) -> dict[str, Any]:
    if not current_path.exists():
        raise RuntimeError(f"History snapshot missing: {current_path}")

    current_size = current_path.stat().st_size
    if current_size <= 0:
        raise RuntimeError("History snapshot is empty")

    if _is_segmented_manifest(current_path):
        result = validate_segmented_storage(current_path, previous_path)
        result["manifest_bytes"] = current_size
        result["legacy_hard_max_bytes"] = HARD_MAX_BYTES
        print(json.dumps(result, indent=2))
        return result

    if current_size > HARD_MAX_BYTES:
        raise RuntimeError(
            f"History snapshot {current_size:,} bytes exceeds hard ceiling {HARD_MAX_BYTES:,} bytes"
        )

    previous_size = None
    growth_ratio = None
    if previous_path and previous_path.exists():
        previous_size = previous_path.stat().st_size
        if previous_size > 0:
            growth_ratio = current_size / previous_size
            # A migration from an oversized prior schema is allowed to shrink freely.
            # Once the prior store itself is below the hard ceiling, large growth is anomalous.
            if (
                previous_size <= HARD_MAX_BYTES
                and current_size > previous_size + GROWTH_ABSOLUTE_ALLOWANCE
                and growth_ratio > GROWTH_RATIO_LIMIT
            ):
                raise RuntimeError(
                    "History snapshot growth anomaly: "
                    f"{previous_size:,} -> {current_size:,} bytes ({growth_ratio:.2f}x)"
                )

    result = {
        "current_bytes": current_size,
        "previous_bytes": previous_size,
        "growth_ratio": growth_ratio,
        "hard_max_bytes": HARD_MAX_BYTES,
    }
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate TowerSignal durable history snapshot size")
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--previous", type=Path)
    args = parser.parse_args()
    validate_history_size(args.current, args.previous)


if __name__ == "__main__":
    main()