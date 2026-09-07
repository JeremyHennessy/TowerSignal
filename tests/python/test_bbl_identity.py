from __future__ import annotations

import unittest

from scripts.towersignal.bbl_identity import apply_bbl_identity_recovery, resolve_system_bbl_identity


class BblIdentityRecoveryTests(unittest.TestCase):
    def system(self, **overrides):
        row = {
            "system_id": "2001",
            "borough": "Brooklyn",
            "bin": "3000001",
            "bbl": None,
        }
        row.update(overrides)
        return row

    def test_registry_bbl_is_never_overwritten(self):
        evidence = resolve_system_bbl_identity(
            self.system(bbl="3000010001"),
            [{"mappluto_bbl": "3000017501", "base_bbl": "3000010001"}],
        )
        self.assertEqual(evidence["canonical_bbl"], "3000010001")
        self.assertEqual(evidence["registry_bbl"], "3000010001")
        self.assertEqual(evidence["status"], "REGISTRY_SOURCE_BBL")

    def test_unique_exact_bin_mappluto_candidate_recovers_missing_bbl(self):
        evidence = resolve_system_bbl_identity(
            self.system(),
            [{"mappluto_bbl": "3000017501", "base_bbl": "3000010044"}],
        )
        self.assertEqual(evidence["canonical_bbl"], "3000017501")
        self.assertIsNone(evidence["registry_bbl"])
        self.assertEqual(evidence["status"], "RECOVERED_EXACT_BIN_MAPPLUTO_BBL")
        self.assertEqual(evidence["base_bbl_context"], ["3000010044"])
        self.assertFalse(evidence["address_matching_used"])
        self.assertFalse(evidence["fuzzy_matching_used"])

    def test_multiple_mappluto_candidates_stay_unresolved(self):
        evidence = resolve_system_bbl_identity(
            self.system(),
            [
                {"mappluto_bbl": "3000017501"},
                {"mappluto_bbl": "3000017502"},
            ],
        )
        self.assertIsNone(evidence["canonical_bbl"])
        self.assertEqual(evidence["status"], "UNRESOLVED_MULTIPLE_MAPPLUTO_BBLS")

    def test_cross_borough_candidate_stays_unresolved(self):
        evidence = resolve_system_bbl_identity(
            self.system(borough="Queens", bin="4000001"),
            [{"mappluto_bbl": "3000017501"}],
        )
        self.assertIsNone(evidence["canonical_bbl"])
        self.assertEqual(evidence["status"], "UNRESOLVED_BOROUGH_PREFIX_CONFLICT")

    def test_apply_preserves_source_and_recovery_counts(self):
        systems = [
            self.system(system_id="source", bbl="3000010001", bin="3000001"),
            self.system(system_id="recovered", bbl=None, bin="3000002"),
            self.system(system_id="unresolved", bbl=None, bin="3000003"),
        ]
        meta = apply_bbl_identity_recovery(
            systems,
            {
                "3000001": [{"mappluto_bbl": "3000017501"}],
                "3000002": [{"mappluto_bbl": "3000027501"}],
                "3000003": [{"mappluto_bbl": "3000037501"}, {"mappluto_bbl": "3000037502"}],
            },
        )
        self.assertEqual(meta["registry_source_bbl_count"], 1)
        self.assertEqual(meta["recovered_bbl_count"], 1)
        self.assertEqual(meta["canonical_bbl_count"], 2)
        self.assertEqual(meta["unresolved_bbl_count"], 1)
        self.assertEqual(systems[0]["registry_bbl"], "3000010001")
        self.assertEqual(systems[1]["bbl"], "3000027501")
        self.assertIsNone(systems[2]["bbl"])


if __name__ == "__main__":
    unittest.main()
