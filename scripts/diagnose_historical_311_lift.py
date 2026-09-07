from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.bbl_identity import apply_bbl_identity_recovery  # noqa: E402
from towersignal.building_footprints import fetch_building_footprints_by_bin  # noqa: E402
from towersignal.fetch import fetch_dataset  # noqa: E402
from towersignal.historical_311_lift import PERIODS, fetch_period_rows, summarize_lift  # noqa: E402
from towersignal.normalize import normalize_registrations  # noqa: E402

REGISTRATION_ID = "y4fw-iqfr"


def build(output: Path, *, bbl_batch_size: int = 60, page_size: int = 5000) -> dict:
    print("[311-lift] Fetching current NYC cooling-tower registrations", flush=True)
    registration_snapshot = fetch_dataset(REGISTRATION_ID, "system_id")
    systems, dedupe_meta = normalize_registrations(registration_snapshot.rows)
    bin_values = {str(system["bin"]) for system in systems if system.get("bin")}

    print(f"[311-lift] Fetching building footprints for {len(bin_values):,} exact BINs", flush=True)
    footprints_by_bin, footprint_meta = fetch_building_footprints_by_bin(bin_values)
    identity_meta = apply_bbl_identity_recovery(systems, footprints_by_bin)

    canonical_bbls = sorted({str(system["bbl"]) for system in systems if system.get("bbl")})
    borough_by_bbl: dict[str, str] = {}
    systems_per_bbl: Counter[str] = Counter()
    for system in systems:
        bbl = system.get("bbl")
        if not bbl:
            continue
        bbl_text = str(bbl)
        systems_per_bbl[bbl_text] += 1
        borough_by_bbl.setdefault(bbl_text, str(system.get("borough") or "UNKNOWN"))

    print(
        f"[311-lift] Canonical TowerSignal property universe: {len(canonical_bbls):,} BBLs; "
        f"{identity_meta['recovered_bbl_count']:,} recovered BBL systems",
        flush=True,
    )

    rows_by_period: dict[str, list[dict]] = {}
    period_meta: list[dict] = []
    for period_name, dataset_id, start, end in PERIODS:
        print(f"[311-lift] Fetching {period_name} exact-BBL DEP water/lead requests", flush=True)
        rows, meta = fetch_period_rows(
            dataset_id=dataset_id,
            period_name=period_name,
            bbls=canonical_bbls,
            start=start,
            end=end,
            batch_size=bbl_batch_size,
            page_size=page_size,
        )
        rows_by_period[period_name] = rows
        period_meta.append(meta)
        print(
            f"[311-lift] {period_name}: {len(rows):,} deduped source rows; "
            f"{sum(1 for row in rows if row.get('is_building_water_signal')):,} building-water rows",
            flush=True,
        )

    historical_rows = rows_by_period["HISTORICAL_2010_2019"] + rows_by_period["HISTORICAL_2020_2024"]
    recent_rows = rows_by_period["CURRENT_2025_PLUS"]
    lift = summarize_lift(
        tower_bbls=canonical_bbls,
        borough_by_bbl=borough_by_bbl,
        historical_rows=historical_rows,
        recent_rows=recent_rows,
    )

    payload = {
        "schema_version": "1.0",
        "domain": "NYC_HISTORICAL_311_COMMERCIAL_LIFT_DIAGNOSTIC",
        "baseline": {
            "registration_dataset_id": REGISTRATION_ID,
            "registration_source_record_count": registration_snapshot.source_record_count,
            "normalized_system_count": len(systems),
            "source_duplicate_registration_rows": dedupe_meta.get("source_duplicate_rows", 0),
            "canonical_bbl_count": len(canonical_bbls),
            "registry_source_bbl_system_count": identity_meta["registry_source_bbl_count"],
            "recovered_exact_bin_mappluto_bbl_system_count": identity_meta["recovered_bbl_count"],
            "unresolved_bbl_system_count": identity_meta["unresolved_bbl_count"],
            "building_footprint_source_record_count": footprint_meta["source_record_count"],
            "building_footprint_matched_bin_count": footprint_meta["matched_bin_count"],
            "identity_contract": identity_meta["recovery_contract"],
        },
        "source_periods": period_meta,
        "commercial_lift": lift,
        "systems_per_bbl_distribution": dict(sorted(Counter(systems_per_bbl.values()).items())),
        "source_scope": {
            "property_identity": "Current TowerSignal canonical BBLs only. Registry BBL is preserved; recovery uses exact BIN to one unique published MapPLUTO BBL with borough reconciliation.",
            "311": "DEP water/lead service requests only; current production classifier is reused. Only categories beginning BUILDING_ count as building-water signals.",
            "historical_window": "2010-01-01 through 2024-12-31",
            "current_comparison_window": "2025-01-01 onward",
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure incremental commercial lift from pre-2025 NYC DEP 311 water history")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bbl-batch-size", type=int, default=60)
    parser.add_argument("--page-size", type=int, default=5000)
    args = parser.parse_args()
    payload = build(args.output, bbl_batch_size=args.bbl_batch_size, page_size=args.page_size)
    lift = payload["commercial_lift"]
    print(
        "[311-lift] Result: "
        f"{lift['historical_only_tower_bbl_count']:,} historical-only BBLs; "
        f"{lift['recurring_historical_only_tower_bbl_count']:,} recurrent; "
        f"{lift['historical_only_with_2024_activity_count']:,} with 2024 activity",
        flush=True,
    )


if __name__ == "__main__":
    main()
