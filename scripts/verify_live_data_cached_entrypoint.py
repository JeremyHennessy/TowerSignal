from __future__ import annotations

import argparse
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any, Iterable

import verify_live_data_live as baseline
from towersignal.oath import normalize_ticket_number
from towersignal.oath_cache import validate_cache

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OATH_CACHE = ROOT / ".history-store/data/history/oath-cache.json.gz"


def verify(
    systems_path: Path,
    details_dir: Path,
    output: Path,
    sample_size: int,
    oath_cache: Path | None = None,
) -> None:
    if oath_cache is None:
        baseline.verify(systems_path, details_dir, output, sample_size)
        return

    cache_result = validate_cache(oath_cache, require_production_volume=True)
    cached_cases = cache_result["cases_by_ticket"]
    original_fetch = baseline.fetch_oath_cases

    def cached_fetch(ticket_values: Iterable[Any]):
        requested = {
            ticket
            for value in ticket_values
            if (ticket := normalize_ticket_number(value))
        }
        return (
            {ticket: cached_cases[ticket] for ticket in requested if ticket in cached_cases},
            {"verification_source": "verified_durable_oath_cache"},
        )

    baseline.fetch_oath_cases = cached_fetch
    try:
        captured = io.StringIO()
        with redirect_stdout(captured):
            baseline.verify(systems_path, details_dir, output, sample_size)
    finally:
        baseline.fetch_oath_cases = original_fetch

    report = json.loads(output.read_text(encoding="utf-8"))
    report["method"] = (
        "Deterministic random sample seeded from snapshot timestamp; registration, inspection, HPD, "
        "planimetric and building-footprint fields independently re-queried from current NYC sources; "
        "OATH exact-ticket fields verified against the production-validated durable OATH cache."
    )
    report["oath_verification_source"] = {
        "type": "verified_durable_cache",
        "generated_at": cache_result["cache"].get("generated_at"),
        "age_days": round(float(cache_result["age_days"]), 4),
        "ticket_universe_count": cache_result["ticket_universe"]["count"],
        "ticket_universe_sha256": cache_result["ticket_universe"]["sha256"],
    }
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--systems", type=Path, default=ROOT / "public/data/systems.json")
    parser.add_argument("--details", type=Path, default=ROOT / "public/data/details")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data/verification.json")
    parser.add_argument("--sample-size", type=int, default=5)
    parser.add_argument(
        "--oath-cache",
        type=Path,
        default=DEFAULT_OATH_CACHE if DEFAULT_OATH_CACHE.exists() else None,
        help="Verified durable OATH cache. Pages auto-detects the durable history checkout.",
    )
    args = parser.parse_args()
    verify(args.systems, args.details, args.output, args.sample_size, args.oath_cache)


if __name__ == "__main__":
    main()
