from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.nys_lsli_detail import (  # noqa: E402
    _explicit_detail_404,
    _unavailable_detail,
    parse_detail,
)
from towersignal.nys_public_water import NysPublicWaterSourceError  # noqa: E402


def sample_html(pws_id: str = "NY7003493") -> str:
    return f"""
    <html><head><title>LSLI</title></head><body>
    <h1>Summary of Lead Service Line Inventory</h1>
    <table>
      <tr><td>Water System Name</td><td>Example Water System</td></tr>
      <tr><td>PWS ID Number</td><td>{pws_id}</td></tr>
    </table>
    <table>
      <tr><td>Contact Name</td><td>Jane Operator</td></tr>
      <tr><td>Contact Phone Number</td><td>555-111-2222</td></tr>
      <tr><td>Contact Email Address</td><td>water@example.org</td></tr>
    </table>
    <table>
      <tr><td>Total Number of Service Lines in the Distribution System</td><td>100</td></tr>
      <tr><td>Total Number of Identified Service Lines</td><td>80</td></tr>
      <tr><td>Total Number of Lead Service Lines</td><td>10</td></tr>
      <tr><td>Total Number of GSLRR</td><td>5</td></tr>
      <tr><td>Total Number of Non-LSL</td><td>65</td></tr>
      <tr><td>Total Number of Unknown Service Lines</td><td>20</td></tr>
    </table>
    <table>
      <tr><th>Service Lines</th><th>Lead</th><th>GSL or GSLRR</th><th>Non-Lead</th><th>Unknown</th></tr>
      <tr><td>PWS - Side Service Lines</td><td>10</td><td>5 GSL</td><td>65</td><td>20</td></tr>
      <tr><td>Customer - Side Service Lines</td><td>10</td><td>5 GSL</td><td>65</td><td>20</td></tr>
      <tr><td>Total Number of Service Lines in the Distribution System</td><td>10</td><td>5 GSLRR</td><td>65</td><td>20</td></tr>
    </table>
    <table>
      <tr><th>Identification Methods</th><th>PWS- Side SLs</th><th>Customer-Side SLs</th></tr>
      <tr><td>Historical Records</td><td>50</td><td>50</td></tr>
      <tr><td>Field Inspection</td><td>30</td><td>30</td></tr>
      <tr><td>Customer Identification with Photo or other Verification</td><td>NA</td><td>0</td></tr>
      <tr><td>Excavation</td><td>0</td><td>0</td></tr>
      <tr><td>Sequential Sampling</td><td>0</td><td>0</td></tr>
      <tr><td>Statistical Analysis/Predictive Model</td><td>0</td><td>0</td></tr>
    </table>
    <table>
      <tr><td>If 50,000 customers or greater: Posting the inventory online water system's website.</td><td>Address: <a href="https://example.org/lsli">https://example.org/lsli</a></td></tr>
      <tr><td>If under 50,000 customers: Explain how to access the inventory</td><td>Available at office</td></tr>
    </table>
    <table>
      <tr><td>Jane Operator</td><td>Name</td></tr>
      <tr><td>Water Superintendent</td><td>Title</td></tr>
      <tr><td>12/29/2025</td><td>Date</td></tr>
    </table>
    </body></html>
    """


class NysLsliDetailTests(unittest.TestCase):
    def test_parses_contact_inventory_methods_and_certification(self) -> None:
        result = parse_detail(
            sample_html(),
            source_url="https://www.health.ny.gov/environmental/water/drinking/service_line/NY7003493.htm",
            expected_pws_id="NY7003493",
        )
        self.assertEqual(result["detail_status"], "PARSED")
        self.assertEqual(result["inventory"]["total_service_lines"], 100)
        self.assertEqual(result["inventory"]["lead_service_lines"], 10)
        self.assertEqual(result["owner_or_operator_form_contact"]["name"], "Jane Operator")
        self.assertEqual(
            result["owner_or_operator_form_contact"]["relationship_role"],
            "OWNER_OR_LICENSED_OPERATOR_OF_RECORD_FORM_CONTACT",
        )
        self.assertEqual(len(result["identification_methods"]), 6)
        self.assertEqual(result["certification"]["name"], "Jane Operator")
        self.assertEqual(result["certification"]["title"], "Water Superintendent")
        self.assertEqual(result["certification"]["date"], "2025-12-29")

    def test_parses_gsl_text_as_numeric_count(self) -> None:
        result = parse_detail(
            sample_html(),
            source_url="https://www.health.ny.gov/environmental/water/drinking/service_line/NY7003493.htm",
        )
        self.assertEqual(result["material_matrix"]["PWS - Side Service Lines"]["gsl_or_gslrr"], 5)

    def test_external_inventory_link_is_preserved(self) -> None:
        result = parse_detail(
            sample_html(),
            source_url="https://www.health.ny.gov/environmental/water/drinking/service_line/NY7003493.htm",
        )
        links = result["inventory_availability"]["external_links"]
        self.assertTrue(any(link["href"] == "https://example.org/lsli" for link in links))

    def test_pws_mismatch_fails_closed(self) -> None:
        with self.assertRaisesRegex(NysPublicWaterSourceError, "PWS mismatch"):
            parse_detail(
                sample_html("NY7003493"),
                source_url="https://example.test/NY9999999.htm",
                expected_pws_id="NY9999999",
            )

    def test_missing_required_inventory_field_fails_closed(self) -> None:
        broken = sample_html().replace(
            "<tr><td>Total Number of Unknown Service Lines</td><td>20</td></tr>",
            "",
        )
        with self.assertRaisesRegex(NysPublicWaterSourceError, "required inventory"):
            parse_detail(broken, source_url="https://example.test/NY7003493.htm")

    def test_only_explicit_fetch_404_is_treated_as_unavailable_detail(self) -> None:
        explicit = NysPublicWaterSourceError(
            "Failed to retrieve NYSDOH page after fallback/retries: "
            "https://www.health.ny.gov/environmental/water/drinking/service_line/NY0117224.htm: "
            "HTTP Error 404: Not Found"
        )
        self.assertTrue(_explicit_detail_404(explicit))
        self.assertFalse(_explicit_detail_404(NysPublicWaterSourceError("Required table not found")))

    def test_unavailable_detail_retains_index_identity_and_no_inventory(self) -> None:
        exc = NysPublicWaterSourceError("HTTP Error 404: Not Found")
        row = _unavailable_detail(
            {
                "pws_id": "NY0117224",
                "pws_name": "Example Indexed System",
                "county": "Example",
                "detail_url": "https://www.health.ny.gov/environmental/water/drinking/service_line/NY0117224.htm",
            },
            exc,
        )
        self.assertEqual(row["detail_status"], "DETAIL_UNAVAILABLE_404")
        self.assertEqual(row["pws_id"], "NY0117224")
        self.assertNotIn("inventory", row)


if __name__ == "__main__":
    unittest.main()
