from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.apply_toronto_tobids_relationships import SOURCE_LINK_KEY, candidate_rows
from scripts.toronto_source_identity import find_source_record, stable_source_record_id

ROOT = Path(__file__).resolve().parents[2]
MARKET = ROOT / "data/toronto/market/current"
TOBIDS = ROOT / "data/toronto/warehouse/current/open_licensed/tobids_awarded_contracts.json"


class TorontoTobidsLegacyProvenanceTests(unittest.TestCase):
    def test_legacy_links_resolve_and_overlap_three_citywide_rows(self) -> None:
        spine = json.loads((MARKET / "property_spine.json").read_text(encoding="utf-8"))
        links_payload = json.loads((MARKET / "property_source_links.json").read_text(encoding="utf-8"))
        tobids = json.loads(TOBIDS.read_text(encoding="utf-8"))
        properties = [item for item in spine.get("properties", []) if isinstance(item, dict)]
        rows = [item for item in tobids.get("rows", []) if isinstance(item, dict)]
        all_tobids_links = [
            item for item in links_payload.get("links", [])
            if isinstance(item, dict) and item.get("source_key") == SOURCE_LINK_KEY
        ]
        legacy = [item for item in all_tobids_links if item.get("source_row_index") is None]
        citywide = [item for item in all_tobids_links if isinstance(item.get("source_row_index"), int)]
        self.assertEqual(len(all_tobids_links), 17)
        self.assertEqual(len(legacy), 5)
        self.assertEqual(len(citywide), 12)

        publisher_keys: set[tuple[str, str]] = set()
        legacy_documents: set[str] = set()
        for link in legacy:
            resolved = find_source_record(SOURCE_LINK_KEY, str(link.get("source_record_id") or ""), rows)
            self.assertTrue(resolved, msg=f"legacy link did not resolve: {link}")
            publisher_keys.add((str(link.get("property_id") or ""), stable_source_record_id(SOURCE_LINK_KEY, resolved)))
            legacy_documents.add(str(resolved.get("Document Number") or ""))

        exact, ambiguous, _ = candidate_rows(properties, rows)
        self.assertEqual(len(exact), 15)
        self.assertEqual(len(ambiguous), 5)
        overlaps = [
            item for item in exact
            if (
                item["property_id"],
                stable_source_record_id(SOURCE_LINK_KEY, item["row"]),
            ) in publisher_keys
        ]
        self.assertEqual(len(overlaps), 3)
        self.assertEqual(
            {str(item["row"].get("Document Number") or "") for item in overlaps},
            {"4730517384", "5065962940", "5440016362"},
        )
        self.assertTrue({"4730517384", "5065962940", "5440016362"}.issubset(legacy_documents))


if __name__ == "__main__":
    unittest.main()
