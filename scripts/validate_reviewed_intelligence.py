"""Fail closed on mismatched accounts, rewritten dates, or irreconcilable priority explanations."""
from __future__ import annotations
import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from towersignal.reviewed_priority import MODEL, score
from towersignal.legionella_links import resolve_rows


def read(p): return json.loads(p.read_text())

def validate(root: Path, baseline: Path | None = None):
    payload = read(root/'systems.json')
    metadata = read(root/'metadata.json')
    assert metadata == payload['metadata'], 'Summary and root metadata disagree'
    assert metadata['priority_model_version'] == MODEL
    assert isinstance(metadata['source_health'], list)
    rows = {r['system_id']:r for r in payload['systems']}
    assert len(rows) == len(payload['systems']) == metadata['normalized_system_count']
    links = read(root/'legionella-tower-links.json')
    archive = read(root/'legionella-alerts.json')
    review = read(root/'priority-model-review.json')
    assert links['domain'] == 'LEGIONELLA_BUILDING_EVIDENCE'
    assert len({i['item_id'] for i in archive['items']}) == len(archive['items']) == archive['summary']['discovered_relevant_item_count']
    asof = date.fromisoformat(metadata['snapshot_date'])
    aliases, actual_linked = {}, set()
    before, after = Counter(), Counter()
    baseline_rows = {r['system_id']:r for r in read(baseline/'systems.json')['systems']} if baseline else {}
    if baseline:
        assert set(rows) == set(baseline_rows), 'The current account universe changed'
        assert metadata['generated_at'] == read(baseline/'metadata.json')['generated_at'], 'Rescoring advanced the source clock'
    for sid, row in rows.items():
        path = Path('details')/sid[:2]/(sid+'.json')
        detail = read(root/path)
        if (detail.get('building_context') or {}).get('address'):
            aliases.setdefault(row['bin'],[]).append(detail['building_context']['address'])
        evidence = links['by_system'].get(sid,[])
        assert detail.get('legionella_building_evidence') == evidence
        result = score(detail,row,evidence,asof)
        assert result == detail['scoring'], f'Non-reproducible score: {sid}'
        assert row['priority_score'] == result['score'] == sum(c['points'] for c in result['components'])
        assert row['score_components'] == result['components']
        assert 0 <= row['priority_score'] <= 100
        assert result['official_building_followup'] == ('OFFICIAL_BUILDING_FOLLOWUP' in row['signal_types'])
        assert row['official_building_evidence_count'] == len(evidence)
        before[detail['priority_review_baseline']['priority_score']] += 1
        after[result['score']] += 1
        for record in evidence:
            assert record['system_id'] == sid and record['bin'] == row['bin']
            assert record['bbl'] == row['bbl'] and record['scope'] == 'BUILDING_LEVEL'
            assert record['outbreak_source_confirmed'] is False
            assert record['source_sha256'] and record['source_url'].startswith('https://www.nyc.gov/')
            actual_linked.add(sid)
        if baseline:
            old = read(baseline/path)
            for key in old:
                if key in ('scoring','metadata','signals'): continue
                assert detail[key] == old[key], f'Underlying account fact changed: {sid}/{key}'
            for key in baseline_rows[sid]:
                if key in ('priority_score','score_components','primary_signal','signal_types'): continue
                assert row[key] == baseline_rows[sid][key], f'Underlying summary fact changed: {sid}/{key}'
            assert detail['metadata']['generated_at'] == old['metadata']['generated_at']
    relinked, unresolved = resolve_rows(links['records'],list(rows.values()),aliases)
    key=lambda r:(r['source_url'],r['address'],r.get('system_id',''))
    assert sorted(relinked,key=key) == sorted(links['linked_records'],key=key), 'Building links do not reproduce'
    assert sorted(unresolved,key=key) == sorted(links['unresolved'],key=key)
    assert len(actual_linked) == links['summary']['matched_systems']
    assert len({r['bin'] for r in relinked}) == links['summary']['matched_buildings']
    assert len(links['records']) == links['summary']['published_building_observations']
    assert len(unresolved) == links['summary']['unresolved_building_observations']
    identities={(r['source_url'],r['system_id'],r['result'],r['source_date']) for r in relinked}
    for item in archive['items']:
        for r in item.get('building_links',[]):
            assert (r['source_url'],r['system_id'],r['result'],r['source_date']) in identities
            assert r['link_basis'] in ('NAMED_IN_SOURCE','RELATED_EPISODE_UPDATE')
            if r['link_basis']=='NAMED_IN_SOURCE': assert r['source_url']==item['url']
    assert dict(sorted((int(k),v) for k,v in review['before_distribution'].items())) == dict(sorted(before.items()))
    assert dict(sorted((int(k),v) for k,v in review['after_distribution'].items())) == dict(sorted(after.items()))
    assert review['changed_system_count'] == len(review['changed_systems'])
    assert len(rows) == review['systems_reviewed']
    if baseline:
        assert (root/'changes.json').read_bytes()==(baseline/'changes.json').read_bytes(), 'Source history was rewritten'
    result={'systems_validated':len(rows),'linked_systems':len(actual_linked),'named_buildings':links['summary']['matched_buildings'],
            'unresolved_observations':len(unresolved),'changed_scores':review['changed_system_count'],'model':MODEL,
            'source_dates_preserved':True,'all_score_components_reconcile':True,'building_links_reproduced':True}
    print(json.dumps(result,indent=2))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('public/data'));p.add_argument('--baseline',type=Path)
    a=p.parse_args();validate(a.output,a.baseline)
