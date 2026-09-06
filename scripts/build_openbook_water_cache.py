from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal import openbook_water  # noqa: E402
from towersignal.openbook_water_guard import classify_water_contract  # noqa: E402


def build(output: Path) -> dict:
    # Apply the source-specific context guard at the build boundary without
    # altering the shared TowerSignal procurement classifier.
    openbook_water.classify_water_contract = classify_water_contract
    payload = openbook_water.build_payload()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build TowerSignal Open Book NY water-contract transaction cache"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build(args.output)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
