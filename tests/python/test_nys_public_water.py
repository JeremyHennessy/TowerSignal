from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.nys_public_water import (  # noqa: E402
    build_pws_profiles,
    discover_pws_contact_pages,
    discover_violation_pages,
    parse_certified_operators,
    parse_lsli_index,
    parse_pws_contact_page,
    parse_violation_page,
)


class NysPublicWaterTests(unittest.TestCase):
    def test_directory_preserves_multiple_contacts_without_assigning_operator_role(self) -> None:
        html = """
        <html><h1>Oneida County Public Drinking Water Supply Contact List 2026</h1><table>
        <tr><th>Public Water Supply Name</th><th>PWS ID</th><th>System Type</th><th>Total Population</th><th>Contact Information</th></tr>
        <tr><td>12 NORTH SPORTS BAR</td><td>NY3220660</td><td>NC-Non-community transient water system</td><td>100</td><td>Mr. Douglas Martin<br>12 NORTH LLC<br>101 ROAD</td></tr>
        <tr><td>12 NORTH SPORTS BAR</td><td>NY3220660</td><td>NC-Non-community transient water system</td><td>100</td><td>Mr. David J Converse<br>CONVERSE LABORATORIES, INC.<br>800 STARBUCK AVE</td></tr>
        </table></html>
        """
        rows = parse_pws_contact_page(html, source_url="https://example.test/onei_contacts.htm")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["contact_name_raw"], "Mr. David J Converse")
        self.assertEqual(rows[1]["relationship_role"], "CONTACT_FOR_PWS")
        self.assertEqual(rows[1]["operator_assignment_confidence"], "NOT_PROOF_OF_OPERATOR_ROLE")
        profiles = build_pws_profiles(rows, [], [])
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0]["contact_count"], 2)
        self.assertEqual(profiles[0]["total_population"], 100)

    def test_certified_operator_is_qualification_only(self) -> None:
        html = """
        <table><tr><th>County</th><th>Name</th><th>Certification</th><th>Expiration</th><th>Level Descriptions</th></tr>
        <tr><td>New York</td><td>Aitken, Rory</td><td>NY0044495</td><td>2/28/2029</td><td>D-Distribution System</td></tr>
        </table>
        """
        rows = parse_certified_operators(html)
        self.assertEqual(rows[0]["certification_number"], "NY0044495")
        self.assertEqual(rows[0]["relationship_evidence"], "QUALIFIED_OPERATOR")
        self.assertEqual(rows[0]["pws_assignment_confidence"], "UNLINKED_TO_PWS")

    def test_lsli_index_creates_pws_detail_url_but_no_operator_assignment(self) -> None:
        html = """
        <table><tr><th>PWS ID Number</th><th>PWS Name</th><th>Principal County Served</th></tr>
        <tr><td>NY7003493</td><td>NEW YORK CITY SYSTEM</td><td>NEW YORK CITY (Bronx, Kings, New York, Queens, Richmond)</td></tr>
        </table>
        """
        rows = parse_lsli_index(html)
        self.assertEqual(rows[0]["pws_id"], "NY7003493")
        self.assertTrue(rows[0]["lead_service_line_inventory_required"])
        self.assertTrue(rows[0]["detail_url"].endswith("/NY7003493.htm"))

    def test_violation_row_is_keyed_to_authoritative_pwsid(self) -> None:
        html = """
        <h1>Erie County Compliance Report 2025</h1><table>
        <tr><th>Name (PWS ID)</th><th>Type</th><th>Violation Type</th><th>Contaminant(s)</th><th>Months Covered</th><th>Status</th></tr>
        <tr><td>ANGOLA VILLAGE (NY1400411)</td><td>C-Community water system</td><td>4G - LSL REPORTING-INITIAL</td><td></td><td>October 2024 to August 2025</td><td>No longer in violation</td></tr>
        </table>
        """
        rows = parse_violation_page(html, source_url="https://example.test/erie_county_compliance_report.htm")
        self.assertEqual(rows[0]["pws_id"], "NY1400411")
        self.assertEqual(rows[0]["pws_name"], "ANGOLA VILLAGE")
        self.assertEqual(rows[0]["calendar_year"], 2025)
        self.assertTrue(rows[0]["violation_id"].startswith("nys-pws-violation-"))

    def test_index_discovery_is_link_driven_and_deduplicated(self) -> None:
        pws = """<a href='alba_contacts.htm'>Albany</a><a href='alba_contacts.htm'>Albany map</a><a href='nass_contacts.htm'>Nassau</a>"""
        self.assertEqual(len(discover_pws_contact_pages(pws)), 2)
        violations = """<a href='erie_county_compliance_report.htm'>Erie</a><a href='nyc_compliance_report.htm'>NYC</a><a href='2025_compliance_report.htm'>state</a>"""
        self.assertEqual(len(discover_violation_pages(violations)), 2)


if __name__ == "__main__":
    unittest.main()
