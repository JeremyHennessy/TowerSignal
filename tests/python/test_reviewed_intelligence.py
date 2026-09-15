import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from towersignal.legionella_links import address_key, resolve_rows, pdf_rows, bronx_rows
from towersignal.legionella_alerts import _parse_html
from towersignal.reviewed_priority import score

TODAY = date(2026, 9, 15)

class ReviewedPriorityTests(unittest.TestCase):
    def setUp(self):
        self.row = {'active_equipment': 1, 'latest_sample_date': '2026-09-14'}
        self.detail = {'inspection_history': [], 'oath_case_history': [], 'dob_activity_history': []}
        self.links = []

    def result(self):
        result = score(self.detail, self.row, self.links, TODAY)
        self.assertEqual(result['score'], sum(c['points'] for c in result['components']))
        self.assertLessEqual(result['score'], 100)
        self.assertGreaterEqual(result['score'], 0)
        return result

    def inspection(self, days=1, severity='PHH', summons='01'):
        self.detail['inspection_history'] = [{'inspection_date': (TODAY - timedelta(days=days)).isoformat(),
                                             'violations': [{'violation_type': severity, 'summons_number': summons}]}]

    def notice(self, days=3, status='INVESTIGATION_REPORTED', result='PCR_POSITIVE_REMEDIATION_ORDER'):
        self.links = [{'scope': 'BUILDING_LEVEL', 'source_url': 'https://www.nyc.gov/source',
                       'source_date': (TODAY - timedelta(days=days)).isoformat(), 'episode_status': status, 'result': result}]

    def test_no_evidence_does_not_manufacture_risk(self):
        self.assertEqual(self.result()['score'], 0)

    def test_phh_is_severe_but_noncritical_is_not(self):
        self.inspection()
        self.assertEqual(self.result()['score'], 50)
        self.inspection(severity='Noncritical')
        self.assertEqual(self.result()['score'], 40)

    def test_findings_decay_and_expire_by_source_date(self):
        for days, expected in [(90, 50), (91, 30), (180, 30), (181, 15), (365, 15), (366, 0)]:
            self.inspection(days)
            self.assertEqual(self.result()['score'], expected)

    def test_future_and_missing_inspections_do_not_add_points(self):
        self.inspection(-1)
        self.assertEqual(self.result()['score'], 0)
        self.detail['inspection_history'][0]['inspection_date'] = None
        self.assertEqual(self.result()['score'], 0)

    def test_exact_dismissal_only_removes_its_citation(self):
        self.inspection()
        self.detail['oath_case_history'] = [{'ticket_number':'01','hearing_result':'DISMISSED','decision_date':'2026-09-15'}]
        self.assertEqual(self.result()['score'], 10)  # only non-adverse inspection activity
        self.detail['inspection_history'][0]['violations'].append({'violation_type':'General','summons_number':'02'})
        self.assertEqual(self.result()['score'], 40)
        self.detail['oath_case_history'][0]['decision_date'] = '2026-09-16'
        self.assertEqual(self.result()['score'], 50)

    def test_paid_fine_does_not_mean_remediated(self):
        self.inspection()
        self.detail['oath_case_history'] = [{'ticket_number':'01','hearing_result':'IN VIOLATION','decision_date':'2026-09-15','balance_due':0,'paid_amount':1000}]
        self.assertEqual(self.result()['score'], 50)

    def test_positive_building_notice_overlaps_not_adds_inspection(self):
        self.inspection()
        self.notice()
        self.assertEqual(self.result()['score'], 70)
        self.assertEqual(len(self.result()['components']), 1)

    def test_closed_negative_area_and_old_notices_do_not_score(self):
        for kwargs in [dict(status='CLOSED'), dict(result='CULTURE_NEGATIVE'), dict(result='PCR_LIST_CLEANING_COMPLETE'), dict(days=91)]:
            self.notice(**kwargs)
            self.assertEqual(self.result()['score'], 0)
        self.notice()
        self.links[0]['scope'] = 'NEIGHBORHOOD'
        self.assertEqual(self.result()['score'], 0)

    def test_named_notice_recency_uses_order_date(self):
        self.notice(days=0)
        self.links[0]['event_date'] = '2026-08-01'
        self.assertEqual(self.result()['score'], 20)

    def test_reporting_window_missing_and_future_sampling(self):
        for days, expected in [(31,0), (32,0), (36,0), (37,20), (46,25), (61,30)]:
            self.row['latest_sample_date'] = (TODAY - timedelta(days=days)).isoformat()
            self.assertEqual(self.result()['score'], expected)
        self.row['latest_sample_date'] = None
        self.assertEqual(self.result()['score'], 18)
        self.row['latest_sample_date'] = '2026-09-16'
        self.assertEqual(self.result()['score'], 0)

    def test_general_context_and_boiler_only_cannot_create_tower_finding(self):
        self.detail.update(property_enforcement_context={'hpd_violations':{'summary':{'open_class_c_count':900}}},
                           domestic_water={'summary':{'violation_record_count':500}},
                           dob_activity_history=[{'mechanical_systems':True,'filing_date':'2026-09-15'}])
        self.assertEqual(self.result()['score'], 0)

    def test_explicit_recent_unsigned_project_is_bounded(self):
        job = {'explicit_cooling_tower_mention':True, 'filing_date':'2026-09-10', 'job_filing_number':'P1'}
        self.detail['dob_activity_history'] = [job, dict(job)]
        self.assertEqual(self.result()['score'], 15)
        job['signoff_date'] = '2026-09-12'
        self.detail['dob_activity_history'] = [job]
        self.assertEqual(self.result()['score'], 0)

    def test_component_points_reconcile_after_cap(self):
        self.notice()
        self.row.update(active_equipment=10, latest_sample_date=None)
        self.assertEqual(self.result()['score'], 100)
        self.assertEqual(self.result()['uncapped_score'], 106)

