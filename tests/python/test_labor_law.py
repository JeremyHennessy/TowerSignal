import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from build_labor_law_decisions import build as build_labor_law_decisions
from towersignal.labor_law import (
    match_decisions_to_systems,
    merge_retained_decisions,
    normalize_decision,
    normalize_property_address,
    normalize_publication_date,
)


class LaborLawDecisionTests(unittest.TestCase):
    def test_property_address_normalization_is_bounded_and_deterministic(self):
        self.assertEqual(normalize_property_address("350 West 71st Street"), "350 W 71ST ST")
        self.assertEqual(normalize_property_address("3420 Bedford Avenue"), "3420 BEDFORD AVE")
        self.assertIsNone(normalize_property_address(None))

    def test_publication_date_normalizes_rss_rfc_date_to_iso_day(self):
        self.assertEqual(normalize_publication_date("Wed, 16 Sep 2026 23:30:00 -0400"), "2026-09-17")
        self.assertIsNone(normalize_publication_date("not a date"))
        self.assertIsNone(normalize_publication_date(None))

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
        self.assertEqual(row["publication_date"], "2026-09-16")
        self.assertEqual(row["publication_date_raw"], "Wed, 16 Sep 2026 12:00:00 GMT")
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
            "publication_date": "2026-09-16",
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

    def test_build_mirrors_retained_cache_into_verified_history_segments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_dir = root / "public" / "data"
            output_dir.mkdir(parents=True)
            systems_path = output_dir / "systems.json"
            systems_path.write_text(json.dumps({
                "schema_version": "1.0",
                "metadata": {"snapshot_date": "2026-09-17"},
                "systems": [{"system_id": "SYS-1", "address": "350 W 71ST ST"}],
            }), encoding="utf-8")
            previous_path = root / "previous.json"
            previous_path.write_text(json.dumps({
                "decisions": [{
                    "decision_id": "old-decision",
                    "publication_date": "2025-01-01",
                    "title": "Old retained decision",
                    "explicit_subject_property_candidates": [],
                }],
            }), encoding="utf-8")
            current = [{
                "decision_id": "new-decision",
                "publication_date": "2026-09-17",
                "publication_date_raw": "Thu, 17 Sep 2026 12:00:00 GMT",
                "title": "New decision",
                "decision_url": "https://example.test/new",
                "explicit_subject_property_candidates": [],
                "labor_law_sections": [],
                "index_numbers": [],
                "case_numbers": [],
                "nyscef_document_numbers": [],
                "source": "NYS_OFFICIAL_REPORTS_PUBLISHED_DECISION",
                "evidence_class": "PUBLISHED_DECISION_PARTIAL_COVERAGE",
            }]
            source = {
                "dataset_id": "NYS_OFFICIAL_REPORTS_LABOR_LAW_PUBLISHED_DECISIONS",
                "name": "New York Official Reports — Labor Law published decisions",
                "url": "https://www.nycourts.gov/reporter/RSS.shtml",
                "retrieved_at": "2026-09-17T12:00:00Z",
                "source_record_count": 10,
                "inspected_record_count": 10,
                "matched_record_count": 1,
                "feed_health": {},
                "retrieval_failures": [],
                "source_query_scope": "fixture",
                "coverage_boundary": "partial",
                "current_filing_status_available": False,
            }
            with patch("build_labor_law_decisions.fetch_published_labor_law_decisions", return_value=(current, source)):
                output_path = output_dir / "labor-law-decisions.json"
                payload = build_labor_law_decisions(systems_path, output_path, previous_path)

            segment_path = output_dir / "history" / "segments" / "labor-law-decisions.json"
            self.assertTrue(segment_path.exists())
            segment = json.loads(segment_path.read_text(encoding="utf-8"))
            self.assertEqual(segment, payload)
            self.assertEqual([row["decision_id"] for row in payload["decisions"]], ["new-decision", "old-decision"])


if __name__ == "__main__":
    unittest.main()
