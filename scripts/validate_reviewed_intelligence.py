"""Check every revised account and preserve source dates, Home matches, history and other facts."""
from __future__ import annotations
import argparse,json,sys
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from attach_reviewed_intelligence import building_links
from towersignal.reviewed_priority import score,MODEL

def read(p): return json.loads(p.read_text())
def validate(root,baseline=None):
    p=read(root/'systems.json'); m=read(root/'metadata.json'); matches=read(root/'legionella-property-matches.json')
    assert p['metadata']==m and m['priority_model_version']==MODEL
    rows=p['systems']; assert len({r['system_id'] for r in rows})==len(rows)==m['normalized_system_count']
    oldrows={r['system_id']:r for r in read(baseline/'systems.json')['systems']} if baseline else {}
    if baseline: assert set(oldrows)=={r['system_id'] for r in rows}
    changed=0
    for r in rows:
        rel=Path('details')/r['system_id'][:2]/(r['system_id']+'.json');d=read(root/rel)
        links=building_links(matches,r)
        assert d['legionella_building_evidence']==links
        revised=score(d,r,links,date.fromisoformat(m['snapshot_date']))
        assert revised==d['scoring'] and r['score_components']==revised['components']
        assert r['priority_score']==sum(c['points'] for c in revised['components'])==revised['score']
        assert 0<=r['priority_score']<=100
        project=next((c for c in revised['components'] if c['source']=='DOB NOW exact BBL'),None)
        project_signals=[s for s in d['signals'] if s['type']=='RECENT_COOLING_TOWER_PROJECT']
        assert bool(project)==('RECENT_COOLING_TOWER_PROJECT' in r['signal_types'])
        assert len(project_signals)==int(bool(project))
        if project:
            assert project_signals[0]['date']==project['source_date'] and project_signals[0]['reason']==project['reason']
            assert r['primary_signal']!='NO_CURRENT_SIGNAL'
        changed+=r['priority_score']!=d['priority_review_baseline']['priority_score']
        if baseline:
            old=read(baseline/rel)
            for k in old:
                if k not in ('scoring','metadata','signals'): assert old[k]==d[k], f'Account source fact changed: {r["system_id"]}/{k}'
            assert {k:v for k,v in old['metadata'].items() if k!='priority_model_version'}=={k:v for k,v in d['metadata'].items() if k!='priority_model_version'}
            for k in oldrows[r['system_id']]:
                if k not in ('priority_score','score_components','signal_types','primary_signal'): assert r[k]==oldrows[r['system_id']][k]
    review=read(root/'priority-model-review.json');assert review['changed_system_count']==changed==len(review['changed_systems'])
    if baseline:
        exceptions={'systems.json','metadata.json','coverage-audit.json','coverage-audit.md'}
        for f in baseline.rglob('*'):
            rel=f.relative_to(baseline)
            if f.is_file() and str(rel) not in exceptions and not str(rel).startswith('details/'):
                assert (root/rel).read_bytes()==f.read_bytes(),f'Unrelated source artifact changed: {rel}'
        assert m['generated_at']==read(baseline/'metadata.json')['generated_at']
    print(json.dumps({'model':MODEL,'systems_validated':len(rows),'changed_scores':changed,'all_components_reconcile':True,'matches':matches['summary'],'source_dates_preserved':True},indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('public/data'));p.add_argument('--baseline',type=Path);a=p.parse_args();validate(a.output,a.baseline)