class BuildingMatchingTests(unittest.TestCase):
    def test_address_tokens_not_fuzzy_or_cross_borough(self):
        self.assertEqual(address_key('234 E. 149th Street'), address_key('234 EAST 149 ST'))
        self.assertNotEqual(address_key('234 EAST 149 ST'), address_key('236 EAST 149 ST'))
        self.assertNotEqual(address_key('9 EAST 90 ST'), address_key('9 WEST 90 ST'))

    def test_all_systems_at_unique_bin_building_scope(self):
        systems = [{'system_id':'1','address':'234 EAST 149 ST','borough':'Bronx','bin':'2000001'},
                   {'system_id':'2','address':'234 EAST 149 ST','borough':'Bronx','bin':'2000001'}]
        records = [{'address':'234 E149th St','borough':'Bronx'}]
        # A glued cardinal is not silently guessed.
        self.assertEqual(len(resolve_rows(records, systems, {})[0]), 0)
        records[0]['address'] = '234 E 149th St'
        linked, unresolved = resolve_rows(records, systems, {})
        self.assertEqual(len(linked), 2)
        self.assertFalse(unresolved)
        self.assertTrue(all(r['scope']=='BUILDING_LEVEL' and r['outbreak_source_confirmed'] is False for r in linked))
        records[0]['borough'] = 'Manhattan'
        self.assertEqual(len(resolve_rows(records, systems, {})[0]), 0)

    def test_ambiguous_and_missing_addresses_remain_unresolved(self):
        systems = [{'system_id':str(i),'address':'10 MAIN ST','borough':'Bronx','bin':str(2000000+i)} for i in (1,2)]
        linked, unresolved = resolve_rows([{'address':'10 Main Street','borough':'Bronx'}, {'address':'12 Main St','borough':'Bronx'}], systems, {})
        self.assertFalse(linked)
        self.assertEqual([r['resolution'] for r in unresolved], ['AMBIGUOUS_BUILDING','NO_EXACT_ADDRESS_MATCH'])

    def test_pluto_alias_must_resolve_unique_bin(self):
        systems=[{'system_id':'1','address':'1 MAIN ST','borough':'Bronx','bin':'2000001'}]
        self.assertEqual(len(resolve_rows([{'address':'10 Side Street','borough':'Bronx'}], systems, {'2000001':['10 SIDE ST']})[0]),1)

    def test_pdf_date_and_result_sections(self):
        text = 'Culture Positive\n • 10 Main St\nCulture Negative\n • 12 Main St\n7.29.26\n'
        with patch('towersignal.legionella_links.subprocess.run', return_value=SimpleNamespace(stdout=text)):
            day, rows = pdf_rows(b'%PDF', 'culture')
        self.assertEqual(day, '2026-07-29')
        self.assertEqual([r['result'] for r in rows], ['CULTURE_POSITIVE','CULTURE_NEGATIVE'])
        self.assertTrue(all(r['date_basis']=='DOCUMENT_REVISION_DATE' for r in rows))

    def test_unknown_pdf_section_fails_closed(self):
        with patch('towersignal.legionella_links.subprocess.run', return_value=SimpleNamespace(stdout='Unclear\n • 10 Main St\n7.29.26')):
            with self.assertRaises(ValueError): pdf_rows(b'%PDF', 'culture')

    def test_generic_pdf_cannot_silently_change_episode(self):
        with patch('towersignal.legionella_links.subprocess.run', return_value=SimpleNamespace(stdout='Culture Positive\n • 10 Main St\n9.29.26')):
            with self.assertRaises(ValueError): pdf_rows(b'%PDF', 'culture')

    def test_bronx_order_date_distinct_from_publication(self):
        html = b'<h1>Orders</h1><p>September 13, 2026</p><p>Preliminary PCR testing was completed by September 12, and orders were issued the same day.</p><p>positive PCR results are located at:</p><ul><li>10 Main St</li></ul>'
        published, rows = bronx_rows(html)
        self.assertEqual(published, '2026-09-13')
        self.assertEqual(rows[0]['event_date'], '2026-09-12')

    def test_human_h1_over_slug(self):
        self.assertEqual(_parse_html(b'<title>slug-headline</title><h1>Readable headline</h1>').title, 'Readable headline')

if __name__ == '__main__': unittest.main()
