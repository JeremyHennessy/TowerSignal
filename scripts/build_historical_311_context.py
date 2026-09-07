from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.historical_311_context import build_historical_context  # noqa: E402


def _normalize_bbl(value: object) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits if len(digits) == 10 and digits[0] in "12345" else None


def load_current_bbls(systems_path: Path) -> list[str]:
    payload = json.loads(systems_path.read_text(encoding="utf-8"))
    systems = payload.get("systems")
    if not isinstance(systems, list):
        raise RuntimeError("TowerSignal systems payload is malformed")
    return sorted({bbl for row in systems if isinstance(row, dict) and (bbl := _normalize_bbl(row.get("bbl")))})


def main() -> None:
    parser = argparse.ArgumentParser(description="Build compact exact-BBL NYC historical 311 building-water context")
    parser.add_argument("--systems", type=Path, default=ROOT / "public/data/systems.json")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data/historical-311-context.json")
    parser.add_argument("--bbl-batch-size", type=int, default=200)
    parser.add_argument("--page-size", type=int, default=5000)
    args = parser.parse_args()

    bbls = load_current_bbls(args.systems)
    if len(bbls) < 3000:
        raise RuntimeError(f"Refusing historical 311 build for implausibly small TowerSignal BBL universe: {len(bbls):,}")
    print(f"[historical-311] Building compact context for {len(bbls):,} exact TowerSignal BBLs", flush=True)
    payload = build_historical_context(bbls, batch_size=args.bbl_batch_size, page_size=args.page_size)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
