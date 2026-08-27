from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.deal_validation import build_deal_validation  # noqa: E402


def load_object(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Expected JSON object: {path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build TowerSignal empirical deal-intelligence validation report")
    parser.add_argument("--city-record", type=Path, default=ROOT / "public" / "data" / "procurement-city-record.json")
    parser.add_argument("--checkbook", type=Path, default=ROOT / "public" / "data" / "procurement-checkbook.json")
    parser.add_argument("--cohort", type=Path, default=ROOT / "data" / "fixtures" / "deal-validation-cohort.json")
    parser.add_argument("--output", type=Path, default=ROOT / "public" / "data" / "deal-validation.json")
    args = parser.parse_args()

    city_record = load_object(args.city_record)
    checkbook = load_object(args.checkbook)
    cohort = load_object(args.cohort)
    notices = city_record.get("notices")
    contracts = checkbook.get("contracts")
    if not isinstance(notices, list) or not isinstance(contracts, list):
        raise SystemExit("Procurement inputs are missing notices[] or contracts[]")

    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    report = build_deal_validation([*notices, *contracts], cohort, generated_at=generated_at)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8")

    print(json.dumps({
        "output": str(args.output),
        "summary": report["summary"],
        "validation_gate": report["validation_gate"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
