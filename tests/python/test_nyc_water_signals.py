from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.domestic_water_market import DomesticWaterSourceError, SourceSnapshot, fetch_snapshot as fetch_source_snapshot  # noqa: E402
from towersignal.nyc_water_signals import (  # noqa: E402
    DOB_APPROVED_PERMITS_DATASET_ID,
    DOB_JOB_FILINGS_DATASET_ID,
    HPD_MAX_PAGE_SIZE,
    HPD_OPEN_WHERE,
    HPD_VIOLATIONS_DATASET_ID,
    HPD_WATER_TERMS,
    LL84_DATASET_ID,
    NYC_311_DATASET_ID,
    _dob_business_profiles,
    build_payload,
    classify_311,
    classify_dob_work,
    normalize_311,
    normalize_dob_job,
    normalize_dob_permit,
    normalize_hpd,
    normalize_ll84,
)
from validate_nyc_water_signals_cache import validate  # noqa: E402


class NycWaterSignalsTests(unittest.TestCase):
    def test_311_keeps_street_context_out_of_building_evidence(self) -> None:
        street = {"unique_key": "1", "agency": "DEP", "complaint_type": "Water System", "descriptor": "Water Main Break", "incident_address": "1 MAIN ST", "bbl": "1000010001"}
        building = {"unique_key": "2", "agency": "DEP", "complaint_type": "Water Quality", "descriptor": "Dirty Water", "incident_address": "2 WATER ST", "bbl": "1000020001"}
        self.assertEqual(classify_311(street), "STREET_WATER_MAIN_CONTEXT")
        normalized_street = normalize_311(street)
        self.assertFalse(normalized_street["is_building_water_signal"])
        self.assertEqual(normalized_street["property_link_confidence"], "CONTEXT_ONLY")
        normalized_building = normalize_311(building)
        self.assertTrue(normalized_building["is_building_water_signal"])
        self.assertEqual(normalized_building["property_link_confidence"], "CONFIRMED_SOURCE_BBL")

    def test_hpd_open_water_violation_preserves_source_property_identifiers(self) -> None:
        normalized = normalize_hpd({
            "violationid": "123", "buildingid": "456", "registrationid": "789", "boro": "MANHATTAN",
            "housenumber": "10", "streetname": "WATER ST", "zip": "10001", "class": "C",
            "inspectiondate": "2026-08-01T00:00:00.000", "novdescription": "PROVIDE HOT WATER",
            "currentstatus": "NOV SENT OUT", "currentstatusdate": "2026-08-02T00:00:00.000",
            "violationstatus": "Open", "rentimpairing": "Y", "bin": "1000001", "bbl": "1000010001",
        })
        self.assertEqual(normalized["category"], "HOT_WATER")
        self.assertEqual(normalized["bbl"], "1000010001")
        self.assertEqual(normalized["bin"], "1000001")
        self.assertEqual(normalized["property_link_confidence"], "CONFIRMED_SOURCE_BBL")

    def test_dob_applicant_role_is_not_promoted_to_service_contract(self) -> None:
        job = normalize_dob_job({
            "job_filing_number": "M123-I1", "filing_status": "Approved", "house_no": "10", "street_name": "TANK ST",
            "borough": "MANHATTAN", "bin": "1000001", "bbl": "1000010001", "plumbing_work_type": "YES",
            "mechanical_systems_work_type_": "NO", "boiler_equipment_work_type_": "NO",
            "job_description": "REPLACE DOMESTIC WATER TANK AND BOOSTER PUMP", "applicant_business_name": "Example Plumbing LLC",
            "applicant_first_name": "Alex", "applicant_last_name": "Smith", "applicant_license": "123456",
        })
        self.assertEqual(job["category"], "DOMESTIC_WATER_STORAGE")
        self.assertEqual(job["relationship_role"], "JOB_APPLICANT_OF_RECORD")
        self.assertEqual(job["relationship_evidence"], "RECORDED_DOB_ROLE")
        self.assertEqual(job["service_assignment_confidence"], "NOT_PROOF_OF_SERVICE_CONTRACT")
        permit = normalize_dob_permit({
            "job_filing_number": "M123-I1", "work_permit": "M123-I1-PL", "sequence_number": "1",
            "house_no": "10", "street_name": "TANK ST", "borough": "MANHATTAN", "bin": "1000001", "bbl": "1000010001",
            "work_type": "Plumbing", "job_description": "INSTALL RPZ BACKFLOW PREVENTER",
            "applicant_business_name": "Example Plumbing Inc.", "applicant_license": "123456", "permittee_s_license_type": "P",
        })
        self.assertEqual(permit["category"], "BACKFLOW_PREVENTION")
        self.assertEqual(permit["relationship_role"], "PERMIT_APPLICANT_OF_RECORD")
        profiles = _dob_business_profiles([job], [permit])
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0]["record_count"], 2)
        self.assertEqual(profiles[0]["job_filing_count"], 1)
        self.assertEqual(profiles[0]["permit_count"], 1)

    def test_dob_fire_water_context_does_not_become_domestic_water(self) -> None:
        self.assertEqual(classify_dob_work({"job_description": "REPLACE FIRE SPRINKLER WATER PIPING", "work_type": "Plumbing"}), "FIRE_WATER_CONTEXT")
        self.assertEqual(classify_dob_work({"job_description": "REPLACE DOMESTIC WATER PIPING", "work_type": "Plumbing"}), "DOMESTIC_WATER_SYSTEM")

    def test_ll84_multi_bbl_is_not_force_linked(self) -> None:
        single = normalize_ll84({"report_year": "2025", "property_id": "1", "nyc_borough_block_and_lot": "1000010001", "nyc_building_identification": "1000001", "municipally_supplied_potable_1": "1234.5"})
        self.assertEqual(single["property_link_confidence"], "EXACT_SINGLE_BBL")
        self.assertEqual(single["property_key"], "NYC-BBL-1000010001")
        self.assertEqual(single["municipal_potable_total_kgal"], 1234.5)
        multi = normalize_ll84({"report_year": "2025", "property_id": "2", "nyc_borough_block_and_lot": "1000010001, 1000020002", "nyc_building_identification": "1000001, 1000002"})
        self.assertEqual(multi["property_link_confidence"], "MULTI_IDENTIFIER_CONTEXT")
        self.assertIsNone(multi["property_key"])
        self.assertEqual(multi["bbls"], ["1000010001", "1000020002"])

    def test_build_payload_fetches_open_hpd_once_and_filters_water_terms_locally(self) -> None:
        calls: list[tuple[str, int]] = []
        hpd_row = {
            "violationid": "123",
            "buildingid": "456",
            "registrationid": "789",
            "boro": "MANHATTAN",
            "housenumber": "10",
            "streetname": "WATER ST",
            "zip": "10001",
            "class": "C",
            "inspectiondate": "2026-08-01T00:00:00.000",
            "novdescription": "PROVIDE HOT WATER AND REPAIR PLUMBING",
            "currentstatus": "NOV SENT OUT",
            "currentstatusdate": "2026-08-02T00:00:00.000",
            "violationstatus": "Open",
            "rentimpairing": "Y",
            "bin": "1000001",
            "bbl": "1000010001",
        }
        non_water_hpd_row = dict(hpd_row, violationid="124", novdescription="PAINT PEELING")

        def fake_fetch_snapshot(dataset_id: str, **kwargs):
            calls.append((dataset_id, int(kwargs["page_size"])))
            if dataset_id == HPD_VIOLATIONS_DATASET_ID:
                self.assertEqual(kwargs.get("where"), HPD_OPEN_WHERE)
                rows = [hpd_row, dict(hpd_row), non_water_hpd_row]
            else:
                rows = []
            return SourceSnapshot(
                dataset_id=dataset_id,
                name=dataset_id,
                api_root=str(kwargs["api_root"]),
                rows=rows,
                retrieved_at="2026-09-05T00:00:00Z",
                source_record_count=len(rows),
                source_last_updated_at="2026-09-05T00:00:00Z",
                source_query_scope=str(kwargs.get("where") or "ALL_ROWS"),
                fields=tuple(kwargs["required_fields"]),
            )

        with patch("towersignal.nyc_water_signals.fetch_snapshot", side_effect=fake_fetch_snapshot):
            payload = build_payload(page_size=50000)

        self.assertEqual(payload["summary"]["hpd_open_water_violation_count"], 1)
        self.assertEqual(payload["summary"]["hpd_source_fetch_strategy"], "OPEN_VIOLATIONS_LOCAL_TERM_FILTER")
        self.assertEqual(payload["summary"]["hpd_source_partition_count"], 1)
        self.assertEqual(payload["summary"]["hpd_source_partition_record_count"], 3)
        self.assertEqual(payload["summary"]["hpd_duplicate_partition_violation_count"], 1)
        page_sizes = dict(calls)
        self.assertEqual(page_sizes[NYC_311_DATASET_ID], 50000)
        self.assertEqual(page_sizes[HPD_VIOLATIONS_DATASET_ID], HPD_MAX_PAGE_SIZE)
        self.assertEqual(page_sizes[DOB_JOB_FILINGS_DATASET_ID], 50000)
        self.assertEqual(page_sizes[DOB_APPROVED_PERMITS_DATASET_ID], 50000)
        self.assertEqual(page_sizes[LL84_DATASET_ID], 50000)
        hpd_calls = [call for call in calls if call[0] == HPD_VIOLATIONS_DATASET_ID]
        self.assertEqual(len(hpd_calls), 1)
        self.assertLessEqual(HPD_MAX_PAGE_SIZE, 25000)

    def test_snapshot_reduces_page_size_after_repeated_source_timeout(self) -> None:
        rows = [{"id": str(index)} for index in range(5)]
        page_limits: list[int] = []

        def fake_query(dataset_id: str, *, api_root: str, params):
            self.assertEqual(dataset_id, "timeout-demo")
            self.assertEqual(api_root, "https://example.test")
            limit = int(params["$limit"])
            offset = int(params["$offset"])
            page_limits.append(limit)
            if limit == 4:
                raise DomesticWaterSourceError("source page timed out")
            return rows[offset:offset + limit]

        with (
            patch("towersignal.domestic_water_market.fetch_metadata", return_value={"name": "Timeout demo", "source_last_updated_at": None, "fields": ("id",)}),
            patch("towersignal.domestic_water_market.fetch_count", return_value=len(rows)),
            patch("towersignal.domestic_water_market._query", side_effect=fake_query),
        ):
            snapshot = fetch_source_snapshot(
                "timeout-demo",
                api_root="https://example.test",
                order_by="id",
                required_fields=("id",),
                page_size=4,
                minimum_page_size=2,
            )

        self.assertEqual([row["id"] for row in snapshot.rows], ["0", "1", "2", "3", "4"])
        self.assertEqual(page_limits, [4, 2, 2, 2])

    def test_snapshot_can_page_to_completion_when_count_query_times_out(self) -> None:
        rows = [{"id": str(index)} for index in range(5)]
        page_offsets: list[int] = []

        def fake_query(dataset_id: str, *, api_root: str, params):
            self.assertEqual(dataset_id, "count-timeout-demo")
            self.assertEqual(api_root, "https://example.test")
            limit = int(params["$limit"])
            offset = int(params["$offset"])
            page_offsets.append(offset)
            return rows[offset:offset + limit]

        with (
            patch("towersignal.domestic_water_market.fetch_metadata", return_value={"name": "Count timeout demo", "source_last_updated_at": None, "fields": ("id",)}),
            patch("towersignal.domestic_water_market.fetch_count", side_effect=DomesticWaterSourceError("count timed out")),
            patch("towersignal.domestic_water_market._query", side_effect=fake_query),
        ):
            snapshot = fetch_source_snapshot(
                "count-timeout-demo",
                api_root="https://example.test",
                order_by="id",
                required_fields=("id",),
                page_size=2,
                allow_count_fallback=True,
            )

        self.assertEqual([row["id"] for row in snapshot.rows], ["0", "1", "2", "3", "4"])
        self.assertEqual(snapshot.source_record_count, 5)
        self.assertEqual(page_offsets, [0, 2, 4])

    def test_validator_accepts_zero_count_source_partitions(self) -> None:
        hpd_row = {
            "violationid": "123",
            "buildingid": "456",
            "registrationid": "789",
            "boro": "MANHATTAN",
            "housenumber": "10",
            "streetname": "WATER ST",
            "zip": "10001",
            "class": "C",
            "inspectiondate": "2026-08-01T00:00:00.000",
            "novdescription": "PROVIDE HOT WATER",
            "currentstatus": "NOV SENT OUT",
            "currentstatusdate": "2026-08-02T00:00:00.000",
            "violationstatus": "Open",
            "rentimpairing": "Y",
            "bin": "1000001",
            "bbl": "1000010001",
        }

        def fake_fetch_snapshot(dataset_id: str, **kwargs):
            where = str(kwargs.get("where") or "")
            rows = [hpd_row] if dataset_id == HPD_VIOLATIONS_DATASET_ID and where == HPD_OPEN_WHERE else []
            return SourceSnapshot(
                dataset_id=dataset_id,
                name=dataset_id,
                api_root=str(kwargs["api_root"]),
                rows=rows,
                retrieved_at="2026-09-05T00:00:00Z",
                source_record_count=len(rows),
                source_last_updated_at="2026-09-05T00:00:00Z",
                source_query_scope=where or "ALL_ROWS",
                fields=tuple(kwargs["required_fields"]),
            )

        with patch("towersignal.nyc_water_signals.fetch_snapshot", side_effect=fake_fetch_snapshot):
            payload = build_payload(page_size=50000)

        handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False)
        with handle:
            json.dump(payload, handle)
        cache = Path(handle.name)
        try:
            validated = validate(cache, max_age_days=1, require_production_volume=False)
        finally:
            cache.unlink()

        self.assertEqual(validated["summary"]["hpd_open_water_violation_count"], 1)
        self.assertEqual(validated["summary"]["hpd_source_partition_record_count"], 1)
        self.assertEqual(validated["summary"]["hpd_duplicate_partition_violation_count"], 0)


if __name__ == "__main__":
    unittest.main()
