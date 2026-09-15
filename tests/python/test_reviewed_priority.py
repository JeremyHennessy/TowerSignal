import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
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

class ExistingMatchAdapterTests(unittest.TestCase):
    def test_canonical_bin_and_negative_result_preserved(self):
        from attach_reviewed_intelligence import building_links
        row = {'system_id':'1', 'bin':'1000001.0', 'address':'10 MAIN ST', 'bbl':'1000010001'}
        observation = {'match_scope':'NAMED_BUILDING_NOT_INDIVIDUAL_SYSTEM', 'system_ids':['1'], 'bin':'1000001',
            'result':'PCR_NEGATIVE','action':'HISTORICAL_RESULT','completion':'CLEANING_REPORTED_COMPLETE',
            'cluster_status':'CLOSED_REPORTED','cluster_status_source':'https://www.nyc.gov/status',
            'address':'10 Main St','source_url':'https://www.nyc.gov/results.pdf','content_sha256':'abc',
            'document_date':'2026-07-29','event_date':None,'cluster_id':'NYC-UES-2026-07',
            'match_basis':'NORMALIZED_ADDRESS_BOROUGH_SINGLE_BIN','observation_id':'record1'}
        payload = {'by_system':{'1':{'building_observations':[observation]}}}
        linked = building_links(payload,row)
        self.assertEqual(linked[0]['result'],'PCR_NEGATIVE')
        self.assertEqual(linked[0]['episode_status'],'CLOSED')
        self.assertEqual(linked[0]['closure_source_url'],'https://www.nyc.gov/status')
        self.assertFalse(linked[0]['outbreak_source_confirmed'])
        self.assertEqual(observation['bin'],'1000001')
        row['bin']='1000002'
        with self.assertRaises(AssertionError): building_links(payload,row)

    def test_unknown_account_has_no_manufactured_findings(self):
        from attach_reviewed_intelligence import building_links
        self.assertEqual(building_links({'by_system':{}},{'system_id':'missing'}),[])

if __name__ == '__main__': unittest.main()
