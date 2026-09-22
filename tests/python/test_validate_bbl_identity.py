from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_bbl_identity import validate


class ValidateBblIdentityTests(unittest.TestCase):
    def _write(self, root: Path, row: dict, footprint: dict, metadata_count: int) -> None:
        root.mkdir(parents=True, exist_ok=True)
        detail_dir = root / "details" / "20"
        detail_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "metadata": {"bbl_reconciled_registry_base_to_mappluto_count": metadata_count},
            "systems": [row],
        }
        (root / "systems.json").write_text(json.dumps(payload))
        detail = {
            "identity": {
                "system_id": row["system_id"],
                "bbl": row.get("bbl"),
                "property_bbl": row.get("property_bbl"),
                "registry_bbl": row.get("registry_bbl"),
                "bbl_identity_evidence": {
                    "registry_base_bridge_confirmed": row.get("bbl_identity_status") == "RECONCILED_REGISTRY_BASE_TO_MAPPLUTO_BBL"
                },
            },
            "building_footprints": [footprint],
        }
        (detail_dir / f"{row['system_id']}.json").write_text(json.dumps(detail))

    def test_accepts_reconciled_exact_bin_registry_base_bridge(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write(
                root,
                {
                    "system_id": "2000014227",
                    "bbl": "1011717513",
                    "property_bbl": "1011717513",
                    "registry_bbl": "1011710154",
                    "bbl_identity_status": "RECONCILED_REGISTRY_BASE_TO_MAPPLUTO_BBL",
                },
                {"base_bbl": "1011710154", "mappluto_bbl": "1011717513"},
                1,
            )
            result = validate(root)
            self.assertEqual(result["exact_bin_registry_base_bridges"], 1)
            self.assertEqual(result["reconciled_registry_base_bridges"], 1)

    def test_rejects_ignored_exact_bin_registry_base_bridge(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write(
                root,
                {
                    "system_id": "2000014227",
                    "bbl": "1011710154",
                    "property_bbl": "1011710154",
                    "registry_bbl": "1011710154",
                    "bbl_identity_status": "REGISTRY_SOURCE_BBL",
                },
                {"base_bbl": "1011710154", "mappluto_bbl": "1011717513"},
                0,
            )
            with self.assertRaisesRegex(RuntimeError, "ignored exact-BIN"):
                validate(root)


if __name__ == "__main__":
    unittest.main()
