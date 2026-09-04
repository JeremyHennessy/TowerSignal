from __future__ import annotations

import unittest

from scripts.build_toronto_app_data import build_unique_record_indexes, indexed_record_for_link
from scripts.toronto_app_sources import normalize_source_link


class TorontoAppBuilderIndexTests(unittest.TestCase):
    def test_unique_index_and_legacy_fallback_preserve_normalization(self) -> None:
        source = "chemtrac_2024"
        row = {"_id": 42, "FACILITY_NAME": "Example", "FACILITY_ID": "F-1", "CHEMICAL_NAME": "Nickel", "FA_ADDRESS_GIVEN": "10 Example St"}
        rows = {source: [row]}
        link = {"source_key": source, "source_record_id": f"{source}:id:42", "source_row_index": 0, "match_basis": "EXACT", "source_address": "10 Example St"}
        indexes = build_unique_record_indexes(rows)
        resolved = indexed_record_for_link(link, rows, indexes)
        self.assertIs(resolved, row)
        self.assertEqual(normalize_source_link(link, rows), normalize_source_link(link, rows, resolved))


if __name__ == "__main__":
    unittest.main()
