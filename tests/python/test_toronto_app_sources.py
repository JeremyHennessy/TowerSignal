import unittest

from scripts.toronto_app_sources import normalize_source_link, valid_public_url


class TorontoAppSourceTests(unittest.TestCase):
    def test_rejects_insecure_and_legacy_aic_urls(self) -> None:
        self.assertIsNone(valid_public_url("http://open.toronto.ca/dataset/example/"))
        self.assertIsNone(valid_public_url("https://example.com/record/1"))
        self.assertIsNone(valid_public_url("https://secure.toronto.ca/AIC/index.do?folderRsn=dead"))
        self.assertEqual(valid_public_url("https://open.toronto.ca/dataset/example/"), "https://open.toronto.ca/dataset/example/")
    def test_aic_uses_current_record_detail_surface(self) -> None:
        link = normalize_source_link(
            {
                "source_key": "toronto_aic_applications",
                "source_record_id": "toronto_aic_applications:1:0",
                "source_row_index": 0,
                "match_basis": "EXACT_ADDRESS",
                "source_address": "100 QUEEN ST W",
            },
            {
                "toronto_aic_applications": [{
                    "APPLICATION_NUMBER": "24 100000 STE 01 OZ",
                    "SUBMIT_DATE": 1704067200000,
                    "STATUS_DESC": "Under Review",
                    "FOLDERTYPE_DESC": "Rezoning",
                    "FOLDERDESCRIPTION": "Planning application",
                    "AIC_ENCRYPTED_VALUE": "legacy-value",
                    "FOLDERRSN": 5813710,
                    "PROPERTYRSN": 949121,
                }]
            },
        )
        self.assertEqual(link["record_url"], "https://www.toronto.ca/city-government/planning-development/application-details/?id=5813710&pid=949121")
        self.assertEqual(link["record_link_label"], "Open official AIC application details")
        self.assertEqual(link["dataset_url"], "https://www.toronto.ca/city-government/planning-development/application-details/")
        self.assertEqual(link["dataset_link_label"], "Open current AIC application search")
        self.assertEqual(link["record_title"], "24 100000 STE 01 OZ")
    def test_rentsafe_building_evaluation_uses_official_record_page(self) -> None:
        link = normalize_source_link(
            {
                "source_key": "apartment_building_evaluation",
                "source_record_id": "apartment_building_evaluation:1:0",
                "source_row_index": 0,
                "match_basis": "EXACT_ADDRESS",
                "source_address": "500 DAWES RD",
            },
            {
                "apartment_building_evaluation": [{
                    "RSN": 4153692,
                    "PROPERTY TYPE": "PRIVATE",
                    "CURRENT BUILDING EVAL SCORE": 47,
                }]
            },
        )
        self.assertEqual(link["record_url"], "https://www.toronto.ca/community-people/housing-shelter/rental-housing-rights-information/housing-property-standards/apartment-building-standards/audits-evaluations/rentsafeto-building-evaluation-report/?id=4153692")
        self.assertEqual(link["record_link_label"], "Open official RentSafeTO building report")

    def test_public_notice_uses_dataset_fallback_and_normalized_context(self) -> None:
        link = normalize_source_link(
            {
                "source_key": "toronto_public_notices_exact_prior_poc",
                "source_record_id": "toronto_public_notices_exact_prior_poc:7529",
                "match_basis": "EXACT_ADDRESS",
                "source_address": "2 BLOOR ST E",
            },
            {
                "toronto_public_notices_exact_prior_poc": [{
                    "noticeId": 7529,
                    "title": "Notice of Application",
                    "noticeDate": 1780632000000,
                    "planningApplicationNumbers": ["26 148240 STE 11 OZ"],
                    "topics": ["Planning"],
                }]
            },
        )
        self.assertIsNone(link["record_url"])
        self.assertIsNone(link["record_link_label"])
        self.assertEqual(link["dataset_link_label"], "Search official public-notices dataset")
        self.assertIn({"label": "Notice ID", "value": "7529"}, link["record_details"])
        self.assertEqual({item["label"] for item in link["record_details"]}, {"Notice ID", "Planning applications", "Topics"})


if __name__ == "__main__":
    unittest.main()
