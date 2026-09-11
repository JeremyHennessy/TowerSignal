"""Bounds must improve query planning without broadening exact property matches."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import io
import itertools
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from scripts import build_legacy_dob_project_cache as c


def original_where(chunk):
    clauses = []
    for bbl in chunk:
        parts = c._bbl_components(bbl)
        if parts:
            borough, block, lot = parts
            clauses.append(f"(borough='{borough}' AND block='{block}' AND lot='{str(int(lot)).zfill(5)}')")
    if not clauses:
        raise ValueError('No valid BBLs')
    return ' OR '.join(clauses)


class FixedTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 9, 11, 14, 0, tzinfo=timezone.utc)


class LegacyDobQueryBoundsTests(unittest.TestCase):
    def test_redundant_guards_keep_the_complete_original_disjunction(self):
        chunk = ['1000010001', '1000020002', '2000010002', '5999999999']
        result = c._exact_where(chunk)
        self.assertTrue(result.endswith(' AND (' + original_where(chunk) + ')'))
        self.assertTrue(result.startswith("borough in('BRONX','MANHATTAN','STATEN ISLAND')"))
        self.assertIn("block in('00001','00002','99999')", result)
        self.assertIn("lot in('00001','00002','09999')", result)

    def test_sql_equivalence_including_cross_combinations_nulls_and_nonmatches(self):
        chunk = ['1000010001', '1000020002', '2000010002', '5999999999']
        with sqlite3.connect(':memory:') as connection:
            connection.execute('create table jobs(borough text, block text, lot text)')
            rows = list(itertools.product([None, *c.BOROUGH_NAMES.values()],
                         [None, '00001', '00002', '00003', '99999'],
                         [None, '00001', '00002', '00003', '09999']))
            connection.executemany('insert into jobs values(?,?,?)', rows)
            query = 'select borough,block,lot from jobs where '
            old = connection.execute(query + original_where(chunk)).fetchall()
            new = connection.execute(query + c._exact_where(chunk)).fetchall()
            self.assertEqual(new, old)
            self.assertEqual(len(new), 4)
            # The guards alone deliberately include cross-combinations: the
            # original exact disjunction is mandatory, not a redundant test.
            guards = c._exact_where(chunk).split(' AND (', 1)[0]
            self.assertGreater(len(connection.execute(query + guards).fetchall()), len(new))

    def test_invalid_only_chunks_still_fail(self):
        for chunk in ([], ['not-a-bbl'], ['0000000000']):
            with self.subTest(chunk=chunk), self.assertRaises(ValueError):
                c._exact_where(chunk)

    def test_mixed_invalid_values_do_not_change_valid_scope(self):
        chunk = ['1000010001', 'invalid', '1000010001']
        self.assertTrue(c._exact_where(chunk).endswith(' AND (' + original_where(chunk) + ')'))

    def run_builder(self, output, query_constructor, responses):
        with patch.object(c, '_exact_where', side_effect=query_constructor), \
             patch.object(c, 'fetch_where', side_effect=responses) as fetch, \
             patch.object(c, 'fetch_metadata', return_value={'name': 'DOB', 'source_last_updated_at': '2026-09-10T00:00:00Z'}), \
             patch.object(c, 'fetch_count', return_value=2700000), \
             patch.object(c, 'datetime', FixedTime), \
             redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as stderr:
            result = c.build(output)
        return result, fetch.call_args_list, stderr.getvalue(), (output/'legacy-dob-projects.json').read_bytes()

    def test_full_cache_bytes_unchanged_with_same_complete_source_rows(self):
        constructor = c._exact_where
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bbls = [f'300001{lot:04d}' for lot in range(1, 32)]
            systems = {'metadata': {'snapshot_date': '2026-09-11'}, 'systems': [{'bbl': b} for b in reversed(bbls)]}
            responses = [[{'borough': 'BROOKLYN', 'block': '00001', 'lot': '00001', 'job_s1_no': '1',
                          'job_description': 'Replace cooling tower', 'latest_action_date': '01/01/2010'}],
                         [{'borough': 'BROOKLYN', 'block': '00001', 'lot': '00031', 'job_s1_no': '2',
                          'job_description': 'Mechanical work', 'mechanical': 'X', 'latest_action_date': '09/01/2026'}]]
            results = []
            for index, where in enumerate((original_where, constructor)):
                folder = root/str(index); folder.mkdir()
                (folder/'systems.json').write_text(json.dumps(systems))
                results.append(self.run_builder(folder, where, responses))
            self.assertEqual(results[0][3], results[1][3])
            self.assertEqual(results[1][0]['summary']['retained_record_count'], 2)
            self.assertIn('Batch 2/2: querying 1 exact BBLs', results[1][2])
            self.assertIn('Metadata received; fetching total source count', results[1][2])
            for before, after in zip(results[0][1], results[1][1]):
                self.assertEqual(before.args, after.args)
                self.assertEqual({k:v for k,v in before.kwargs.items() if k != 'where'},
                                 {k:v for k,v in after.kwargs.items() if k != 'where'})
                self.assertEqual(after.kwargs['limit'], 50000)
                self.assertEqual(after.kwargs['request_timeout'], 120)
                self.assertEqual(after.kwargs['order_by'], 'borough,block,lot,job_s1_no')

    def test_cap_and_source_failure_never_publish_partial_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output/'systems.json').write_text(json.dumps({'systems':[{'bbl':'1000010001'}]}))
            target = output/'legacy-dob-projects.json'; target.write_bytes(b'previous verified cache')
            for cap in (False, True):
                with self.subTest(cap=cap), \
                     patch.object(c, 'fetch_where', return_value=[{}]*c.FETCH_CAP if cap else None,
                                  side_effect=None if cap else c.SourceFetchError('source failed')), \
                     redirect_stderr(io.StringIO()), self.assertRaises(c.SourceFetchError):
                    c.build(output)
                self.assertEqual(target.read_bytes(), b'previous verified cache')

    def test_count_failure_does_not_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output/'systems.json').write_text(json.dumps({'systems':[{'bbl':'1000010001'}]}))
            with patch.object(c, 'fetch_where', return_value=[]), \
                 patch.object(c, 'fetch_metadata', return_value={}), \
                 patch.object(c, 'fetch_count', side_effect=c.SourceFetchError('count failed')), \
                 redirect_stderr(io.StringIO()), self.assertRaises(c.SourceFetchError):
                c.build(output)
            self.assertFalse((output/'legacy-dob-projects.json').exists())


if __name__ == '__main__':
    unittest.main()
