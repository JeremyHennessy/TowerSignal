from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.legionella_alerts import collect  # noqa: E402


def build(output_path: Path) -> dict:
    payload = collect()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect official Legionella / Legionnaires public-health alerts for TowerSignal")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data/legionella-alerts.json")
    args = parser.parse_args()
    build(args.output)


if __name__ == "__main__":
    main()
