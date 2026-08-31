from __future__ import annotations

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


def stable_id_from_link(link: dict[str, Any]) -> str | None:
    source = clean(link.get("source_key"))
    rid = clean(link.get("source_record_id"))
    prefix = f"{source}:"
    if not rid.startswith(prefix):
        return None
    tail = rid[len(prefix):]
    if ":" not in tail:
        return tail or None
    stable, _index = tail.rsplit(":", 1)
    if stable in {"", "row"}:
        return None
    return stable


def stable_row(link: dict[str, Any], source_rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    source = clean(link.get("source_key"))
    stable_id = stable_id_from_link(link)
    if not stable_id:
        return {}
    for row in source_rows.get(source, []):
        if clean(row.get("_id")) == stable_id:
            return row
    return {}


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
    links = [x for x in (load(MARKET / "property_source_links.json").get("links") or []) if isinstance(x, dict)]
    rows = load_source_rows(ROOT, load)
    stats: dict[str, Counter] = {}
    samples: list[dict[str, Any]] = []
    stable_recovers = 0
    unresolved_stable_ids = 0

    for link in links:
        source = clean(link.get("source_key"))
        if source not in ADDRESS_FIELDS:
            continue
        counter = stats.setdefault(source, Counter())
        index_row = _record_for_link(link, rows)
        index_match = address_matches(link, index_row)
        if index_match is True:
            counter["index_address_match"] += 1
            continue
        if index_match is None:
            counter["not_comparable"] += 1
            continue
        counter["index_address_mismatch"] += 1
        recovered = stable_row(link, rows)
        stable_match = address_matches(link, recovered) if recovered else None
        if stable_match is True:
            counter["stable_id_recovers"] += 1
            stable_recovers += 1
        elif stable_id_from_link(link):
            counter["stable_id_not_resolved_or_mismatch"] += 1
            unresolved_stable_ids += 1
        else:
            counter["no_stable_id_available"] += 1
        if len(samples) < 100:
            fields = ADDRESS_FIELDS[source]
            samples.append({
                "source_key": source,
                "property_id": link.get("property_id"),
                "source_record_id": link.get("source_record_id"),
                "source_row_index": link.get("source_row_index"),
                "expected_source_address": link.get("source_address"),
                "index_row_addresses": {field: index_row.get(field) for field in fields} if index_row else {},
                "stable_id": stable_id_from_link(link),
                "stable_row_addresses": {field: recovered.get(field) for field in fields} if recovered else {},
            })

    output = {
        "schema_version": "toronto-source-row-resolution-audit-1.0",
        "source_links": len(links),
        "sources": {source: dict(counter) for source, counter in sorted(stats.items())},
        "total_index_address_mismatches": sum(c["index_address_mismatch"] for c in stats.values()),
        "stable_id_recovers": stable_recovers,
        "stable_id_not_resolved_or_mismatch": unresolved_stable_ids,
        "samples": samples,
    }
    REPORT.write_text(json.dumps(output, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in output.items() if key != "samples"}, indent=2))


if __name__ == "__main__":
    main()
