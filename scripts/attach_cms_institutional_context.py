from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _normalize_bbl(value: Any) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits if len(digits) == 10 and digits[0] in "12345" else None


def _safe_detail_path(base: Path, system_id: str) -> Path:
    safe = "".join(ch for ch in system_id if ch.isalnum() or ch in ("-", "_"))
    return base / "details" / (safe[:2] or "xx").lower() / f"{safe}.json"


def attach(output_dir: Path, cache_path: Path) -> dict[str, int]:
    systems_path = output_dir / "systems.json"
    payload = json.loads(systems_path.read_text(encoding="utf-8"))
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    if cache.get("schema_version") != "1.0" or cache.get("domain") != "CMS_NYC_INSTITUTIONAL_CONTEXT":
        raise RuntimeError("Unexpected CMS institutional context cache")
    systems = payload.get("systems")
    by_bbl = cache.get("by_bbl")
    if not isinstance(systems, list) or not isinstance(by_bbl, dict):
        raise RuntimeError("CMS institutional attachment inputs are malformed")

    attached_systems = 0
    attached_facilities = 0
    for system in systems:
        if not isinstance(system, dict):
            continue
        system_id = str(system.get("system_id") or "")
        bbl = _normalize_bbl(system.get("bbl"))
        facilities = by_bbl.get(bbl, []) if bbl else []
        if not isinstance(facilities, list):
            raise RuntimeError(f"CMS institutional context malformed for BBL {bbl}")
        system["cms_institutional_facility_count"] = len(facilities)
        system["cms_institutional_facility_types"] = sorted({str(row.get("source_kind") or "") for row in facilities if isinstance(row, dict) and row.get("source_kind")})
        if facilities:
            attached_systems += 1
            attached_facilities += len(facilities)
        detail_path = _safe_detail_path(output_dir, system_id)
        if not detail_path.exists():
            raise RuntimeError(f"Missing account detail while attaching CMS context: {system_id}")
        detail = json.loads(detail_path.read_text(encoding="utf-8"))
        detail["cms_institutional_context"] = {
            "facilities": facilities,
            "evidence_boundaries": cache.get("evidence_boundaries") or {},
            "source": cache.get("source") or {},
            "generated_at": cache.get("generated_at"),
        } if facilities else None
        detail_path.write_text(json.dumps(detail, separators=(",", ":")), encoding="utf-8")

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise RuntimeError("TowerSignal systems metadata is malformed")
    summary = cache.get("summary") or {}
    metadata.update({
        "cms_institutional_context_available": True,
        "cms_institutional_match_basis": "PAD_EXACT_ADDRESS_BBL",
        "cms_institutional_exact_resolved_facility_count": int(summary.get("exact_resolved_facility_count") or 0),
        "cms_institutional_tower_overlap_facility_count": attached_facilities,
        "cms_institutional_systems_attached": attached_systems,
        "cms_institutional_resolved_non_tower_bbl_count": int(summary.get("resolved_non_tower_bbl_count") or 0),
    })
    payload["summary"]["systems_with_cms_institutional_context"] = attached_systems
    systems_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    result = {"systems_attached": attached_systems, "facilities_attached": attached_facilities}
    (output_dir / "cms-institutional-context-coverage.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Attach exact-BBL CMS institutional context to TowerSignal accounts")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data")
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(attach(args.output, args.cache), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
