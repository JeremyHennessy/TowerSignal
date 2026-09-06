from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.nyc_water_signals import build_payload  # noqa: E402


def log_step(message: str) -> None:
    print(f"[build_nyc_water_signals_cache] {message}", flush=True)


def build(output: Path, *, page_size: int) -> dict:
    log_step(f"building payload with page size {page_size:,}")
    payload = build_payload(page_size=page_size)
    log_step("writing NYC building-water signal cache")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    log_step("wrote NYC building-water signal cache")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build TowerSignal NYC building-water signal cache")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--page-size", type=int, default=50000)
    args = parser.parse_args()
    payload = build(args.output, page_size=args.page_size)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
