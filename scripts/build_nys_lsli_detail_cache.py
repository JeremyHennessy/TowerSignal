from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.nys_lsli_detail import build_payload  # noqa: E402


def build(output: Path, *, request_delay_seconds: float, max_workers: int) -> dict:
    payload = build_payload(request_delay_seconds=request_delay_seconds, max_workers=max_workers)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build complete NYSDOH LSLI detail cache")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--request-delay-seconds", type=float, default=0.15)
    parser.add_argument("--max-workers", type=int, default=1)
    args = parser.parse_args()
    payload = build(args.output, request_delay_seconds=args.request_delay_seconds, max_workers=args.max_workers)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
