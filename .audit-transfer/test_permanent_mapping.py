import unittest
from scripts.towersignal.planimetrics import normalize_bin
from scripts.towersignal.normalize import normalize_registrations
from scripts.towersignal.bbl_identity import resolve_system_bbl_identity
from scripts.towersignal.hpd_identity import index_registrations, assemble_contacts, positive_id
from scripts.towersignal.inspections import aggregate_inspections
from scripts.towersignal.pluto import normalize_pluto_record


class PermanentMappingTests(unittest.TestCase):
    def system(self, **kw):
        return {"system_id": "2000000001", "bin": "1089723", "borough": "Manhattan", "bbl": "1011717513", "bbl_aliases": ["1011710154", "1011717513"], **kw}

    def registration(self, **kw):
        return {"registrationid": "123", "buildingid": "456", "bin": "1089723", "boroid": "1", "block": "1171", "lot": "7513", "lastregistrationdate": "2026-08-01T00:00:00", **kw}

    def contacts(self, system, registrations, rows):
        return assemble_contacts([system], index_registrations(registrations), rows)[system["system_id"]]

    def test_all_borough_placeholders_are_not_buildings(self):
        for b in "12345":
            for value in [b+"000000", b+"000000.0", int(b+"000000")]:
                self.assertIsNone(normalize_bin(value))

    def test_assigned_decimal_identifier_is_preserved(self):
        for value in ["1089723", "1089723.0", "1089723.000", 1089723]:
            self.assertEqual(normalize_bin(value), "1089723")

    def test_malformed_identifiers_are_not_guessed(self):
        for value in ["1089723.5", "1089723x", "1.089723e6", "9999999", True, None, "123"]:
            self.assertIsNone(normalize_bin(value))

    def test_sampling_is_independent_of_property_identifier(self):
        rows, _ = normalize_registrations([{"system_id": "S", "bin": "1000000", "sampledates": "09/01/2026", "activeequipment": "1"}])
        self.assertIsNone(rows[0]["bin"])
        self.assertEqual(rows[0]["source_bin_raw"], "1000000")
        self.assertEqual(rows[0]["sample_dates"], ["2026-09-01"])

    def test_unknown_bin_does_not_join_unrelated_footprints(self):
        result = resolve_system_bbl_identity(self.system(bin="1000000", bbl=None), [{"bin": "1000000", "mappluto_bbl": "1000010001"}])
        self.assertIsNone(result["canonical_bbl"])

    def test_wrong_building_footprint_does_not_create_alias(self):
        result = resolve_system_bbl_identity(self.system(), [{"bin": "1089999", "mappluto_bbl": "1011717513", "base_bbl": "1011710020"}])
        self.assertNotIn("1011710020", result["bbl_aliases"])

    def test_unique_same_block_base_alias_is_preserved(self):
        result = resolve_system_bbl_identity(self.system(), [{"bin": "1089723", "mappluto_bbl": "1011717513", "base_bbl": "1011710154"}])
        self.assertEqual(result["bbl_aliases"], ["1011710154", "1011717513"])

    def test_cross_block_base_lot_is_not_added(self):
        result = resolve_system_bbl_identity(self.system(), [{"bin": "1089723", "mappluto_bbl": "1011717513", "base_bbl": "1011720154"}])
        self.assertNotIn("1011720154", result["bbl_aliases"])

    def test_correlated_sources_resolve_conflict_without_reusing_bad_registry_lot(self):
        result = resolve_system_bbl_identity(self.system(bbl="1011700030"), [{"bin": "1089723", "mappluto_bbl": "1011717513", "base_bbl": "1011710154"}], [self.registration()])
        self.assertEqual(result["canonical_bbl"], "1011717513")
        self.assertEqual(result["registry_bbl"], "1011700030")
        self.assertNotIn("1011700030", result["bbl_aliases"])

    def test_hpd_recovers_missing_property_by_assigned_bin_only(self):
        result = resolve_system_bbl_identity(self.system(bbl=None), [], [self.registration()])
        self.assertEqual(result["canonical_bbl"], "1011717513")
        self.assertFalse(result["address_matching_used"])

    def test_registration_zero_contacts_are_quarantined(self):
        result = self.contacts(self.system(), [self.registration(registrationid="0")], [{"registrationid": "0", "firstname": "Wrong", "lastname": "Contact"}])
        self.assertEqual(result["status"], "UNUSABLE_SOURCE_REGISTRATION_ID")
        self.assertEqual(result["registration"]["contacts"], [])

    def test_colliding_registration_id_is_not_contact_evidence(self):
        registrations = [self.registration(), self.registration(bin="1089999", buildingid="789", block="1180")]
        result = self.contacts(self.system(), registrations, [{"registrationid": "123", "firstname": "Contact"}])
        self.assertEqual(result["status"], "COLLIDING_SOURCE_REGISTRATION_ID")
        self.assertEqual(result["registration"]["contacts"], [])

    def test_exact_building_contact_preserves_source_property(self):
        result = self.contacts(self.system(), [self.registration(lot="154")], [{"registrationid": "123", "firstname": "Public", "lastname": "Agent"}])
        self.assertEqual(result["status"], "MATCHED")
        self.assertEqual(result["registration"]["match_basis"], "BIN_EXACT")
        self.assertEqual(result["registration"]["source_bbl"], "1011710154")

    def test_ambiguous_building_property_does_not_choose_arbitrarily(self):
        result = self.contacts(self.system(), [self.registration(), self.registration(registrationid="124", lot="100")], [])
        self.assertEqual(result["status"], "AMBIGUOUS_HPD_BUILDING_PROPERTY")
        self.assertIsNone(result["registration"])

    def test_current_empty_registration_does_not_fall_back_to_old_contacts(self):
        result = self.contacts(self.system(), [self.registration(registrationid="122", lastregistrationdate="2020-01-01"), self.registration()], [{"registrationid": "122", "firstname": "Former", "lastname": "Agent"}])
        self.assertEqual(result["status"], "VERIFIED_EMPTY_CONTACTS")
        self.assertEqual(result["registration"]["registration_id"], "123")

    def test_parcel_contact_is_not_claimed_as_building_contact(self):
        result = self.contacts(self.system(bin="1088888"), [self.registration()], [{"registrationid": "123", "firstname": "Agent"}])
        self.assertEqual(result["registration"]["match_basis"], "BBL_PARCEL_EXACT")
        self.assertEqual(result["registration"]["source_bin"], "1089723")

    def test_positive_registration_ids_only(self):
        for value in [0, "0", "-1", "abc", "1.5", True, None]:
            self.assertIsNone(positive_id(value))
        self.assertEqual(positive_id("00123"), "123")

    def test_owner_placeholder_is_not_a_company(self):
        result = normalize_pluto_record({"ownername": "UNAVAILABLE OWNER"})
        self.assertIsNone(result["owner_name"])
        self.assertEqual(result["source_owner_name_raw"], "UNAVAILABLE OWNER")

    def test_inspection_conflicts_are_order_independent_and_visible(self):
        rows = [{"system_id": "S", "inspection_date": "2026-09-01", "inspection_type": "Routine", "status": "A", "active_equip": "2", "violation_code": "Z"}, {"system_id": "S", "inspection_date": "2026-09-01", "inspection_type": "Routine", "status": "B", "active_equip": "3", "violation_code": "A"}]
        result = aggregate_inspections(rows)
        self.assertEqual(result, aggregate_inspections(list(reversed(rows))))
        self.assertEqual(result["S"][0]["status"], "SOURCE_CONFLICT")
        self.assertEqual(result["S"][0]["violation_count"], 2)
        self.assertIsNone(result["S"][0]["active_equipment_at_publication"])


if __name__ == "__main__":
    unittest.main()
