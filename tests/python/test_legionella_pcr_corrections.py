from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts'))
from build_legionella_matches import reconcile_explicit_pcr_corrections
from towersignal.legionella_matching import CULTURE, PCR


class PcrCorrectionTests(unittest.TestCase):
    def records(self, text):
        common = {'cluster_id': 'NYC-UES-2026-07', 'address': '300 E 83rd Street', 'related_article_urls': []}
        return {'observations': [
            {**common, 'result': 'PCR_POSITIVE', 'document_date': '2026-07-20', 'source_url': PCR, 'evidence_text': '300 E 83rd Street (unregistered cooling tower)'},
            {**common, 'result': 'CULTURE_NEGATIVE', 'document_date': '2026-07-29', 'source_url': CULTURE, 'evidence_text': text},
        ]}

    def test_explicit_later_pcr_correction_keeps_original_provenance(self):
        result = reconcile_explicit_pcr_corrections(self.records('300 E 83rd Street (unregistered cooling tower, tested PCR negative)'))
        row = result['observations'][0]
        self.assertEqual(row['result'], 'PCR_NEGATIVE')
        self.assertEqual(row['source_url'], CULTURE)
        self.assertEqual(row['document_date'], '2026-07-29')
        self.assertEqual(row['prior_observation']['result'], 'PCR_POSITIVE')
        self.assertEqual(row['prior_observation']['source_url'], PCR)
        self.assertEqual(result['observations'][1]['result'], 'CULTURE_NEGATIVE')

    def test_culture_negative_does_not_imply_pcr_negative(self):
        documents = self.records('300 E 83rd Street')
        self.assertEqual(reconcile_explicit_pcr_corrections(documents), documents)

    def test_older_source_does_not_overwrite_newer_pcr(self):
        documents = self.records('300 E 83rd Street tested PCR negative')
        documents['observations'][0]['document_date'] = '2026-08-01'
        self.assertEqual(reconcile_explicit_pcr_corrections(documents), documents)


if __name__ == '__main__':
    unittest.main()
