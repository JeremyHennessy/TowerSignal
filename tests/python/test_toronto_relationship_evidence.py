import unittest

from scripts.build_toronto_app_data import normalize_relationship_evidence


class TorontoRelationshipEvidenceTests(unittest.TestCase):
    def test_projects_scalar_and_list_evidence_without_nested_inference(self) -> None:
        details = normalize_relationship_evidence({
            "evidence": {
                "document_number": "4951580548",
                "award": "12345.00",
                "facility_ids": ["A", "B"],
                "source_observation_count": 4,
                "nested": {"do_not": "project"},
                "empty": "",
            }
        })
        self.assertIn({"label": "Document number", "value": "4951580548"}, details)
        self.assertIn({"label": "Award", "value": "12345.00"}, details)
        self.assertIn({"label": "Facility IDs", "value": "A, B"}, details)
        self.assertIn({"label": "Source observations", "value": "4"}, details)
        self.assertFalse(any(item["label"] == "Nested" for item in details))

    def test_missing_evidence_is_an_empty_list(self) -> None:
        self.assertEqual(normalize_relationship_evidence({}), [])


if __name__ == "__main__":
    unittest.main()
