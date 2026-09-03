import unittest

from scripts.toronto_source_identity import find_source_record, stable_source_record_id


class TorontoSourceIdentityRegressionTests(unittest.TestCase):
    def test_business_licence_identity_uses_nested_publisher_row(self) -> None:
        source = "business_licence_matches_prior_poc"
        source_row = {
            "_id": "82",
            "Licence No.": "B03-4304369",
            "Licence Address Line 1": "40 WYNFORD DR, #106",
            "Operating Name": "MAPLE LEAF TAXI-CAB",
        }
        wrapper = {
            "canonical_address": "40 WYNFORD DR",
            "property_keys": ["toronto-geoid:10142946"],
            "tower_statuses": ["NO_TOWER_ASSERTION"],
            "source_row": source_row,
        }

        record_id = stable_source_record_id(source, wrapper)
        self.assertEqual(record_id, f"{source}:id:82")
        self.assertIs(find_source_record(source, record_id, [source_row]), source_row)

    def test_renewable_identity_does_not_cross_match_other_id_fields(self) -> None:
        source = "renewable_energy_installations"
        first = {
            "_id": 7,
            "ID": 86,
            "OBJECTID": 86,
            "CLIENT_ADDRESS": "45 Ancaster Rd",
        }
        second = {
            "_id": 86,
            "ID": 7,
            "OBJECTID": 7,
            "CLIENT_ADDRESS": "Different Address",
        }
        rows = [first, second]

        record_id = stable_source_record_id(source, second)
        self.assertEqual(record_id, f"{source}:id:86")
        self.assertIs(find_source_record(source, record_id, rows), second)

    def test_fingerprint_identity_still_round_trips_without_publisher_id(self) -> None:
        source = "example_source"
        row = {"name": "Alpha", "address": "10 Example St"}
        record_id = stable_source_record_id(source, row)
        self.assertTrue(record_id.startswith(f"{source}:sha256:"))
        self.assertIs(find_source_record(source, record_id, [row]), row)


if __name__ == "__main__":
    unittest.main()
