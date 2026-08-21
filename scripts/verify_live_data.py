from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.fetch import fetch_where  # noqa: E402
from towersignal.inspections import aggregate_inspections  # noqa: E402
from towersignal.normalize import normalize_registrations  # noqa: E402
from towersignal.oath import fetch_oath_cases  # noqa: E402

REGISTRATION_ID = "y4fw-iqfr"
INSPECTION_ID = "f9wb-g8mb"


def escape_soql(value: str) -> str:
    return value.replace("'", "''")


def detail_path(base: Path, system_id: str) -> Path:
    safe = "".join(ch for ch in system_id if ch.isalnum() or ch in ("-", "_"))
    return base / (safe[:2] or "xx").lower() / f"{safe}.json"


def verify(systems_path: Path, details_dir: Path, output: Path, sample_size: int) -> None:
    payload = json.loads(systems_path.read_text(encoding="utf-8"))
    systems = payload["systems"]
    seed = payload["metadata"]["generated_at"]
    rng = random.Random(seed)
    selected = rng.sample(systems, min(sample_size, len(systems)))
    results = []

    for displayed in selected:
        system_id = displayed["system_id"]
        where = f"system_id='{escape_soql(system_id)}'"
        registration_rows = fetch_where(REGISTRATION_ID, where, "system_id")
        normalized, _ = normalize_registrations(registration_rows)
        if len(normalized) != 1:
            raise RuntimeError(f"Verification expected one normalized registration for {system_id}; got {len(normalized)}")
        source = normalized[0]

        inspection_rows = fetch_where(INSPECTION_ID, where, "inspection_date")
        source_inspections = aggregate_inspections(inspection_rows).get(system_id, [])
        detail = json.loads(detail_path(details_dir, system_id).read_text(encoding="utf-8"))

        checks = {
            "system_id": displayed["system_id"] == source["system_id"],
            "address": displayed["address"] == source["address"],
            "active_equipment": displayed["active_equipment"] == source["active_equipment"],
            "public_sample_dates": detail["sample_history"]["dates"] == source["sample_dates"],
            "inspection_count": len(detail["inspection_history"]) == len(source_inspections),
            "violation_count": sum(item["violation_count"] for item in detail["inspection_history"]) == sum(item["violation_count"] for item in source_inspections),
        }
        if not all(checks.values()):
            raise RuntimeError(f"Live source comparison failed for {system_id}: {checks}")
        results.append({"system_id": system_id, "address": displayed["address"], "checks": checks, "result": "PASS"})

    oath_candidates = [system for system in systems if int(system.get("oath_case_count") or 0) > 0]
    oath_selected = rng.sample(oath_candidates, min(sample_size, len(oath_candidates)))
    oath_results = []
    for displayed in oath_selected:
        detail = json.loads(detail_path(details_dir, displayed["system_id"]).read_text(encoding="utf-8"))
        cases = detail.get("oath_case_history") or []
        if not cases:
            raise RuntimeError(f"Summary reports OATH cases but detail is empty for {displayed['system_id']}")
        generated_case = cases[0]
        ticket = generated_case["ticket_number"]
        live_cases, _ = fetch_oath_cases([ticket])
        live_case = live_cases.get(ticket)
        if live_case is None:
            raise RuntimeError(f"Exact OATH ticket {ticket} disappeared during verification")
        checks = {
            "ticket_number": live_case["ticket_number"] == generated_case["ticket_number"],
            "match_basis": generated_case["match_basis"] == "SUMMONS_NUMBER_EXACT",
            "hearing_status": live_case["hearing_status"] == generated_case["hearing_status"],
            "hearing_result": live_case["hearing_result"] == generated_case["hearing_result"],
            "decision_date": live_case["decision_date"] == generated_case["decision_date"],
            "penalty_imposed": live_case["penalty_imposed"] == generated_case["penalty_imposed"],
            "paid_amount": live_case["paid_amount"] == generated_case["paid_amount"],
            "balance_due": live_case["balance_due"] == generated_case["balance_due"],
        }
        if not all(checks.values()):
            raise RuntimeError(f"Live OATH comparison failed for {ticket}: {checks}")
        oath_results.append({"system_id": displayed["system_id"], "ticket_number": ticket, "checks": checks, "result": "PASS"})

    if payload["metadata"].get("oath_requested_ticket_count", 0) and not oath_candidates:
        raise RuntimeError("OATH summonses were requested but generated output contains zero exact-matched systems")

    report = {
        "generated_at": payload["metadata"]["generated_at"],
        "method": "Deterministic random sample seeded from snapshot timestamp and independently re-queried from NYC Open Data",
        "sample_size": len(results),
        "oath_sample_size": len(oath_results),
        "result": "PASS",
        "systems": results,
        "oath_cases": oath_results,
    }
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--systems", type=Path, default=ROOT / "public/data/systems.json")
    parser.add_argument("--details", type=Path, default=ROOT / "public/data/details")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data/verification.json")
    parser.add_argument("--sample-size", type=int, default=5)
    args = parser.parse_args()
    verify(args.systems, args.details, args.output, args.sample_size)


if __name__ == "__main__":
    main()
