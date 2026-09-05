from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.nys_lsli_detail import (  # noqa: E402
    _explicit_detail_404,
    _unavailable_detail,
    build_payload,
    parse_detail,
)
from towersignal.nys_public_water import HtmlSnapshot, LSLI_INDEX_URL, NysPublicWaterSourceError  # noqa: E402
from validate_nys_lsli_detail_cache import validate as validate_lsli_cache  # noqa: E402


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


def index_html(pws_ids: list[str]) -> str:
    rows = "\n".join(
        f"<tr><td>{pws_id}</td><td>System {pws_id}</td><td>Albany</td></tr>"
        for pws_id in pws_ids
    )
    return f"""
    <html><body>
    <table>
      <tr><th>PWS ID Number</th><th>PWS Name</th><th>Principal County Served</th></tr>
      {rows}
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
        self.assertEqual(
            result["inventory_evidence"]["identified_service_lines"],
            "SOURCE_REPORTED",
        )
        self.assertEqual(result["owner_or_operator_form_contact"]["name"], "Jane Operator")
        self.assertEqual(
            result["owner_or_operator_form_contact"]["relationship_role"],
            "OWNER_OR_LICENSED_OPERATOR_OF_RECORD_FORM_CONTACT",
        )
        self.assertEqual(len(result["identification_methods"]), 6)
        self.assertEqual(result["certification"]["name"], "Jane Operator")
        self.assertEqual(result["certification"]["title"], "Water Superintendent")
        self.assertEqual(result["certification"]["date"], "2025-12-29")

    def test_missing_identified_aggregate_is_derived_from_source_components(self) -> None:
        html = sample_html().replace(
            "<tr><td>Total Number of Identified Service Lines</td><td>80</td></tr>",
            "",
        )
        result = parse_detail(html, source_url="https://example.test/NY7003493.htm")
        self.assertIsNone(result["source_reported_inventory"]["identified_service_lines"])
        self.assertEqual(result["inventory"]["identified_service_lines"], 80)
        self.assertEqual(
            result["inventory_evidence"]["identified_service_lines"],
            "DERIVED_FROM_SOURCE_COMPONENT_COUNTS",
        )

    def test_source_total_reconciliation_mismatch_is_preserved_with_evidence(self) -> None:
        html = sample_html().replace(
            "<tr><td>Total Number of Service Lines in the Distribution System</td><td>100</td></tr>",
            "<tr><td>Total Number of Service Lines in the Distribution System</td><td>111</td></tr>",
        )
        result = parse_detail(html, source_url="https://example.test/NY7003493.htm")
        self.assertEqual(result["inventory"]["total_service_lines"], 111)
        self.assertEqual(result["source_reported_inventory"]["total_service_lines"], 111)
        self.assertEqual(
            result["inventory_evidence"]["total_service_lines"],
            "SOURCE_REPORTED_RECONCILIATION_MISMATCH",
        )
        self.assertFalse(
            result["inventory_reconciliation"]["total_matches_identified_plus_unknown"]
        )
        self.assertEqual(
            result["inventory_reconciliation"]["total_expected_from_identified_plus_unknown"],
            100,
        )
        self.assertEqual(result["inventory_reconciliation"]["total_identified_unknown_delta"], 11)

    def test_source_identified_reconciliation_mismatch_is_preserved_with_evidence(self) -> None:
        html = sample_html().replace(
            "<tr><td>Total Number of Identified Service Lines</td><td>80</td></tr>",
            "<tr><td>Total Number of Identified Service Lines</td><td>81</td></tr>",
        ).replace(
            "<tr><td>Total Number of Service Lines in the Distribution System</td><td>100</td></tr>",
            "<tr><td>Total Number of Service Lines in the Distribution System</td><td>101</td></tr>",
        )
        result = parse_detail(html, source_url="https://example.test/NY7003493.htm")
        self.assertEqual(result["inventory"]["identified_service_lines"], 81)
        self.assertEqual(result["source_reported_inventory"]["identified_service_lines"], 81)
        self.assertEqual(
            result["inventory_evidence"]["identified_service_lines"],
            "SOURCE_REPORTED_RECONCILIATION_MISMATCH",
        )
        self.assertFalse(result["inventory_reconciliation"]["identified_matches_components"])
        self.assertEqual(
            result["inventory_reconciliation"]["identified_expected_from_components"],
            80,
        )
        self.assertEqual(result["inventory_reconciliation"]["identified_component_delta"], 1)

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

    def test_missing_required_inventory_component_fails_closed(self) -> None:
        broken = sample_html().replace(
            "<tr><td>Total Number of Unknown Service Lines</td><td>20</td></tr>",
            "",
        )
        with self.assertRaisesRegex(NysPublicWaterSourceError, "required inventory component"):
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
                "principal_county_served": "ALBANY",
                "detail_url": "https://www.health.ny.gov/environmental/water/drinking/service_line/NY0117224.htm",
            },
            exc,
        )
        self.assertEqual(row["detail_status"], "DETAIL_UNAVAILABLE_404")
        self.assertEqual(row["pws_id"], "NY0117224")
        self.assertEqual(row["principal_county_served"], "ALBANY")
        self.assertNotIn("inventory", row)

    def test_concurrent_payload_crawl_preserves_index_order_and_metadata(self) -> None:
        pws_ids = ["NY0000001", "NY0000002", "NY0000003"]

        def fake_fetch_html(url: str):
            if url == LSLI_INDEX_URL:
                return HtmlSnapshot(url=url, html=index_html(pws_ids), retrieved_at="2026-09-05T00:00:00Z")
            pws_id = Path(url).stem
            return HtmlSnapshot(url=url, html=sample_html(pws_id), retrieved_at="2026-09-05T00:00:00Z")

        with patch("towersignal.nys_lsli_detail.fetch_html", side_effect=fake_fetch_html):
            payload = build_payload(request_delay_seconds=0, max_workers=3)

        self.assertEqual(payload["source"]["index_record_count"], 3)
        self.assertEqual(payload["source"]["parsed_detail_count"], 3)
        self.assertEqual(payload["source"]["max_workers"], 3)
        self.assertEqual([row["pws_id"] for row in payload["details"]], pws_ids)

    def test_payload_retains_many_explicit_404_details(self) -> None:
        pws_ids = [f"NY{index:07d}" for index in range(1, 31)]

        def fake_fetch_html(url: str):
            if url == LSLI_INDEX_URL:
                return HtmlSnapshot(url=url, html=index_html(pws_ids), retrieved_at="2026-09-05T00:00:00Z")
            raise NysPublicWaterSourceError(
                "Failed to retrieve NYSDOH page after fallback/retries: "
                f"{url}: HTTP Error 404: Not Found"
            )

        with patch("towersignal.nys_lsli_detail.fetch_html", side_effect=fake_fetch_html):
            payload = build_payload(request_delay_seconds=0, max_workers=4)

        self.assertEqual(payload["source"]["index_record_count"], 30)
        self.assertEqual(payload["source"]["parsed_detail_count"], 0)
        self.assertEqual(payload["source"]["explicit_unavailable_404_count"], 30)
        self.assertTrue(payload["source"]["coverage_complete"])
        self.assertFalse(payload["source"]["parsed_detail_complete"])
        self.assertEqual(len(payload["unavailable_details"]), 30)

    def test_validator_accepts_many_explicit_404_details_when_coverage_is_complete(self) -> None:
        base = parse_detail(
            sample_html("NY0000001"),
            source_url="https://www.health.ny.gov/environmental/water/drinking/service_line/NY0000001.htm",
            expected_pws_id="NY0000001",
        )
        base["inventory"] = {
            "total_service_lines": 1000,
            "identified_service_lines": 800,
            "lead_service_lines": 100,
            "gslrr_service_lines": 50,
            "non_lead_service_lines": 650,
            "unknown_service_lines": 200,
        }
        base["source_reported_inventory"] = dict(base["inventory"])
        base["inventory_evidence"] = {
            "identified_service_lines": "SOURCE_REPORTED",
            "total_service_lines": "SOURCE_REPORTED",
            "all_other_inventory_fields": "SOURCE_REPORTED",
        }
        base["inventory_reconciliation"] = {
            "identified_matches_components": True,
            "identified_expected_from_components": 800,
            "identified_component_delta": 0,
            "total_matches_identified_plus_unknown": True,
            "total_expected_from_identified_plus_unknown": 1000,
            "total_identified_unknown_delta": 0,
        }
        details = []
        for index in range(1, 2551):
            pws_id = f"NY{index:07d}"
            row = copy.deepcopy(base)
            row["pws_id"] = pws_id
            row["source_url"] = (
                "https://www.health.ny.gov/environmental/water/drinking/service_line/"
                f"{pws_id}.htm"
            )
            details.append(row)

        unavailable_details = [
            _unavailable_detail(
                {
                    "pws_id": f"NY{index:07d}",
                    "pws_name": f"System NY{index:07d}",
                    "principal_county_served": "ALBANY",
                    "detail_url": (
                        "https://www.health.ny.gov/environmental/water/drinking/service_line/"
                        f"NY{index:07d}.htm"
                    ),
                },
                NysPublicWaterSourceError(
                    "Failed to retrieve NYSDOH page after fallback/retries: "
                    "HTTP Error 404: Not Found"
                ),
            )
            for index in range(2551, 2601)
        ]
        payload = {
            "schema_version": "1.2",
            "generated_at": "2026-09-05T00:00:00Z",
            "domain": "NYS_LEAD_SERVICE_LINE_INVENTORY_DETAILS",
            "source": {
                "index_record_count": 2600,
                "parsed_detail_count": len(details),
                "explicit_unavailable_404_count": len(unavailable_details),
                "coverage_record_count": 2600,
                "coverage_complete": True,
            },
            "summary": {
                "index_count": 2600,
                "parsed_detail_count": len(details),
                "unavailable_detail_count": len(unavailable_details),
                "details_with_derived_identified_count": 0,
                "details_with_identified_reconciliation_mismatch_count": 0,
                "details_with_total_reconciliation_mismatch_count": 0,
                "details_with_form_contact": len(details),
                "source_reported_total_service_lines_sum": len(details) * 1000,
            },
            "details": details,
            "unavailable_details": unavailable_details,
        }

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
            json.dump(payload, handle)
            path = Path(handle.name)
        self.addCleanup(path.unlink, missing_ok=True)

        validated = validate_lsli_cache(path, max_age_days=2, require_production_volume=True)
        self.assertEqual(validated["source"]["explicit_unavailable_404_count"], 50)


if __name__ == "__main__":
    unittest.main()
