"""Proposed regression tests for confirmed audit findings.

These tests intentionally describe the desired post-repair behavior and therefore
fail against TowerSignal main f1cbdb925b704a8b7a34aaccd169be6649b80a92.
They live under docs/audits, not the production test suite. They are evidence of
the demonstrated failure mechanisms, not repair acceptance.
"""
from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

spec = importlib.util.spec_from_file_location("known_firms_audit", ROOT / "scripts/towersignal/known_firms.py")
known_firms = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(known_firms)

class ProposedRegressionFailures(unittest.TestCase):
    def test_placeholder_bin_is_not_a_unique_firm_site_identity(self):
        row = {
            "system_id": "audit-fixture",
            "bin": "1000000",
            "bbl": "1005977503",
            "address": "110 CHARLTON STREET",
            "borough": "MANHATTAN",
            "zip": "10014",
        }
        # Desired behavior: an invalid borough-only placeholder BIN must not
        # outrank an independently valid parcel identity.
        self.assertEqual(known_firms._system_site_key(row), "NYC-BBL-1005977503")
        site = known_firms._site_from_systems([row])
        self.assertEqual(site["site_id"], "NYC-BBL-1005977503")
        self.assertIsNone(site["bin"])
        self.assertEqual(site["bbl"], "1005977503")

    def test_dob_role_provenance_is_not_hardcoded_to_exact_bbl(self):
        source = (ROOT / "src/domain/accountEvidence.ts").read_text(encoding="utf-8")
        block = re.search(
            r"const addDobWaterRole = \(.*?\) => \{(?P<body>.*?)\n  \}",
            source,
            re.S,
        )
        self.assertIsNotNone(block)
        body = block.group("body")
        # Desired behavior: the role row must carry the validated match basis
        # from the attached evidence rather than fabricating a BBL_EXACT label.
        self.assertNotIn("matchBasis: 'BBL_EXACT'", body)
        self.assertNotIn("· exact BBL", body)
        self.assertRegex(body, r"matchBasis\s*:\s*.*(?:relationship|match|link).*")

    def test_dob_preview_does_not_hide_newer_permits_behind_jobs(self):
        source = (ROOT / "src/components/BuildingWaterSignalsSection.tsx").read_text(encoding="utf-8")
        # Desired behavior: DOB job and permit records must be merged by a
        # deterministic observation date before any bounded preview is applied,
        # and a bounded preview must expose a path to all records.
        self.assertNotIn(
            "[...context.dob_water_job_filings, ...context.dob_water_permits].slice(0, 8)",
            source,
        )
        self.assertRegex(source, r"(sort\(|toSorted\().*(issued_date|approved_date|filing_date)")
        self.assertRegex(source.lower(), r"(show all|view all|full list|all records)")

if __name__ == "__main__":
    unittest.main(verbosity=2)
