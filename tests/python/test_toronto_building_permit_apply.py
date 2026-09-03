from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MARKET = ROOT / "data/toronto/market/current"
WAREHOUSE = ROOT / "data/toronto/warehouse/current/open_licensed"
PERMIT_SOURCES = {
    "toronto_building_permits_active_targeted": ("toronto_building_permits_active_targeted.json", 573, 540),
    "toronto_building_permits_cleared_targeted_since_2017": ("toronto_building_permits_cleared_targeted_since_2017.json", 721, 704),
}


class TorontoBuildingPermitApplyTests(unittest.TestCase):
    def test_persisted_permit_apply_contract(self) -> None:
        report = json.loads((MARKET / "building_permit_apply_report.json").read_text(encoding="utf-8"))
        spine = json.loads((MARKET / "property_spine.json").read_text(encoding="utf-8"))
        links = json.loads((MARKET / "property_source_links.json").read_text(encoding="utf-8"))
        graph = json.loads((MARKET / "entity_graph.json").read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "PASSED")
        self.assertEqual(report["metrics"]["new_properties"], 306)
        self.assertEqual(report["metrics"]["final_properties"], 13371)
        self.assertEqual(report["metrics"]["new_source_links"], 1244)
        self.assertEqual(report["metrics"]["final_source_links"], 40012)
        self.assertEqual(report["metrics"]["unresolved_rows_not_forced"], 50)
        self.assertEqual(report["metrics"]["source_summary_entries"], 19)
        self.assertEqual(report["metrics"]["linked_source_families"], 16)
        self.assertEqual(len(spine["properties"]), 13371)
        new_ids = set(report["new_property_ids"])
        self.assertEqual(len(new_ids), 306)
        for prop in spine["properties"]:
            if prop.get("property_id") in new_ids:
                self.assertFalse(prop.get("is_original_poc_property"))
                self.assertEqual(prop.get("poc_tower_statuses") or [], [])
        permit_edges = [edge for edge in graph.get("edges", []) if edge.get("source_key") in PERMIT_SOURCES]
        self.assertEqual(permit_edges, [])
        self.assertEqual(len(graph.get("edges", [])), 6343)
        permit_links = [link for link in links.get("links", []) if link.get("source_key") in PERMIT_SOURCES]
        self.assertEqual(len(permit_links), 1244)

    def test_snapshots_and_link_counts_match(self) -> None:
        links = json.loads((MARKET / "property_source_links.json").read_text(encoding="utf-8"))
        for source, (filename, rows_expected, links_expected) in PERMIT_SOURCES.items():
            snapshot = json.loads((WAREHOUSE / filename).read_text(encoding="utf-8"))
            self.assertEqual(len(snapshot.get("rows", [])), rows_expected)
            self.assertEqual(sum(link.get("source_key") == source for link in links.get("links", [])), links_expected)


if __name__ == "__main__":
    unittest.main()
