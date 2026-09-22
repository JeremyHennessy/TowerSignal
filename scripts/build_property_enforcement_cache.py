from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_labor_law_decisions import build as build_labor_law_decisions  # noqa: E402
from towersignal.planimetrics import normalize_bin  # noqa: E402
from towersignal.pluto import normalize_bbl  # noqa: E402
from towersignal.property_enforcement import (  # noqa: E402
    fetch_facade_filings_by_bin,
    fetch_hpd_violations_by_bbl,
    fetch_official_swo_snapshot_by_bin,
    fetch_stop_work_orders_by_bin,
)

DOMAIN = "NYC_PROPERTY_ENFORCEMENT_CONTEXT"
SCHEMA_VERSION = "1.1"


def _hpd_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    open_records = [row for row in records if row.get("is_open")]
    return {
        "record_count": len(records),
        "open_count": len(open_records),
        "open_class_a_count": sum(1 for row in open_records if row.get("class") == "A"),
        "open_class_b_count": sum(1 for row in open_records if row.get("class") == "B"),
        "open_class_c_count": sum(1 for row in open_records if row.get("class") == "C"),
        "latest_inspection_date": max((row.get("inspection_date") or "" for row in records), default="") or None,
    }


def _swo_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "record_count": len(records),
        "issue_event_count": sum(1 for row in records if str(row.get("event_type") or "").startswith("ISSUED")),
        "rescission_event_count": sum(1 for row in records if str(row.get("event_type") or "").startswith("RESCINDED")),
        "latest_event_date": max(
            (row.get("disposition_date") or row.get("inspection_date") or row.get("date_entered") or "" for row in records),
            default="",
        ) or None,
    }


def _official_swo_snapshot_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "record_count": len(records),
        "active_at_snapshot_count": sum(1 for row in records if row.get("status_at_snapshot") == "ACTIVE"),
        "rescinded_at_snapshot_count": sum(1 for row in records if row.get("status_at_snapshot") == "RESCINDED"),
        "latest_disposition_date": max((row.get("last_disposition_date") or "" for row in records), default="") or None,
    }


def _facade_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    latest = records[0] if records else None
    return {
        "record_count": len(records),
        "latest_status": latest.get("current_status") if latest else None,
        "latest_cycle": latest.get("cycle") if latest else None,
        "latest_submitted_on": latest.get("submitted_on") if latest else None,
        "unsafe_count": sum(1 for row in records if str(row.get("current_status") or "").upper() == "UNSAFE"),
        "swarmp_count": sum(1 for row in records if str(row.get("current_status") or "").upper() == "SWARMP"),
        "no_report_filed_count": sum(1 for row in records if str(row.get("current_status") or "").upper() == "NO REPORT FILED"),
    }


