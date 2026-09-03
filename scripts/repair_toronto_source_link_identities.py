from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from toronto_app_sources import load_source_rows
from toronto_market_common import canonical_street_address, utc_now
from toronto_source_identity import clean, find_source_record, stable_source_record_id

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data/toronto/market/current"
LINKS_PATH = MARKET / "property_source_links.json"
REPORT_PATH = MARKET / "source_identity_repair_report.json"

TARGET_ADDRESS_FIELDS = {
    "business_licence_matches_prior_poc": ("Licence Address Line 1",),
    "renewable_energy_installations": ("CLIENT_ADDRESS", "ADDRESS_FULL"),
}
GENERIC_ID_FIELDS = ("_id", "OBJECTID", "id", "APPLICATION_NUMBER", "FOLDERRSN", "RSN", "document_number", "noticeId")


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected object: {path}")
    return value


def canonical(value: Any) -> str:
    return canonical_street_address(value) or ""


def address_matches(source: str, link: dict[str, Any], row: dict[str, Any]) -> bool:
    expected = canonical(link.get("source_address"))
    observed = {
        canonical(row.get(field))
        for field in TARGET_ADDRESS_FIELDS[source]
        if canonical(row.get(field))
    }
    return bool(expected) and expected in observed


def legacy_generic_id_resolve(source: str, record_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    prefix = f"{source}:id:"
    if not record_id.startswith(prefix):
        return {}
    wanted = record_id[len(prefix):]
    return next(
        (
            row
            for row in rows
            if any(clean(row.get(field)) == wanted for field in GENERIC_ID_FIELDS)
        ),
        {},
    )


def main() -> None:
    payload = load(LINKS_PATH)
    links = [item for item in payload.get("links", []) if isinstance(item, dict)]
    source_rows = load_source_rows(ROOT, load)
    stats: dict[str, Counter] = {source: Counter() for source in TARGET_ADDRESS_FIELDS}
    failures: list[dict[str, Any]] = []

    for link in links:
        source = clean(link.get("source_key"))
        if source not in TARGET_ADDRESS_FIELDS:
            continue
        counter = stats[source]
        counter["links"] += 1
        rows = source_rows.get(source) or []
        index = link.get("source_row_index")
        if not isinstance(index, int) or not (0 <= index < len(rows)):
            counter["invalid_source_row_index"] += 1
            failures.append({"reason": "INVALID_SOURCE_ROW_INDEX", "link": link})
            continue

        indexed_row = rows[index]
        if not address_matches(source, link, indexed_row):
            counter["index_address_mismatch"] += 1
            failures.append({
                "reason": "INDEX_ADDRESS_MISMATCH",
                "source_key": source,
                "source_record_id": link.get("source_record_id"),
                "source_row_index": index,
                "source_address": link.get("source_address"),
                "indexed_addresses": {field: indexed_row.get(field) for field in TARGET_ADDRESS_FIELDS[source]},
            })
            continue
        counter["index_address_match"] += 1

        old_record_id = clean(link.get("source_record_id"))
        resolved_before = find_source_record(source, old_record_id, rows)
        if resolved_before and address_matches(source, link, resolved_before):
            counter["stable_identity_resolved_before"] += 1
        else:
            counter["stable_identity_unresolved_before"] += 1

        if source == "renewable_energy_installations":
            legacy_row = legacy_generic_id_resolve(source, old_record_id, rows)
            if legacy_row and not address_matches(source, link, legacy_row):
                counter["legacy_cross_field_id_collision"] += 1

        expected_record_id = stable_source_record_id(source, indexed_row)
        if old_record_id != expected_record_id:
            link["source_record_id"] = expected_record_id
            counter["record_ids_rewritten"] += 1
        else:
            counter["record_ids_unchanged"] += 1

        resolved_after = find_source_record(source, clean(link.get("source_record_id")), rows)
        if not resolved_after or not address_matches(source, link, resolved_after):
            counter["stable_identity_failed_after"] += 1
            failures.append({
                "reason": "STABLE_IDENTITY_FAILED_AFTER_REPAIR",
                "source_key": source,
                "old_source_record_id": old_record_id,
                "new_source_record_id": link.get("source_record_id"),
                "source_row_index": index,
                "source_address": link.get("source_address"),
            })
        else:
            counter["stable_identity_resolved_after"] += 1

    exact_identities: set[tuple[str, str, str]] = set()
    duplicate_identities: list[tuple[str, str, str]] = []
    for link in links:
        identity = (
            clean(link.get("property_id")),
            clean(link.get("source_key")),
            clean(link.get("source_record_id")),
        )
        if identity in exact_identities:
            duplicate_identities.append(identity)
        exact_identities.add(identity)

    if duplicate_identities:
        failures.append({"reason": "EXACT_DUPLICATE_IDENTITIES", "count": len(duplicate_identities), "sample": duplicate_identities[:20]})

    business = stats["business_licence_matches_prior_poc"]
    renewable = stats["renewable_energy_installations"]
    if business["links"] != 1452:
        failures.append({"reason": "BUSINESS_LINK_COUNT_DRIFT", "expected": 1452, "actual": business["links"]})
    if renewable["links"] != 85:
        failures.append({"reason": "RENEWABLE_LINK_COUNT_DRIFT", "expected": 85, "actual": renewable["links"]})
    if renewable["legacy_cross_field_id_collision"] != 4:
        failures.append({
            "reason": "RENEWABLE_COLLISION_COUNT_DRIFT",
            "expected": 4,
            "actual": renewable["legacy_cross_field_id_collision"],
        })

    already_repaired = business["record_ids_rewritten"] == 0 and business["stable_identity_resolved_before"] == business["links"]
    first_repair = business["record_ids_rewritten"] == business["links"] and business["stable_identity_unresolved_before"] == business["links"]
    if not (already_repaired or first_repair):
        failures.append({
            "reason": "BUSINESS_REPAIR_NOT_ATOMIC",
            "rewritten": business["record_ids_rewritten"],
            "resolved_before": business["stable_identity_resolved_before"],
            "unresolved_before": business["stable_identity_unresolved_before"],
        })

    report = {
        "schema_version": "toronto-source-identity-repair-1.0",
        "generated_at": utc_now(),
        "status": "FAILED" if failures else "PASSED",
        "root_cause": {
            "business_licences": "Durable IDs were generated from outer matches[] wrappers but app resolution uses nested source_row publisher records.",
            "renewable_energy": "Generic id lookup matched any ID-like field instead of the ordered field contract used to generate the durable ID, producing cross-field collisions.",
        },
        "sources": {source: dict(counter) for source, counter in stats.items()},
        "failures": failures[:100],
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if failures:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        raise SystemExit(1)

    payload["generated_at"] = report["generated_at"]
    payload["source_identity_repair"] = {
        "schema_version": report["schema_version"],
        "status": report["status"],
        "business_record_ids_rewritten": business["record_ids_rewritten"],
        "renewable_legacy_cross_field_collisions": renewable["legacy_cross_field_id_collision"],
    }
    LINKS_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
