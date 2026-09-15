import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from build_legionella_alert_cache import merge_previous


class LegionellaAlertHistoryTests(unittest.TestCase):
    def test_previous_alert_is_retained_and_current_record_wins_on_same_item_id(self):
        previous = {
            "domain": "LEGIONELLA_PUBLIC_HEALTH_ALERTS",
            "generated_at": "2026-09-10T22:00:00Z",
            "items": [
                {
                    "item_id": "notify-old",
                    "agency": "NYC Emergency Management",
                    "channel_key": "NYC_NOTIFY_NYC",
                    "title": "Notify NYC - Legionnaires' Disease Cluster (BX)",
                    "published_date": "2026-09-10",
                    "retrieved_at": "2026-09-10T22:00:00Z",
                },
                {
                    "item_id": "same-page",
                    "agency": "NYC Health Department",
                    "channel_key": "NYC_DOH_PRESS_RELEASES",
                    "title": "Earlier title",
                    "published_date": "2026-09-10",
                    "retrieved_at": "2026-09-10T22:00:00Z",
                },
            ],
        }
        current = {
            "domain": "LEGIONELLA_PUBLIC_HEALTH_ALERTS",
            "generated_at": "2026-09-15T15:00:00Z",
            "source_channels": [{"channel_key": "NYC_DOH_PRESS_RELEASES"}],
            "errors": [],
            "items": [
                {
                    "item_id": "same-page",
                    "agency": "NYC Health Department",
                    "channel_key": "NYC_DOH_PRESS_RELEASES",
                    "title": "Current title",
                    "published_date": "2026-09-10",
                    "retrieved_at": "2026-09-15T15:00:00Z",
                },
                {
                    "item_id": "new-page",
                    "agency": "NYC311",
                    "channel_key": "NYC_311_LEGIONNAIRES",
                    "title": "Legionnaires' Disease",
                    "published_date": "2026-09-15",
                    "retrieved_at": "2026-09-15T15:00:00Z",
                },
            ],
        }

        merged = merge_previous(current, previous)
        by_id = {item["item_id"]: item for item in merged["items"]}

        self.assertEqual(set(by_id), {"notify-old", "same-page", "new-page"})
        self.assertEqual(by_id["same-page"]["title"], "Current title")
        self.assertEqual(merged["history_merge"]["retained_prior_item_count"], 1)
        self.assertEqual(merged["history_merge"]["refreshed_existing_item_count"], 1)
        self.assertEqual(merged["history_merge"]["new_item_count"], 1)
        self.assertEqual(merged["history_merge"]["merged_item_count"], 3)
        self.assertEqual(merged["summary"]["discovered_relevant_item_count"], 3)
        self.assertEqual(merged["summary"]["nyc_emergency_management_item_count"], 1)

    def test_no_previous_cache_is_explicit_and_does_not_mutate_count(self):
        current = {
            "domain": "LEGIONELLA_PUBLIC_HEALTH_ALERTS",
            "generated_at": "2026-09-15T15:00:00Z",
            "source_channels": [],
            "errors": [],
            "items": [
                {
                    "item_id": "only",
                    "agency": "NYC Health Department",
                    "title": "Legionella item",
                    "published_date": "2026-09-15",
                }
            ],
        }
        merged = merge_previous(current, None)
        self.assertFalse(merged["history_merge"]["previous_cache_available"])
        self.assertEqual(merged["history_merge"]["merged_item_count"], 1)
        self.assertEqual(merged["summary"]["discovered_relevant_item_count"], 1)


if __name__ == "__main__":
    unittest.main()
