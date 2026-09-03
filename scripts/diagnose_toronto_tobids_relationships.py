from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from toronto_final_identity_cleanup import canonical_address

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data" / "toronto" / "market" / "current"
TOBIDS = ROOT / "data" / "toronto" / "warehouse" / "current" / "open_licensed" / "tobids_awarded_contracts.json"

SUFFIX_MAP = {
    "ST": "STREET",
    "STREET": "STREET",
    "RD": "ROAD",
    "ROAD": "ROAD",
    "AVE": "AVENUE",
    "AV": "AVENUE",
    "AVENUE": "AVENUE",
    "BLVD": "BOULEVARD",
    "BOULEVARD": "BOULEVARD",
    "DR": "DRIVE",
    "DRIVE": "DRIVE",
    "CT": "COURT",
    "CRT": "COURT",
    "COURT": "COURT",
    "CRES": "CRESCENT",
    "CR": "CRESCENT",
    "CRESCENT": "CRESCENT",
    "HWY": "HIGHWAY",
    "HIGHWAY": "HIGHWAY",
    "PKWY": "PARKWAY",
    "PARKWAY": "PARKWAY",
    "PL": "PLACE",
    "PLACE": "PLACE",
    "LN": "LANE",
    "LANE": "LANE",
    "TRL": "TRAIL",
    "TRAIL": "TRAIL",
    "TER": "TERRACE",
    "TERR": "TERRACE",
    "TERRACE": "TERRACE",
    "SQ": "SQUARE",
    "SQUARE": "SQUARE",
    "CIR": "CIRCLE",
    "CIRCLE": "CIRCLE",
    "GRV": "GROVE",
    "GROVE": "GROVE",
}

MECHANICAL_TERMS = (
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
    "boilers",
)


def load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_free_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).upper()
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    tokens = [SUFFIX_MAP.get(token, token) for token in text.split()]
    return " ".join(tokens)


def normalized_property_address(value: Any) -> str:
    return normalize_free_text(canonical_address(value))


def address_number(address: str) -> str | None:
    if not address:
        return None
    token = address.split()[0]
    return token if re.fullmatch(r"\d{1,5}[A-Z]?", token) else None


def mechanical_terms(text: Any) -> list[str]:
    lowered = str(text or "").lower()
    return [term for term in MECHANICAL_TERMS if term in lowered]


