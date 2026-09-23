from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.pluto import normalize_bbl  # noqa: E402


def safe_detail_path(base: Path, system_id: str) -> Path:
    safe = "".join(ch for ch in system_id if ch.isalnum() or ch in ("-", "_"))
    return base / "details" / (safe[:2] or "xx").lower() / f"{safe}.json"


def _normalized_bbl(value: Any) -> str | None:
    result = normalize_bbl(value)
    return result.zfill(10) if result else None


def validate(output_dir: Path, *, require_production_volume: bool = False) -> dict[str, int]:
    payload = json.loads((output_dir / "systems.json").read_text(encoding="utf-8"))
    systems = payload.get("systems") or []
    metadata = payload.get("metadata") or {}
    if not isinstance(systems, list):
        raise RuntimeError("systems.json systems payload is malformed")
    if require_production_volume and len(systems) < 3500:
        raise RuntimeError(f"Identity validation received only {len(systems):,} NYC systems")

    bridge_count = 0
    reconciled_count = 0
    explicit_conflict_count = 0

    for row in systems:
        system_id = str(row.get("system_id") or "")
        canonical = _normalized_bbl(row.get("bbl"))
        property_bbl = _normalized_bbl(row.get("property_bbl"))
        registry = _normalized_bbl(row.get("registry_bbl"))
        status = str(row.get("bbl_identity_status") or "")
        aliases = sorted({
            value
            for raw in (row.get("bbl_aliases") or [])
            if (value := _normalized_bbl(raw))
        })
        expected_aliases = sorted({value for value in (canonical, registry) if value})
        # The expected alias set is derived below from retained source evidence.
        if canonical and canonical not in aliases:
            raise RuntimeError(
                f"System {system_id} exact BBL alias mismatch: aliases={aliases} expected={expected_aliases}"
            )

        if canonical != property_bbl:
            raise RuntimeError(
                f"System {system_id} canonical bbl/property_bbl mismatch: {canonical!r} != {property_bbl!r}"
            )

        detail_path = safe_detail_path(output_dir, system_id)
        if not detail_path.exists():
            raise RuntimeError(f"Missing detail payload for identity validation: {system_id}")
        detail = json.loads(detail_path.read_text(encoding="utf-8"))
        identity = detail.get("identity") or {}
        if _normalized_bbl(identity.get("bbl")) != canonical:
            raise RuntimeError(f"System {system_id} summary/detail canonical BBL mismatch")
        if _normalized_bbl(identity.get("registry_bbl")) != registry:
            raise RuntimeError(f"System {system_id} summary/detail registry BBL mismatch")
        if _normalized_bbl(identity.get("property_bbl")) != property_bbl:
            raise RuntimeError(f"System {system_id} summary/detail property BBL mismatch")
        detail_aliases = sorted({
            value
            for raw in (identity.get("bbl_aliases") or [])
            if (value := _normalized_bbl(raw))
        })
        if detail_aliases != aliases:
            raise RuntimeError(f"System {system_id} summary/detail BBL alias mismatch")

        footprints = detail.get("building_footprints") or []
        candidates = {
            value
            for item in footprints
            if isinstance(item, dict)
            and (value := _normalized_bbl(item.get("mappluto_bbl")))
        }
        bases = {
            value
            for item in footprints
            if isinstance(item, dict)
            and (value := _normalized_bbl(item.get("base_bbl")))
        }

        evidence = identity.get("bbl_identity_evidence") or {}
        from towersignal.bbl_identity import resolve_system_bbl_identity
        from towersignal.planimetrics import normalize_bin
        recomputed = resolve_system_bbl_identity(
            {**identity, "bbl": registry}, footprints, evidence.get("hpd_identity_rows") or [])
        if aliases != recomputed["bbl_aliases"] or canonical != recomputed["canonical_bbl"]:
            raise RuntimeError(f"System {system_id} identity is not supported by its exact-key sources")
        if identity.get("bin") and normalize_bin(identity["bin"]) is None:
            raise RuntimeError(f"System {system_id} uses an unassigned BIN as a relationship key")

        strong_bridge = (
            registry is not None
            and len(candidates) == 1
            and registry in bases
            and next(iter(candidates)) != registry
        )
        if strong_bridge:
            bridge_count += 1
            expected = next(iter(candidates))
            if canonical != expected or property_bbl != expected:
                raise RuntimeError(
                    f"System {system_id} ignored exact-BIN registry/base→MapPLUTO bridge: "
                    f"registry={registry} expected_property={expected} canonical={canonical}"
                )
            if status != "RECONCILED_REGISTRY_BASE_TO_MAPPLUTO_BBL":
                raise RuntimeError(
                    f"System {system_id} reconciled property BBL has wrong identity status: {status}"
                )
            evidence = identity.get("bbl_identity_evidence") or {}
            if evidence.get("registry_base_bridge_confirmed") is not True:
                raise RuntimeError(
                    f"System {system_id} is missing explicit registry-base bridge provenance"
                )
            reconciled_count += 1

        if "CONFLICT" in status or "MULTIPLE_MAPPLUTO" in status:
            explicit_conflict_count += 1

    metadata_count = int(metadata.get("bbl_reconciled_registry_base_to_mappluto_count") or 0)
    if metadata_count != reconciled_count:
        raise RuntimeError(
            f"Reconciled property-BBL metadata mismatch: metadata={metadata_count}, observed={reconciled_count}"
        )
    if bridge_count != reconciled_count:
        raise RuntimeError(
            f"Unreconciled exact-BIN property bridges remain: bridges={bridge_count}, reconciled={reconciled_count}"
        )

    result = {
        "system_count": len(systems),
        "exact_bin_registry_base_bridges": bridge_count,
        "reconciled_registry_base_bridges": reconciled_count,
        "explicit_identity_conflicts": explicit_conflict_count,
    }
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate TowerSignal NYC property-BBL identity reconciliation")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data")
    parser.add_argument("--require-production-volume", action="store_true")
    args = parser.parse_args()
    validate(args.output, require_production_volume=args.require_production_volume)


if __name__ == "__main__":
    main()
