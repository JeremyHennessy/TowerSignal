import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from build_coverage_audit import ARTIFACT_CONTRACTS, build
from validate_coverage_audit import validate


def health(source_key, requested=2, matched=1, *, coverage=50.0):
    return {
        "source_key": source_key,
        "dataset_id": source_key,
        "name": source_key,
        "entity_unit": "records",
        "retrieved_record_count": matched,
        "requested_entity_count": requested,
        "normalized_entity_count": matched,
        "matched_entity_count": matched,
        "attached_entity_count": matched,
        "displayed_entity_count": matched,
        "coverage_percentage": coverage,
        "previous_coverage_percentage": None,
        "coverage_change_percentage_points": None,
        "coverage_note": "test",
        "status": "HEALTHY",
        "status_reasons": [],
    }


class CoverageAuditTests(unittest.TestCase):
    def _write_fixture(self, output: Path):
        output.mkdir(parents=True, exist_ok=True)
        systems = [
            {
                "system_id": "1",
                "borough": "Manhattan",
                "bbl": "1000000001",
                "bin": "1000001",
                "inspection_count": 1,
                "pluto_match": True,
                "dob_activity_count": 1,
                "hpd_contact_count": 1,
                "planimetric_bin_match": True,
                "building_footprint_bin_match": True,
                "dwt_planimetric_bin_match": True,
                "dwt_compliance_record_count": 1,
                "dwt_self_report_record_count": 1,
                "acris_recent_document_count": 1,
            },
            {
                "system_id": "2",
                "borough": "Brooklyn",
                "bbl": None,
                "bin": "3000001",
                "inspection_count": 0,
                "pluto_match": False,
                "dob_activity_count": 0,
                "hpd_contact_count": 0,
                "planimetric_bin_match": False,
                "building_footprint_bin_match": True,
                "dwt_planimetric_bin_match": False,
                "dwt_compliance_record_count": 0,
                "dwt_self_report_record_count": 0,
                "acris_recent_document_count": 0,
            },
        ]
        health_entries = [
            health("registrations", 2, 2, coverage=100.0),
            health("inspections"),
            health("oath"),
            health("pluto"),
            health("dob_now_jobs"),
            health("hpd_registrations"),
            health("hpd_contacts", 1, 1, coverage=100.0),
            health("planimetric_cooling_towers"),
            health("building_footprints", 2, 2, coverage=100.0),
            health("nys_registry", 1, 1, coverage=100.0),
            health("dwt_planimetric"),
            health("dwt_compliance"),
            health("dwt_self_reports"),
            health("acris_recent"),
        ]
        metadata = {
            "generated_at": "2026-09-07T12:00:00Z",
            "normalized_system_count": 2,
            "source_health": health_entries,
            "pluto_requested_bbl_count": 1,
            "pluto_matched_bbl_count": 1,
            "dob_requested_bbl_count": 1,
            "dob_matched_bbl_count": 1,
        }
        (output / "systems.json").write_text(json.dumps({"metadata": metadata, "systems": systems}), encoding="utf-8")
        (output / "nys-systems.json").write_text(json.dumps({"metadata": {"normalized_equipment_count": 1}, "systems": [{"system_id": "NYS-1"}]}), encoding="utf-8")
        (output / "source-health.json").write_text(json.dumps({"generated_at": metadata["generated_at"], "sources": health_entries}), encoding="utf-8")
        (output / "elap-source-probe.json").write_text(json.dumps({"status": "SOURCE_UNAVAILABLE"}), encoding="utf-8")
        for _, filename, _, _ in ARTIFACT_CONTRACTS:
            path = output / filename
            if path.exists():
                continue
            path.write_text(json.dumps({"generated_at": metadata["generated_at"], "summary": {"record_count": 1}}), encoding="utf-8")
        (output / "history").mkdir(parents=True, exist_ok=True)
        (output / "history/events.json").write_text(json.dumps({"history_started_at": "2026-08-01T00:00:00Z", "events": [{"id": "1"}]}), encoding="utf-8")
        (output / "history/nys").mkdir(parents=True, exist_ok=True)
        (output / "history/nys/events.json").write_text(json.dumps({"history_started_at": "2026-08-01T00:00:00Z", "events": []}), encoding="utf-8")

    def test_build_audit_reconciles_identifiers_and_preserves_gap_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "data"
            self._write_fixture(output)
            report = build(output)
            validate(report)

            identifiers = report["nyc"]["identifier_coverage"]
            self.assertEqual(identifiers["systems"], 2)
            self.assertEqual(identifiers["with_bbl"], 1)
            self.assertEqual(identifiers["missing_bbl"], 1)
            self.assertEqual(identifiers["with_bin"], 2)
            self.assertEqual(identifiers["missing_bin"], 0)

            sources = {item["source_key"]: item for item in report["standardized_coverage_sources"]}
            self.assertEqual(sources["pluto"]["identity_key"], "BBL_EXACT")
            self.assertEqual(sources["pluto"]["borough_breakdown"], {"Manhattan": 1})
            self.assertEqual(sources["hpd_registrations"]["borough_breakdown"], None)

            gaps = {item["gap_key"]: item for item in report["gap_analysis"]}
            self.assertEqual(gaps["CMS"]["classification"], "NOT_INTEGRATED_SOURCE_CONTRACT_REQUIRED")
            self.assertFalse(gaps["CMS"]["observed"]["integrated"])
            self.assertEqual(gaps["NYC_311_HISTORICAL"]["classification"], "BOUNDED_HISTORICAL_CONTEXT_INTEGRATED")
            self.assertTrue(gaps["NYC_311_HISTORICAL"]["observed"]["integrated"])
            self.assertEqual(gaps["ELAP"]["observed"]["probe_status"], "SOURCE_UNAVAILABLE")
            self.assertFalse(report["governance"]["priority_score_1_0_changed"])
            self.assertFalse(report["governance"]["opportunity_score_authorized"])
            self.assertGreater(report["storage_footprint"]["public_data_total_bytes"], 0)

    def test_validator_rejects_cms_promotion_without_source_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "data"
            self._write_fixture(output)
            report = build(output)
            cms = next(item for item in report["gap_analysis"] if item["gap_key"] == "CMS")
            cms["classification"] = "INTEGRATED"
            cms["observed"]["integrated"] = True
            with self.assertRaisesRegex(RuntimeError, "CMS"):
                validate(report)

    def test_validator_rejects_opportunity_score_authorization(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "data"
            self._write_fixture(output)
            report = build(output)
            report["governance"]["opportunity_score_authorized"] = True
            with self.assertRaisesRegex(RuntimeError, "opportunity_score_authorized"):
                validate(report)


if __name__ == "__main__":
    unittest.main()
