from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from diagnose_toronto_building_permit_targeted_v2 import (
    DISCOVERY_QUERIES,
    SOURCES,
    fetch_query_rows,
    permit_identity,
    property_indexes,
    row_address,
    signal_keys,
)
from toronto_final_identity_cleanup import canonical_address
from toronto_market_common import clean_text, read_json

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data/toronto/market/current"


def match_property(row: dict[str, Any], by_apid: dict[str, str], by_address: dict[str, list[str]]) -> str | None:
    apid = clean_text(row.get("GEO_ID"))
    if apid and apid in by_apid:
        return by_apid[apid]
    address = canonical_address(row_address(row))
    matches = set(by_address.get(address, [])) if address else set()
    return next(iter(matches)) if len(matches) == 1 else None


def source_summary(
    resource_id: str,
    by_apid: dict[str, str],
    by_address: dict[str, list[str]],
    scope_by_pid: dict[str, str],
) -> tuple[dict[str, Any], dict[str, set[str]]]:
    discovered: dict[str, dict[str, Any]] = {}
    for query in DISCOVERY_QUERIES:
        _, rows = fetch_query_rows(resource_id, query)
        for row in rows:
            discovered.setdefault(permit_identity(row), row)
    targeted = {identity: row for identity, row in discovered.items() if signal_keys(row)}

    row_scope = Counter()
    property_scope: dict[str, set[str]] = defaultdict(set)
    signal_property_scope: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    signal_row_scope: dict[str, Counter] = defaultdict(Counter)
    property_sets: dict[str, set[str]] = defaultdict(set)

    for row in targeted.values():
        pid = match_property(row, by_apid, by_address)
        if not pid:
            row_scope["UNMATCHED"] += 1
            continue
        scope = scope_by_pid.get(pid, "UNKNOWN")
        row_scope[scope] += 1
        property_scope[scope].add(pid)
        property_sets[scope].add(pid)
        for signal in signal_keys(row):
            signal_row_scope[signal][scope] += 1
            signal_property_scope[signal][scope].add(pid)

    return {
        "targeted_rows": len(targeted),
        "matched_row_scope_counts": dict(sorted(row_scope.items())),
        "matched_property_scope_counts": {scope: len(values) for scope, values in sorted(property_scope.items())},
        "signal_row_scope_counts": {signal: dict(sorted(counts.items())) for signal, counts in sorted(signal_row_scope.items())},
        "signal_property_scope_counts": {
            signal: {scope: len(values) for scope, values in sorted(scopes.items())}
            for signal, scopes in sorted(signal_property_scope.items())
        },
    }, property_sets


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only scope audit for targeted Toronto building permits")
    parser.add_argument("--output", type=Path, default=Path("toronto-building-permit-scope.json"))
    args = parser.parse_args()

    spine = read_json(MARKET / "property_spine.json") or {}
    properties = [row for row in spine.get("properties", []) if isinstance(row, dict)]
    by_apid, by_address = property_indexes(properties)
    scope_by_pid = {
        clean_text(prop.get("property_id")): ("ORIGINAL_POC" if prop.get("is_original_poc_property") else "EXPANDED_UNIVERSE")
        for prop in properties if clean_text(prop.get("property_id"))
    }

    summaries: dict[str, Any] = {}
    property_sets_by_source: dict[str, dict[str, set[str]]] = {}
    for source, resource_id in SOURCES.items():
        summaries[source], property_sets_by_source[source] = source_summary(resource_id, by_apid, by_address, scope_by_pid)

    union_by_scope: dict[str, set[str]] = defaultdict(set)
    for source_sets in property_sets_by_source.values():
        for scope, properties_set in source_sets.items():
            union_by_scope[scope].update(properties_set)

    report = {
        "schema_version": "toronto-building-permit-scope-diagnostic-1.0",
        "status": "PASSED_DIAGNOSTIC",
        "scope": "Read-only measurement of targeted permit joins split between original POC and expanded Toronto Address Point universe.",
        "sources": summaries,
        "union_matched_properties_by_scope": {scope: len(values) for scope, values in sorted(union_by_scope.items())},
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
