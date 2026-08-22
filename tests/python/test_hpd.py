import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.hpd import bbl_parts, normalize_contact, parts_to_bbl


class HpdContactTests(unittest.TestCase):
    def test_bbl_round_trip_uses_exact_borough_block_lot_identity(self):
        self.assertEqual(bbl_parts("1001230045"), (1, 123, 45))
        self.assertEqual(parts_to_bbl("1", "123", "45"), "1001230045")
        self.assertIsNone(bbl_parts("not-a-bbl"))
        self.assertIsNone(parts_to_bbl("9", "123", "45"))

    def test_contact_normalization_preserves_role_and_business_identity(self):
        contact = normalize_contact({
            "registrationcontactid": "777",
            "type": "Managing Agent",
            "contactdescription": "Agent",
            "corporationname": "Example Management LLC",
            "title": "Property Manager",
            "firstname": "Ada",
            "middleinitial": "L",
            "lastname": "Manager",
            "businesshousenumber": "10",
            "businessstreetname": "MAIN ST",
            "businessapartment": "STE 4",
            "businesscity": "NEW YORK",
            "businessstate": "NY",
            "businesszip": "10001",
        })
        self.assertEqual(contact["type"], "Managing Agent")
        self.assertEqual(contact["corporation_name"], "Example Management LLC")
        self.assertEqual(contact["person_name"], "Ada L Manager")
        self.assertEqual(contact["title"], "Property Manager")
        self.assertEqual(contact["business_address"], "10 MAIN ST, STE 4, NEW YORK, NY 10001")
        self.assertEqual(contact["source"], "NYC_HPD_REGISTRATION_CONTACTS")


if __name__ == "__main__":
    unittest.main()
