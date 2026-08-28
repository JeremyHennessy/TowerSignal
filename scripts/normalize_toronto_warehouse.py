from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TORONTO_OPEN_DATA_LICENSE = "Open Government Licence - Toronto"
TORONTO_MUNICIPALITIES = {
    "TORONTO",
    "ETOBICOKE",
    "NORTH YORK",
    "SCARBOROUGH",
    "EAST YORK",
    "YORK",
}


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def write_json(path: Path, payload: Any, *, pretty: bool = False) -> None:
    path.write_text(
        json.dumps(
            payload,
            indent=2 if pretty else None,
            separators=None if pretty else (",", ":"),
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )


def normalize_city(value: Any) -> str:
    return str(value or "").strip().upper()


def normalize_portal_licenses(output_dir: Path, inventory: dict[str, Any]) -> int:
    updated = 0
    for source in inventory.get("open_licensed_sources") or []:
        portal_url = str(source.get("portal_url") or "")
        license_value = str(source.get("license") or "").strip()
        if "open.toronto.ca" in portal_url and license_value.lower() in {
            "",
            "license not specified",
            "not specified",
            "none",
        }:
            source["license"] = TORONTO_OPEN_DATA_LICENSE
            source["license_basis"] = "Toronto Open Data portal-wide licence; package metadata did not provide a useful licence label."
            key = source.get("key")
            if key:
                candidates = [
                    output_dir / "open_licensed" / f"{key}.json",
                    output_dir / "open_licensed" / f"{key}_metadata.json",
                ]
                for path in candidates:
                    if not path.exists():
                        continue
                    payload = read_json(path)
                    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else payload
                    metadata["license"] = TORONTO_OPEN_DATA_LICENSE
                    metadata["license_basis"] = source["license_basis"]
                    write_json(path, payload, pretty=path.name.endswith("_metadata.json"))
            updated += 1
    return updated


def tighten_bps_scope(output_dir: Path, inventory: dict[str, Any]) -> dict[str, int]:
    path = output_dir / "open_licensed" / "ontario_bps_energy_2024.json"
    payload = read_json(path)
    rows = payload.get("toronto_candidates") or []
    if not isinstance(rows, list):
        raise RuntimeError("BPS Toronto candidate rows are not a list")
    strict = [
        row
        for row in rows
        if isinstance(row, dict) and normalize_city(row.get("City")) in TORONTO_MUNICIPALITIES
    ]
    relevant = []
    for row in strict:
        matches = []
        text = " | ".join(str(value) for value in row.values() if value not in (None, "")).lower()
        for keyword in (
            "cooling tower",
            "cooling towers",
            "chiller",
            "chillers",
            "condenser water",
            "evaporative condenser",
            "water treatment",
            "cooling water",
            "legionella",
            "chemical feed",
            "mechanical",
            "hvac",
            "boiler",
        ):
            if keyword in text:
                matches.append(keyword)
        if matches:
            enriched = dict(row)
            enriched["_towersignal_keyword_matches"] = sorted(set(matches))
            relevant.append(enriched)

    metadata = payload.get("metadata") or {}
    original = int(metadata.get("toronto_candidate_row_count") or len(rows))
    metadata["pre_normalization_candidate_row_count"] = original
    metadata["toronto_candidate_row_count"] = len(strict)
    metadata["keyword_match_row_count"] = len(relevant)
    metadata["candidate_contract"] = (
        "Exact City field is Toronto, Etobicoke, North York, Scarborough, East York, or York. "
        "These are facility candidates only and do not establish cooling-tower presence."
    )
    payload["toronto_candidates"] = strict
    payload["keyword_matches"] = relevant
    write_json(path, payload)

    for source in inventory.get("open_licensed_sources") or []:
        if source.get("key") == "ontario_bps_energy_2024":
            source["pre_normalization_candidate_row_count"] = original
            source["toronto_candidate_row_count"] = len(strict)
            source["keyword_match_row_count"] = len(relevant)
            source["candidate_contract"] = metadata["candidate_contract"]

    return {"before": original, "after": len(strict), "keyword_matches": len(relevant)}


def tighten_access_environment_scope(output_dir: Path, inventory: dict[str, Any]) -> dict[str, dict[str, int]]:
    rights_dir = output_dir / "rights_review"
    results: dict[str, dict[str, int]] = {}
    access_summary = next(
        (
            item
            for item in inventory.get("rights_review_sources") or []
            if item.get("key") == "ontario_access_environment"
        ),
        None,
    )
    if not isinstance(access_summary, dict):
        return results

    for path in sorted(rights_dir.glob("*.json")):
        payload = read_json(path)
        metadata = payload.get("metadata") or {}
        key = str(metadata.get("key") or path.stem)
        features = payload.get("features") or []
        if not isinstance(features, list):
            raise RuntimeError(f"Access Environment features are not a list: {path}")

        # PTTW frequently omits municipality/address. Keep it bounded by the original
        # Toronto-envelope query and label it approximate rather than dropping records.
        if key == "permits_to_take_water":
            metadata["municipal_scope_contract"] = (
                "Approximate Toronto bounding-box only because source PTTW rows frequently omit municipality/address. "
                "Do not treat as exact Toronto membership until spatially joined to the municipal boundary."
            )
            results[key] = {"before": len(features), "after": len(features)}
            write_json(path, payload)
            continue

        strict_features = []
        for feature in features:
            if not isinstance(feature, dict):
                continue
            attributes = feature.get("attributes") or {}
            if normalize_city(attributes.get("MUNICIPALITY")) in TORONTO_MUNICIPALITIES:
                strict_features.append(feature)

        strict_ids = {
            (feature.get("attributes") or {}).get("OBJECTID")
            for feature in strict_features
        }
        keyword_matches = [
            item
            for item in (payload.get("keyword_matches") or [])
            if ((item.get("feature") or {}).get("attributes") or {}).get("OBJECTID") in strict_ids
        ]
        before = len(features)
        metadata["pre_normalization_feature_count"] = before
        metadata["feature_count"] = len(strict_features)
        metadata["keyword_match_feature_count"] = len(keyword_matches)
        metadata["scope"] = "EXACT_SOURCE_MUNICIPALITY_FIELD"
        metadata["municipal_scope_contract"] = (
            "Source MUNICIPALITY must equal Toronto, Etobicoke, North York, Scarborough, East York, or York."
        )
        payload["features"] = strict_features
        payload["keyword_matches"] = keyword_matches
        write_json(path, payload)
        results[key] = {"before": before, "after": len(strict_features)}

        layer_summary = (access_summary.get("layers") or {}).get(key)
        if isinstance(layer_summary, dict):
            layer_summary["pre_normalization_feature_count"] = before
            layer_summary["feature_count"] = len(strict_features)
            layer_summary["keyword_match_feature_count"] = len(keyword_matches)
            layer_summary["scope"] = metadata["scope"]
            layer_summary["municipal_scope_contract"] = metadata["municipal_scope_contract"]

    return results


def build(output_dir: Path) -> dict[str, Any]:
    inventory_path = output_dir / "source_inventory.json"
    inventory = read_json(inventory_path)
    licenses = normalize_portal_licenses(output_dir, inventory)
    bps = tighten_bps_scope(output_dir, inventory)
    environment = tighten_access_environment_scope(output_dir, inventory)
    inventory["normalization"] = {
        "toronto_portal_license_labels_normalized": licenses,
        "bps_city_scope": bps,
        "access_environment_scope": environment,
    }
    write_json(inventory_path, inventory, pretty=True)
    result = {
        "licenses_normalized": licenses,
        "bps": bps,
        "access_environment": environment,
    }
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize Toronto warehouse scope and metadata")
    parser.add_argument("--output", type=Path, default=ROOT / "data/toronto/warehouse/current")
    args = parser.parse_args()
    build(args.output)


if __name__ == "__main__":
    main()