def build(systems_path: Path, output_path: Path) -> dict[str, Any]:
    systems_payload = json.loads(systems_path.read_text(encoding="utf-8"))
    systems = systems_payload.get("systems") or []
    requested_bbls = sorted({
        bbl
        for row in systems
        for value in (row.get("bbl_aliases") if isinstance(row.get("bbl_aliases"), list) else [row.get("bbl")])
        if (bbl := normalize_bbl(value))
    }, key=int)
    requested_bins = sorted({value for row in systems if (value := normalize_bin(row.get("bin")))}, key=int)

    hpd_by_bbl, hpd_source = fetch_hpd_violations_by_bbl(requested_bbls)
    swo_by_bin, swo_source = fetch_stop_work_orders_by_bin(requested_bins)
    official_swo_by_bin, official_swo_source = fetch_official_swo_snapshot_by_bin(requested_bins)
    facade_by_bin, facade_source = fetch_facade_filings_by_bin(requested_bins)

    by_bbl = {
        bbl: {"summary": _hpd_summary(records), "hpd_violations": records}
        for bbl, records in hpd_by_bbl.items()
    }
    all_bins = sorted(set(swo_by_bin) | set(official_swo_by_bin) | set(facade_by_bin), key=int)
    by_bin: dict[str, Any] = {}
    for bin_value in all_bins:
        swo_records = swo_by_bin.get(bin_value, [])
        official_swo_records = official_swo_by_bin.get(bin_value, [])
        facade_records = facade_by_bin.get(bin_value, [])
        by_bin[bin_value] = {
            "stop_work_orders": {"summary": _swo_summary(swo_records), "records": swo_records},
            "official_swo_snapshot": {"summary": _official_swo_snapshot_summary(official_swo_records), "records": official_swo_records},
            "facade_compliance": {"summary": _facade_summary(facade_records), "records": facade_records},
        }

    result = {
        "schema_version": SCHEMA_VERSION,
        "domain": DOMAIN,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_systems_snapshot": {
            "schema_version": systems_payload.get("schema_version"),
            "snapshot_date": (systems_payload.get("metadata") or {}).get("snapshot_date"),
            "system_count": len(systems),
            "canonical_bbl_count": len(requested_bbls),
            "canonical_bin_count": len(requested_bins),
        },
        "sources": {
            "hpd_violations": hpd_source,
            "stop_work_orders": swo_source,
            "official_swo_snapshot": official_swo_source,
            "facade_compliance": facade_source,
        },
        "summary": {
            "requested_bbl_count": len(requested_bbls),
            "requested_bin_count": len(requested_bins),
            "hpd_matched_bbl_count": len(by_bbl),
            "hpd_violation_count": sum(item["summary"]["record_count"] for item in by_bbl.values()),
            "hpd_open_violation_count": sum(item["summary"]["open_count"] for item in by_bbl.values()),
            "hpd_open_class_c_count": sum(item["summary"]["open_class_c_count"] for item in by_bbl.values()),
            "swo_matched_bin_count": len(swo_by_bin),
            "swo_event_count": sum(len(rows) for rows in swo_by_bin.values()),
            "official_swo_snapshot_matched_bin_count": len(official_swo_by_bin),
            "official_swo_snapshot_record_count": sum(len(rows) for rows in official_swo_by_bin.values()),
            "official_swo_snapshot_active_count": sum(1 for rows in official_swo_by_bin.values() for row in rows if row.get("status_at_snapshot") == "ACTIVE"),
            "official_swo_snapshot_rescinded_count": sum(1 for rows in official_swo_by_bin.values() for row in rows if row.get("status_at_snapshot") == "RESCINDED"),
            "facade_matched_bin_count": len(facade_by_bin),
            "facade_filing_count": sum(len(rows) for rows in facade_by_bin.values()),
        },
        "evidence_semantics": {
            "hpd": "Official HPD Housing Maintenance Code / Multiple Dwelling Law violations joined only by exact current/base BBL aliases. violation_status is used directly for open/close state; TowerSignal does not infer closure from free text.",
            "stop_work_orders": "Official DOB Complaints current disposition records joined only by exact BIN and restricted to SWO-related disposition codes documented by DOB. These are complaint disposition events, not a reconstructed complete SWO disposition-history ledger.",
            "official_swo_snapshot": "Separate official DOB Stop Work Orders snapshot joined only by exact BIN. ACTIVE/RESCINDED is preserved exactly as published at the dated 2024 snapshot; it must never be presented as current status. Absence from the snapshot means no matching dated observation, not no order.",
            "facade_compliance": "Official DOB NOW Safety Facades (Local Law 11 / FISP) compliance filings joined only by exact BIN. SAFE/SWARMP/UNSAFE/No Report Filed are preserved as published.",
            "scoring": "Property enforcement evidence is context only in this build and does not modify TowerSignal Priority Score.",
        },
        "by_bbl": by_bbl,
        "by_bin": by_bin,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")

    labor_path = output_path.with_name("labor-law-decisions.json")
    previous_labor_path = ROOT / ".history-store" / "data" / "history" / "segments" / "labor-law-decisions.json"
    labor_payload = build_labor_law_decisions(systems_path, labor_path, previous_labor_path)
    result["labor_law_summary"] = labor_payload.get("summary") or {}

    print(json.dumps({**result["summary"], "labor_law": result["labor_law_summary"]}, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Build exact-key NYC property enforcement context for TowerSignal")
    parser.add_argument("--systems", type=Path, default=ROOT / "public/data/systems.json")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data/property-enforcement.json")
    args = parser.parse_args()
    build(args.systems, args.output)


if __name__ == "__main__":
    main()
