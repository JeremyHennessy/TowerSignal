import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from company_enrichment import candidate_id, fetch_page, observations, validate_url


def html(value):
    return '<script type="application/ld+json">' + json.dumps(value) + '</script>'


class CompanyEnrichmentTests(unittest.TestCase):
    def test_exact_subject_and_evidence_only(self):
        outcome, rows = observations(html({'@type':'Organization','name':'Alpha Water','legalName':'Alpha Water LLC',
            'address':{'streetAddress':'1 Main St','addressLocality':'New York'},
            'parentOrganization':{'@type':'Organization','name':'Holding Co'}}),'alpha water')
        self.assertEqual(outcome,'observed')
        self.assertEqual(dict(rows)['parent_company_name'],'Holding Co')
        self.assertEqual(dict(rows)['headquarters']['headquarters_city'],'New York')
        self.assertNotIn('revenue',dict(rows))

    def test_parent_is_not_subject(self):
        outcome, rows=observations(html({'@type':'Organization','name':'Other',
            'parentOrganization':{'@type':'Organization','name':'Alpha','legalName':'Wrong LLC'}}),'Alpha')
        self.assertEqual((outcome,rows),('identity-unresolved',[]))

    def test_conflicting_organizations_stay_unresolved(self):
        outcome, rows=observations(html([{'@type':'Organization','name':'Alpha','legalName':'A'},
            {'@type':'Organization','name':'Alpha','legalName':'B'}]),'Alpha')
        self.assertEqual((outcome,rows),('identity-unresolved',[]))

    def test_missing_data_never_zero(self):
        self.assertEqual(observations('<html>Contact us</html>','Alpha'),('no-structured-data',[]))
        self.assertEqual(observations(html({'@type':'Organization','name':'Alpha'}),'Alpha'),('observed',[]))

    def test_candidate_identity_is_stable_and_source_specific(self):
        self.assertEqual(candidate_id('s','headquarters',{'x':1,'y':2}),candidate_id('s','headquarters',{'y':2,'x':1}))
        self.assertNotEqual(candidate_id('s','name','A'),candidate_id('s2','name','A'))

    def test_invalid_and_private_sources_are_blocked(self):
        for url in ['http://example.com','https://user:pass@example.com','file:///tmp/x','https://example.com:8080','https://example.com/#x']:
            with self.assertRaises(ValueError):validate_url(url)
        with patch('company_enrichment.socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]):
            with self.assertRaisesRegex(ValueError,'non-public'):fetch_page('https://example.com')

    def test_graph_and_malformed_json(self):
        self.assertEqual(observations(html({'@graph':[{'@type':'Corporation','name':'Alpha','legalName':'Alpha Inc.'}]}),'Alpha')[1],[('legal_name','Alpha Inc.')])
        self.assertEqual(observations('<script type="application/ld+json">bad</script>','Alpha')[1],[])


if __name__ == '__main__':unittest.main()
