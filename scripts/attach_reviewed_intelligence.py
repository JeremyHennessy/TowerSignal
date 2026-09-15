"""Apply Priority 1.1 using the already-merged, source-scoped building match contract."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from towersignal.reviewed_priority import score, MODEL, CONTEXT_NOTE
from towersignal.legionella_matching import canonical_bin


def read(p): return json.loads(p.read_text())
def write(p, value):
    tmp = p.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(value, separators=(',', ':'), ensure_ascii=False))
    tmp.replace(p)

def building_links(matches, row):
    """Presentation adapter only; never rematches or rewrites the approved Home findings."""
    links = []
    for r in matches['by_system'].get(row['system_id'], {}).get('building_observations', []):
        assert r['match_scope'] == 'NAMED_BUILDING_NOT_INDIVIDUAL_SYSTEM'
        assert row['system_id'] in r['system_ids'] and canonical_bin(row['bin']) == r['bin']
        result = r['result']
        if result == 'PCR_POSITIVE' and r['action'] == 'REMEDIATION_ORDER_REPORTED':
            result = 'PCR_POSITIVE_REMEDIATION_ORDER'
        elif result == 'PCR_POSITIVE' and r['completion'] == 'CLEANING_REPORTED_COMPLETE':
            result = 'PCR_LIST_CLEANING_COMPLETE'
        closed = r['cluster_status'] == 'CLOSED_REPORTED'
        links.append({'system_id': row['system_id'], 'system_address': row['address'], 'address': r['address'],
                      'bin': r['bin'], 'bbl': row['bbl'], 'result': result,
                      'source_url': r['source_url'], 'source_title': 'Official named-building result',
                      'source_sha256': r['content_sha256'], 'source_date': r['document_date'],
                      'date_basis': 'DOCUMENT_REVISION_DATE' if r['source_url'].endswith('.pdf') else 'PUBLICATION_DATE',
                      'event_date': r['event_date'], 'episode_id': r['cluster_id'],
                      'episode_status': 'CLOSED' if closed else r['cluster_status'],
                      'episode_closed_at': None, 'closure_source_url': r.get('cluster_status_source') if closed else None,
                      'match_basis': r['match_basis'], 'scope': 'BUILDING_LEVEL', 'outbreak_source_confirmed': False,
                      'observation_id': r['observation_id']})
    return links

def attach(root: Path):
    raw = (root/'systems.json').read_bytes()
    payload = json.loads(raw)
    matches = read(root/'legionella-property-matches.json')
    assert matches['domain'] == 'LEGIONELLA_PROPERTY_MATCHES'
    expected_registry = payload['metadata'].get('priority_review_source_registry_sha256') or hashlib.sha256(raw).hexdigest()
    assert matches['registry_sha256'] == expected_registry, 'Match index is from a different registry snapshot'
    as_of = date.fromisoformat(payload['metadata']['snapshot_date'])
    before, after, changed = Counter(), Counter(), []
    for row in payload['systems']:
        path = root/'details'/row['system_id'][:2]/(row['system_id']+'.json')
        detail = read(path)
        prior = detail.get('priority_review_baseline') or {'priority_score': row['priority_score'], 'primary_signal': row['primary_signal'], 'scoring': detail['scoring']}
        evidence = building_links(matches, row)
        revised = score(detail, row, evidence, as_of)
        before[prior['priority_score']] += 1
        after[revised['score']] += 1
        if revised['score'] != prior['priority_score']:
            changed.append({'system_id': row['system_id'], 'address': row['address'], 'before': prior['priority_score'], 'after': revised['score'], 'components': revised['components']})
        row.update(priority_score=revised['score'], score_components=revised['components'], official_building_evidence_count=len(evidence), official_building_followup=revised['official_building_followup'])
        row['signal_types'] = [s for s in row['signal_types'] if s != 'OFFICIAL_BUILDING_FOLLOWUP']
        row['primary_signal'] = prior['primary_signal']
        detail['signals'] = [s for s in detail['signals'] if s['type'] != 'OFFICIAL_BUILDING_FOLLOWUP']
        if revised['official_building_followup']:
            row['signal_types'].append('OFFICIAL_BUILDING_FOLLOWUP')
            row['primary_signal'] = 'OFFICIAL_BUILDING_FOLLOWUP'
            detail['signals'].insert(0, {'type':'OFFICIAL_BUILDING_FOLLOWUP', 'title':'Official building follow-up',
                'evidence_confidence':'CONFIRMED', 'fact_class':'COMMERCIAL_SIGNAL',
                'date':max(r.get('event_date') or r['source_date'] for r in evidence),
                'reason':'Building explicitly named in official testing/remediation evidence. Individual tested-system and outbreak-source identity are not established.'})
        detail.update(scoring=revised, priority_review_baseline=prior, legionella_building_evidence=evidence)
        detail['metadata']['priority_model_version'] = MODEL
        write(path,detail)
    payload['metadata']['priority_model_version'] = MODEL
    payload['metadata'].setdefault('priority_review_source_registry_sha256',hashlib.sha256(raw).hexdigest())
    payload['systems'].sort(key=lambda r:(-r['priority_score'],r['system_id']))
    review = {'model_version':MODEL, 'as_of':as_of.isoformat(), 'systems_reviewed':len(payload['systems']),
        'validation_status':'RULE_BASED_NOT_PREDICTIVELY_CALIBRATED', 'context_note':CONTEXT_NOTE,
        'before_distribution':dict(before),'after_distribution':dict(after),'changed_system_count':len(changed),'changed_systems':changed,
        'building_evidence':matches['summary'], 'input_coverage':payload['summary'],
        'boundary':'Scores express research/commercial follow-up priority, not health risk or purchase probability. Source collection clocks are preserved. The existing Home matching evidence is unchanged.'}
    write(root/'systems.json',payload); write(root/'metadata.json',payload['metadata']);write(root/'priority-model-review.json',review)
    print(json.dumps({k:v for k,v in review.items() if k not in ('changed_systems','input_coverage','before_distribution','after_distribution')},indent=2))
    return review

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('public/data'));a=p.parse_args();attach(a.output)
