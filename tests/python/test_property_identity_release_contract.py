from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class PropertyIdentityReleaseContractTests(unittest.TestCase):
    def test_full_data_release_preserves_approved_report_revision(self):
        workflow = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
        self.assertIn("VITE_REPORT_APPLICATION_SHA: ${{ github.sha }}", workflow)
        self.assertIn("EXPECTED_REPORT_SHA: ${{ github.sha }}", workflow)

    def test_full_data_release_requires_downstream_mapping_coherence(self):
        workflow = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
        self.assertIn(
            "python scripts/validate_mapping_coherence.py --output public/data --require-production-volume",
            workflow,
        )

    def test_full_data_release_keeps_strict_property_acceptance(self):
        workflow = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
        self.assertIn(
            "python scripts/validate_property_identity_acceptance.py --output public/data --require-acris",
            workflow,
        )
        self.assertIn(
            "python scripts/validate_bbl_identity.py --output public/data --require-production-volume",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
