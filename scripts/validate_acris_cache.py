from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.acris import validate_cache_file  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate TowerSignal verified ACRIS cache")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--max-age-days", type=float, default=30.0)
    parser.add_argument("--require-production-volume", action="store_true")
    args = parser.parse_args()
    result = validate_cache_file(
        args.cache,
        max_age_days=args.max_age_days,
        require_production_volume=args.require_production_volume,
    )
    cache = result["cache"]
    print(json.dumps({
        "status": "PASS",
        "size_bytes": result["size_bytes"],
        "age_days": result["age_days"],
        "generated_at": cache["generated_at"],
        "properties": len(cache["properties"]),
        "documents": cache["metrics"]["matched_recent_document_count"],
    }, indent=2))


if __name__ == "__main__":
    main()
