from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

DOMAIN = "NYC_PROPERTY_ENFORCEMENT_CONTEXT"
EXPECTED_DATASETS = {
    "hpd_violations": "wvxf-dwi5",
    "stop_work_orders": "eabe-havv",
    "facade_compliance": "xubg-57si",
}
VALID_FACADE_STATUSES = {"SAFE", "SWARMP", "UNSAFE", "No Report Filed", None}


def validate(path: Path, *, max_age_days: float = 1.0, require_production_universe: bool = False) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("domain") != DOMAIN:
        raise RuntimeError(f"Unexpected property enforcement domain: {payload.get('domain')}")
    generated = datetime.fromisoformat(str(payload.get("generated_at") or "").replace("Z", "+00:00"))
    age_days = (datetime.now(timezone.utc) - generated).total_seconds() / 86400
    if age_days > max_age_days:
        raise RuntimeError(f"property enforcement cache is stale: {age_days:.2f} days")

    sources = payload.get("sources") or {}
    for key, dataset_id in EXPECTED_DATASETS.items():
        if (sources.get(key) or {}).get("dataset_id") != dataset_id:
            raise RuntimeError(f"{key} must use authoritative dataset {dataset_id}")

    by_bbl = payload.get("by_bbl")
    by_bin = payload.get("by_bin")
    if not isinstance(by_bbl, dict) or not isinstance(by_bin, dict):
        raise RuntimeError("property enforcement cache must contain by_bbl and by_bin objects")

    hpd_records = []
    for bbl, context in by_bbl.items():
        if len(str(bbl)) != 10 or not str(bbl).isdigit():
            raise RuntimeError(f"invalid BBL in property enforcement cache: {bbl}")
        records = (context or {}).get("hpd_violations") or []
        local_summary = (context or {}).get("summary") or {}
        if int(local_summary.get("record_count") or 0) != len(records):
            raise RuntimeError(f"HPD record count mismatch on BBL {bbl}")
        for row in records:
            if row.get("bbl") != bbl or row.get("match_basis") != "BBL_EXACT":
                raise RuntimeError(f"HPD cache contains non-exact BBL match on {bbl}")
            if row.get("violation_status") not in {"OPEN", "CLOSE", None}:
                raise RuntimeError(f"Unexpected HPD violation_status {row.get('violation_status')!r}")
            if bool(row.get("is_open")) != (row.get("violation_status") == "OPEN"):
                raise RuntimeError("HPD is_open must be derived only from published violation_status")
            hpd_records.append(row)

    swo_records = []
    facade_records = []
    for bin_value, context in by_bin.items():
        if not str(bin_value).isdigit():
            raise RuntimeError(f"invalid BIN in property enforcement cache: {bin_value}")
        swo_context = (context or {}).get("stop_work_orders") or {}
        facade_context = (context or {}).get("facade_compliance") or {}
        swos = swo_context.get("records") or []
        facades = facade_context.get("records") or []
        if int((swo_context.get("summary") or {}).get("record_count") or 0) != len(swos):
            raise RuntimeError(f"SWO record count mismatch on BIN {bin_value}")
        if int((facade_context.get("summary") or {}).get("record_count") or 0) != len(facades):
            raise RuntimeError(f"facade record count mismatch on BIN {bin_value}")
        for row in swos:
            if row.get("bin") != bin_value or row.get("match_basis") != "BIN_EXACT":
                raise RuntimeError(f"SWO cache contains non-exact BIN match on {bin_value}")
            if not row.get("disposition_code") or not row.get("event_type"):
                raise RuntimeError("SWO record lacks disposition semantics")
            swo_records.append(row)
        for row in facades:
            if row.get("bin") != bin_value or row.get("match_basis") != "BIN_EXACT":
                raise RuntimeError(f"facade cache contains non-exact BIN match on {bin_value}")
            if row.get("current_status") not in VALID_FACADE_STATUSES:
                raise RuntimeError(f"Unexpected facade current_status {row.get('current_status')!r}")
            facade_records.append(row)

    summary = payload.get("summary") or {}
    reconciliations = {
        "hpd_violation_count": len(hpd_records),
        "hpd_open_violation_count": sum(1 for row in hpd_records if row.get("is_open")),
        "hpd_open_class_c_count": sum(1 for row in hpd_records if row.get("is_open") and row.get("class") == "C"),
        "swo_event_count": len(swo_records),
        "facade_filing_count": len(facade_records),
    }
    for key, count in reconciliations.items():
        if int(summary.get(key) or 0) != count:
            raise RuntimeError(f"{key} does not reconcile: summary={summary.get(key)} actual={count}")

    universe = payload.get("source_systems_snapshot") or {}
    if require_production_universe:
        if int(universe.get("system_count") or 0) < 3000:
            raise RuntimeError("property enforcement build did not use a production-scale TowerSignal system universe")
        if int(universe.get("canonical_bin_count") or 0) < 3000:
            raise RuntimeError("property enforcement build has unexpectedly few canonical BINs")

    result = {"age_days": round(age_days, 3), **reconciliations}
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate TowerSignal property enforcement cache")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--max-age-days", type=float, default=1.0)
    parser.add_argument("--require-production-universe", action="store_true")
    args = parser.parse_args()
    validate(args.cache, max_age_days=args.max_age_days, require_production_universe=args.require_production_universe)


if __name__ == "__main__":
    main()
