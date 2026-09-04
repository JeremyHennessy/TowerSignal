from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.provider_resolution import build_resolution_payload  # noqa: E402


def build(domestic_cache: Path, output: Path) -> dict:
    source = json.loads(domestic_cache.read_text(encoding="utf-8"))
    payload = build_resolution_payload(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build conservative TowerSignal provider identity review queue")
    parser.add_argument("--domestic-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build(args.domestic_cache, args.output)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
