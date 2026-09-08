from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.fetch import fetch_dataset  # noqa: E402
from towersignal.inspections import aggregate_inspections  # noqa: E402
from towersignal.normalize import normalize_registrations  # noqa: E402
from towersignal.oath import fetch_oath_cases, summons_numbers_from_inspections  # noqa: E402
from towersignal.oath_cache import build_cache_payload, validate_cache, write_cache  # noqa: E402
from towersignal.validate import validate_normalized, validate_sources  # noqa: E402

REGISTRATION_ID = "y4fw-iqfr"
INSPECTION_ID = "f9wb-g8mb"


def build(output: Path) -> dict:
    registration_snapshot = fetch_dataset(REGISTRATION_ID, "system_id")
    inspection_snapshot = fetch_dataset(INSPECTION_ID, "system_id,inspection_date")
    validate_sources(registration_snapshot.rows, inspection_snapshot.rows)

    systems, _ = normalize_registrations(registration_snapshot.rows)
    snapshot_date = datetime.now(ZoneInfo("America/New_York")).date()
    validate_normalized(systems, snapshot_date)

    inspections_by_system = aggregate_inspections(inspection_snapshot.rows)
    current_system_ids = {str(system["system_id"]) for system in systems}
    current_inspections = {
        system_id: inspections_by_system.get(system_id, [])
        for system_id in current_system_ids
    }
    tickets = summons_numbers_from_inspections(current_inspections)
    print(
        f"[oath-cache-refresh] current systems={len(current_system_ids):,} "
        f"summons={len(tickets):,}",
        flush=True,
    )

    cases, oath_metadata = fetch_oath_cases(tickets)
    payload = build_cache_payload(
        inspection_snapshot=inspection_snapshot,
        requested_tickets=tickets,
        cases_by_ticket=cases,
        oath_metadata=oath_metadata,
    )
    write_cache(output, payload)
    result = validate_cache(
        output,
        max_age_days=0.25,
        require_production_volume=True,
        current_tickets=tickets,
    )
    summary = {
        "status": result["status"],
        "system_count": len(current_system_ids),
        "requested_ticket_count": result["ticket_universe"]["count"],
        "matched_ticket_count": len(result["cases_by_ticket"]),
        "match_ratio": result["match_ratio"],
        "size_bytes": result["size_bytes"],
    }
    print(json.dumps(summary, indent=2), flush=True)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a verified durable OATH lifecycle cache")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.output)


if __name__ == "__main__":
    main()
