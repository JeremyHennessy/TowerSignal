import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from build_acris_cache import tower_bbls_from_current_registrations


class AcrisCacheBuilderTests(unittest.TestCase):
    def test_integration_budget_allows_bounded_source_steps_and_validation(self):
        workflow = (ROOT / ".github/workflows/acris-cache.yml").read_text(encoding="utf-8")
        integration = workflow.split("\n  integration:\n", 1)[1].split("\n  persist-cache:\n", 1)[0]
        job_budget = int(re.search(r"^    timeout-minutes: (\d+)$", integration, re.MULTILINE).group(1))
        source_budgets = [int(value) for value in re.findall(r"^        timeout-minutes: (\d+)$", integration, re.MULTILINE)]
        self.assertEqual(source_budgets, [45, 15])
        self.assertGreaterEqual(job_budget, sum(source_budgets) + 15)
        self.assertNotIn("continue-on-error", integration)
        self.assertIn("Require canonical ACRIS cache universe alignment", integration)

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
