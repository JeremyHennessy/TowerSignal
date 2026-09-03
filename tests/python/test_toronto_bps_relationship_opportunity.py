import json
import unittest
from collections import defaultdict
from pathlib import Path

from scripts.toronto_final_identity_cleanup import canonical_address

ROOT = Path(__file__).resolve().parents[2]
BPS = ROOT / "data/toronto/warehouse/current/open_licensed/ontario_bps_energy_2024.json"
SPINE = ROOT / "data/toronto/market/current/property_spine.json"


class TorontoBpsRelationshipOpportunityTests(unittest.TestCase):
    def test_persisted_bps_has_deterministic_relationship_opportunity(self) -> None:
        payload = json.loads(BPS.read_text(encoding="utf-8"))
        rows = [row for row in payload.get("toronto_candidates", []) if isinstance(row, dict)]
        metadata = payload.get("metadata") or {}
        self.assertEqual(int(metadata.get("toronto_candidate_row_count") or 0), len(rows))
        self.assertGreater(len(rows), 0)

        spine = json.loads(SPINE.read_text(encoding="utf-8"))
        by_address = defaultdict(list)
        for prop in spine.get("properties", []):
            if not isinstance(prop, dict):
                continue
            for address in [prop.get("canonical_address"), *(prop.get("address_aliases") or [])]:
                canon = canonical_address(address)
                if canon:
                    by_address[canon].append(prop)

        matched_rows = 0
        matched_properties = set()
        organizations = set()
        ambiguous_rows = 0
        rows_with_address = 0
        rows_with_organization = 0
        for row in rows:
            address = canonical_address(row.get("Address"))
            organization = str(row.get("Organization") or "").strip()
            if address:
                rows_with_address += 1
            if organization:
                rows_with_organization += 1
            matches = by_address.get(address, []) if address else []
            unique_ids = {str(item.get("property_id") or "") for item in matches if item.get("property_id")}
            if len(unique_ids) > 1:
                ambiguous_rows += 1
                continue
            if len(unique_ids) != 1:
                continue
            matched_rows += 1
            matched_properties.update(unique_ids)
            if organization:
                organizations.add(organization)

        metrics = {
            "source_rows": len(rows),
            "rows_with_address": rows_with_address,
            "rows_with_organization": rows_with_organization,
            "exact_unique_address_matched_rows": matched_rows,
            "exact_unique_address_matched_properties": len(matched_properties),
            "distinct_organizations_on_matches": len(organizations),
            "ambiguous_address_rows_not_forced": ambiguous_rows,
        }
        print("TORONTO_BPS_RELATIONSHIP_OPPORTUNITY=" + json.dumps(metrics, sort_keys=True))

        self.assertEqual(rows_with_address, len(rows))
        self.assertEqual(rows_with_organization, len(rows))
        self.assertGreater(matched_rows, 0)
        self.assertGreater(len(matched_properties), 0)
        self.assertGreater(len(organizations), 0)


if __name__ == "__main__":
    unittest.main()
