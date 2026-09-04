from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.fetch import fetch_dataset  # noqa: E402
from towersignal.normalize import normalize_registrations  # noqa: E402
from towersignal.planimetrics import fetch_planimetric_towers_by_bin  # noqa: E402

REGISTRATION_ID = "y4fw-iqfr"


def verify(output: Path) -> dict:
    registration_snapshot = fetch_dataset(REGISTRATION_ID, "system_id")
    systems, _ = normalize_registrations(registration_snapshot.rows)
    requested_bins = sorted({str(system["bin"]) for system in systems if system.get("bin")}, key=int)
    by_bin, metadata = fetch_planimetric_towers_by_bin(requested_bins)

    if not requested_bins:
        raise RuntimeError("Current NYC cooling-tower registry produced zero usable BINs")
    if metadata["matched_bin_count"] <= 0 or metadata["matched_feature_count"] <= 0:
        raise RuntimeError("NYC Planimetric source produced zero exact-BIN physical tower matches")

    feature_ids: set[str] = set()
    statuses: Counter[str] = Counter()
    feature_codes: Counter[str] = Counter()
    sub_feature_codes: Counter[str] = Counter()
    geometry_types: Counter[str] = Counter()
    matched_system_count = 0

    for system in systems:
        if system.get("bin") and str(system["bin"]) in by_bin:
            matched_system_count += 1

    for bin_value, features in by_bin.items():
        if bin_value not in requested_bins:
            raise RuntimeError(f"Live Planimetric query returned unrequested BIN {bin_value}")
        for feature in features:
            if feature["bin"] != bin_value or feature["match_basis"] != "BIN_EXACT":
                raise RuntimeError(f"Invalid exact-BIN provenance for Planimetric feature on BIN {bin_value}")
            identity = str(feature.get("source_id") or feature.get("global_id") or "")
            if not identity or identity in feature_ids:
                raise RuntimeError(f"Missing or duplicate Planimetric feature identity: {identity!r}")
            feature_ids.add(identity)
            statuses[str(feature.get("status") or "UNPUBLISHED")] += 1
            feature_codes[str(feature.get("feature_code") or "UNPUBLISHED")] += 1
            sub_feature_codes[str(feature.get("sub_feature_code") or "UNPUBLISHED")] += 1
            geometry_types[str(feature["geometry"]["type"])] += 1

    unmatched_bins = len(requested_bins) - metadata["matched_bin_count"]
    coverage = round((metadata["matched_bin_count"] / len(requested_bins)) * 100, 2)
    sample = []
    for bin_value in sorted(by_bin, key=int)[:5]:
        for feature in by_bin[bin_value][:2]:
            sample.append({
                "bin": bin_value,
                "source_id": feature.get("source_id"),
                "global_id": feature.get("global_id"),
                "feature_code": feature.get("feature_code"),
                "sub_feature_code": feature.get("sub_feature_code"),
                "status": feature.get("status"),
                "geometry_type": feature["geometry"]["type"],
                "imagery_year": feature["imagery_year"],
                "match_basis": feature["match_basis"],
            })

    report = {
        "result": "PASS",
        "registry": {
            "source_record_count": registration_snapshot.source_record_count,
            "normalized_system_count": len(systems),
            "usable_distinct_bin_count": len(requested_bins),
        },
        "planimetric": {
            **metadata,
            "matched_system_count": matched_system_count,
            "unmatched_registry_bin_count": unmatched_bins,
            "exact_bin_coverage_percentage": coverage,
            "status_counts": dict(sorted(statuses.items())),
            "feature_code_counts": dict(sorted(feature_codes.items())),
            "sub_feature_code_counts": dict(sorted(sub_feature_codes.items())),
            "geometry_type_counts": dict(sorted(geometry_types.items())),
        },
        "sample_features": sample,
        "evidence_boundary": (
            "Exact BIN coverage compares the current regulatory registry with a 2022 aerial-derived physical inventory. "
            "A missing physical match is not evidence that a registered tower does not exist, and a matched building feature is not a one-to-one System ID identity claim."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Independently verify current NYC Planimetric cooling-tower exact-BIN coverage")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/planimetric-live-verification.json")
    args = parser.parse_args()
    verify(args.output)


if __name__ == "__main__":
    main()
