from __future__ import annotations

import unittest

from scripts.build_coverage_audit import _identifier_gap


class BblCoverageAuditTests(unittest.TestCase):
    def test_recovered_bbl_does_not_inflate_registry_source_coverage(self):
        systems = [
            {
                "system_id": "source",
                "borough": "Manhattan",
                "bin": "1000001",
                "bbl": "1000010001",
                "registry_bbl": "1000010001",
                "bbl_identity_status": "REGISTRY_SOURCE_BBL",
            },
            {
                "system_id": "recovered",
                "borough": "Brooklyn",
                "bin": "3000001",
                "bbl": "3000017501",
                "registry_bbl": None,
                "bbl_identity_status": "RECOVERED_EXACT_BIN_MAPPLUTO_BBL",
            },
            {
                "system_id": "unresolved",
                "borough": "Queens",
                "bin": "4000001",
                "bbl": None,
                "registry_bbl": None,
                "bbl_identity_status": "UNRESOLVED_NO_MAPPLUTO_BBL",
            },
        ]

        gap = _identifier_gap(systems)

        self.assertEqual(gap["with_bbl"], 1)
        self.assertEqual(gap["missing_bbl"], 2)
        self.assertEqual(gap["with_registry_source_bbl"], 1)
        self.assertEqual(gap["with_canonical_bbl"], 2)
        self.assertEqual(gap["missing_canonical_bbl"], 1)
        self.assertEqual(gap["recovered_bbl_count"], 1)
        self.assertEqual(gap["by_borough"]["Brooklyn"]["with_registry_source_bbl"], 0)
        self.assertEqual(gap["by_borough"]["Brooklyn"]["with_canonical_bbl"], 1)
        self.assertEqual(gap["by_borough"]["Brooklyn"]["recovered_bbl"], 1)
        self.assertIn("do not inflate source completeness", gap["bbl_semantics"]["with_bbl"])
        self.assertIn("no address or fuzzy matching", gap["bbl_semantics"]["recovery"])


if __name__ == "__main__":
    unittest.main()
