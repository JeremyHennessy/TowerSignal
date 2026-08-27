from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.checkbook import (
    CITYWIDE_SCOPE,
    CheckbookSourceError,
    compact_cache_summary,
    fetch_scope,
)
from towersignal.checkbook_recent import DEFAULT_FISCAL_YEAR_COUNT, build_recent_checkbook_cache


_CONFLICT_RE = re.compile(r"prime_contract_id=([^ ]+) in FY(\d+)(?: version ([^ ]+))?")


def _print_conflict_evidence(exc: CheckbookSourceError) -> None:
    """Re-query one conflicting public contract so CI logs show the exact source disagreement."""
    match = _CONFLICT_RE.search(str(exc))
    if not match:
        return
    contract_id, fiscal_year, _ = match.groups()
    try:
        result = fetch_scope(
            CITYWIDE_SCOPE,
            page_size=100,
            extra_criteria=(
                ("fiscal_year", "value", fiscal_year),
                ("contract_id", "value", contract_id),
            ),
        )
    except Exception as diagnostic_exc:  # pragma: no cover - live diagnostic only
        print(f"Checkbook conflict diagnostic failed: {diagnostic_exc}", file=sys.stderr)
        return
    print(
        json.dumps(
            {
                "checkbook_conflict": {
                    "contract_id": contract_id,
                    "fiscal_year": int(fiscal_year),
                    "record_count": result.expected_count,
                    "rows": list(result.rows),
                }
            },
            indent=2,
            sort_keys=True,
        ),
        file=sys.stderr,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a verified TowerSignal Checkbook NYC procurement cache")
    parser.add_argument("--output", type=Path, default=Path("checkbook-cache/cache.json"))
    parser.add_argument("--page-size", type=int, default=5000)
    parser.add_argument("--fiscal-year-count", type=int, default=DEFAULT_FISCAL_YEAR_COUNT)
    parser.add_argument("--as-of", type=date.fromisoformat, default=None)
    args = parser.parse_args()

    try:
        payload = build_recent_checkbook_cache(
            as_of=args.as_of,
            fiscal_year_count=args.fiscal_year_count,
            page_size=args.page_size,
        )
    except CheckbookSourceError as exc:
        _print_conflict_evidence(exc)
        raise
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(compact_cache_summary(payload))


if __name__ == "__main__":
    main()
