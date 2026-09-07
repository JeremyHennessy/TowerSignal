from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate(path: Path, *, require_production_volume: bool = False) -> dict[str, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0" or payload.get("domain") != "CMS_NYC_INSTITUTIONAL_CONTEXT":
        raise RuntimeError("Unexpected CMS institutional context contract")
    summary = payload.get("summary")
    by_bbl = payload.get("by_bbl")
    governance = payload.get("governance")
    if not isinstance(summary, dict) or not isinstance(by_bbl, dict) or not isinstance(governance, dict):
        raise RuntimeError("CMS institutional context payload is malformed")
    required_false = (
        "priority_score_1_0_changed",
        "current_trigger_created",
        "fuzzy_matching_used",
        "provider_or_incumbent_inference",
        "cms_only_properties_promoted_to_tower_universe",
        "raw_cms_rows_published",
    )
    if any(governance.get(key) is not False for key in required_false):
        raise RuntimeError("CMS institutional context governance boundary was weakened")
    facility_count = 0
    identities: set[tuple[str, str]] = set()
    for bbl, facilities in by_bbl.items():
        if not (isinstance(bbl, str) and len(bbl) == 10 and bbl[0] in "12345") or not isinstance(facilities, list):
            raise RuntimeError(f"CMS exact-BBL context is malformed for {bbl!r}")
        for facility in facilities:
            if not isinstance(facility, dict) or facility.get("bbl") != bbl:
                raise RuntimeError(f"CMS facility property identity mismatch for {bbl}")
            if facility.get("property_link_confidence") != "CONFIRMED_PAD_EXACT_ADDRESS_BBL":
                raise RuntimeError(f"CMS facility lacks exact PAD evidence for {bbl}")
            if any(key in facility for key in ("raw", "source_row", "source_payload")):
                raise RuntimeError("CMS production cache contains raw source material")
            identity = (str(facility.get("source_dataset_id") or ""), str(facility.get("source_facility_id") or ""))
            if not all(identity) or identity in identities:
                raise RuntimeError(f"CMS source facility identity is missing or duplicated: {identity}")
            identities.add(identity)
            facility_count += 1
    if facility_count != int(summary.get("tower_overlap_facility_count") or 0):
        raise RuntimeError("CMS tower-overlap facility count does not reconcile")
    if len(by_bbl) != int(summary.get("tower_overlap_bbl_count") or 0):
        raise RuntimeError("CMS tower-overlap BBL count does not reconcile")
    if require_production_volume:
        if int(summary.get("hospital_source_rows") or 0) < 5000:
            raise RuntimeError("CMS hospital source population unexpectedly low")
        if int(summary.get("nursing_home_source_rows") or 0) < 14000:
            raise RuntimeError("CMS nursing-home source population unexpectedly low")
        if int(summary.get("exact_resolved_facility_count") or 0) < 100:
            raise RuntimeError("CMS exact property resolution unexpectedly low")
        if facility_count < 35:
            raise RuntimeError("CMS TowerSignal overlap unexpectedly low")
    return {
        "exact_resolved_facility_count": int(summary.get("exact_resolved_facility_count") or 0),
        "tower_overlap_facility_count": facility_count,
        "tower_overlap_bbl_count": len(by_bbl),
        "resolved_non_tower_bbl_count": int(summary.get("resolved_non_tower_bbl_count") or 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate exact-BBL CMS institutional context")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--require-production-volume", action="store_true")
    args = parser.parse_args()
    print(json.dumps(validate(args.cache, require_production_volume=args.require_production_volume), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
