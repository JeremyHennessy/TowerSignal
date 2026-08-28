from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.deal_validation import build_deal_validation  # noqa: E402


def load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Expected JSON object: {path}")
    return payload


def rows_from_payload(payload: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    for key in ("contracts", "notices", "records"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    raise SystemExit(f"Procurement input has no contracts[], notices[] or records[]: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build TowerSignal empirical deal-intelligence validation report")
    parser.add_argument("--city-record", type=Path, default=ROOT / "public" / "data" / "procurement-city-record.json")
    parser.add_argument("--checkbook", type=Path, default=ROOT / "public" / "data" / "procurement-checkbook.json")
    parser.add_argument("--extra-procurement", action="append", type=Path, default=[], help="Additional normalized procurement payload; may be repeated.")
    parser.add_argument("--cohort", type=Path, default=ROOT / "data" / "fixtures" / "deal-validation-cohort.json")
    parser.add_argument("--output", type=Path, default=ROOT / "public" / "data" / "deal-validation.json")
    args = parser.parse_args()

    input_paths = [args.city_record, args.checkbook, *args.extra_procurement]
    rows = [row for path in input_paths for row in rows_from_payload(load_object(path), path)]
    cohort = load_object(args.cohort)

    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    report = build_deal_validation(rows, cohort, generated_at=generated_at)
    report.setdefault("methodology", {})["source_payload_count"] = len(input_paths)
    report["methodology"]["source_payloads"] = [path.name for path in input_paths]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8")

    print(json.dumps({
        "output": str(args.output),
        "source_payload_count": len(input_paths),
        "summary": report["summary"],
        "validation_gate": report["validation_gate"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
