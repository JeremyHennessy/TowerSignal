from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

DOMAIN = "LEGIONELLA_PUBLIC_HEALTH_ALERTS"
REQUIRED_CHANNELS = {
    "NYC_DOH_LEGIONNAIRES_TOPIC",
    "NYC_DOH_PROVIDER_LEGIONELLOSIS",
    "NYC_DOH_HEALTH_ALERT_NETWORK",
    "NYC_DOH_PRESS_RELEASES",
    "NYC_DOH_COOLING_TOWER_REQUIREMENTS",
    "NYC_MAYOR_NEWS",
    "NYC_NOTIFY_NYC_RSS",
    "NYC_311_LEGIONNAIRES",
    "NYC_311_COOLING_TOWER",
    "NYSDOH_LEGIONNAIRES_TOPIC",
    "NYSDOH_LEGIONELLA_REGULATION",
    "NYSDOH_PROTECTION_AGAINST_LEGIONELLA",
}
ALLOWED_HOSTS = {
    "www.nyc.gov", "nyc.gov", "home4.nyc.gov", "www.health.ny.gov", "health.ny.gov", "regs.health.ny.gov",
    "a858-nycnotify.nyc.gov", "portal.311.nyc.gov",
}


def validate(path: Path, *, max_age_days: float = 1.0, require_clean_retrieval: bool = False) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("domain") != DOMAIN:
        raise RuntimeError(f"Unexpected Legionella alert domain: {payload.get('domain')}")
    generated = datetime.fromisoformat(str(payload.get("generated_at") or "").replace("Z", "+00:00"))
    age_days = (datetime.now(timezone.utc) - generated).total_seconds() / 86400
    if age_days > max_age_days:
        raise RuntimeError(f"Legionella alert cache is stale: {age_days:.2f} days")

    channels = payload.get("source_channels") or []
    channel_keys = {row.get("channel_key") for row in channels}
    missing = REQUIRED_CHANNELS - channel_keys
    if missing:
        raise RuntimeError(f"Missing required Legionella source channels: {sorted(missing)}")
    for row in channels:
        if urlparse(str(row.get("url") or "")).netloc.lower() not in ALLOWED_HOSTS:
            raise RuntimeError(f"Unapproved source channel host: {row.get('url')}")
        if not row.get("content_sha256") or int(row.get("content_bytes") or 0) <= 0:
            raise RuntimeError(f"Source channel snapshot lacks content proof: {row.get('url')}")

    items = payload.get("items") or []
    seen_item_ids: set[str] = set()
    for item in items:
        item_id = str(item.get("item_id") or "")
        url = str(item.get("url") or "")
        if not item_id or item_id in seen_item_ids:
            raise RuntimeError(f"Duplicate or missing Legionella item identity: {item_id!r}")
        seen_item_ids.add(item_id)
        if not url:
            raise RuntimeError(f"Legionella item {item_id} lacks a source URL")
        if urlparse(url).netloc.lower() not in ALLOWED_HOSTS:
            raise RuntimeError(f"Unapproved discovered item host: {url}")
        terms = item.get("match_terms") or {}
        if not (terms.get("legionella") or terms.get("cooling_tower")):
            raise RuntimeError(f"Discovered item lacks required relevance terms: {url}")
        if not item.get("content_sha256") or int(item.get("content_bytes") or 0) <= 0:
            raise RuntimeError(f"Discovered item lacks content proof: {url}")
        if item.get("document_type") == "RSS_ITEM" and item.get("channel_key") != "NYC_NOTIFY_NYC_RSS":
            raise RuntimeError(f"Unexpected RSS item channel: {item.get('channel_key')}")

    errors = payload.get("errors") or []
    if require_clean_retrieval and errors:
        raise RuntimeError(f"Legionella source retrieval had {len(errors)} errors")
    summary = payload.get("summary") or {}
    if int(summary.get("source_channel_count") or 0) != len(channels):
        raise RuntimeError("Legionella source channel count does not reconcile")
    if int(summary.get("discovered_relevant_item_count") or 0) != len(items):
        raise RuntimeError("Legionella item count does not reconcile")
    if int(summary.get("retrieval_error_count") or 0) != len(errors):
        raise RuntimeError("Legionella retrieval error count does not reconcile")

    result = {"age_days": round(age_days, 3), "source_channel_count": len(channels), "item_count": len(items), "retrieval_error_count": len(errors)}
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate TowerSignal Legionella public-health alert cache")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--max-age-days", type=float, default=1.0)
    parser.add_argument("--require-clean-retrieval", action="store_true")
    args = parser.parse_args()
    validate(args.cache, max_age_days=args.max_age_days, require_clean_retrieval=args.require_clean_retrieval)


if __name__ == "__main__":
    main()
