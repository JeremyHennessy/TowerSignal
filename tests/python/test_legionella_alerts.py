import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.legionella_alerts import _PageParser, _canonical_url, _published_date, _relevant


class LegionellaAlertTests(unittest.TestCase):
    def test_parser_discovers_legionella_link_and_page_title(self):
        parser = _PageParser()
        parser.feed("""
        <html><head><title>Health Alert Network</title></head><body>
        <a href='/alert26.pdf'>Alert #26: Cluster of Legionnaires' Disease in the South Bronx</a>
        <a href='/unrelated'>Unrelated alert</a>
        </body></html>
        """)
        parsed = parser.parsed()
        self.assertEqual(parsed.title, "Health Alert Network")
        self.assertEqual(len(parsed.links), 2)
        self.assertTrue(_relevant(parsed.links[0][1]))
        self.assertFalse(_relevant(parsed.links[1][1]))

    def test_date_and_url_normalization_are_deterministic(self):
        self.assertEqual(_published_date("September 13, 2026 — Health Department update"), "2026-09-13")
        self.assertEqual(_canonical_url("http://WWW.NYC.GOV/path#fragment"), "https://www.nyc.gov/path")


if __name__ == "__main__":
    unittest.main()
