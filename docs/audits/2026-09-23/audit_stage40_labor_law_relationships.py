from __future__ import annotations
import hashlib,json,re
from collections import defaultdict,Counter
from pathlib import Path
import urllib.request as ur

OUT=Path('.audit-stage40');OUT.mkdir(exist_ok=True)
LIVE='https://jeremyhennessy.github.io/TowerSignal/data/'
UA={'User-Agent':'TowerSignal-independent-labor-law-relationship-audit/20260923'}
SUFFIXES={"STREET":"ST","ST":"ST","AVENUE":"AVE","AVE":"AVE","ROAD":"RD","RD":"RD","BOULEVARD":"BLVD","BLVD":"BLVD","PLACE":"PL","PL":"PL","LANE":"LN","LN":"LN","DRIVE":"DR","DR":"DR","EAST":"E","WEST":"W","NORTH":"N","SOUTH":"S"}

def get(name):
    with ur.urlopen(ur.Request(LIVE+name,headers=UA),timeout=120) as r:
        b=r.read();return json.loads(b),hashlib.sha256(b).hexdigest()
def norm(v):
    text=str(v or '').upper().strip()
    text=re.sub(r'[^A-Z0-9 ]+',' ',text)
    return re.sub(r'\s+',' ',' '.join(SUFFIXES.get(t,t) for t in text.split())).strip() or None

systems,ssha=get('systems.json'); labor,lsha=get('labor-law-decisions.json')
index=defaultdict(list)
for s in systems.get('systems') or []:
    a=norm(s.get('address'))
    if a:index[a].append(s)

expected_edges=set();issues=[]
for dec in labor.get('decisions') or []:
    did=str(dec.get('decision_id') or '')
    for c in dec.get('explicit_subject_property_candidates') or []:
        a=norm(c.get('address') or c.get('normalized_address'))
        for s in index.get(a,[]):
            expected_edges.add((str(s.get('system_id')),did,a))

served_edges=set()
for sid,rows in (labor.get('by_system') or {}).items():
    for r in rows:
        a=norm(r.get('published_subject_address') or r.get('matched_normalized_address'))
        served_edges.add((str(sid),str(r.get('decision_id') or ''),a))
        if r.get('match_basis')!='PUBLISHED_DECISION_EXPLICIT_WORKSITE_ADDRESS_EXACT':
            issues.append({'type':'WRONG_MATCH_BASIS','system_id':sid,'decision_id':r.get('decision_id'),'value':r.get('match_basis')})
        if r.get('fact_class')!='CONFIRMED_FACT' or r.get('evidence_confidence')!='CONFIRMED':
            issues.append({'type':'WRONG_EVIDENCE_CLASS','system_id':sid,'decision_id':r.get('decision_id'),'fact_class':r.get('fact_class'),'confidence':r.get('evidence_confidence')})
        if r.get('building_level_context') is not True or r.get('liability_claim') is not False:
            issues.append({'type':'BOUNDARY_FLAGS_WRONG','system_id':sid,'decision_id':r.get('decision_id'),'building_level_context':r.get('building_level_context'),'liability_claim':r.get('liability_claim')})

source_only=sorted(expected_edges-served_edges); served_only=sorted(served_edges-expected_edges)
if source_only:issues.append({'type':'EXPECTED_EDGE_NOT_SERVED','count':len(source_only),'examples':[list(x) for x in source_only[:100]]})
if served_only:issues.append({'type':'SERVED_EDGE_NOT_REPRODUCIBLE','count':len(served_only),'examples':[list(x) for x in served_only[:100]]})

summary={
 'systems_sha256':ssha,'labor_cache_sha256':lsha,
 'system_count':len(systems.get('systems') or []),
 'retained_decision_count':len(labor.get('decisions') or []),
 'explicit_subject_candidate_count':sum(len(d.get('explicit_subject_property_candidates') or []) for d in labor.get('decisions') or []),
 'expected_relationship_edges':len(expected_edges),'served_relationship_edges':len(served_edges),
 'relationship_sets_equal':expected_edges==served_edges,
 'issue_count':len(issues),'issue_type_counts':dict(Counter(i['type'] for i in issues)),
 'all_served_boundaries_correct':not any(i['type'] in {'WRONG_MATCH_BASIS','WRONG_EVIDENCE_CLASS','BOUNDARY_FLAGS_WRONG'} for i in issues),
 'boundary':'Independent relationship replay from the served source-owned decision cache to the current TowerSignal registry. It proves exact normalized-address attachment and boundary flags; it does not independently re-extract decision body text from Official Reports or imply current filing/liability status.'
}
(OUT/'labor-law-relationship-summary.json').write_text(json.dumps(summary,indent=2))
(OUT/'labor-law-relationship-issues.json').write_text(json.dumps(issues,indent=2))
print(json.dumps(summary,indent=2))
