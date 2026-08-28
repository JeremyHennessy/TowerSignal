from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.nys_authority_procurement import build_payload  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and normalize relevant NYS public-authority procurement reports")
    parser.add_argument("--output", type=Path, default=ROOT / "public" / "data" / "procurement-nys-authorities.json")
    parser.add_argument("--cohort", type=Path, default=ROOT / "data" / "fixtures" / "deal-validation-cohort.json")
    args = parser.parse_args()

    cohort = json.loads(args.cohort.read_text(encoding="utf-8"))
    aliases = [
        str(alias)
        for target in cohort.get("targets", [])
        if isinstance(target, dict)
        for alias in target.get("aliases", [])
        if str(alias).strip()
    ]
    payload = build_payload(cohort_aliases=aliases)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    print(json.dumps({"output": str(args.output), **payload["summary"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
