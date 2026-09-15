from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts'))
from towersignal.legionella_matching import normalized_address, match_documents, parse_bronx_orders, parse_result_pdf


class MatchingTests(unittest.TestCase):
    def test_address_normalization(self):
        self.assertEqual(normalized_address('234 E. 149th St.'), normalized_address('234 EAST 149 STREET'))
        self.assertNotEqual(normalized_address('100 East End Avenue'), normalized_address('100 East Avenue'))
        self.assertNotEqual(normalized_address('64-80 Kissena Blvd'), normalized_address('6480 Kissena Blvd'))
    def test_multiple_systems_one_building_not_individual_test(self):
        rows=[{'system_id':str(i),'address':'234 E 149TH ST','borough':'Bronx','bin':'2097050'} for i in (1,2)]
        docs={'observations':[{'address':'234 East 149 Street','borough':'BRONX','cluster_id':'B'}], 'sources':[]}
        result=match_documents(docs,rows)
        self.assertEqual(result['summary']['named_buildings_matched'],1)
        self.assertEqual(result['summary']['systems_with_named_building_evidence'],2)
        self.assertEqual(result['matched_observations'][0]['match_scope'],'NAMED_BUILDING_NOT_INDIVIDUAL_SYSTEM')
        rows[1]['bin']='2097051'
        self.assertEqual(match_documents(docs,rows)['unresolved'][0]['match_status'],'AMBIGUOUS')
    def test_borough_not_optional(self):
        result=match_documents({'observations':[{'address':'1 Park Ave','borough':'BRONX','cluster_id':'B'}],'sources':[]},[{'system_id':'1','address':'1 Park Ave','borough':'Manhattan','bin':'1000001'}])
        self.assertEqual(result['summary']['named_buildings_matched'],0)
    def test_missing_bin_never_high_confidence(self):
        docs={'observations':[{'address':'1 Park Ave','borough':'BRONX','cluster_id':'B'}],'sources':[]}
        result=match_documents(docs,[{'system_id':'1','address':'1 Park Ave','borough':'BRONX','bin':None}])
        self.assertEqual(result['unresolved'][0]['match_status'],'AMBIGUOUS')
    def test_area_context_never_named_building(self):
        docs={'observations':[], 'sources':[], 'areas':[{'borough':'BRONX','zip_codes':['10451'],'score_points':0}]}
        result=match_documents(docs,[{'system_id':'1','borough':'BRONX','zip':'10451'}])
        self.assertEqual(result['summary']['systems_with_area_context'],1)
        self.assertEqual(result['summary']['systems_with_named_building_evidence'],0)
    def test_venue_is_not_tower(self):
        html='<p>September 13, 2026: 10 cooling towers. PCR.</p><p>The 10 cooling towers with positive PCR results are located at:</p><ul>'+''.join(f'<li>{i} E. 149th St.</li>' for i in range(1,11))+'</ul><p>Town hall: 463 E 149th St</p>'
        records=parse_bronx_orders(html.encode())
        self.assertEqual(len(records),10)
        self.assertFalse(any('463' in r['address'] for r in records))
    def test_partial_source_fails_closed(self):
        with self.assertRaises(ValueError):
            parse_bronx_orders(b'<p>Nothing</p>')
    def test_pdf_status_and_printed_date(self):
        text='7.29.26\nCulture Positive\n'+''.join(f'• {i} E 79th Street\n' for i in range(1,21))+'Culture Negative\n• 99 E 79th Street\n'
        records=parse_result_pdf(text,'source.pdf')
        self.assertEqual(records[-1]['result'],'CULTURE_NEGATIVE')
        self.assertEqual(records[0]['document_date'],'2026-07-29')
        self.assertIsNone(records[0]['event_date'])
        self.assertEqual(records[0]['outbreak_attribution'],'NOT_ESTABLISHED')
    def test_inconsistent_pdf_dates_refused(self):
        with self.assertRaises(ValueError):
            parse_result_pdf('7.29.26\n7.21.26\nCulture Positive','source.pdf')


if __name__=='__main__':
    unittest.main()
