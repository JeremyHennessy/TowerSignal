from __future__ import annotations
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from towersignal.legionella_tower_links import (normalized_address, resolve_building, scoped_list, html_blocks, parse_pdf, build_payload, SOURCES, TOPIC, BRONX_LIST, BRONX_INITIAL)


class TowerLinkTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {'system_id': 'one', 'address': '234 E 149TH ST', 'borough': 'Bronx', 'bin': '2097050', 'zip': '10451'},
            {'system_id': 'two', 'address': '234 EAST 149 STREET', 'borough': 'Bronx', 'bin': '2097050.0', 'zip': '10451'},
            {'system_id': 'melrose', 'address': '567 Melrose Avenue', 'borough': 'Bronx', 'bin': '2000857', 'zip': '10455'},
            {'system_id': 'wrongstreet', 'address': '567 E 149TH ST', 'borough': 'Bronx', 'bin': '2128228', 'zip': '10455'},
            {'system_id': 'area', 'address': '999 GRAND CONCOURSE', 'borough': 'Bronx', 'bin': '2111111', 'zip': '10456'},
            {'system_id': 'wrongborough', 'address': '234 E 149TH ST', 'borough': 'Queens', 'bin': '4111111', 'zip': '10451'},
        ]

    def test_only_lexical_normalization(self):
        self.assertEqual(normalized_address('234 E. 149th St.'), normalized_address('234 EAST 149 STREET'))
        self.assertEqual(normalized_address('1875 Second Avenue'), normalized_address('1875 2ND AVE'))
        self.assertNotEqual(normalized_address('567 E 149TH ST'), normalized_address('567 MELROSE AVE'))
        self.assertNotEqual(normalized_address('234 E 149TH ST'), normalized_address('234 W 149TH ST'))
        self.assertNotEqual(normalized_address('234-236 E 149TH ST'), normalized_address('234 E 149TH ST'))

    def test_multiple_systems_remain_building_level(self):
        match = resolve_building({'published_address': '234 E. 149th St.'}, 'Bronx', self.rows)
        self.assertEqual([r['system_id'] for r in match['systems']], ['one', 'two'])
        self.assertEqual(match['entity_level'], 'BUILDING')
        self.assertFalse(match['system_specific'])

    def test_explicit_address_wins_over_zip(self):
        match = resolve_building({'published_address': '567 Melrose Ave.'}, 'Bronx', self.rows)
        self.assertEqual([r['system_id'] for r in match['systems']], ['melrose'])
        self.assertEqual(match['systems'][0]['zip'], '10455')

    def test_ambiguity_is_not_merged(self):
        rows = self.rows + [{'system_id': 'three', 'address': '234 E 149TH ST', 'borough': 'Bronx', 'bin': '2000001'}]
        match = resolve_building({'published_address': '234 E. 149th St.'}, 'Bronx', rows)
        self.assertEqual(match['status'], 'AMBIGUOUS')
        self.assertEqual(match['systems'], [])

    def test_no_fuzzy_matching(self):
        self.assertEqual(resolve_building({'published_address': '233 E 149TH ST'}, 'Bronx', self.rows)['status'], 'UNMATCHED')

    def test_meeting_venue_not_a_test_result(self):
        blocks = html_blocks(b'<p>Town hall: 463 E 149th St.</p><p>The following buildings have cooling towers that tested positive in a PCR test.</p><ul><li>234 E. 149th St.</li></ul><p>Visit 567 E 149th St.</p>')
        self.assertEqual(scoped_list(blocks, r'^The following buildings'), ['234 E. 149th St.'])
        with self.assertRaises(ValueError): scoped_list(blocks, 'nonexistent heading')
        with self.assertRaises(ValueError): scoped_list(html_blocks(b'<p>The following buildings</p><p>no list</p>'), '^The following')

    def test_pdf_result_sections_and_date_not_link_label(self):
        date, records = parse_pdf('Culture Positive\n• 100 East End Avenue\n• 1486 Lexington Avenue *\nCulture Negative\n• 117 E 85th Street\nTest Results Pending\n• 60 East End Avenue\n* Tested PCR negative and culture positive. All have been remediated.\n7.21.26\n', 'culture')
        self.assertEqual(date, '2026-07-21')
        self.assertEqual([r['result'] for r in records], ['CULTURE_POSITIVE','CULTURE_POSITIVE','CULTURE_NEGATIVE','CULTURE_PENDING'])
        self.assertIn('PCR-negative', records[1]['source_note'])
        with self.assertRaises(ValueError): parse_pdf('Culture Positive\n• 100 East End Avenue\n7.21.27', 'culture')
        with self.assertRaises(ValueError): parse_pdf('Culture Positive\n• 100 East End Avenue', 'culture')

    def test_area_is_never_positive_and_inputs_unchanged(self):
        docs = {url: b'' for url in SOURCES}
        docs[TOPIC] = b'<h1>Legionnaires Disease</h1><p>Currently reviewing Melrose and Morrisania.</p><p>The following buildings have cooling towers that tested positive in a PCR test.</p><ul><li>234 E. 149th St.</li><li>567 Melrose Ave.</li></ul><h2>Upper East Side Legionnaires</h2><p>NYC has concluded its investigation.</p>'
        docs[BRONX_INITIAL] = b'<h1>South Bronx investigation</h1><p>September 10, 2026 Melrose 10451 10456</p>'
        docs[BRONX_LIST] = b'<h1>South Bronx remediation</h1><p>September 13, 2026</p><p>The 10 cooling towers with positive PCR results are located at:</p><ul><li>234 E. 149th St.</li><li>567 Melrose Ave.</li></ul>'
        old = copy.deepcopy(self.rows)
        outputs = [SimpleNamespace(stdout=b'Culture Positive\n\xe2\x80\xa2 100 East End Avenue\n7.21.26\n'), SimpleNamespace(stdout=b'Cleaning Complete\n\xe2\x80\xa2 180 East End Avenue\n7.20.2026\n')]
        with patch('towersignal.legionella_tower_links.subprocess.run', side_effect=outputs):
            result = build_payload(self.rows, docs, {'items': []}, collected_at='2026-09-15T19:00:00Z')
        self.assertEqual(self.rows, old)
        self.assertEqual(result['system_links']['area'][0]['relationship'], 'AREA_CONTEXT')
        self.assertEqual(result['system_links']['area'][0]['observation_ids'], [])
        self.assertNotIn('wrongstreet', result['system_links'])
        self.assertNotIn('wrongborough', result['system_links'])
        self.assertFalse(result['system_links']['melrose'][0]['shares_published_zip'])
        self.assertEqual(result['events'][0]['named_system_count'], 3)
        self.assertEqual(result['events'][0]['named_building_count'], 2)
        self.assertEqual(result['events'][0]['area_only_system_count'], 1)
        self.assertEqual(result['events'][1]['status'], 'CONCLUDED_AS_REPORTED')


if __name__ == '__main__': unittest.main()
