"""Attach verified building links and apply reviewed research-priority rules after enrichment."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from towersignal.legionella_links import collect_links, BRONX, CULTURE, PCR, CLOSURE, BOUNDARY
from towersignal.reviewed_priority import score, MODEL


def read(path: Path):
    return json.loads(path.read_text())

def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(value, separators=(',', ':'), ensure_ascii=False))
    temporary.replace(path)

def attach(root: Path, source_dir: Path | None = None, evidence_dir: Path | None = None):
    payload = read(root / 'systems.json')
    systems = payload['systems']
    as_of = date.fromisoformat(payload['metadata']['snapshot_date'])
    aliases = {}
    def detail_path(row):
        return root / 'details' / row['system_id'][:2] / (row['system_id'] + '.json')
    for row in systems:
        detail = read(detail_path(row))
        context = detail.get('building_context') or {}
        if context.get('address'):
            aliases.setdefault(row.get('bin'), []).append(context['address'])
    links = collect_links(systems, aliases, source_dir, evidence_dir)
    links['as_of'] = as_of.isoformat()
    archive = read(root / 'legionella-alerts.json')
    by_id = {item['item_id']: item for item in archive['items']}
    for doc in links['documents']:
        if doc['url'] not in (BRONX, CULTURE, PCR, CLOSURE):
            continue
        old = by_id.get(doc['item_id'], {})
        by_id[doc['item_id']] = {**old, **doc, 'agency': 'NYC Health Department', 'channel_key': 'NYC_DOH_LEGIONNAIRES_TOPIC',
                               'channel_kind': 'SOURCE_DOCUMENT' if doc['document_type'] == 'PDF' else 'PRESS_RELEASE',
                               'retrieved_at': doc.get('retrieved_at') or old.get('retrieved_at'),
                               'discovered_from': 'https://www.nyc.gov/site/doh/health/health-topics/legionnaires-disease.page',
                               'match_terms': {'legionella': True, 'cooling_tower': True}}
    def latest_for_system(rows):
        result = {}
        for row in rows:
            old = result.get(row['system_id'])
            if not old or row['source_date'] > old['source_date']:
                result[row['system_id']] = row
        return sorted(result.values(), key=lambda r: (r['system_address'], r['system_id']))
    for item in by_id.values():
        if '/mayors-office/' in item['url']:
            item['agency'] = "NYC Mayor's Office"
        direct = [r for r in links['linked_records'] if r['source_url'] == item['url']]
        text = ((item.get('title') or '') + ' ' + item['url']).lower()
        episode = None
        if 'pr2026/' in item['url'] and ('south-bronx' in text or 'cluster-in-the-bronx' in text or 'in the bronx' in text):
            episode = 'NYC-BRONX-2026-09'
        elif 'pr2026/' in item['url'] and any(term in text for term in ('upper-east-side', 'upper east side', 'ues-legionnaires')):
            episode = 'NYC-UES-2026-07'
        rows = direct or ([r for r in links['linked_records'] if r['episode_id'] == episode] if episode else [])
        item['building_links'] = [{**r, 'link_basis': 'NAMED_IN_SOURCE' if direct else 'RELATED_EPISODE_UPDATE'} for r in latest_for_system(rows)]
        item['linked_building_count'] = len({r['bin'] for r in rows})
        item['tower_link_boundary'] = BOUNDARY
    archive['items'] = sorted(by_id.values(), key=lambda i: (i.get('published_date') or '', i['item_id']), reverse=True)
    archive['summary'].update(discovered_relevant_item_count=len(by_id),
                              nyc_health_item_count=sum(i['agency'] == 'NYC Health Department' for i in by_id.values()),
                              mayor_office_item_count=sum(i['agency'] == "NYC Mayor's Office" for i in by_id.values()),
                              matched_system_count=links['summary']['matched_systems'],
                              matched_building_count=links['summary']['matched_buildings'])
    archive['building_match_summary'] = links['summary']
    archive['building_enrichment'] = {'base_archive_item_count': (archive.get('building_enrichment') or {}).get('base_archive_item_count', len(archive['items'])),
                                     'enriched_item_count': len(by_id), 'identity_basis': 'item_id',
                                     'note': 'Named-building documents are added after the retained-archive merge; the earlier history_merge describes that collection stage.'}
    health = read(root / 'source-health.json')
    matched = links['summary']['matched_systems']
    health_entry = {'source_key': 'official_legionella_building_evidence', 'dataset_id': 'NYC-DOHMH-NAMED-BUILDING-RESULTS',
                    'name': 'NYC Health official Legionella building results', 'entity_unit': 'current registered systems linked at building level',
                    'retrieved_record_count': len(links['records']), 'requested_entity_count': len(systems),
                    'normalized_entity_count': len(links['records']), 'matched_entity_count': matched,
                    'attached_entity_count': matched, 'displayed_entity_count': matched,
                    'coverage_percentage': round(100 * matched / len(systems), 2),
                    'previous_coverage_percentage': None, 'coverage_change_percentage_points': None,
                    'coverage_note': f"{links['summary']['matched_buildings']} unique buildings; {len(links['unresolved'])} unresolved source observations retained for review. Coverage is a building match, not a population positivity rate or outbreak attribution.",
                    'status': 'HEALTHY', 'status_reasons': []}
    health['sources'] = [h for h in health['sources'] if h['source_key'] != health_entry['source_key']] + [health_entry]
    # The source-health snapshot timestamp is preserved; each new document carries its own retrieval proof.
    payload['metadata']['source_health'] = health['sources']

    before, after = Counter(), Counter()
    changed = []
    for row in systems:
        detail = read(detail_path(row))
        prior = detail.get('priority_review_baseline') or {'priority_score': row['priority_score'], 'primary_signal': row['primary_signal'], 'scoring': detail['scoring']}
        matches = links['by_system'].get(row['system_id'], [])
        revised = score(detail, row, matches, as_of)
        before[prior['priority_score']] += 1
        after[revised['score']] += 1
        if revised['score'] != prior['priority_score']:
            changed.append({'system_id': row['system_id'], 'address': row['address'], 'before': prior['priority_score'], 'after': revised['score'], 'components': revised['components']})
        row.update(priority_score=revised['score'], score_components=revised['components'],
                   official_building_evidence_count=len(matches), official_building_followup=revised['official_building_followup'])
        row['signal_types'] = [s for s in row['signal_types'] if s != 'OFFICIAL_BUILDING_FOLLOWUP']
        row['primary_signal'] = prior['primary_signal']
        detail['signals'] = [s for s in detail['signals'] if s['type'] != 'OFFICIAL_BUILDING_FOLLOWUP']
        if revised['official_building_followup']:
            row['signal_types'].append('OFFICIAL_BUILDING_FOLLOWUP')
            row['primary_signal'] = 'OFFICIAL_BUILDING_FOLLOWUP'
            detail['signals'].insert(0, {'type': 'OFFICIAL_BUILDING_FOLLOWUP', 'title': 'Official building follow-up',
                                        'evidence_confidence': 'CONFIRMED', 'fact_class': 'COMMERCIAL_SIGNAL',
                                        'date': max(r.get('event_date') or r['source_date'] for r in matches),
                                        'reason': 'The building is explicitly named in official testing/remediation evidence. Individual system and outbreak-source identity are not established.'})
        detail.update(scoring=revised, priority_review_baseline=prior, legionella_building_evidence=matches)
        detail['metadata']['priority_model_version'] = MODEL
        write(detail_path(row), detail)
    payload['metadata']['priority_model_version'] = MODEL
    payload['metadata']['legionella_building_match_summary'] = links['summary']
    payload['systems'] = sorted(systems, key=lambda r: (-r['priority_score'], r['system_id']))
    payload['summary']['systems_with_official_building_evidence'] = links['summary']['matched_systems']
    review = {'model_version': MODEL, 'as_of': as_of.isoformat(), 'validation_status': 'RULE_BASED_NOT_PREDICTIVELY_CALIBRATED',
              'systems_reviewed': len(systems), 'input_coverage': payload['summary'], 'before_distribution': dict(before), 'after_distribution': dict(after),
              'changed_system_count': len(changed), 'changed_systems': changed,
              'source_families_reviewed': ['Cooling-tower registry and samples', 'NYC Health inspections and citations', 'OATH exact summons outcomes',
              'Official Legionella building results', 'DOB NOW and legacy projects', 'HPD housing and water violations', 'SWO dispositions',
              'FISP / Local Law 11', 'Domestic-water inspections and self-reports', '311 water complaints', 'LL84 water benchmarks',
              'CMS institutional facilities', 'Lead service lines', 'Distribution-water quality', 'ACRIS property records', 'Procurement and provider identities'],
              'boundary': 'Correctness and scenario tests establish deterministic behavior, not improved predictive accuracy. Source collection dates are not advanced by rescoring.'}
    for name, data in [('systems.json', payload), ('metadata.json', payload['metadata']), ('legionella-alerts.json', archive),
                       ('legionella-tower-links.json', links), ('priority-model-review.json', review), ('source-health.json', health)]:
        write(root / name, data)
    print(json.dumps({'matches': links['summary'], 'systems_reviewed': len(systems), 'changed_scores': len(changed),
                      'high_priority_before': sum(n for s,n in before.items() if s >= 70),
                      'high_priority_after': sum(n for s,n in after.items() if s >= 70)}, indent=2))
    return review

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, default=Path('public/data'))
    p.add_argument('--source-dir', type=Path)
    p.add_argument('--evidence-output', type=Path)
    args = p.parse_args()
    attach(args.output, args.source_dir, args.evidence_output)
