from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.acris import browser_property_context, load_cache, normalize_bbl, tower_bbl_hash  # noqa: E402

ACRIS_DATASET_IDS = {"bnx9-e6tj", "8h5j-fqxa", "636b-3b5g"}


def safe_detail_path(base: Path, system_id: str) -> Path:
    safe = "".join(ch for ch in system_id if ch.isalnum() or ch in ("-", "_"))
    return base / "details" / (safe[:2] or "xx").lower() / f"{safe}.json"


def attach(output_dir: Path, cache_path: Path | None) -> dict[str, Any]:
    systems_path = output_dir / "systems.json"
    payload = json.loads(systems_path.read_text(encoding="utf-8"))
    metadata = payload.get("metadata") or {}
    systems = payload.get("systems") or []
    current_bbls = sorted({bbl for row in systems if (bbl := normalize_bbl(row.get("bbl"))) is not None})

    cache = None
    if cache_path is not None and cache_path.exists():
        cache = load_cache(cache_path)

    sources = [source for source in metadata.get("sources", []) if source.get("dataset_id") not in ACRIS_DATASET_IDS]
    if cache is None:
        metadata.update({
            "acris_cache_available": False,
            "acris_cache_generated_at": None,
            "acris_cache_cutoff": None,
            "acris_cache_lookback_days": None,
            "acris_requested_bbl_count": len(current_bbls),
            "acris_matched_bbl_count": 0,
            "acris_matched_document_count": 0,
            "acris_cache_universe_aligned": False,
        })
        properties: dict[str, Any] = {}
    else:
        metrics = cache["metrics"]
        metadata.update({
            "acris_cache_available": True,
            "acris_cache_generated_at": cache["generated_at"],
            "acris_cache_cutoff": cache["cutoff"],
            "acris_cache_lookback_days": cache["lookback_days"],
            "acris_requested_bbl_count": metrics["requested_tower_bbl_count"],
            "acris_matched_bbl_count": metrics["tower_bbls_with_recent_relevant_acris"],
            "acris_matched_document_count": metrics["matched_recent_document_count"],
            "acris_cache_universe_aligned": cache["tower_bbl_universe"].get("sha256") == tower_bbl_hash(current_bbls),
        })
        sources.extend(cache["sources"])
        properties = cache["properties"]
    metadata["sources"] = sources

    systems_with_activity = 0
    for row in systems:
        bbl = normalize_bbl(row.get("bbl"))
        property_context = properties.get(bbl) if bbl else None
        if cache is not None:
            row["acris_recent_document_count"] = int(property_context.get("recent_document_count") or 0) if property_context else 0
            row["latest_acris_recorded_date"] = property_context.get("latest_recorded_date") if property_context else None
            row["acris_deed_count"] = int(property_context.get("deed_count") or 0) if property_context else 0
            row["acris_mortgage_count"] = int(property_context.get("mortgage_count") or 0) if property_context else 0
            row["acris_lease_count"] = int(property_context.get("lease_count") or 0) if property_context else 0
            row["acris_recorded_party_count"] = int(property_context.get("recorded_party_count") or 0) if property_context else 0
            if property_context:
                systems_with_activity += 1

        detail_path = safe_detail_path(output_dir, str(row.get("system_id") or ""))
        detail = json.loads(detail_path.read_text(encoding="utf-8"))
        detail["metadata"] = metadata
        if cache is not None:
            detail["acris_activity"] = browser_property_context(property_context) if property_context else None
        else:
            detail.pop("acris_activity", None)
        detail_path.write_text(json.dumps(detail, separators=(",", ":")), encoding="utf-8")

    summary = payload.get("summary") or {}
    if cache is not None:
        summary["systems_with_recent_acris_activity"] = systems_with_activity
    else:
        summary.pop("systems_with_recent_acris_activity", None)
    payload["summary"] = summary
    payload["metadata"] = metadata
    payload["systems"] = systems
    systems_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    result = {
        "cache_available": cache is not None,
        "cache_generated_at": metadata.get("acris_cache_generated_at"),
        "cache_universe_aligned": metadata.get("acris_cache_universe_aligned"),
        "systems_with_recent_acris_activity": systems_with_activity,
        "matched_bbl_count": metadata.get("acris_matched_bbl_count"),
        "matched_document_count": metadata.get("acris_matched_document_count"),
    }
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Attach last verified ACRIS cache to generated TowerSignal NYC payload")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data")
    parser.add_argument("--cache", type=Path)
    args = parser.parse_args()
    attach(args.output, args.cache)


if __name__ == "__main__":
    main()
