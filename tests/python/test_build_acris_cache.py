import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import build_acris_cache  # noqa: E402


class BuildAcrisCacheTests(unittest.TestCase):
    def test_current_registry_defines_cache_bbl_universe(self):
        systems = [
            {"system_id": f"CT-{index}", "bbl": str(1_000_000_000 + (index % 1500))}
            for index in range(4000)
        ]
        with (
            patch.object(
                build_acris_cache,
                "fetch_dataset",
                return_value=SimpleNamespace(rows=[{"system_id": "source-row"}]),
            ) as fetch,
            patch.object(build_acris_cache, "normalize_registrations", return_value=(systems, {})) as normalize,
        ):
            bbls = build_acris_cache.tower_bbls_from_current_registrations()

        fetch.assert_called_once_with(build_acris_cache.REGISTRATION_DATASET_ID, "system_id")
        normalize.assert_called_once_with([{"system_id": "source-row"}])
        self.assertEqual(len(bbls), 1500)
        self.assertIn("1000000000", bbls)

    def test_current_registry_rejects_implausibly_small_normalized_snapshot(self):
        with (
            patch.object(build_acris_cache, "fetch_dataset", return_value=SimpleNamespace(rows=[])),
            patch.object(build_acris_cache, "normalize_registrations", return_value=([], {})),
        ):
            with self.assertRaisesRegex(RuntimeError, "normalized current systems"):
                build_acris_cache.tower_bbls_from_current_registrations()


if __name__ == "__main__":
    unittest.main()
