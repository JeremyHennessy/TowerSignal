from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_coverage_audit import build as build_coverage_audit
from validate_coverage_audit import validate as validate_coverage_audit

HARD_MAX_BYTES = 8 * 1024 * 1024
GROWTH_RATIO_LIMIT = 1.75
GROWTH_ABSOLUTE_ALLOWANCE = 1 * 1024 * 1024


def validate_history_size(current_path: Path, previous_path: Path | None = None) -> dict[str, int | float | None]:
    if not current_path.exists():
        raise RuntimeError(f"NYS history snapshot missing: {current_path}")
    current_size = current_path.stat().st_size
    if current_size <= 0:
        raise RuntimeError("NYS history snapshot is empty")
    if current_size > HARD_MAX_BYTES:
        raise RuntimeError(
            f"NYS history snapshot {current_size:,} bytes exceeds hard ceiling {HARD_MAX_BYTES:,} bytes"
        )

    previous_size = None
    growth_ratio = None
    if previous_path and previous_path.exists():
        previous_size = previous_path.stat().st_size
        if previous_size > 0:
            growth_ratio = current_size / previous_size
            if (
                previous_size <= HARD_MAX_BYTES
                and current_size > previous_size + GROWTH_ABSOLUTE_ALLOWANCE
                and growth_ratio > GROWTH_RATIO_LIMIT
            ):
                raise RuntimeError(
                    "NYS history snapshot growth anomaly: "
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


def build_release_coverage_audit(current_path: Path) -> dict | None:
    # Normal Pages passes public/data/history/nys/latest.json. Keep unit/history-only
    # callers unaffected by requiring the generated product spine before auditing.
    try:
        output_dir = current_path.parents[2]
    except IndexError:
        return None
    if not (output_dir / "systems.json").exists() or not (output_dir / "source-health.json").exists():
        return None

    report = build_coverage_audit(output_dir)
    validate_coverage_audit(report)
    print(json.dumps({
        "coverage_audit": "validated",
        "report": str(output_dir / "coverage-audit.json"),
        "standardized_sources": len(report.get("standardized_coverage_sources") or []),
        "source_artifacts": len(report.get("source_artifacts") or []),
    }, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate TowerSignal NYS durable history size")
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--previous", type=Path)
    args = parser.parse_args()
    validate_history_size(args.current, args.previous)
    build_release_coverage_audit(args.current)


if __name__ == "__main__":
    main()
