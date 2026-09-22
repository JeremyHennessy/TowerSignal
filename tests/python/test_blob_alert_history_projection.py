"""Exercise real seal/publication code with root-level alert fixtures; no live writes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_blob_data_refresh as fixtures


class BlobAlertHistoryProjectionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.DataRefreshTests(methodName='runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.original_payload = fixtures.fixture_payload

    def candidate_with_alert(self, alert_bytes):
        def payload(when):
            data = self.original_payload(when)
            data['legionella-alerts.json'] = alert_bytes
            return data
        with patch.object(fixtures, 'fixture_payload', side_effect=payload):
            return self.fixture.candidate()

    def test_seal_reads_alert_from_runtime_root_and_proves_history_parity(self):
        alert = b'{"items":[{"item_id":"retained-alert"}],"generated_at":"2026-09-22T00:00:00Z"}\n'
        pointer_before = self.fixture.store.data[fixtures.b.POINTER]
        _, sealed = self.candidate_with_alert(alert)
        staged = self.fixture.work / fixtures.d.WORK / 'staged'
        self.assertEqual((staged / 'runtime/legionella-alerts.json').read_bytes(), alert)
        self.assertEqual((staged / 'history/legionella-alerts.json').read_bytes(), alert)
        self.assertFalse((self.fixture.work / 'public/data/history/legionella-alerts.json').exists())
        digest = hashlib.sha256(alert).hexdigest()
        for kind in ('runtime', 'history'):
            records = [r for r in sealed[kind] if r['path'] == 'legionella-alerts.json']
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]['sha256'], digest)
            self.assertEqual(records[0]['bytes'], len(alert))
        self.assertEqual(
            sealed['history_parity'],
            fixtures.p.check_history_parity(sealed['runtime'], sealed['history']),
        )
        self.assertEqual(self.fixture.store.data[fixtures.b.POINTER], pointer_before)
        self.assertEqual(self.fixture.store.writes, [])

    def test_alert_history_survives_two_paired_publications_and_retains_parent(self):
        first_alert = b'{"items":[{"item_id":"first"}]}\n'
        self.candidate_with_alert(first_alert)
        first = self.fixture.publish()
        first_pointer = self.fixture.store.data[fixtures.b.POINTER]
        first_name = first['current']['history']['data_prefix'] + '/legionella-alerts.json'
        self.assertEqual(self.fixture.store.data[first_name], first_alert)

        self.fixture.work = self.fixture.root / 'second'
        self.fixture.work.mkdir()
        self.fixture.make_caches(self.fixture.work)
        self.fixture.reader = fixtures.Reader(1002)
        second_alert = b'{"items":[{"item_id":"first"},{"item_id":"second"}]}\n'
        inputs, _ = self.candidate_with_alert(second_alert)
        self.assertEqual(inputs['parent']['current']['source']['run_id'], 1001)
        self.assertTrue(any(r['path'] == 'legionella-alerts.json' for r in inputs['input_history']))
        self.assertEqual(
            (self.fixture.work / fixtures.d.HISTORY / 'legionella-alerts.json').read_bytes(),
            first_alert,
        )
        second = self.fixture.publish()
        for kind in ('runtime', 'history'):
            name = second['current'][kind]['data_prefix'] + '/legionella-alerts.json'
            self.assertEqual(self.fixture.store.data[name], second_alert)
        self.assertEqual(second['current']['revision'], 2)
        self.assertEqual(
            self.fixture.store.data[second['current']['previous']['blob']], first_pointer,
        )
        self.assertEqual(self.fixture.store.data[first_name], first_alert)
        self.assertFalse(second['site_deployed'])
        self.assertFalse(second['github_history_written'])


if __name__ == '__main__':
    unittest.main()
