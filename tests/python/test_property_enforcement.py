import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.property_enforcement import (
    fetch_official_swo_snapshot_by_bin,
    normalize_facade_filing,
    normalize_hpd_violation,
    normalize_official_swo_snapshot,
    normalize_stop_work_order,
)


class PropertyEnforcementTests(unittest.TestCase):
    def test_hpd_violation_uses_published_violation_status_for_open_state(self):
        row = normalize_hpd_violation({
            "violationid": "80421324",
            "bbl": "1001230045",
            "bin": "1001234",
            "class": "C",
            "inspectiondate": "2026-09-10T00:00:00.000",
            "currentstatus": "NOV SENT OUT",
            "violationstatus": "Open",
            "rentimpairing": "Y",
            "novdescription": "Example immediately hazardous condition",
        })
        self.assertEqual(row["bbl"], "1001230045")
        self.assertEqual(row["bin"], "1001234")
        self.assertEqual(row["class"], "C")
        self.assertEqual(row["violation_status"], "OPEN")
        self.assertTrue(row["is_open"])
        self.assertTrue(row["rent_impairing"])
        self.assertEqual(row["match_basis"], "BBL_EXACT")

    def test_swo_disposition_preserves_issue_and_rescission_semantics(self):
        issued = normalize_stop_work_order({
            "complaint_number": "1234567",
            "bin": "1001234",
            "disposition_code": "A3",
            "disposition_date": "09/10/2026",
        })
        rescinded = normalize_stop_work_order({
            "complaint_number": "1234567",
            "bin": "1001234",
            "disposition_code": "L2",
            "disposition_date": "09/12/2026",
        })
        self.assertEqual(issued["event_type"], "ISSUED_FULL")
        self.assertEqual(issued["disposition_text"], "Full Stop Work Order Served")
        self.assertEqual(rescinded["event_type"], "RESCINDED_FULL")
        self.assertEqual(rescinded["disposition_text"], "Stop Work Order Fully Rescinded")
        self.assertEqual(rescinded["match_basis"], "BIN_EXACT")

    def test_official_swo_snapshot_preserves_dated_status_without_current_claim(self):
        record = normalize_official_swo_snapshot({
            "Borough Name": "Manhattan",
            "Complaint Number": "1234567",
            "BIN": "1001234",
            "Disposition Code Description": "FULL STOP WORK ORDER SERVED F",
            "Disposition Category": "ACTIVE",
            "Last Disposition Date": "2/3/2024",
            "Last Disposition Year": "2024",
            "Latitude": "40.75",
            "Longitude": "-73.98",
            "Address": "1 TEST STREET",
            "Community Board": "105",
        })
        self.assertEqual(record["status_at_snapshot"], "ACTIVE")
        self.assertEqual(record["last_disposition_date"], "2024-02-03")
        self.assertEqual(record["match_basis"], "BIN_EXACT")
        self.assertFalse(record["current_status_claim"])

    def test_official_swo_snapshot_filters_only_after_complete_source_parse(self):
        raw = (
            "Borough Name,Complaint Number,BIN,Disposition Code Description,Disposition Category,Last Disposition Date,Last Disposition Year,Latitude,Longitude,Address,Community Board\n"
            "Manhattan,1111111,1001234,FULL STOP WORK ORDER SERVED F,ACTIVE,2/3/2024,2024,40.7,-73.9,1 TEST ST,105\n"
            "Queens,2222222,4004321,STOP WORK ORDER FULLY RESCINDED N,RESCINDED,1/2/2024,2024,40.7,-73.8,2 TEST ST,401\n"
        ).encode()
        by_bin, source = fetch_official_swo_snapshot_by_bin(["1001234"], request_bytes=lambda: raw)
        self.assertEqual(source["source_record_count"], 2)
        self.assertEqual(source["matched_bin_count"], 1)
        self.assertEqual(source["source_observation_end_at"], "2024-02-03")
        self.assertEqual(source["source_health_status"], "WARNING")
        self.assertFalse(source["current_status_available"])
        self.assertEqual(by_bin["1001234"][0]["status_at_snapshot"], "ACTIVE")

    def test_facade_status_and_professional_are_preserved_without_inference(self):
        filing = normalize_facade_filing({
            "control_no": "FISP-1",
            "bin": "1001234",
            "filing_type": "Initial",
            "cycle": "10",
            "submitted_on": "2026-08-01T00:00:00.000",
            "current_status": "UNSAFE",
            "qewi_name": "Example Engineer",
            "qewi_bus_name": "Example Engineering PLLC",
        })
        self.assertEqual(filing["current_status"], "UNSAFE")
        self.assertEqual(filing["cycle"], "10")
        self.assertEqual(filing["qewi_name"], "Example Engineer")
        self.assertEqual(filing["match_basis"], "BIN_EXACT")


if __name__ == "__main__":
    unittest.main()
