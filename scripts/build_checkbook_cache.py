from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.checkbook import build_checkbook_cache, compact_cache_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a verified TowerSignal Checkbook NYC procurement cache")
    parser.add_argument("--output", type=Path, default=Path("checkbook-cache/cache.json"))
    parser.add_argument("--page-size", type=int, default=20000)
    args = parser.parse_args()

    payload = build_checkbook_cache(page_size=args.page_size)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(compact_cache_summary(payload))


if __name__ == "__main__":
    main()
