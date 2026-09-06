from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_nycha_water_cache import validate  # noqa: E402


class ValidateNychaWaterCacheTests(unittest.TestCase):
    def test_zero_count_partition_is_valid_when_fetched_count_is_zero(self) -> None:
        payload = {
            "schema_version": "1.0",
            "domain": "NYCHA_WATER_CONTRACT_RELEASE_LINES",
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "summary": {
                "fiscal_year_count": 1,
                "purpose_query_term_count": 2,
                "source_record_count": 1,
                "relevant_release_line_count": 0,
                "relevant_contract_count": 0,
                "relevant_vendor_count": 0,
                "relevant_location_count": 0,
            },
            "source_health": [
                {
                    "source": "NYC_CHECKBOOK_NYCHA",
                    "fiscal_year": 2026,
                    "purpose_query": "water",
                    "status": "HEALTHY",
                    "source_record_count": 1,
                    "fetched_record_count": 1,
                    "pagination_complete": True,
                    "schema_valid": True,
                },
                {
                    "source": "NYC_CHECKBOOK_NYCHA",
                    "fiscal_year": 2026,
                    "purpose_query": "chlorination",
                    "status": "HEALTHY",
                    "source_record_count": 0,
                    "fetched_record_count": 0,
                    "pagination_complete": True,
                    "schema_valid": True,
                },
            ],
            "records": [],
        }
        handle = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
        with handle:
            json.dump(payload, handle)
        self.addCleanup(Path(handle.name).unlink, missing_ok=True)
        result = validate(Path(handle.name), max_age_days=1, require_production_volume=False)
        self.assertEqual(result["summary"]["source_record_count"], 1)


if __name__ == "__main__":
    unittest.main()
