import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.legionella_alerts import (
    _PageParser,
    _canonical_url,
    _discovery_relevant,
    _parse_notify_notifications,
    _published_date,
    _relevant,
)


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
        self.assertTrue(_discovery_relevant(parsed.links[0][1]))
        self.assertFalse(_relevant(parsed.links[1][1]))
        self.assertFalse(_discovery_relevant(parsed.links[1][1]))

    def test_generic_cooling_tower_form_is_not_alert_discovery(self):
        generic_form = "Cooling Tower Certification Form https://www.health.ny.gov/forms/cooling_tower_certification_form.docx"
        self.assertTrue(_relevant(generic_form))
        self.assertFalse(_discovery_relevant(generic_form))
        self.assertTrue(_discovery_relevant("Legionella Cluster Health Alert"))

    def test_legacy_official_aliases_canonicalize_to_current_pages(self):
        self.assertEqual(
            _canonical_url("https://health.ny.gov/diseases/communicable/legionellosis.htm"),
            "https://www.health.ny.gov/diseases/communicable/legionellosis/",
        )
        self.assertEqual(
            _canonical_url("https://portal.311.nyc.gov/article/KA-02845"),
            "https://portal.311.nyc.gov/article/?kanumber=KA-02845",
        )
        self.assertEqual(
            _canonical_url("https://portal.311.nyc.gov/article/KA-02664"),
            "https://portal.311.nyc.gov/article/?kanumber=KA-02664",
        )

    def test_notify_nyc_recent_notifications_preserve_local_calendar_date(self):
        text = """
        Recent Notifications
        09/10/2026 20:31:10
        Notify NYC - Legionnaires' Disease Cluster (BX)
        Notification issued 09-10-2026 at 08:31 PM. There is a Legionnaires' disease cluster in the Bronx.
        09/10/2026 19:50:37
        Notify NYC - MTA Disruption - B, D, M, F, N, W, R, Q (BK/MN)
        Notification issued 09-10-2026 at 07:50 PM. Due to an NYPD investigation, expect delays.
        The information you want to receive, the way you want to receive it
        """
        notifications = _parse_notify_notifications(text)
        self.assertEqual(len(notifications), 2)
        self.assertEqual(notifications[0]["title"], "Notify NYC - Legionnaires' Disease Cluster (BX)")
        self.assertEqual(notifications[0]["published_date"], "2026-09-10")
        self.assertTrue(_relevant(f"{notifications[0]['title']} {notifications[0]['body']}"))
        self.assertFalse(_relevant(f"{notifications[1]['title']} {notifications[1]['body']}"))

    def test_date_and_url_normalization_are_deterministic(self):
        self.assertEqual(_published_date("September 13, 2026 — Health Department update"), "2026-09-13")
        self.assertEqual(_canonical_url("http://WWW.NYC.GOV/path#fragment"), "https://www.nyc.gov/path")


if __name__ == "__main__":
    unittest.main()
