from __future__ import annotations

import unittest

from scripts.towersignal.bbl_identity import apply_bbl_identity_recovery
from scripts.towersignal.normalize import normalize_registrations


class RegistryBinIdentityTests(unittest.TestCase):
    def registration(self, bin_value):
        return {
            "system_id": "2000014227",
            "bin": bin_value,
            "bbl": "1011710154",
            "number": "400",
            "street": "WEST 61ST STREET",
            "borough": "Manhattan",
            "zip": "10023",
            "activeequipment": "1",
            "sampledates": "",
        }

    def test_registry_numeric_bin_representations_have_one_canonical_identity(self):
        for value in ("1089723", "1089723.0", 1089723, 1089723.0, " 1089723.0 "):
            with self.subTest(source_bin=value):
                systems, _ = normalize_registrations([self.registration(value)])
                self.assertEqual(systems[0]["bin"], "1089723")

    def test_fractional_or_malformed_bin_is_not_rounded_or_guessed(self):
        for value in ("1089723.5", "1089723x", "1.089723e6", True, "", None):
            with self.subTest(source_bin=value):
                systems, _ = normalize_registrations([self.registration(value)])
                self.assertIsNone(systems[0]["bin"])

    def test_bin_normalization_does_not_change_other_registry_fields(self):
        canonical, canonical_meta = normalize_registrations([self.registration("1089723")])
        decimal, decimal_meta = normalize_registrations([self.registration("1089723.0")])
        self.assertEqual(decimal[0].pop("source_bin_raw"), "1089723.0")
        self.assertEqual(canonical[0].pop("source_bin_raw"), "1089723")
        self.assertEqual(decimal, canonical)
        self.assertEqual(decimal_meta, canonical_meta)

    def test_decimal_registry_bin_retains_exact_property_bridge_and_base_alias(self):
        systems, _ = normalize_registrations([self.registration("1089723.0")])
        footprints = {
            "1089723": [{"base_bbl": "1011710154", "mappluto_bbl": "1011717513"}],
        }
        metadata = apply_bbl_identity_recovery(systems, footprints)
        self.assertEqual(systems[0]["bin"], "1089723")
        self.assertEqual(systems[0]["registry_bbl"], "1011710154")
        self.assertEqual(systems[0]["property_bbl"], "1011717513")
        self.assertEqual(systems[0]["bbl_aliases"], ["1011710154", "1011717513"])
        self.assertEqual(metadata["reconciled_registry_bbl_count"], 1)
        self.assertEqual(
            systems[0]["bbl_identity_status"],
            "RECONCILED_REGISTRY_BASE_TO_MAPPLUTO_BBL",
        )


if __name__ == "__main__":
    unittest.main()
