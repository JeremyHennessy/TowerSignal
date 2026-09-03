from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.apply_toronto_tobids_relationships import (
    EXPECTED_AMBIGUOUS_ROWS,
    EXPECTED_EXACT_ROWS,
    EXPECTED_ROWS_WITH_DESCRIPTION,
    EXPECTED_SOURCE_ROWS,
    candidate_rows,
    exact_address_matches,
    normalize_free_text,
)

ROOT = Path(__file__).resolve().parents[2]


class TorontoTobidsRelationshipApplyTests(unittest.TestCase):
    def test_normalization_and_phrase_boundary(self) -> None:
        candidates = [("31 GLEN WATFORD DRIVE", "property:31", "31 Glen Watford Dr")]
        self.assertEqual(normalize_free_text("31 Glen Watford Dr."), "31 GLEN WATFORD DRIVE")
        self.assertEqual(
            exact_address_matches(normalize_free_text("Design work at 31 Glen Watford Drive, Toronto"), candidates),
            candidates,
        )
        self.assertEqual(exact_address_matches(normalize_free_text("Design work at 131 Glen Watford Drive"), candidates), [])
        self.assertEqual(exact_address_matches(normalize_free_text("Design work near 31 Glen Watford"), candidates), [])

    def test_persisted_snapshot_has_expected_bounded_opportunity(self) -> None:
        spine = json.loads((ROOT / "data/toronto/market/current/property_spine.json").read_text(encoding="utf-8"))
        tobids = json.loads((ROOT / "data/toronto/warehouse/current/open_licensed/tobids_awarded_contracts.json").read_text(encoding="utf-8"))
        properties = [item for item in spine.get("properties", []) if isinstance(item, dict)]
        rows = [item for item in tobids.get("rows", []) if isinstance(item, dict)]
        self.assertEqual(len(rows), EXPECTED_SOURCE_ROWS)
        self.assertEqual(
            sum(bool(str(row.get("Solicitation Document Description") or "").strip()) for row in rows),
            EXPECTED_ROWS_WITH_DESCRIPTION,
        )
        exact, ambiguous, _ = candidate_rows(properties, rows)
        self.assertEqual(len(exact), EXPECTED_EXACT_ROWS)
        self.assertEqual(len(ambiguous), EXPECTED_AMBIGUOUS_ROWS)
        self.assertTrue(all(item["successful_supplier"] for item in exact))
        self.assertTrue(all(item["display_address"] for item in exact))

    def test_multi_property_rows_are_not_promoted(self) -> None:
        properties = [
            {"property_id": "p1", "display_address": "1615 Dufferin St"},
            {"property_id": "p2", "display_address": "2 Buttonwood Ave"},
        ]
        rows = [{
            "Successful Supplier": "Example Construction",
            "Solicitation Document Description": "Renovations at 1615 Dufferin Street and 2 Buttonwood Avenue, Toronto",
        }]
        exact, ambiguous, _ = candidate_rows(properties, rows)
        self.assertEqual(exact, [])
        self.assertEqual(len(ambiguous), 1)
        self.assertEqual(set(ambiguous[0]["matched_properties"]), {"p1", "p2"})


if __name__ == "__main__":
    unittest.main()
