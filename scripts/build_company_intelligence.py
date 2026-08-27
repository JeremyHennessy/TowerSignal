#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.company_intelligence import build_company_intelligence
from towersignal.procurement import utc_now


def load_json(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"Required procurement input is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Malformed procurement input {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"Procurement input must be an object: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build conservative TowerSignal observed-vendor company intelligence.")
    parser.add_argument("--city-record", default="public/data/procurement-city-record.json")
    parser.add_argument("--checkbook", default="public/data/procurement-checkbook.json")
    parser.add_argument("--output", default="public/data/companies.json")
    parser.add_argument("--as-of", default=None, help="Optional YYYY-MM-DD metric date; defaults to today.")
    args = parser.parse_args()

    city_record = load_json(Path(args.city_record))
    checkbook = load_json(Path(args.checkbook))
    notices = city_record.get("notices")
    contracts = checkbook.get("contracts")
    if not isinstance(notices, list):
        raise SystemExit("City Record procurement input is missing notices[]")
    if not isinstance(contracts, list):
        raise SystemExit("Checkbook procurement input is missing contracts[]")

    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    generated_at = max(
        str(city_record.get("generated_at") or ""),
        str(checkbook.get("generated_at") or ""),
        utc_now(),
    )
    payload = build_company_intelligence([*notices, *contracts], generated_at=generated_at, as_of=as_of)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = payload["summary"]
    print(json.dumps({"output": str(output), **summary}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
