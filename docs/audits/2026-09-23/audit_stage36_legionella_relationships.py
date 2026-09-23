from __future__ import annotations
import hashlib,json,re
from collections import defaultdict
from pathlib import Path
import urllib.request as ur

OUT=Path('.audit-stage36');OUT.mkdir(exist_ok=True)
LIVE='https://jeremyhennessy.github.io/TowerSignal/'
def get(name):
    with ur.urlopen(ur.Request(LIVE+'data/'+name,headers={'User-Agent':'TowerSignal-independent-legionella-relationship-audit/20260923'}),timeout=120) as r:return r.read()
def normaddr(v):
    text=re.sub(r'[.,*]','',str(v or '').upper())
    text=re.sub(r'\([^)]*\)','',text)
    text=re.sub(r'\b(\d+)(?:ST|ND|RD|TH)\b',r'\1',text)
    repl={'EAST':'E','WEST':'W','NORTH':'N','SOUTH':'S','STREET':'ST','AVENUE':'AVE','AV':'AVE','BOULEVARD':'BLVD','ROAD':'RD','FIRST':'1','SECOND':'2','THIRD':'3','FOURTH':'4','FIFTH':'5'}
    return ' '.join(repl.get(t,t) for t in text.split())
def abin(v):
    d=re.sub(r'\D','',str(v or ''))
    return d if len(d)==7 and d[0] in '12345' and d[1:]!='000000' else None

systems_raw=get('systems.json');systems=json.loads(systems_raw)['systems']
matches=json.loads(get('legionella-property-matches.json'))
index=defaultdict(list)
for s in systems:
    index[(str(s.get('borough') or '').upper(),normaddr(s.get('address')))].append(s)

issues=[];replayed=[]
for obs in matches.get('matched_observations') or []:
    candidates=index.get((str(obs.get('borough') or '').upper(),normaddr(obs.get('address'))),[])
    bins={abin(s.get('bin')) for s in candidates}
    expected_status='MATCHED' if candidates and None not in bins and len(bins)==1 else ('UNMATCHED' if not candidates else 'AMBIGUOUS')
    expected_ids=sorted(str(s['system_id']) for s in candidates) if expected_status=='MATCHED' else []
    expected_bin=next(iter(bins)) if expected_status=='MATCHED' else None
    ok=expected_status=='MATCHED' and expected_ids==sorted(map(str,obs.get('system_ids') or [])) and expected_bin==str(obs.get('bin') or '')
    if not ok:issues.append({'type':'MATCH_REPLAY_MISMATCH','observation_id':obs.get('observation_id'),'expected_status':expected_status,'expected_system_ids':expected_ids,'served_system_ids':obs.get('system_ids'),'expected_bin':expected_bin,'served_bin':obs.get('bin')})
    replayed.append((obs.get('observation_id'),ok))
for obs in matches.get('unresolved') or []:
    candidates=index.get((str(obs.get('borough') or '').upper(),normaddr(obs.get('address'))),[])
    bins={abin(s.get('bin')) for s in candidates}
    expected='UNMATCHED' if not candidates else ('MATCHED' if None not in bins and len(bins)==1 else 'AMBIGUOUS')
    if expected=='MATCHED':
        issues.append({'type':'UNRESOLVED_NOW_HAS_UNIQUE_ASSIGNED_BIN','observation_id':obs.get('observation_id'),'system_ids':sorted(str(s['system_id']) for s in candidates),'bin':next(iter(bins))})
    elif str(obs.get('match_status'))!=expected:
        issues.append({'type':'UNRESOLVED_STATUS_MISMATCH','observation_id':obs.get('observation_id'),'expected':expected,'served':obs.get('match_status')})

summary={
 'registry_systems':len(systems),
 'registry_sha256':hashlib.sha256(systems_raw).hexdigest(),
 'artifact_registry_sha256':matches.get('registry_sha256'),
 'artifact_registry_equal_current':matches.get('registry_sha256')==hashlib.sha256(systems_raw).hexdigest(),
 'matched_observations':len(matches.get('matched_observations') or []),
 'unresolved_observations':len(matches.get('unresolved') or []),
 'issue_count':len(issues),
 'relationship_replay_exact':not issues,
 'match_basis_expected':'NORMALIZED_ADDRESS_BOROUGH_SINGLE_BIN',
 'scope_expected':'NAMED_BUILDING_NOT_INDIVIDUAL_SYSTEM',
 'all_served_match_basis_correct':all(x.get('match_basis')=='NORMALIZED_ADDRESS_BOROUGH_SINGLE_BIN' and x.get('match_scope')=='NAMED_BUILDING_NOT_INDIVIDUAL_SYSTEM' for x in matches.get('matched_observations') or []),
 'boundary':'Independent replay of observation-to-current-registry relationship only. It does not re-extract the official NYC Health documents or attribute an observation to an individual tower within the matched building.'
}
(OUT/'legionella-relationship-summary.json').write_text(json.dumps(summary,indent=2))
(OUT/'legionella-relationship-issues.json').write_text(json.dumps(issues,indent=2))
print(json.dumps(summary,indent=2))
