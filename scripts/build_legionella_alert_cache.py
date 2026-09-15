from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.legionella_alerts import collect  # noqa: E402

DOMAIN = "LEGIONELLA_PUBLIC_HEALTH_ALERTS"


def _load_previous(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists(): return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("domain") != DOMAIN: raise RuntimeError(f"Previous Legionella cache has an unexpected domain: {path}")
    if not isinstance(payload.get("items"), list): raise RuntimeError(f"Previous Legionella cache lacks an items list: {path}")
    return payload


def _recompute_summary(payload: dict[str, Any]) -> dict[str, Any]:
    items = payload.get("items") or []; channels = payload.get("source_channels") or []; errors = payload.get("errors") or []
    return {"source_channel_count": len(channels), "discovered_relevant_item_count": len(items), "retrieval_error_count": len(errors), "nyc_health_item_count": sum(1 for item in items if item.get("agency") == "NYC Health Department"), "nyc_emergency_management_item_count": sum(1 for item in items if item.get("agency") == "NYC Emergency Management"), "nyc_311_item_count": sum(1 for item in items if item.get("agency") == "NYC311"), "nys_health_item_count": sum(1 for item in items if item.get("agency") == "New York State Department of Health"), "mayor_office_item_count": sum(1 for item in items if item.get("agency") == "NYC Mayor's Office")}


def merge_previous(current: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    current_items = current.get("items") or []
    if not isinstance(current_items, list): raise RuntimeError("Current Legionella collection lacks an items list")
    previous_items = (previous or {}).get("items") or []; by_id: dict[str, dict[str, Any]] = {}
    for item in previous_items:
        item_id = str(item.get("item_id") or "")
        if not item_id: raise RuntimeError("Previous Legionella cache contains an item without item_id")
        by_id[item_id] = item
    previous_ids = set(by_id); current_ids: set[str] = set()
    for item in current_items:
        item_id = str(item.get("item_id") or "")
        if not item_id: raise RuntimeError("Current Legionella collection contains an item without item_id")
        current_ids.add(item_id); by_id[item_id] = item
    merged_items = sorted(by_id.values(), key=lambda item: (item.get("published_date") or "", item.get("title") or "", item.get("item_id") or ""), reverse=True)
    current["items"] = merged_items
    current["history_merge"] = {"previous_cache_available": previous is not None, "previous_cache_generated_at": (previous or {}).get("generated_at"), "previous_item_count": len(previous_items), "current_collection_item_count": len(current_items), "retained_prior_item_count": len(previous_ids - current_ids), "refreshed_existing_item_count": len(previous_ids & current_ids), "new_item_count": len(current_ids - previous_ids), "merged_item_count": len(merged_items), "identity_basis": "item_id", "retention_rule": "Prior verified official-source items are retained when absent from a later bounded source page; current observations replace prior records with the same stable item_id."}
    current["summary"] = _recompute_summary(current)
    return current


def build(output_path: Path, previous_cache: Path | None = None) -> dict[str, Any]:
    payload = merge_previous(collect(), _load_previous(previous_cache))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    # The NYC Pages pipeline builds systems.json before this cache. Enrich both the
    # alert records and those exact generated systems while the source observation
    # is fresh. This does not change Priority Score.
    systems_path = output_path.parent / "systems.json"
    if systems_path.exists():
        from attach_legionella_tower_matches import attach  # noqa: E402
        attach(output_path.parent, output_path)
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    print(json.dumps({"summary": payload["summary"], "history_merge": payload["history_merge"], "tower_matching": payload.get("tower_matching")}, indent=2))
    if payload.get("errors"): print(json.dumps({"retrieval_errors": payload["errors"]}, indent=2))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect official Legionella / Legionnaires public-health alerts for TowerSignal")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data/legionella-alerts.json")
    parser.add_argument("--previous-cache", type=Path, default=None, help="Optional prior verified Legionella cache. Items are merged by stable item_id so bounded alert pages do not erase previously observed official alerts.")
    args = parser.parse_args(); build(args.output, args.previous_cache)


if __name__ == "__main__": main()
