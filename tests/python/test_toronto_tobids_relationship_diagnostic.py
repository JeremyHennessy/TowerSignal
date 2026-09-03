from __future__ import annotations

import unittest

from scripts.diagnose_toronto_tobids_relationships import exact_address_matches, mechanical_terms, normalize_free_text


class TorontoTobidsRelationshipDiagnosticTests(unittest.TestCase):
    def test_normalize_free_text_expands_common_suffix(self) -> None:
        self.assertEqual(normalize_free_text("31 Glen Watford Dr."), "31 GLEN WATFORD DRIVE")

    def test_exact_address_requires_full_normalized_phrase(self) -> None:
        candidates = [("31 GLEN WATFORD DRIVE", "property:31", "31 Glen Watford Dr")]
        self.assertEqual(
            exact_address_matches(normalize_free_text("Work at 31 Glen Watford Drive, Toronto"), candidates),
            candidates,
        )
        self.assertEqual(
            exact_address_matches(normalize_free_text("Work near 31 Glen Watford"), candidates),
            [],
        )

    def test_exact_address_does_not_match_inside_larger_civic_number(self) -> None:
        candidates = [("31 GLEN WATFORD DRIVE", "property:31", "31 Glen Watford Dr")]
        self.assertEqual(
            exact_address_matches(normalize_free_text("Work at 131 Glen Watford Drive"), candidates),
            [],
        )

    def test_mechanical_keywords_are_segmentation_only(self) -> None:
        terms = mechanical_terms("Replace HVAC equipment, chillers and boiler controls.")
        self.assertIn("hvac", terms)
        self.assertIn("chiller", terms)
        self.assertIn("boiler", terms)


if __name__ == "__main__":
    unittest.main()
