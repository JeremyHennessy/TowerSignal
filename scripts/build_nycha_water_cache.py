from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.checkbook_nycha import build_payload  # noqa: E402


def build(output: Path, *, fiscal_year_count: int, page_size: int) -> dict:
    payload = build_payload(
        fiscal_year_count=fiscal_year_count,
        page_size=page_size,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build TowerSignal NYCHA water-contract release/line cache"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fiscal-year-count", type=int, default=5)
    parser.add_argument("--page-size", type=int, default=5000)
    args = parser.parse_args()
    payload = build(
        args.output,
        fiscal_year_count=args.fiscal_year_count,
        page_size=args.page_size,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
