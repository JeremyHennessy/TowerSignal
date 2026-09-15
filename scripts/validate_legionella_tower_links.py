"""Validate relationship cardinality, provenance and registry alignment independently."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from towersignal.legionella_tower_links import normalized_address, identifier


def validate(data: Path, max_age_days: float = 1) -> dict:
    payload = json.loads((data / 'legionella-tower-links.json').read_text())
    rows = json.loads((data / 'systems.json').read_text())['systems']
    assert payload['domain'] == 'LEGIONELLA_TOWER_LINKS'
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(payload['generated_at'].replace('Z', '+00:00'))).total_seconds() / 86400
    assert -0.01 <= age <= max_age_days, 'Tower links have a stale or future collection timestamp'
    registry = {row['system_id']: row for row in rows}
    assert len(registry) == len(rows) == payload['registry_system_count']
    projection = [{key: row.get(key) for key in ('system_id', 'address', 'borough', 'bin', 'bbl', 'zip')} for row in sorted(rows, key=lambda row: row['system_id'])]
    assert hashlib.sha256(json.dumps(projection, sort_keys=True).encode()).hexdigest() == payload['registry_identity_sha256'], 'Registry identity changed'
    documents = {row['source_url']: row for row in payload['source_documents']}
    events = {event['event_id']: event for event in payload['events']}
    assert len(events) == len(payload['events']) > 0
    expected = {sid: [] for sid in registry}
    for eid, event in events.items():
        named = set()
        for building in event['buildings']:
            resolution = building['resolution']
            systems = resolution['systems']
            if resolution['status'] != 'MATCHED':
                assert not systems
                continue
            assert resolution['system_specific'] is False and resolution['entity_level'] == 'BUILDING'
            assert identifier(resolution['bin'], 7)
            assert systems
            assert any(normalized_address(row['address']) == normalized_address(building['published_address']) for row in systems)
            assert {row['system_id'] for row in systems} == {sid for sid, row in registry.items() if identifier(row.get('bin'), 7) == resolution['bin'] and row.get('borough') == event['borough']}
            for row in systems:
                assert row['system_id'] in registry
                named.add(row['system_id'])
            for observation in building['observations']:
                assert observation['result'] in {'PCR_POSITIVE', 'CULTURE_POSITIVE', 'CULTURE_NEGATIVE', 'CULTURE_PENDING'}
                assert re.fullmatch(r'[a-f0-9]{64}', observation['content_sha256'])
                assert documents[observation['source_url']]['content_sha256'] == observation['content_sha256']
                assert observation['source_date'] is None or observation['source_date'].startswith('2026-')
        area = {sid for sid, row in registry.items() if row.get('borough') == event['borough'] and row.get('zip') in event['zip_codes']}
        assert len(named) == event['named_system_count']
        assert len(area - named) == event['area_only_system_count']
        assert len(named | area) == event['linked_system_count']
        assert sum(b['resolution']['status'] == 'MATCHED' for b in event['buildings']) == event['named_building_count']
        for sid in named | area:
            expected[sid].append((eid, 'NAMED_BUILDING' if sid in named else 'AREA_CONTEXT'))
    for sid, row in registry.items():
        links = payload['system_links'].get(sid, [])
        assert sorted((link['event_id'], link['relationship']) for link in links) == sorted(expected[sid])
        for link in links:
            assert link['system_specific'] is False
            if link['relationship'] == 'AREA_CONTEXT':
                assert link['observation_ids'] == [] and link['source_listed_building'] is False
        for field, relationship in [('legionella_event_ids', None), ('legionella_named_event_ids', 'NAMED_BUILDING'), ('legionella_area_only_event_ids', 'AREA_CONTEXT')]:
            assert sorted(row[field]) == sorted(eid for eid, kind in expected[sid] if relationship is None or kind == relationship)
    assert set(payload['system_links']).issubset(registry)
    assert len(payload['observation_history']) == len({row['observation_id'] for row in payload['observation_history']})
    return {'registry_systems': len(rows), 'linked_systems': len(payload['system_links']), 'reviewed_incidents': len(events), 'status': 'PASS'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, default=Path('public/data'))
    parser.add_argument('--max-age-days', type=float, default=1)
    args = parser.parse_args()
    print(json.dumps(validate(args.data, args.max_age_days), indent=2))
