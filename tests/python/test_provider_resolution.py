from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.provider_resolution import (  # noqa: E402
    build_alias_review_queue,
    build_dec_name_matches,
    candidate_pair,
)


class ProviderResolutionTests(unittest.TestCase):
    def test_typo_candidate_is_review_only(self) -> None:
        left = {"provider_id": "p1", "provider_key": "AMERICAN PIPE AND TANK", "observed_building_count": 1000}
        right = {"provider_id": "p2", "provider_key": "AMERICAN PIP AND TANK", "observed_building_count": 10}
        candidate = candidate_pair(left, right)
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate["candidate_type"], "PROBABLE_TYPO_VARIANT")
        self.assertEqual(candidate["recommended_action"], "REVIEW")
        self.assertFalse(candidate["merge_applied"])
        self.assertEqual(candidate["identity_confidence"], "VERIFY")
        self.assertEqual(candidate["suggested_canonical_provider_id"], "p1")

    def test_short_form_is_not_auto_merged(self) -> None:
        left = {"provider_id": "p1", "provider_key": "ISSEKS", "observed_building_count": 400}
        right = {"provider_id": "p2", "provider_key": "ISSEKS BROS", "observed_building_count": 2400}
        candidate = candidate_pair(left, right)
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate["candidate_type"], "SHORT_FORM_OR_RELATED_NAME")
        self.assertFalse(candidate["merge_applied"])
        self.assertEqual(candidate["suggested_canonical_provider_id"], "p2")

    def test_service_line_differentiator_prevents_typo_promotion(self) -> None:
        left = {"provider_id": "p1", "provider_key": "AMERICAN PIPE AND TANK", "observed_building_count": 1000}
        right = {"provider_id": "p2", "provider_key": "AMERICAN PIPE AND TANK LINING", "observed_building_count": 100}
        candidate = candidate_pair(left, right)
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertNotEqual(candidate["candidate_type"], "PROBABLE_TYPO_VARIANT")
        self.assertTrue(candidate["differentiating_terms_changed"])
        self.assertFalse(candidate["merge_applied"])

    def test_review_queue_filters_one_off_noise(self) -> None:
        providers = [
            {"provider_id": "p1", "provider_key": "ROSENWACH TANK", "observed_building_count": 3000},
            {"provider_id": "p2", "provider_key": "ROSEWACH TANK", "observed_building_count": 2},
            {"provider_id": "p3", "provider_key": "RANDOM ONE OFF", "observed_building_count": 1},
        ]
        queue = build_alias_review_queue(providers, minimum_buildings=2)
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["review_priority"], "HIGH")

    def test_dec_exact_name_match_stays_verify(self) -> None:
        providers = [{"provider_id": "p1", "provider_key": "NALCO", "observed_building_count": 167}]
        dec = [{
            "provider_name": "NALCO COMPANY LLC",
            "provider_key": "NALCO",
            "registration_number": "14477",
            "registration_expiration_date": "2029-02-28",
            "qualification_scope": "NYS DEC Category 7G Cooling Towers",
        }]
        matches = build_dec_name_matches(providers, dec)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["match_method"], "NORMALIZED_NAME_EXACT")
        self.assertEqual(matches[0]["identity_confidence"], "VERIFY")
        self.assertEqual(matches[0]["relationship_evidence"], "CROSS_SOURCE_NAME_MATCH_ONLY")
        self.assertFalse(matches[0]["merge_applied"])


if __name__ == "__main__":
    unittest.main()
