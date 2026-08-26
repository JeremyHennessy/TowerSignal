from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.city_record import DEFAULT_AWARD_LOOKBACK_DAYS, build_city_record_payload  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch, classify and normalize NYC City Record procurement notices")
    parser.add_argument("--output", type=Path, default=ROOT / "public" / "data" / "procurement-city-record.json")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--award-lookback-days", type=int, default=DEFAULT_AWARD_LOOKBACK_DAYS)
    args = parser.parse_args()

    payload = build_city_record_payload(as_of=args.as_of, award_lookback_days=args.award_lookback_days)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=True), encoding="utf-8")

    summary = payload["summary"]
    health = payload["source_health"]
    print(json.dumps({
        "source": health["source"],
        "status": health["status"],
        "scoped_record_count": summary["scoped_record_count"],
        "relevant_record_count": summary["relevant_record_count"],
        "open_relevant_opportunities": summary["open_relevant_opportunities"],
        "recent_relevant_awards": summary["recent_relevant_awards"],
        "unresolved_vendor_count": summary["unresolved_vendor_count"],
        "pagination_complete": health["pagination_complete"],
        "schema_valid": health["schema_valid"],
        "output": str(args.output),
    }, indent=2))


if __name__ == "__main__":
    main()
