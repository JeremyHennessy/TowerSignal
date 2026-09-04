from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.building_footprints import feature_identity as building_footprint_identity, fetch_building_footprints_by_bin  # noqa: E402
from towersignal.fetch import fetch_where  # noqa: E402
from towersignal.hpd import fetch_hpd_contacts_by_bbl  # noqa: E402
from towersignal.inspections import aggregate_inspections  # noqa: E402
from towersignal.normalize import normalize_registrations  # noqa: E402
from towersignal.oath import fetch_oath_cases  # noqa: E402
from towersignal.planimetrics import fetch_planimetric_towers_by_bin, normalize_bin as normalize_planimetric_bin  # noqa: E402
from towersignal.pluto import normalize_bbl  # noqa: E402

REGISTRATION_ID = "y4fw-iqfr"
INSPECTION_ID = "f9wb-g8mb"


def escape_soql(value: str) -> str:
    return value.replace("'", "''")


def detail_path(base: Path, system_id: str) -> Path:
    safe = "".join(ch for ch in system_id if ch.isalnum() or ch in ("-", "_"))
    return base / (safe[:2] or "xx").lower() / f"{safe}.json"


def planimetric_identity(feature: dict) -> tuple[str, str]:
    return (str(feature.get("source_id") or ""), str(feature.get("global_id") or ""))


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

    hpd_candidates = [system for system in systems if int(system.get("hpd_contact_count") or 0) > 0 and system.get("bbl")]
    hpd_selected = rng.sample(hpd_candidates, min(sample_size, len(hpd_candidates)))
    hpd_results = []
    for displayed in hpd_selected:
        bbl = normalize_bbl(displayed.get("bbl"))
        if bbl is None:
            raise RuntimeError(f"HPD candidate lacks usable BBL for {displayed['system_id']}")
        detail = json.loads(detail_path(details_dir, displayed["system_id"]).read_text(encoding="utf-8"))
        generated = detail.get("hpd_registration")
        if not generated or not generated.get("contacts"):
            raise RuntimeError(f"Summary reports HPD contacts but detail is empty for {displayed['system_id']}")
        live_by_bbl, _ = fetch_hpd_contacts_by_bbl([bbl])
        live = live_by_bbl.get(bbl)
        checks = {
            "bbl_exact": live is not None,
            "registration_id": bool(live) and live["registration_id"] == generated["registration_id"],
            "last_registration_date": bool(live) and live["last_registration_date"] == generated["last_registration_date"],
            "contact_count": bool(live) and len(live["contacts"]) == len(generated["contacts"]),
            "first_contact_type": bool(live) and live["contacts"][0]["type"] == generated["contacts"][0]["type"],
        }
        if not all(checks.values()):
            raise RuntimeError(f"Live HPD comparison failed for BBL {bbl}: {checks}")
        hpd_results.append({"system_id": displayed["system_id"], "bbl": bbl, "checks": checks, "result": "PASS"})

    if payload["metadata"].get("hpd_matched_contact_bbl_count", 0) and not hpd_candidates:
        raise RuntimeError("HPD metadata reports contact matches but generated output contains zero contact-bearing systems")

    planimetric_candidates_by_bin: dict[str, dict] = {}
    for system in systems:
        bin_value = normalize_planimetric_bin(system.get("bin"))
        if system.get("planimetric_bin_match") and bin_value:
            planimetric_candidates_by_bin.setdefault(bin_value, system)
    planimetric_bins = sorted(planimetric_candidates_by_bin, key=int)
    selected_planimetric_bins = rng.sample(planimetric_bins, min(sample_size, len(planimetric_bins)))
    live_planimetric_by_bin, _ = fetch_planimetric_towers_by_bin(selected_planimetric_bins)
    planimetric_results = []
    for bin_value in selected_planimetric_bins:
        displayed = planimetric_candidates_by_bin[bin_value]
        detail = json.loads(detail_path(details_dir, displayed["system_id"]).read_text(encoding="utf-8"))
        generated_features = detail.get("planimetric_building_tower_features") or []
        live_features = live_planimetric_by_bin.get(bin_value) or []
        generated_sorted = sorted(generated_features, key=planimetric_identity)
        live_sorted = sorted(live_features, key=planimetric_identity)
        checks = {
            "bin_exact": bool(generated_sorted) and all(feature.get("bin") == bin_value for feature in generated_sorted),
            "feature_count": len(generated_sorted) == len(live_sorted),
            "feature_identity": [planimetric_identity(feature) for feature in generated_sorted] == [planimetric_identity(feature) for feature in live_sorted],
            "source_status": [feature.get("status") for feature in generated_sorted] == [feature.get("status") for feature in live_sorted],
            "geometry": [feature.get("geometry") for feature in generated_sorted] == [feature.get("geometry") for feature in live_sorted],
            "match_basis": bool(generated_sorted) and all(feature.get("match_basis") == "BIN_EXACT" for feature in generated_sorted),
            "imagery_year": bool(generated_sorted) and all(feature.get("imagery_year") == 2022 for feature in generated_sorted),
        }
        if not all(checks.values()):
            raise RuntimeError(f"Live Planimetric comparison failed for BIN {bin_value}: {checks}")
        planimetric_results.append({
            "system_id": displayed["system_id"],
            "bin": bin_value,
            "feature_count": len(generated_sorted),
            "checks": checks,
            "result": "PASS",
        })

    if payload["metadata"].get("planimetric_matched_bin_count", 0) and not planimetric_candidates_by_bin:
        raise RuntimeError("Planimetric metadata reports exact BIN matches but generated output contains zero matched systems")

    footprint_candidates_by_bin: dict[str, dict] = {}
    for system in systems:
        bin_value = normalize_planimetric_bin(system.get("bin"))
        if system.get("building_footprint_bin_match") and bin_value:
            footprint_candidates_by_bin.setdefault(bin_value, system)
    footprint_bins = sorted(footprint_candidates_by_bin, key=int)
    selected_footprint_bins = rng.sample(footprint_bins, min(sample_size, len(footprint_bins)))
    live_footprints_by_bin, _ = fetch_building_footprints_by_bin(selected_footprint_bins)
    footprint_results = []
    for bin_value in selected_footprint_bins:
        displayed = footprint_candidates_by_bin[bin_value]
        detail = json.loads(detail_path(details_dir, displayed["system_id"]).read_text(encoding="utf-8"))
        generated_features = detail.get("building_footprints") or []
        live_features = live_footprints_by_bin.get(bin_value) or []
        generated_sorted = sorted(generated_features, key=building_footprint_identity)
        live_sorted = sorted(live_features, key=building_footprint_identity)
        checks = {
            "bin_exact": bool(generated_sorted) and all(feature.get("bin") == bin_value for feature in generated_sorted),
            "feature_count": len(generated_sorted) == len(live_sorted),
            "feature_identity": [building_footprint_identity(feature) for feature in generated_sorted] == [building_footprint_identity(feature) for feature in live_sorted],
            "source_status": [feature.get("last_status_type") for feature in generated_sorted] == [feature.get("last_status_type") for feature in live_sorted],
            "roof_height": [feature.get("height_roof_ft") for feature in generated_sorted] == [feature.get("height_roof_ft") for feature in live_sorted],
            "geometry": [feature.get("geometry") for feature in generated_sorted] == [feature.get("geometry") for feature in live_sorted],
            "match_basis": bool(generated_sorted) and all(feature.get("match_basis") == "BIN_EXACT" for feature in generated_sorted),
        }
        if not all(checks.values()):
            raise RuntimeError(f"Live building-footprint comparison failed for BIN {bin_value}: {checks}")
        footprint_results.append({
            "system_id": displayed["system_id"],
            "bin": bin_value,
            "feature_count": len(generated_sorted),
            "checks": checks,
            "result": "PASS",
        })

    if payload["metadata"].get("building_footprint_matched_bin_count", 0) and not footprint_candidates_by_bin:
        raise RuntimeError("Building-footprint metadata reports exact BIN matches but generated output contains zero matched systems")

    report = {
        "generated_at": payload["metadata"]["generated_at"],
        "method": "Deterministic random sample seeded from snapshot timestamp and independently re-queried from NYC Open Data",
        "sample_size": len(results),
        "oath_sample_size": len(oath_results),
        "hpd_sample_size": len(hpd_results),
        "planimetric_sample_size": len(planimetric_results),
        "building_footprint_sample_size": len(footprint_results),
        "result": "PASS",
        "systems": results,
        "oath_cases": oath_results,
        "hpd_contacts": hpd_results,
        "planimetric_building_features": planimetric_results,
        "building_footprints": footprint_results,
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