def exact_address_matches(normalized_text: str, candidates: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    padded = f" {normalized_text} "
    return [candidate for candidate in candidates if f" {candidate[0]} " in padded]


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure deterministic citywide TOBids property/supplier relationship opportunity")
    parser.add_argument("--output", type=Path, default=Path("tobids-relationship-diagnostic.json"))
    args = parser.parse_args()

    spine = load(MARKET / "property_spine.json")
    graph = load(MARKET / "entity_graph.json")
    tobids = load(TOBIDS)

    properties = [item for item in spine.get("properties", []) if isinstance(item, dict)]
    rows = [item for item in tobids.get("rows", []) if isinstance(item, dict)]
    if not properties or not rows:
        raise RuntimeError("Toronto property spine or TOBids rows missing")

    by_address: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for prop in properties:
        address = normalized_property_address(prop.get("display_address") or prop.get("canonical_address"))
        if address:
            by_address[address].append(prop)

    candidates_by_number: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    excluded_ambiguous_property_addresses = 0
    excluded_non_civic_property_addresses = 0
    for address, matches in by_address.items():
        number = address_number(address)
        if not number or len(address.split()) < 3:
            excluded_non_civic_property_addresses += 1
            continue
        if len(matches) != 1:
            excluded_ambiguous_property_addresses += 1
            continue
        prop = matches[0]
        candidates_by_number[number].append((address, str(prop.get("property_id") or ""), str(prop.get("display_address") or prop.get("canonical_address") or "")))

    nodes = {str(node.get("node_id")): node for node in graph.get("nodes", []) if isinstance(node, dict)}
    existing_pairs: set[tuple[str, str]] = set()
    for edge in graph.get("edges", []):
        if not isinstance(edge, dict):
            continue
        if edge.get("relationship") != "SUCCESSFUL_BIDDER_AT_PROPERTY":
            continue
        if edge.get("source_key") != "tobids_awarded_contracts":
            continue
        name = (nodes.get(str(edge.get("from_node"))) or {}).get("name")
        if name:
            existing_pairs.add((str(edge.get("property_id") or edge.get("to_node") or ""), normalize_free_text(name)))

    exact_rows: list[dict[str, Any]] = []
    ambiguous_rows: list[dict[str, Any]] = []
    no_supplier_exact_rows = 0
    rows_with_description = 0
    rows_with_supplier = 0

    for index, row in enumerate(rows):
        description = row.get("Solicitation Document Description")
        supplier = str(row.get("Successful Supplier") or "").strip()
        if description:
            rows_with_description += 1
        if supplier:
            rows_with_supplier += 1
        normalized = normalize_free_text(description)
        if not normalized:
            continue
        numbers = set(re.findall(r"\b\d{1,5}[A-Z]?\b", normalized))
        matched: dict[str, tuple[str, str, str]] = {}
        for number in numbers:
            for candidate in exact_address_matches(normalized, candidates_by_number.get(number, [])):
                matched[candidate[1]] = candidate
        if not matched:
            continue
        if len(matched) > 1:
            ambiguous_rows.append({
                "source_row_index": index,
                "document_number": row.get("Document Number"),
                "successful_supplier": supplier or None,
                "matched_properties": [
                    {"property_id": candidate[1], "display_address": candidate[2]}
                    for candidate in sorted(matched.values())
                ],
                "description": description,
            })
            continue
        candidate = next(iter(matched.values()))
        if not supplier:
            no_supplier_exact_rows += 1
            continue
        terms = mechanical_terms(description)
        pair = (candidate[1], normalize_free_text(supplier))
        exact_rows.append({
            "source_row_index": index,
            "document_number": row.get("Document Number"),
            "award_date": row.get("Award Authority Obtained Date"),
            "award": row.get("Award"),
            "high_level_category": row.get("High Level Category"),
            "successful_supplier": supplier,
            "property_id": candidate[1],
            "display_address": candidate[2],
            "match_basis": "EXACT_NORMALIZED_CIVIC_ADDRESS_PHRASE_IN_SOLICITATION_DESCRIPTION_TO_UNIQUE_CURRENT_ADDRESS_POINT_PROPERTY",
            "mechanical_terms": terms,
            "already_in_graph": pair in existing_pairs,
            "description": description,
        })

    exact_properties = {item["property_id"] for item in exact_rows}
    exact_suppliers = {normalize_free_text(item["successful_supplier"]) for item in exact_rows}
    exact_pairs = {(item["property_id"], normalize_free_text(item["successful_supplier"])) for item in exact_rows}
    new_pairs = {pair for pair in exact_pairs if pair not in existing_pairs}
    mechanical_rows = [item for item in exact_rows if item["mechanical_terms"]]
    mechanical_properties = {item["property_id"] for item in mechanical_rows}
    mechanical_pairs = {(item["property_id"], normalize_free_text(item["successful_supplier"])) for item in mechanical_rows}
    professional_rows = [
        item for item in exact_rows
        if "PROFESSIONAL" in normalize_free_text(item.get("high_level_category"))
    ]

    category_counts = Counter(str(item.get("high_level_category") or "UNKNOWN") for item in exact_rows)
    examples = sorted(
        exact_rows,
        key=lambda item: (
            0 if item["mechanical_terms"] else 1,
            str(item.get("award_date") or ""),
            str(item.get("document_number") or ""),
        ),
        reverse=False,
    )[:100]

    report = {
        "schema_version": "toronto-tobids-relationship-diagnostic-1.0",
        "generated_at": utc_now(),
        "status": "PASSED_DIAGNOSTIC",
        "scope": "Read-only diagnostic. No source links or relationship edges are modified.",
        "relationship_contract": "Successful Supplier can support SUCCESSFUL_BIDDER_AT_PROPERTY only when one normalized civic address phrase in the solicitation description maps to exactly one current Toronto Address Point property. Mechanical/consulting roles are not inferred from category or keywords.",
        "counts": {
            "canonical_properties": len(properties),
            "source_rows": len(rows),
            "rows_with_description": rows_with_description,
            "rows_with_supplier": rows_with_supplier,
            "unique_property_addresses_eligible_for_phrase_matching": sum(len(v) for v in candidates_by_number.values()),
            "excluded_ambiguous_property_addresses": excluded_ambiguous_property_addresses,
            "excluded_non_civic_property_addresses": excluded_non_civic_property_addresses,
            "exact_unique_property_rows": len(exact_rows),
            "exact_unique_properties": len(exact_properties),
            "exact_unique_suppliers": len(exact_suppliers),
            "exact_unique_property_supplier_pairs": len(exact_pairs),
            "existing_graph_property_supplier_pairs": len(existing_pairs),
            "new_exact_property_supplier_pairs": len(new_pairs),
            "ambiguous_multi_property_rows_not_promotable": len(ambiguous_rows),
            "exact_rows_without_supplier_not_promotable": no_supplier_exact_rows,
            "mechanical_keyword_exact_rows": len(mechanical_rows),
            "mechanical_keyword_exact_properties": len(mechanical_properties),
            "mechanical_keyword_exact_property_supplier_pairs": len(mechanical_pairs),
            "professional_services_exact_rows": len(professional_rows),
        },
        "category_counts": dict(sorted(category_counts.items())),
        "examples": examples,
        "ambiguous_examples": ambiguous_rows[:50],
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "counts": report["counts"], "category_counts": report["category_counts"], "examples": examples[:12]}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
