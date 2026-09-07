from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.fetch import fetch_dataset  # noqa: E402
from towersignal.normalize import normalize_registrations  # noqa: E402
from towersignal.pluto import normalize_bbl  # noqa: E402

REGISTRATION_DATASET_ID = "y4fw-iqfr"
BOROUGH_CODE_BY_NAME = {
    "MANHATTAN": "1",
    "BRONX": "2",
    "BROOKLYN": "3",
    "QUEENS": "4",
    "STATEN ISLAND": "5",
}
BOROUGH_NAME_BY_CODE = {value: key for key, value in BOROUGH_CODE_BY_NAME.items()}


def _published_borough(value: Any) -> str:
    text = str(value or "UNKNOWN").strip().upper() or "UNKNOWN"
    aliases = {
        "MN": "MANHATTAN",
        "BX": "BRONX",
        "BK": "BROOKLYN",
        "QN": "QUEENS",
        "SI": "STATEN ISLAND",
        "STATEN ISLAND / RICHMOND": "STATEN ISLAND",
    }
    return aliases.get(text, text)


def build_quality_report(systems: list[dict[str, Any]]) -> dict[str, Any]:
    published = Counter()
    valid = Counter()
    missing = Counter()
    prefix = Counter()
    mismatch = Counter()
    invalid_examples: list[dict[str, Any]] = []
    mismatch_examples: list[dict[str, Any]] = []

    for system in systems:
        borough = _published_borough(system.get("borough"))
        published[borough] += 1
        raw_bbl = system.get("bbl")
        bbl = normalize_bbl(raw_bbl)
        if not bbl:
            missing[borough] += 1
            if len(invalid_examples) < 50:
                invalid_examples.append({
                    "system_id": system.get("system_id"),
                    "borough": borough,
                    "raw_bbl": raw_bbl,
                    "bin": system.get("bin"),
                    "address": system.get("address"),
                })
            continue

        padded = bbl.zfill(10)
        if len(padded) != 10 or padded[0] not in BOROUGH_NAME_BY_CODE:
            missing[borough] += 1
            if len(invalid_examples) < 50:
                invalid_examples.append({
                    "system_id": system.get("system_id"),
                    "borough": borough,
                    "raw_bbl": raw_bbl,
                    "normalized_bbl": bbl,
                    "bin": system.get("bin"),
                    "address": system.get("address"),
                })
            continue

        valid[borough] += 1
        prefix_borough = BOROUGH_NAME_BY_CODE[padded[0]]
        prefix[prefix_borough] += 1
        expected = BOROUGH_CODE_BY_NAME.get(borough)
        if expected is not None and expected != padded[0]:
            mismatch[borough] += 1
            if len(mismatch_examples) < 50:
                mismatch_examples.append({
                    "system_id": system.get("system_id"),
                    "published_borough": borough,
                    "bbl_prefix_borough": prefix_borough,
                    "raw_bbl": raw_bbl,
                    "normalized_bbl": bbl,
                    "bin": system.get("bin"),
                    "address": system.get("address"),
                })

    totals = {
        borough: {
            "systems": published.get(borough, 0),
            "valid_bbl": valid.get(borough, 0),
            "missing_or_invalid_bbl": missing.get(borough, 0),
            "valid_bbl_percentage": round(
                (valid.get(borough, 0) / published[borough] * 100.0) if published[borough] else 0.0,
                2,
            ),
            "published_borough_vs_bbl_prefix_mismatches": mismatch.get(borough, 0),
        }
        for borough in sorted(published)
    }

    valid_total = sum(valid.values())
    system_total = len(systems)
    return {
        "system_count": system_total,
        "valid_bbl_system_count": valid_total,
        "missing_or_invalid_bbl_system_count": system_total - valid_total,
        "valid_bbl_percentage": round(valid_total / system_total * 100.0, 2) if system_total else 0.0,
        "published_borough_breakdown": totals,
        "valid_bbl_prefix_breakdown": dict(sorted(prefix.items())),
        "published_borough_vs_bbl_prefix_mismatch_count": sum(mismatch.values()),
        "invalid_bbl_examples": invalid_examples,
        "borough_prefix_mismatch_examples": mismatch_examples,
        "evidence_boundary": (
            "Missing or conflicting registry BBL values are source-identity gaps. They do not authorize fuzzy property joins, "
            "do not imply a missing cooling tower, and must not be repaired through scoring or display logic."
        ),
    }


def run(output: Path) -> dict[str, Any]:
    snapshot = fetch_dataset(REGISTRATION_DATASET_ID, "system_id")
    systems, dedupe = normalize_registrations(snapshot.rows)
    report = {
        "dataset_id": snapshot.dataset_id,
        "dataset_name": snapshot.name,
        "source_record_count": snapshot.source_record_count,
        "source_last_updated_at": snapshot.source_last_updated_at,
        "retrieved_at": snapshot.retrieved_at,
        "dedupe": dedupe,
        "quality": build_quality_report(systems),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["quality"], indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit cooling-tower registration BBL quality by borough")
    parser.add_argument("--output", type=Path, default=Path("registration-bbl-quality.json"))
    args = parser.parse_args()
    run(args.output)


if __name__ == "__main__":
    main()
