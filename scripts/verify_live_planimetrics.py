from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.fetch import fetch_count, fetch_dataset, fetch_metadata, fetch_where  # noqa: E402
from towersignal.normalize import normalize_registrations  # noqa: E402
from towersignal.planimetrics import DATASET_ID, DATASET_URL, IMAGERY_YEAR, MATCH_BASIS, SELECT_FIELDS, normalize_bin, normalize_planimetric_row  # noqa: E402

REGISTRATION_ID = "y4fw-iqfr"
BATCH_SIZE = 150


def verify(output: Path) -> dict:
    registration_snapshot = fetch_dataset(REGISTRATION_ID, "system_id")
    systems, _ = normalize_registrations(registration_snapshot.rows)
    requested_bins = sorted({value for system in systems if (value := normalize_bin(system.get("bin")))}, key=int)
    requested_set = set(requested_bins)

    source_record_count = fetch_count(DATASET_ID)
    source_metadata = fetch_metadata(DATASET_ID)
    by_bin: dict[str, list[dict]] = {}
    source_ids: Counter[str] = Counter()
    global_ids: Counter[str] = Counter()

    for start in range(0, len(requested_bins), BATCH_SIZE):
        chunk = requested_bins[start:start + BATCH_SIZE]
        rows = fetch_where(
            DATASET_ID,
            f"bin in ({','.join(chunk)})",
            order_by="bin,source_id",
            select=SELECT_FIELDS,
        )
        for raw in rows:
            feature = normalize_planimetric_row(raw)
            bin_value = feature["bin"]
            if bin_value not in requested_set:
                raise RuntimeError(f"Live Planimetric query returned unrequested BIN {bin_value}")
            by_bin.setdefault(bin_value, []).append(feature)
            if feature.get("source_id"):
                source_ids[str(feature["source_id"])] += 1
            if feature.get("global_id"):
                global_ids[str(feature["global_id"])] += 1

    features = [feature for bin_features in by_bin.values() for feature in bin_features]
    missing_global_id_count = sum(1 for feature in features if not feature.get("global_id"))
    duplicate_source_ids = {key: count for key, count in source_ids.items() if count > 1}
    duplicate_global_ids = {key: count for key, count in global_ids.items() if count > 1}

    if not requested_bins:
        raise RuntimeError("Current NYC cooling-tower registry produced zero usable BINs")
    if not features:
        raise RuntimeError("NYC Planimetric source produced zero exact-BIN physical tower matches")
    if missing_global_id_count:
        raise RuntimeError(f"Matched Planimetric features contain {missing_global_id_count} rows without GlobalID")
    if duplicate_global_ids:
        examples = list(sorted(duplicate_global_ids.items()))[:5]
        raise RuntimeError(f"Matched Planimetric GlobalID values are not unique; examples: {examples}")

    statuses: Counter[str] = Counter()
    feature_codes: Counter[str] = Counter()
    sub_feature_codes: Counter[str] = Counter()
    geometry_types: Counter[str] = Counter()
    matched_system_count = 0

    for system in systems:
        bin_value = normalize_bin(system.get("bin"))
        if bin_value and bin_value in by_bin:
            matched_system_count += 1

    for bin_value, bin_features in by_bin.items():
        for feature in bin_features:
            if feature["bin"] != bin_value or feature["match_basis"] != MATCH_BASIS:
                raise RuntimeError(f"Invalid exact-BIN provenance for Planimetric feature on BIN {bin_value}")
            statuses[str(feature.get("status") or "UNPUBLISHED")] += 1
            feature_codes[str(feature.get("feature_code") or "UNPUBLISHED")] += 1
            sub_feature_codes[str(feature.get("sub_feature_code") or "UNPUBLISHED")] += 1
            geometry_types[str(feature["geometry"]["type"])] += 1

    unmatched_bins = len(requested_bins) - len(by_bin)
    coverage = round((len(by_bin) / len(requested_bins)) * 100, 2)
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
            "dataset_id": DATASET_ID,
            "name": source_metadata.get("name"),
            "url": DATASET_URL,
            "source_record_count": source_record_count,
            "source_last_updated_at": source_metadata.get("source_last_updated_at"),
            "matched_bin_count": len(by_bin),
            "matched_feature_count": len(features),
            "matched_system_count": matched_system_count,
            "unmatched_registry_bin_count": unmatched_bins,
            "exact_bin_coverage_percentage": coverage,
            "imagery_year": IMAGERY_YEAR,
            "match_basis": MATCH_BASIS,
            "identifier_diagnostic": {
                "source_id_distinct_count": len(source_ids),
                "source_id_duplicate_value_count": len(duplicate_source_ids),
                "source_id_duplicate_examples": list(sorted(duplicate_source_ids.items()))[:10],
                "global_id_distinct_count": len(global_ids),
                "global_id_missing_count": missing_global_id_count,
                "global_id_duplicate_value_count": len(duplicate_global_ids),
            },
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
