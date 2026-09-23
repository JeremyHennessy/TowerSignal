from __future__ import annotations
import hashlib,json
from collections import Counter
from pathlib import Path
import urllib.request as ur

OUT=Path('.audit-stage39');OUT.mkdir(exist_ok=True)
LIVE='https://jeremyhennessy.github.io/TowerSignal/data/'
def get(name):
    with ur.urlopen(ur.Request(LIVE+name,headers={'User-Agent':'TowerSignal-nys-role-boundary-audit/20260923'}),timeout=120) as r:
        b=r.read();return json.loads(b),hashlib.sha256(b).hexdigest()
pws,pws_sha=get('nys-public-water.json')
lsli,lsli_sha=get('nys-lsli-details.json')
issues=[]
contacts=0
for sys in pws.get('pws_systems') or []:
    for c in sys.get('contacts') or []:
        contacts+=1
        if c.get('relationship_role')!='CONTACT_FOR_PWS':
            issues.append({'type':'PWS_CONTACT_ROLE_OVERCLAIM','pws_id':sys.get('pws_id'),'role':c.get('relationship_role')})
        if c.get('operator_assignment_confidence')!='NOT_PROOF_OF_OPERATOR_ROLE':
            issues.append({'type':'PWS_CONTACT_OPERATOR_BOUNDARY_MISSING','pws_id':sys.get('pws_id'),'value':c.get('operator_assignment_confidence')})
operators=pws.get('certified_operators') or pws.get('operators') or []
for op in operators:
    if op.get('pws_assignment_confidence')!='UNLINKED_TO_PWS':
        issues.append({'type':'CERTIFIED_OPERATOR_LINKED_TO_PWS_WITHOUT_ASSIGNMENT_SOURCE','operator_id':op.get('operator_id'),'value':op.get('pws_assignment_confidence')})
details=lsli.get('details') or [];form_contacts=0
for d in details:
    c=d.get('owner_or_operator_form_contact') or {}
    if any(c.get(k) for k in ('name','phone','email')):
        form_contacts+=1
        if c.get('relationship_role')!='OWNER_OR_LICENSED_OPERATOR_OF_RECORD_FORM_CONTACT':
            issues.append({'type':'LSLI_FORM_CONTACT_ROLE_OVERCLAIM','pws_id':d.get('pws_id'),'role':c.get('relationship_role')})
        if c.get('relationship_evidence')!='NYSDOH_LSLI_SECTION_II':
            issues.append({'type':'LSLI_FORM_CONTACT_EVIDENCE_MISSING','pws_id':d.get('pws_id'),'evidence':c.get('relationship_evidence')})
        if 'does not infer whether' not in str(c.get('role_semantics') or ''):
            issues.append({'type':'LSLI_COMBINED_ROLE_BOUNDARY_MISSING','pws_id':d.get('pws_id')})
for d in lsli.get('unavailable_details') or []:
    if d.get('inventory') or d.get('owner_or_operator_form_contact'):
        issues.append({'type':'UNAVAILABLE_LSLI_DETAIL_HAS_INFERRED_VALUES','pws_id':d.get('pws_id')})

# Reject any accidental direct TowerSignal tower/account IDs in these statewide source artifacts.
def walk(v,path=''):
    if isinstance(v,dict):
        for k,x in v.items():
            p=f'{path}.{k}' if path else k
            if k in {'tower_account_system_ids','tower_system_ids','system_id'} and x not in (None,[],{}):
                yield (p,x)
            yield from walk(x,p)
    elif isinstance(v,list):
        for i,x in enumerate(v):yield from walk(x,f'{path}[{i}]')
direct=list(walk(pws))+list(walk(lsli))
if direct:issues.append({'type':'DIRECT_TOWER_ACCOUNT_LINK_PRESENT_IN_STATEWIDE_PWS_ARTIFACT','examples':direct[:30]})
summary={
 'pws_sha256':pws_sha,'lsli_detail_sha256':lsli_sha,
 'pws_system_count':len(pws.get('pws_systems') or []),'pws_contact_count':contacts,
 'certified_operator_count':len(operators),'lsli_parsed_detail_count':len(details),
 'lsli_form_contact_count':form_contacts,'lsli_unavailable_count':len(lsli.get('unavailable_details') or []),
 'direct_tower_account_id_occurrences':len(direct),
 'issue_count':len(issues),'issue_type_counts':dict(Counter(x['type'] for x in issues)),
 'role_boundaries_clean':not issues,
 'boundary':'Served semantic-boundary audit. It proves statewide PWS/operator/LSLI artifacts do not manufacture building/tower assignments or split the combined Section II owner/operator role; source-page value accuracy is a separate source-retrieval gate.'
}
(OUT/'nys-public-water-role-summary.json').write_text(json.dumps(summary,indent=2))
(OUT/'nys-public-water-role-issues.json').write_text(json.dumps(issues,indent=2))
print(json.dumps(summary,indent=2))
