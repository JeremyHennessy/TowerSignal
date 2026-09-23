from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.dob_activity import summarize_dob_activity  # noqa: E402
from towersignal.pluto import normalize_bbl  # noqa: E402


SUMMARY_DETAIL_FIELDS = (
    "pluto_match",
    "pluto_owner_name",
    "pluto_building_area_sqft",
    "hpd_contact_count",
    "dob_activity_count",
    "dob_recent_activity_count",
    "dob_explicit_cooling_tower_count",
    "dob_mechanical_or_boiler_count",
    "latest_dob_activity_date",
)

ALIAS_LAYER_COUNTS = {
    "dob_requested_bbl_count": "core DOB NOW",
    "hpd_violation_requested_bbl_count": "HPD property enforcement",
    "legacy_dob_project_requested_bbl_count": "legacy DOB/BIS",
    "nyc_water_signal_requested_bbl_count": "NYC building-water signals",
    "cms_institutional_requested_bbl_count": "CMS institutional context",
    "nyc_lead_service_line_requested_bbl_count": "NYC lead service lines",
    "nyc_historical_311_requested_bbl_count": "historical NYC 311",
}

ALIAS_MATCH_CONTRACTS = {
    "dob_match_basis": "BBL_ALIAS_EXACT",
    "hpd_violation_match_basis": "BBL_ALIAS_EXACT",
    "legacy_dob_project_match_basis": "BBL_ALIAS_EXACT",
    "nyc_water_signal_match_basis": "EXACT_SOURCE_BBL_ALIAS_OR_BIN",
    "cms_institutional_match_basis": "PAD_EXACT_ADDRESS_BBL_ALIAS",
    "nyc_lead_service_line_match_basis": "BBL_ALIAS_EXACT",
    "nyc_historical_311_match_basis": "BBL_ALIAS_EXACT",
}


def _detail_path(root: Path, system_id: str) -> Path:
    safe = "".join(ch for ch in system_id if ch.isalnum() or ch in ("-", "_"))
    return root / "details" / (safe[:2] or "xx").lower() / f"{safe}.json"


def _bbl(value: Any) -> str | None:
    normalized = normalize_bbl(value)
    return normalized.zfill(10) if normalized else None


def _aliases(row: dict[str, Any]) -> set[str]:
    raw = row.get("bbl_aliases") if isinstance(row.get("bbl_aliases"), list) else [row.get("bbl")]
    return {value for item in raw if (value := _bbl(item))}


def _expected_summary(detail: dict[str, Any], snapshot_date: date) -> dict[str, Any]:
    building = detail.get("building_context") if isinstance(detail.get("building_context"), dict) else None
    hpd = detail.get("hpd_registration") if isinstance(detail.get("hpd_registration"), dict) else None
    contacts = hpd.get("contacts") if hpd and isinstance(hpd.get("contacts"), list) else []
    dob_records = detail.get("dob_activity_history") if isinstance(detail.get("dob_activity_history"), list) else []
    dob = summarize_dob_activity([row for row in dob_records if isinstance(row, dict)], snapshot_date)
    return {
        "pluto_match": building is not None,
        "pluto_owner_name": building.get("owner_name") if building else None,
        "pluto_building_area_sqft": building.get("building_area_sqft") if building else None,
        "hpd_contact_count": len(contacts),
        "dob_activity_count": dob["activity_count"],
        "dob_recent_activity_count": dob["recent_activity_count"],
        "dob_explicit_cooling_tower_count": dob["explicit_cooling_tower_count"],
        "dob_mechanical_or_boiler_count": dob["mechanical_or_boiler_count"],
        "latest_dob_activity_date": dob["latest_activity_date"],
    }


def validate(output_dir: Path, *, require_production_volume: bool = False) -> dict[str, Any]:
    payload = json.loads((output_dir / "systems.json").read_text(encoding="utf-8"))
    systems = payload.get("systems")
    metadata = payload.get("metadata")
    if not isinstance(systems, list) or not isinstance(metadata, dict):
        raise RuntimeError("TowerSignal systems payload is malformed")

    if require_production_volume and len(systems) < 3500:
        raise RuntimeError(f"Mapping coherence received only {len(systems):,} systems")

    snapshot_raw = str(metadata.get("snapshot_date") or "")
    try:
        snapshot_date = date.fromisoformat(snapshot_raw[:10])
    except ValueError as exc:
        raise RuntimeError(f"Invalid TowerSignal snapshot_date: {snapshot_raw!r}") from exc

    canonical_bbls = {value for row in systems if isinstance(row, dict) and (value := _bbl(row.get("bbl")))}
    alias_bbls = {
        alias
        for row in systems
        if isinstance(row, dict)
        for alias in _aliases(row)
    }
    if require_production_volume and len(canonical_bbls) < 3000:
        raise RuntimeError(f"Implausibly small canonical BBL universe: {len(canonical_bbls):,}")
    if len(alias_bbls) < len(canonical_bbls):
        raise RuntimeError("Exact current/base BBL alias universe cannot be smaller than canonical BBL universe")

    mismatches: list[dict[str, Any]] = []
    for row in systems:
        if not isinstance(row, dict):
            continue
        system_id = str(row.get("system_id") or "")
        path = _detail_path(output_dir, system_id)
        if not path.exists():
            raise RuntimeError(f"Missing detail payload while checking summary/detail coherence: {system_id}")
        detail = json.loads(path.read_text(encoding="utf-8"))
        expected = _expected_summary(detail, snapshot_date)
        for field in SUMMARY_DETAIL_FIELDS:
            if row.get(field) != expected[field]:
                mismatches.append({
                    "system_id": system_id,
                    "address": row.get("address"),
                    "field": field,
                    "summary": row.get(field),
                    "detail_derived": expected[field],
                })
                if len(mismatches) >= 25:
                    break
        if len(mismatches) >= 25:
            break

    if mismatches:
        raise RuntimeError(
            "Summary/detail mapping coherence failed; examples="
            + json.dumps(mismatches, separators=(",", ":"), ensure_ascii=False)
        )

    canonical_count = len(canonical_bbls)
    alias_count = len(alias_bbls)
    for field in ("pluto_requested_bbl_count", "hpd_requested_bbl_count"):
        actual = int(metadata.get(field) or 0)
        if actual != canonical_count:
            raise RuntimeError(
                f"{field}={actual:,} but current canonical property-BBL universe={canonical_count:,}"
            )

    for field, label in ALIAS_LAYER_COUNTS.items():
        actual = int(metadata.get(field) or 0)
        if actual != alias_count:
            raise RuntimeError(
                f"{label} was built against {actual:,} BBLs, but current exact current/base alias universe={alias_count:,}"
            )

    for field, expected in ALIAS_MATCH_CONTRACTS.items():
        actual = metadata.get(field)
        if actual != expected:
            raise RuntimeError(f"{field}={actual!r}; expected {expected!r}")

    result = {
        "system_count": len(systems),
        "canonical_bbl_count": canonical_count,
        "exact_bbl_alias_count": alias_count,
        "summary_detail_mismatch_count": 0,
        "validated_alias_layers": len(ALIAS_LAYER_COUNTS),
        "validated_alias_match_contracts": len(ALIAS_MATCH_CONTRACTS),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate NYC property mapping coherence across summary, detail and downstream alias-aware layers")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data")
    parser.add_argument("--require-production-volume", action="store_true")
    args = parser.parse_args()
    validate(args.output, require_production_volume=args.require_production_volume)


if __name__ == "__main__":
    main()
