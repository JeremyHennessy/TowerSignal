from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_property_identity_acceptance import validate


class PropertyIdentityAcceptanceTests(unittest.TestCase):
    def _write(self, root: Path, *, acris: bool = True, contacts: bool = True) -> None:
        row = {
            "system_id": "2000014227",
            "bin": "1089723",
            "bbl": "1011717513",
            "property_bbl": "1011717513",
            "registry_bbl": "1011710154",
            "bbl_aliases": ["1011710154", "1011717513"],
            "bbl_identity_status": "RECONCILED_REGISTRY_BASE_TO_MAPPLUTO_BBL",
            "bbl_identity_basis": "REGISTRY_BASE_BBL_TO_MAPPLUTO_BBL_EXACT_BIN",
        }
        payload = {
            "metadata": {"bbl_reconciled_registry_base_to_mappluto_count": 1},
            "systems": [row],
        }
        (root / "systems.json").write_text(json.dumps(payload))
        detail_dir = root / "details" / "20"
        detail_dir.mkdir(parents=True)
        detail = {
            "identity": {
                **row,
                "bbl_identity_evidence": {
                    "registry_base_bridge_confirmed": True,
                    "address_matching_used": False,
                    "fuzzy_matching_used": False,
                },
            },
            "building_context": {"bbl": "1011717513", "owner_name": "OWNER LLC"},
            "hpd_registration": {
                "registration_id": "REG1",
                "contacts": [{"type": "Agent"}] if contacts else [],
            },
            "building_footprints": [{
                "base_bbl": "1011710154",
                "mappluto_bbl": "1011717513",
            }],
            "acris_activity": {
                "recent_document_count": 3,
                "displayed_document_count": 3,
                "documents": [{
                    "document_id": "D1",
                    "match_basis": "CONDO_BILLING_BBL_BLOCK_ADDRESS_EXACT",
                }],
            } if acris else None,
        }
        (detail_dir / "2000014227.json").write_text(json.dumps(detail))

    def test_accepts_complete_reconciled_account(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write(root)
            result = validate(root, require_acris=True)
            self.assertEqual(result["property_bbl"], "1011717513")
            self.assertEqual(result["hpd_contact_count"], 1)
            self.assertEqual(result["acris_recent_document_count"], 3)

    def test_rejects_missing_hpd_contacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write(root, contacts=False)
            with self.assertRaisesRegex(RuntimeError, "lacks HPD contacts"):
                validate(root)

    def test_rejects_missing_acris_when_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write(root, acris=False)
            with self.assertRaisesRegex(RuntimeError, "lacks recent ACRIS activity"):
                validate(root, require_acris=True)


if __name__ == "__main__":
    unittest.main()
