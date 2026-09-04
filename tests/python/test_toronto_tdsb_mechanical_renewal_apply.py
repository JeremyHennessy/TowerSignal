from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MARKET = ROOT / "data/toronto/market/current"
SNAPSHOT = ROOT / "data/toronto/warehouse/current/open_licensed/tdsb_facility_condition_renewal.json"
REPORT = MARKET / "tdsb_mechanical_renewal_apply_report.json"
SOURCE = "tdsb_facility_condition_renewal"


@unittest.skipUnless(SNAPSHOT.exists() and REPORT.exists(), "TDSB mechanical renewal outputs are not persisted on this branch yet")
class TorontoTdsbMechanicalRenewalApplyTests(unittest.TestCase):
    def test_persisted_source_and_apply_counts(self) -> None:
        snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        links = json.loads((MARKET / "property_source_links.json").read_text(encoding="utf-8"))
        self.assertEqual(len(snapshot["rows"]), 826)
        self.assertEqual(report["metrics"]["linked_records"], 782)
        self.assertEqual(report["metrics"]["unlinked_records"], 44)
        self.assertEqual(report["metrics"]["matched_property_roots"], 330)
        self.assertEqual(report["metrics"]["new_properties"], 289)
        self.assertEqual(report["metrics"]["final_properties"], 13669)
        self.assertEqual(report["metrics"]["final_source_links"], 40841)
        self.assertEqual(len([x for x in links["links"] if x.get("source_key") == SOURCE]), 782)
        self.assertEqual((links["sources"][SOURCE])["matched_canonical_properties"], 330)

    def test_tdsb_does_not_create_relationships_or_tower_promotions(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        graph = json.loads((MARKET / "entity_graph.json").read_text(encoding="utf-8"))
        app = json.loads((ROOT / "public/data/toronto-market.json").read_text(encoding="utf-8"))
        self.assertEqual(report["metrics"]["relationship_edges_added"], 0)
        self.assertEqual(report["metrics"]["tower_status_promotions"], 0)
        self.assertEqual(len(graph["edges"]), 6343)
        self.assertFalse(any(x.get("source_key") == SOURCE for x in graph["edges"]))
        by_id = {x["property_id"]: x for x in app["properties"]}
        for pid in report["new_property_ids"]:
            self.assertEqual(by_id[pid]["tower_evidence_status"], "NO_TOWER_ASSERTION")
        snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        tower_pids = {x["property_id"] for x in snapshot["rows"] if x.get("property_id") and "cooling_tower" in (x.get("signals") or [])}
        self.assertEqual(len(tower_pids), 13)
        self.assertTrue(all(by_id[pid]["tower_evidence_status"] == "CONFIRMED_DOCUMENTARY_TOWER" for pid in tower_pids))

    def test_unresolved_tdsb_rows_remain_unlinked(self) -> None:
        snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        unresolved = [x for x in snapshot["rows"] if x.get("resolution_status") != "EXACT_LITERAL_TDSB_CIVIC_ADDRESS_TO_UNIQUE_CURRENT_ROOT"]
        self.assertEqual(len(unresolved), 44)
        self.assertTrue(all(x.get("property_id") is None for x in unresolved))
        self.assertTrue(all(x.get("address_point_id") is None for x in unresolved))


if __name__ == "__main__":
    unittest.main()
