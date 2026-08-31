import unittest

from scripts.toronto_app_sources import normalize_source_link, valid_public_url


class TorontoAppSourceTests(unittest.TestCase):
    def test_rejects_insecure_and_legacy_aic_urls(self) -> None:
        self.assertIsNone(valid_public_url("http://open.toronto.ca/dataset/example/"))
        self.assertIsNone(valid_public_url("https://example.com/record/1"))
        self.assertIsNone(valid_public_url("https://secure.toronto.ca/AIC/index.do?folderRsn=dead"))
        self.assertEqual(valid_public_url("https://open.toronto.ca/dataset/example/"), "https://open.toronto.ca/dataset/example/")

    def test_aic_uses_current_record_specific_application_action(self) -> None:
        link = normalize_source_link(
            {
                "source_key": "toronto_aic_applications",
                "source_record_id": "toronto_aic_applications:1:0",
                "source_row_index": 0,
                "match_basis": "EXACT_ADDRESS",
                "source_address": "2595 ST CLAIR AVE W",
            },
            {
                "toronto_aic_applications": [{
                    "OBJECTID": 1,
                    "APPLICATION_NUMBER": "24 100000 STE 01 OZ",
                    "FOLDERRSN": 5736884,
                    "PROPERTYRSN": 753435,
                    "FULL_ADDRESS": "2595 ST CLAIR AVE W",
                    "SUBMIT_DATE": 1704067200000,
                    "STATUS_DESC": "Under Review",
                    "FOLDERTYPE_DESC": "Rezoning",
                    "FOLDERDESCRIPTION": "Planning application",
                    "AIC_ENCRYPTED_VALUE": "legacy-value",
                }]
            },
        )
        self.assertEqual(
            link["record_url"],
            "https://www.toronto.ca/city-government/planning-development/application-details/?id=5736884&pid=753435&title=2595-ST-CLAIR-AVE-W",
        )
        self.assertEqual(link["record_link_label"], "Open AIC application")
        self.assertEqual(link["dataset_url"], "https://www.toronto.ca/city-government/planning-development/application-details/")
        self.assertEqual(link["dataset_link_label"], "Open current AIC application search")
        self.assertEqual(link["record_title"], "24 100000 STE 01 OZ")

    def test_development_pipeline_only_links_to_exact_aic_application_and_address(self) -> None:
        link = normalize_source_link(
            {
                "source_key": "development_pipeline",
                "source_record_id": "development_pipeline:id:100",
                "match_basis": "EXACT_ADDRESS",
                "source_address": "2595 ST CLAIR AVE W",
            },
            {
                "development_pipeline": [{"_id": 100, "Application Number": "24 100000 STE 01 OZ", "Address": "2595 ST CLAIR AVE W"}],
                "toronto_aic_applications": [{
                    "APPLICATION_NUMBER": "24 100000 STE 01 OZ",
                    "FOLDERRSN": 5736884,
                    "PROPERTYRSN": 753435,
                    "FULL_ADDRESS": "2595 ST CLAIR AVE W",
                }],
            },
        )
        self.assertEqual(link["record_link_label"], "Open AIC application")
        self.assertIn("id=5736884", link["record_url"])
        self.assertIn("pid=753435", link["record_url"])

    def test_public_notice_uses_direct_notice_action_and_normalized_context(self) -> None:
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
        self.assertEqual(link["record_url"], "https://secure.toronto.ca/nm/api/individual/notice/7529.do")
        self.assertEqual(link["record_link_label"], "Open public notice")
        self.assertEqual(link["dataset_link_label"], "Search official public-notices dataset")
        self.assertIn({"label": "Notice ID", "value": "7529"}, link["record_details"])
        self.assertEqual({item["label"] for item in link["record_details"]}, {"Notice ID", "Planning applications", "Topics"})

    def test_active_business_licence_uses_current_detail_action(self) -> None:
        link = normalize_source_link(
            {
                "source_key": "business_licence_matches_prior_poc",
                "source_record_id": "business_licence_matches_prior_poc:id:1",
                "match_basis": "EXACT_ADDRESS",
                "source_address": "68 PALMERSTON SQ",
            },
            {
                "business_licence_matches_prior_poc": [{
                    "_id": 1,
                    "Licence No.": "T85-5336861",
                    "Operating Name": "WHITESTONE DESIGN BUILD",
                    "Client Name": "WHITESTONE DESIGN BUILD INC",
                    "Cancel Date": None,
                }]
            },
        )
        self.assertEqual(link["record_url"], "https://secure.toronto.ca/LicenceStatus/detail.do?licenceNo=T855336861")
        self.assertEqual(link["record_link_label"], "Open licence details")

    def test_cancelled_business_licence_retains_dataset_fallback(self) -> None:
        link = normalize_source_link(
            {
                "source_key": "business_licence_matches_prior_poc",
                "source_record_id": "business_licence_matches_prior_poc:id:1",
                "match_basis": "EXACT_ADDRESS",
                "source_address": "68 PALMERSTON SQ",
            },
            {
                "business_licence_matches_prior_poc": [{
                    "_id": 1,
                    "Licence No.": "T85-5336861",
                    "Cancel Date": "2025-01-01",
                }]
            },
        )
        self.assertIsNone(link["record_url"])
        self.assertIsNone(link["record_link_label"])

    def test_apartment_evaluation_uses_rentsafeto_report_action(self) -> None:
        link = normalize_source_link(
            {
                "source_key": "apartment_building_evaluation",
                "source_record_id": "apartment_building_evaluation:id:1",
                "match_basis": "EXACT_ADDRESS",
                "source_address": "10 SKAGWAY AVE",
            },
            {
                "apartment_building_evaluation": [{
                    "_id": 1,
                    "RSN": 4622902,
                    "SITE ADDRESS": "10 SKAGWAY AVE",
                    "PROPERTY TYPE": "PRIVATE",
                }]
            },
        )
        self.assertEqual(link["record_link_label"], "Open RentSafeTO evaluation")
        self.assertIn("id=4622902", link["record_url"])
        self.assertIn("title=10-SKAGWAY-AVE", link["record_url"])


if __name__ == "__main__":
    unittest.main()
