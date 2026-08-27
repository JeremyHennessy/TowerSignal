from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.checkbook import compact_cache_summary
from towersignal.checkbook_recent import DEFAULT_FISCAL_YEAR_COUNT, build_recent_checkbook_cache


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a verified TowerSignal Checkbook NYC procurement cache")
    parser.add_argument("--output", type=Path, default=Path("checkbook-cache/cache.json"))
    parser.add_argument("--page-size", type=int, default=5000)
    parser.add_argument("--fiscal-year-count", type=int, default=DEFAULT_FISCAL_YEAR_COUNT)
    parser.add_argument("--as-of", type=date.fromisoformat, default=None)
    args = parser.parse_args()

    payload = build_recent_checkbook_cache(
        as_of=args.as_of,
        fiscal_year_count=args.fiscal_year_count,
        page_size=args.page_size,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(compact_cache_summary(payload))


if __name__ == "__main__":
    main()
