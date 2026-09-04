from __future__ import annotations

import unittest

from scripts.toronto_app_sources import normalize_source_link


class TorontoAuditIndexNormalizationTests(unittest.TestCase):
    def test_optional_resolved_row_has_exact_default_projection(self) -> None:
        source = "chemtrac_2024"
        row = {"_id": 42, "FACILITY_NAME": "Example", "FACILITY_ID": "F-1", "CHEMICAL_NAME": "Nickel", "FA_ADDRESS_GIVEN": "10 Example St"}
        link = {"source_key": source, "source_record_id": f"{source}:id:42", "source_row_index": 0, "match_basis": "EXACT", "source_address": "10 Example St"}
        rows = {source: [row]}
        self.assertEqual(normalize_source_link(link, rows), normalize_source_link(link, rows, row))


if __name__ == "__main__":
    unittest.main()
