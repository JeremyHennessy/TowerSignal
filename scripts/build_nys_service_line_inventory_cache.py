from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.nys_service_line_inventory import build_cache  # noqa: E402


def build(data: Path, summary: Path) -> dict:
    return build_cache(data, summary)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build coherent full NYSDOH address-level service-line inventory cache"
    )
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    payload = build(args.data, args.summary)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
