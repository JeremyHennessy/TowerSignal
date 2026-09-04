from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MARKET = ROOT / "data/toronto/market/current"
PERMIT_SOURCES = {
    "toronto_building_permits_active_targeted",
    "toronto_building_permits_cleared_targeted_since_2017",
}


class TorontoBuildingPermitRecoveryTests(unittest.TestCase):
    def test_recovery_counts_and_quarantine(self) -> None:
        report = json.loads((MARKET / "building_permit_recovery_report.json").read_text(encoding="utf-8"))
        strict = json.loads((MARKET / "building_permit_apply_report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "PASSED")
        self.assertEqual(report["strict_baseline_sha"], "101c6808b22bb5ce69a16697f97df95424ad0e2c")
        self.assertEqual(strict["metrics"]["final_properties"], 13371)
        self.assertEqual(strict["metrics"]["final_source_links"], 40012)
        self.assertEqual(report["metrics"]["recovered_rows"], 47)
        self.assertEqual(report["metrics"]["new_properties"], 9)
        self.assertEqual(report["metrics"]["remaining_unresolved_rows"], 3)
        self.assertEqual(report["metrics"]["final_properties"], 13380)
        self.assertEqual(report["metrics"]["final_source_links"], 40059)
        self.assertEqual(report["metrics"]["final_permit_links"], 1291)
        self.assertEqual(report["metrics"]["final_permit_linked_properties"], 700)
        self.assertEqual(report["metrics"]["relationship_edges_before_and_after"], 6343)
        self.assertEqual(report["metrics"]["linked_source_families"], 16)
        self.assertEqual(len(report["remaining_unresolved"]), 3)
        remaining = {(item["source_key"], item["permit_identity"]) for item in report["remaining_unresolved"]}
        self.assertEqual(remaining, {
            ("toronto_building_permits_active_targeted", "12 148282 BLD::00"),
            ("toronto_building_permits_cleared_targeted_since_2017", "17 139058 MSA::00"),
            ("toronto_building_permits_cleared_targeted_since_2017", "16 146056 MSA::00"),
        })

    def test_new_properties_do_not_gain_tower_or_relationship_assertions(self) -> None:
        report = json.loads((MARKET / "building_permit_recovery_report.json").read_text(encoding="utf-8"))
        spine = json.loads((MARKET / "property_spine.json").read_text(encoding="utf-8"))
        graph = json.loads((MARKET / "entity_graph.json").read_text(encoding="utf-8"))
        new_ids = set(report["new_property_ids"])
        self.assertEqual(len(new_ids), 9)
        by_id = {prop["property_id"]: prop for prop in spine["properties"]}
        for property_id in new_ids:
            prop = by_id[property_id]
            self.assertFalse(prop["is_original_poc_property"])
            self.assertEqual(prop.get("poc_property_keys") or [], [])
            self.assertEqual(prop.get("poc_tower_statuses") or [], [])
            self.assertEqual(prop["identity_confidence"], "DETERMINISTIC")
            self.assertEqual(prop["identity_basis"], "TARGETED_BUILDING_PERMIT_DETERMINISTIC_RECOVERY_TO_CURRENT_ADDRESS_POINT_ROOT")
        permit_edges = [edge for edge in graph.get("edges", []) if edge.get("source_key") in PERMIT_SOURCES]
        self.assertEqual(permit_edges, [])
        new_property_edges = [edge for edge in graph.get("edges", []) if edge.get("property_id") in new_ids]
        self.assertEqual(new_property_edges, [])
        self.assertEqual(len(graph.get("edges", [])), 6344)

    def test_recovery_links_are_exactly_the_manifest_rows(self) -> None:
        report = json.loads((MARKET / "building_permit_recovery_report.json").read_text(encoding="utf-8"))
        manifest = json.loads((MARKET / "building_permit_recovery_manifest.json").read_text(encoding="utf-8"))
        links = json.loads((MARKET / "property_source_links.json").read_text(encoding="utf-8"))
        expected = {(row[0], row[1], row[2], row[3]) for row in manifest["recoveries"]}
        recovered = {
            (item["source_key"], item["permit_identity"], item["address_point_id"], item["recovery_basis"])
            for item in report["recovered_records"]
        }
        self.assertEqual(recovered, expected)
        report_record_ids = {(item["source_key"], item["source_record_id"]) for item in report["recovered_records"]}
        actual_links = {(item["source_key"], item["source_record_id"]) for item in links["links"]}
        self.assertTrue(report_record_ids.issubset(actual_links))
        self.assertEqual(sum(item.get("source_key") in PERMIT_SOURCES for item in links["links"]), 1291)


if __name__ == "__main__":
    unittest.main()
