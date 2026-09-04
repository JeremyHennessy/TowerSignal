from __future__ import annotations

import unittest

from scripts.build_toronto_history import build_changes


def property_payload(*, sources=None, relationships=None, tower="NO_TOWER_ASSERTION", address="10 Bay St"):
    return {
        "property_id": "toronto-address-point:1",
        "address_point_id": "1",
        "display_address": address,
        "tower_evidence_status": tower,
        "source_links": sources or [],
        "relationships": relationships or [],
    }


class TorontoHistoryTests(unittest.TestCase):
    def test_detects_source_relationship_and_evidence_changes_without_inference(self):
        previous = {
            "generated_at": "2026-09-01T00:00:00Z",
            "properties": [property_payload()],
        }
        current = {
            "generated_at": "2026-09-04T00:00:00Z",
            "properties": [property_payload(
                tower="CONFIRMED_DOCUMENTARY_TOWER",
                sources=[{
                    "source_key": "toronto_building_permits_active_targeted",
                    "source_record_id": "permit:1",
                    "record_title": "Mechanical permit",
                    "record_status": "Permit Issued",
                    "record_date": "2026-09-03",
                }],
                relationships=[{
                    "relationship": "SUCCESSFUL_BIDDER_AT_PROPERTY",
                    "organization": "Example Mechanical Ltd.",
                    "source_key": "tobids_awarded_contracts",
                }],
            )],
        }
        result = build_changes(previous, current, "2026-09-04T12:00:00Z", "old", "new")
        types = {item["event_type"] for item in result["events"]}
        self.assertEqual(types, {"TOWER_EVIDENCE_CHANGED", "PERMIT_RECORD_ADDED", "RELATIONSHIP_ADDED"})
        permit = next(item for item in result["events"] if item["event_type"] == "PERMIT_RECORD_ADDED")
        self.assertEqual(permit["source_record_id"], "permit:1")
        self.assertEqual(permit["evidence_basis"], "PROPERTY_ID_EXACT_AND_STABLE_SOURCE_RECORD_ID")
        relationship = next(item for item in result["events"] if item["event_type"] == "RELATIONSHIP_ADDED")
        self.assertEqual(relationship["new_value"]["relationship"], "SUCCESSFUL_BIDDER_AT_PROPERTY")
        self.assertNotIn("contractor", str(relationship).lower())

    def test_first_seen_and_removed_are_release_presence_not_tower_claims(self):
        old_property = property_payload(address="1 Old St")
        old_property["property_id"] = "toronto-address-point:old"
        new_property = property_payload(address="2 New St")
        new_property["property_id"] = "toronto-address-point:new"
        result = build_changes(
            {"properties": [old_property]},
            {"properties": [new_property]},
            "2026-09-04T12:00:00Z",
            "old",
            "new",
        )
        types = {item["event_type"] for item in result["events"]}
        self.assertEqual(types, {"PROPERTY_FIRST_SEEN", "PROPERTY_NO_LONGER_PRESENT"})
        first_seen = next(item for item in result["events"] if item["event_type"] == "PROPERTY_FIRST_SEEN")
        self.assertEqual(first_seen["new_value"], {"present_in_release": True})
        self.assertNotIn("confirmed", str(first_seen["new_value"]).lower())

    def test_source_removal_uses_stable_record_identity(self):
        link = {
            "source_key": "chemtrac_history",
            "source_record_id": "chem:2024:1",
            "record_title": "Chemical report",
            "record_date": "2024-01-01",
        }
        result = build_changes(
            {"properties": [property_payload(sources=[link])]},
            {"properties": [property_payload()]},
            "2026-09-04T12:00:00Z",
            "old",
            "new",
        )
        self.assertEqual(result["event_count"], 1)
        self.assertEqual(result["events"][0]["event_type"], "CHEMTRAC_RECORD_REMOVED")
        self.assertEqual(result["events"][0]["source_record_id"], "chem:2024:1")


if __name__ == "__main__":
    unittest.main()
