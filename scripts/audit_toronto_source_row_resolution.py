from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from toronto_app_sources import _record_for_link, load_source_rows
from toronto_market_common import canonical_street_address

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data/toronto/market/current"
REPORT = MARKET / "source_row_resolution_audit.json"

ADDRESS_FIELDS = {
    "affordable_housing_pipeline": ("Anchor Address", "Addresses"),
    "apartment_building_evaluation": ("SITE ADDRESS",),
    "business_licence_matches_prior_poc": ("Licence Address Line 1",),
    "chemtrac_2024": ("FA_ADDRESS_GIVEN",),
    "chemtrac_history": ("FA_ADDRESS_GIVEN",),
    "development_pipeline": ("Address",),
    "ontario_environmental_compliance_reports": ("Site Address",),
    "renewable_energy_installations": ("CLIENT_ADDRESS", "ADDRESS_FULL"),
    "toronto_aic_applications": ("FULL_ADDRESS",),
    "toronto_highrise_residential_health_hazards": ("address",),
}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected object: {path}")
    return value


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def canonical(value: Any) -> str:
    return canonical_street_address(value) or ""


def address_matches(link: dict[str, Any], row: dict[str, Any]) -> bool | None:
    source = clean(link.get("source_key"))
    fields = ADDRESS_FIELDS.get(source)
    if not fields:
        return None
    expected = canonical(link.get("source_address"))
    if not expected:
        return None
    observed = {canonical(row.get(field)) for field in fields if canonical(row.get(field))}
    return expected in observed


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Toronto stable source-row resolution and row-index provenance")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    links = [x for x in (load(MARKET / "property_source_links.json").get("links") or []) if isinstance(x, dict)]
    rows = load_source_rows(ROOT, load)
    stats: dict[str, Counter] = {}
    samples: list[dict[str, Any]] = []

    for link in links:
        source = clean(link.get("source_key"))
        if source not in ADDRESS_FIELDS:
            continue
        counter = stats.setdefault(source, Counter())
        source_rows = rows.get(source) or []

        index = link.get("source_row_index")
        indexed_row = source_rows[index] if isinstance(index, int) and 0 <= index < len(source_rows) else {}
        index_match = address_matches(link, indexed_row) if indexed_row else None
        if index_match is True:
            counter["index_address_match"] += 1
        elif index_match is False:
            counter["index_address_mismatch"] += 1
        else:
            counter["index_not_comparable"] += 1

        resolved_row = _record_for_link(link, rows)
        resolved_match = address_matches(link, resolved_row) if resolved_row else None
        if resolved_match is True:
            counter["stable_id_address_match"] += 1
        elif resolved_row and resolved_match is False:
            counter["stable_id_address_mismatch"] += 1
        else:
            counter["stable_id_unresolved"] += 1

        if (index_match is False or resolved_match is not True) and len(samples) < 100:
            fields = ADDRESS_FIELDS[source]
            samples.append({
                "source_key": source,
                "property_id": link.get("property_id"),
                "source_record_id": link.get("source_record_id"),
                "source_row_index": link.get("source_row_index"),
                "expected_source_address": link.get("source_address"),
                "indexed_row_addresses": {field: indexed_row.get(field) for field in fields} if indexed_row else {},
                "resolved_row_addresses": {field: resolved_row.get(field) for field in fields} if resolved_row else {},
            })

    hard_failures = {
        "stable_id_unresolved": sum(counter["stable_id_unresolved"] for counter in stats.values()),
        "stable_id_address_mismatch": sum(counter["stable_id_address_mismatch"] for counter in stats.values()),
    }
    hard_failures = {key: value for key, value in hard_failures.items() if value}
    index_mismatches = sum(counter["index_address_mismatch"] for counter in stats.values())

    output = {
        "schema_version": "toronto-source-row-resolution-audit-1.1",
        "source_links": len(links),
        "status": "FAILED" if hard_failures else "PASSED_WITH_INDEX_PROVENANCE_DRIFT" if index_mismatches else "PASSED",
        "sources": {source: dict(counter) for source, counter in sorted(stats.items())},
        "hard_failures": hard_failures,
        "index_address_mismatches": index_mismatches,
        "samples": samples,
    }
    REPORT.write_text(json.dumps(output, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in output.items() if key != "samples"}, indent=2))
    if args.strict and hard_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
