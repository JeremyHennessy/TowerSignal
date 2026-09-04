from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MARKET = ROOT / "data/toronto/market/current"


class TorontoApartmentEvaluationRsnTests(unittest.TestCase):
    def test_persisted_recovery_contract(self) -> None:
        report = json.loads((MARKET / "apartment_evaluation_rsn_recovery_report.json").read_text(encoding="utf-8"))
        links = json.loads((MARKET / "property_source_links.json").read_text(encoding="utf-8"))
        graph = json.loads((MARKET / "entity_graph.json").read_text(encoding="utf-8"))
        spine = json.loads((MARKET / "property_spine.json").read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "PASSED")
        metrics = report["metrics"]
        self.assertEqual(metrics["source_records"], 6252)
        self.assertEqual(metrics["baseline_source_links"], 5288)
        self.assertEqual(metrics["linked_rsn_agreements"], 4509)
        self.assertEqual(metrics["linked_rsn_conflicts"], 0)
        self.assertEqual(metrics["rentsafe_ambiguous_rsn"], 0)
        self.assertEqual(metrics["recovered_rows"], 26)
        self.assertEqual(metrics["recovered_properties"], 14)
        self.assertEqual(metrics["final_source_links"], 5314)
        self.assertEqual(metrics["final_total_links"], 40086)
        self.assertEqual(metrics["remaining_unmatched_rows"], 938)
        self.assertEqual(metrics["property_spine_changes"], 0)
        self.assertEqual(metrics["relationship_edge_changes"], 0)
        self.assertEqual(metrics["tower_status_promotions"], 0)
        apartment_links = [item for item in links["links"] if item.get("source_key") == "apartment_building_evaluation"]
        self.assertEqual(len(apartment_links), 5314)
        recovered_ids = {item["source_record_id"] for item in report["recoveries"]}
        recovered_links = [item for item in apartment_links if item.get("source_record_id") in recovered_ids]
        self.assertEqual(len(recovered_links), 26)
        self.assertTrue(all(item.get("match_basis") == "EXACT_SHARED_RENTSAFE_RSN_TO_SOURCE_BACKED_CANONICAL_PROPERTY" for item in recovered_links))
        self.assertEqual(len(spine["properties"]), 13380)
        self.assertEqual(len(graph["edges"]), 6344)

    def test_recoveries_are_unique_rsn_backed_and_do_not_create_roles(self) -> None:
        report = json.loads((MARKET / "apartment_evaluation_rsn_recovery_report.json").read_text(encoding="utf-8"))
        graph = json.loads((MARKET / "entity_graph.json").read_text(encoding="utf-8"))
        recoveries = report["recoveries"]
        self.assertEqual(len({item["source_record_id"] for item in recoveries}), 26)
        self.assertTrue(all(item.get("rsn") for item in recoveries))
        self.assertFalse(any(edge.get("source_key") == "apartment_building_evaluation" for edge in graph["edges"]))


if __name__ == "__main__":
    unittest.main()
