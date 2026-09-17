import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.labor_law import (
    match_decisions_to_systems,
    merge_retained_decisions,
    normalize_decision,
    normalize_property_address,
)


class LaborLawDecisionTests(unittest.TestCase):
    def test_property_address_normalization_is_bounded_and_deterministic(self):
        self.assertEqual(normalize_property_address("350 West 71st Street"), "350 W 71ST ST")
        self.assertEqual(normalize_property_address("3420 Bedford Avenue"), "3420 BEDFORD AVE")
        self.assertIsNone(normalize_property_address(None))

    def test_explicit_worksite_address_is_attachment_candidate(self):
        body = b"""
        <html><body>
        Plaintiff alleges an accident while performing work at the construction site located at 350 West 71st Street.
        The parties dispute Labor Law sections 240(1) and 241(6).
        INDEX NO. 123456/2025
        </body></html>
        """
        row = normalize_decision(
            "APP_DIV_FIRST",
            "https://www.nycourts.gov/reporter/RSS/AD1st.xml",
            {"title": "Example v Owner", "link": "https://example.test/decision", "pub_date": "Wed, 16 Sep 2026 12:00:00 GMT"},
            body,
            "text/html",
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["explicit_subject_property_candidates"][0]["normalized_address"], "350 W 71ST ST")
        self.assertIn("123456/2025", row["index_numbers"])

    def test_case_citation_address_is_not_a_property_candidate(self):
        body = b"""
        <html><body>
        The appeal concerns Labor Law 240(1). See Guaman v 178 Ct. St., LLC for the relevant rule.
        The decision does not publish the subject worksite address.
        </body></html>
        """
        row = normalize_decision(
            "APP_DIV_SECOND",
            "https://www.nycourts.gov/reporter/RSS/AD2d.xml",
            {"title": "Example Appeal", "link": "https://example.test/decision2", "pub_date": "Wed, 16 Sep 2026 12:00:00 GMT"},
            body,
            "text/html",
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["explicit_subject_property_candidates"], [])
        self.assertTrue(any(item["normalized_address"] == "178 CT ST" for item in row["rejected_address_candidates"]))

    def test_exact_subject_address_attaches_at_building_level_only(self):
        decision = {
            "decision_id": "decision-1",
            "title": "Worker v Owner",
            "decision_url": "https://example.test/decision",
            "publication_date": "Wed, 16 Sep 2026 12:00:00 GMT",
            "labor_law_sections": ["240(1)"],
            "index_numbers": ["123/2026"],
            "case_numbers": [],
            "nyscef_document_numbers": [],
            "explicit_subject_property_candidates": [{"address": "350 West 71st Street", "normalized_address": "350 W 71ST ST", "context": "construction site located at 350 West 71st Street"}],
            "source": "NYS_OFFICIAL_REPORTS_PUBLISHED_DECISION",
        }
        systems = [
            {"system_id": "a", "address": "350 W 71ST ST"},
            {"system_id": "b", "address": "350 WEST 71ST STREET"},
            {"system_id": "c", "address": "351 W 71ST ST"},
        ]
        by_system, unmatched = match_decisions_to_systems([decision], systems)
        self.assertEqual(set(by_system), {"a", "b"})
        self.assertEqual(unmatched, [])
        for system_id in ("a", "b"):
            record = by_system[system_id][0]
            self.assertEqual(record["match_basis"], "PUBLISHED_DECISION_EXPLICIT_WORKSITE_ADDRESS_EXACT")
            self.assertTrue(record["building_level_context"])
            self.assertFalse(record["liability_claim"])
            self.assertEqual(record["property_system_ids"], ["a", "b"])

    def test_no_explicit_subject_property_remains_unattached(self):
        decision = {
            "decision_id": "decision-2",
            "explicit_subject_property_candidates": [],
        }
        by_system, unmatched = match_decisions_to_systems([decision], [{"system_id": "a", "address": "1 TEST ST"}])
        self.assertEqual(by_system, {})
        self.assertEqual(unmatched[0]["reason"], "NO_EXPLICIT_SUBJECT_PROPERTY_ADDRESS")

    def test_retained_decisions_survive_when_not_in_current_feed_window(self):
        previous = [{"decision_id": "old", "publication_date": "2025-01-01", "title": "Old"}]
        current = [{"decision_id": "new", "publication_date": "2026-09-16", "title": "New"}]
        merged = merge_retained_decisions(current, previous)
        self.assertEqual([row["decision_id"] for row in merged], ["new", "old"])


if __name__ == "__main__":
    unittest.main()
