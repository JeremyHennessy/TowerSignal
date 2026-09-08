from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import build_data_live as baseline
from towersignal.oath import summons_numbers_from_inspections
from towersignal.oath_cache_consumer import cases_and_metadata_for_current_tickets

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OATH_CACHE = ROOT / ".history-store/data/history/oath-cache.json.gz"


def current_registered_system_summons(
    inspections_by_system: dict[str, list[dict[str, Any]]],
    current_system_ids: set[str],
) -> set[str]:
    scoped = {
        system_id: inspections_by_system.get(system_id, [])
        for system_id in current_system_ids
    }
    return summons_numbers_from_inspections(scoped)


def build(output_dir: Path, oath_cache: Path | None = None) -> dict:
    if oath_cache is None:
        return baseline.build(output_dir)

    current_system_ids: set[str] = set()
    original_normalize = baseline.normalize_registrations
    original_summons = baseline.summons_numbers_from_inspections
    original_fetch = baseline.fetch_oath_cases

    def capture_current_systems(rows):
        systems, metadata = original_normalize(rows)
        current_system_ids.clear()
        current_system_ids.update(str(system["system_id"]) for system in systems)
        return systems, metadata

    def scoped_summons(inspections_by_system):
        return current_registered_system_summons(inspections_by_system, current_system_ids)

    def cached_oath(tickets):
        cases, metadata, _ = cases_and_metadata_for_current_tickets(oath_cache, tickets)
        return cases, metadata

    baseline.normalize_registrations = capture_current_systems
    baseline.summons_numbers_from_inspections = scoped_summons
    baseline.fetch_oath_cases = cached_oath
    try:
        baseline.progress(f"Using verified durable OATH cache: {oath_cache}")
        return baseline.build(output_dir)
    finally:
        baseline.normalize_registrations = original_normalize
        baseline.summons_numbers_from_inspections = original_summons
        baseline.fetch_oath_cases = original_fetch


def main() -> None:
    parser = argparse.ArgumentParser(description="Build TowerSignal static NYC data")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data")
    parser.add_argument(
        "--oath-cache",
        type=Path,
        default=DEFAULT_OATH_CACHE if DEFAULT_OATH_CACHE.exists() else None,
        help="Verified durable OATH cache. Pages auto-detects the durable history checkout.",
    )
    args = parser.parse_args()
    build(args.output, args.oath_cache)


if __name__ == "__main__":
    main()
