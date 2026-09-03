from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from diagnose_toronto_tobids_relationships import address_number, exact_address_matches, normalize_free_text, normalized_property_address
from toronto_source_identity import find_source_record

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data/toronto/market/current"
TOBIDS = ROOT / "data/toronto/warehouse/current/open_licensed/tobids_awarded_contracts.json"
SOURCE_KEY = "tobids_awarded_contracts_exact_document_address_prior_poc"
GRAPH_SOURCE_KEY = "tobids_awarded_contracts"


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected object: {path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("tobids-existing-provenance.json"))
    args = parser.parse_args()

    spine = load(MARKET / "property_spine.json")
    links_payload = load(MARKET / "property_source_links.json")
    graph = load(MARKET / "entity_graph.json")
    tobids = load(TOBIDS)
    properties = [x for x in spine.get("properties", []) if isinstance(x, dict)]
    rows = [x for x in tobids.get("rows", []) if isinstance(x, dict)]

    by_address: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for prop in properties:
        address = normalized_property_address(prop.get("display_address") or prop.get("canonical_address"))
        if address:
            by_address[address].append(prop)
    candidates_by_number: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for address, matches in by_address.items():
        number = address_number(address)
        if not number or len(address.split()) < 3 or len(matches) != 1:
            continue
        prop = matches[0]
        candidates_by_number[number].append((address, str(prop.get("property_id") or ""), str(prop.get("display_address") or prop.get("canonical_address") or "")))

    exact_by_index: dict[int, dict[str, Any]] = {}
    ambiguous_indices: set[int] = set()
    for index, row in enumerate(rows):
        description = row.get("Solicitation Document Description")
        supplier = str(row.get("Successful Supplier") or "").strip()
        normalized = normalize_free_text(description)
        if not normalized or not supplier:
            continue
        numbers = set(re.findall(r"\b\d{1,5}[A-Z]?\b", normalized))
        matched: dict[str, tuple[str, str, str]] = {}
        for number in numbers:
            for candidate in exact_address_matches(normalized, candidates_by_number.get(number, [])):
                matched[candidate[1]] = candidate
        if len(matched) > 1:
            ambiguous_indices.add(index)
        elif len(matched) == 1:
            candidate = next(iter(matched.values()))
            exact_by_index[index] = {
                "property_id": candidate[1],
                "display_address": candidate[2],
                "successful_supplier": supplier,
                "document_number": row.get("Document Number"),
            }

    nodes = {str(x.get("node_id")): x for x in graph.get("nodes", []) if isinstance(x, dict)}
    graph_pairs: set[tuple[str, str]] = set()
    for edge in graph.get("edges", []):
        if not isinstance(edge, dict) or edge.get("source_key") != GRAPH_SOURCE_KEY or edge.get("relationship") != "SUCCESSFUL_BIDDER_AT_PROPERTY":
            continue
        node = nodes.get(str(edge.get("from_node"))) or {}
        name = normalize_free_text(node.get("name"))
        pid = str(edge.get("property_id") or edge.get("to_node") or "")
        if name and pid:
            graph_pairs.add((pid, name))

    existing = [x for x in links_payload.get("links", []) if isinstance(x, dict) and x.get("source_key") == SOURCE_KEY]
    summaries = []
    exact_overlap = 0
    for link in existing:
        resolved = find_source_record(SOURCE_KEY, str(link.get("source_record_id") or ""), rows)
        index = link.get("source_row_index")
        indexed = rows[index] if isinstance(index, int) and 0 <= index < len(rows) else {}
        row = resolved or indexed
        supplier = str(row.get("Successful Supplier") or "").strip()
        pid = str(link.get("property_id") or "")
        exact = exact_by_index.get(index) if isinstance(index, int) else None
        if exact and exact.get("property_id") == pid:
            exact_overlap += 1
        summaries.append({
            "property_id": pid,
            "source_record_id": link.get("source_record_id"),
            "source_row_index": index,
            "source_address": link.get("source_address"),
            "match_basis": link.get("match_basis"),
            "stable_id_resolved": bool(resolved),
            "indexed_and_resolved_same_row": bool(resolved and indexed and resolved == indexed),
            "document_number": row.get("Document Number"),
            "successful_supplier": supplier or None,
            "award_date": row.get("Award Authority Obtained Date"),
            "description": row.get("Solicitation Document Description"),
            "overlaps_citywide_exact_description_row": bool(exact and exact.get("property_id") == pid),
            "graph_pair_exists": (pid, normalize_free_text(supplier)) in graph_pairs if supplier else False,
        })

    report = {
        "status": "PASSED_DIAGNOSTIC",
        "counts": {
            "existing_source_links": len(existing),
            "existing_graph_pairs": len(graph_pairs),
            "citywide_exact_description_rows": len(exact_by_index),
            "citywide_ambiguous_description_rows": len(ambiguous_indices),
            "existing_source_links_overlapping_citywide_exact_rows": exact_overlap,
        },
        "existing_source_links": summaries,
        "citywide_exact_rows": [
            {"source_row_index": index, **payload}
            for index, payload in sorted(exact_by_index.items())
        ],
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
