import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from build_acris_cache import tower_bbls_from_current_registrations


class AcrisCacheBuilderTests(unittest.TestCase):
    def test_current_cache_universe_uses_canonical_bbl_recovery(self):
        systems = [
            {
                "system_id": f"SYS-{index}",
                "bbl": f"1{index:05d}0001",
                "bin": f"{index:07d}",
                "borough": "Manhattan",
            }
            for index in range(1, 3499)
        ]
        systems.extend([
            {
                "system_id": "SYS-RECOVERED",
                "bbl": None,
                "bin": "9000001",
                "borough": "Brooklyn",
            },
            {
                "system_id": "SYS-AMBIGUOUS",
                "bbl": None,
                "bin": "9000002",
                "borough": "Queens",
            },
        ])

        footprints = {
            "9000001": [{"mappluto_bbl": "3000010001"}],
            "9000002": [
                {"mappluto_bbl": "4000010001"},
                {"mappluto_bbl": "4000010002"},
            ],
        }

        with patch("build_acris_cache.fetch_dataset", return_value=SimpleNamespace(rows=[{"source": "fixture"}])), \
             patch("build_acris_cache.normalize_registrations", return_value=(systems, {})), \
             patch("build_acris_cache.fetch_building_footprints_by_bin", return_value=(footprints, {"fixture": True})) as footprint_fetch:
            bbls = tower_bbls_from_current_registrations()

        self.assertIn("3000010001", bbls)
        self.assertNotIn("4000010001", bbls)
        self.assertNotIn("4000010002", bbls)
        self.assertEqual(len(bbls), 3499)
        self.assertEqual(systems[-2]["bbl_identity_status"], "RECOVERED_EXACT_BIN_MAPPLUTO_BBL")
        self.assertEqual(systems[-1]["bbl_identity_status"], "UNRESOLVED_MULTIPLE_MAPPLUTO_BBLS")
        footprint_fetch.assert_called_once()
        requested_bins = footprint_fetch.call_args.args[0]
        self.assertIn("9000001", requested_bins)
        self.assertIn("9000002", requested_bins)


if __name__ == "__main__":
    unittest.main()
