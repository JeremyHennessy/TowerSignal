from __future__ import annotations

import argparse
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path


def validate(data_path: Path, summary_path: Path, *, max_age_days: int, require_production_volume: bool) -> dict:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("schema_version") != "1.0":
        raise RuntimeError("Unexpected lead-service-line schema version")
    generated = datetime.fromisoformat(str(summary.get("generated_at") or "").replace("Z", "+00:00"))
    age = (datetime.now(timezone.utc) - generated).total_seconds() / 86400
    if age < -0.05 or age > max_age_days:
        raise RuntimeError(f"Lead-service-line cache generated_at age is {age:.2f} days")

    source = summary.get("source")
    counts = summary.get("summary")
    if not isinstance(source, dict) or not isinstance(counts, dict):
        raise RuntimeError("Lead-service-line summary missing source/counts")
    expected = int(source.get("source_record_count") or -1)
    fetched = int(source.get("fetched_record_count") or -2)
    if expected != fetched or source.get("pagination_complete") is not True:
        raise RuntimeError("Lead-service-line source count/pagination proof failed")
    if int(counts.get("record_count") or -3) != expected:
        raise RuntimeError("Lead-service-line summary record count mismatch")
    if source.get("geometry_excluded") is not True:
        raise RuntimeError("Lead-service-line cache unexpectedly includes geometry")

    if require_production_volume:
        if expected < 800000:
            raise RuntimeError(f"Implausibly small lead-service-line source: {expected:,}")
        if int(counts.get("unique_bbl_count") or 0) < 500000:
            raise RuntimeError(f"Implausibly small unique BBL count: {counts.get('unique_bbl_count')}")

    line_count = 0
    with gzip.open(data_path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row.get("source_dataset_id") != source.get("dataset_id"):
                raise RuntimeError("Lead-service-line row has wrong source dataset ID")
            line_count += 1
    if line_count != expected:
        raise RuntimeError(f"Lead-service-line gzip row count mismatch: {line_count:,} != {expected:,}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate exact-count NYC DEP lead-service-line cache")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--max-age-days", type=int, default=1)
    parser.add_argument("--require-production-volume", action="store_true")
    args = parser.parse_args()
    summary = validate(args.data, args.summary, max_age_days=args.max_age_days, require_production_volume=args.require_production_volume)
    print(json.dumps(summary["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
