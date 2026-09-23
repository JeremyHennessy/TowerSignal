from __future__ import annotations
import hashlib,json,re
from collections import Counter,defaultdict
from pathlib import Path
import urllib.request as ur

OUT=Path('.audit-stage38');OUT.mkdir(exist_ok=True)
LIVE='https://jeremyhennessy.github.io/TowerSignal/'
GENERIC={"WATER","ENVIRONMENTAL","SERVICES","SERVICE","SOLUTIONS","SYSTEMS","GROUP","TECHNOLOGIES","TECHNOLOGY","INDUSTRIAL","MECHANICAL","CHEMICAL"}
def get(name):
    with ur.urlopen(ur.Request(LIVE+'data/'+name,headers={'User-Agent':'TowerSignal-company-identity-invariant-audit/20260923'}),timeout=120) as r:
        b=r.read();return json.loads(b),hashlib.sha256(b).hexdigest()
payload,sha=get('companies.json')
companies=payload.get('companies') or [];unresolved=payload.get('unresolved_vendor_observations') or []
issues=[]
ids=[str(c.get('company_id') or '') for c in companies]
if len(ids)!=len(set(ids)):issues.append({'type':'DUPLICATE_COMPANY_ID'})
strict=[str(c.get('strict_vendor_key') or '') for c in companies]
if len([x for x in strict if x])!=len(set(x for x in strict if x)):issues.append({'type':'DUPLICATE_STRICT_VENDOR_KEY'})
by_base=defaultdict(list)
for c in companies:by_base[str(c.get('normalized_base_name') or '')].append(c)
proc_owner={}
for c in companies:
    cid=str(c.get('company_id'))
    base=str(c.get('normalized_base_name') or '')
    peers={str(x.get('company_id')) for x in by_base[base]}-{cid}
    cand=set(map(str,c.get('candidate_related_company_ids') or []))
    toks=base.split();amb=bool(not toks or len(toks)<2 or all(t in GENERIC for t in toks))
    if peers:
        if c.get('cross_source_resolution_confidence')!='VERIFY':
            issues.append({'type':'LEGAL_SUFFIX_OR_SOURCE_VARIANT_NOT_VERIFY','company_id':cid,'base':base,'confidence':c.get('cross_source_resolution_confidence')})
        if cand!=peers:
            issues.append({'type':'CANDIDATE_RELATED_COMPANY_SET_MISMATCH','company_id':cid,'expected':sorted(peers),'actual':sorted(cand)})
    if amb:
        if c.get('identity_confidence')!='VERIFY' or c.get('cross_source_resolution_confidence')!='VERIFY':
            issues.append({'type':'AMBIGUOUS_BASE_NOT_VERIFY','company_id':cid,'base':base,'identity':c.get('identity_confidence'),'cross':c.get('cross_source_resolution_confidence')})
    for a in c.get('aliases') or []:
        conf=str(a.get('confidence') or '');method=str(a.get('resolution_method') or '')
        if conf=='CONFIRMED' and method!='EXPLICIT_SOURCE_DBA_ALIAS':
            issues.append({'type':'CONFIRMED_ALIAS_WITHOUT_EXPLICIT_DBA_BASIS','company_id':cid,'alias':a.get('alias'),'method':method})
        if method=='EXPLICIT_SOURCE_DBA_ALIAS' and conf!='CONFIRMED':
            issues.append({'type':'EXPLICIT_DBA_NOT_CONFIRMED','company_id':cid,'alias':a.get('alias'),'confidence':conf})
    for pid in c.get('procurement_ids') or []:
        p=str(pid)
        if p in proc_owner and proc_owner[p]!=cid:
            issues.append({'type':'PROCUREMENT_OBSERVATION_ASSIGNED_TO_MULTIPLE_COMPANIES','procurement_id':p,'companies':[proc_owner[p],cid]})
        proc_owner[p]=cid

review_company_ids={str(c.get('company_id')) for c in companies if c.get('cross_source_resolution_confidence')=='VERIFY'}
unresolved_company_ids={str(r.get('observed_company_id')) for r in unresolved if r.get('observed_company_id')}
missing_review=sorted(review_company_ids-unresolved_company_ids)
if missing_review:issues.append({'type':'VERIFY_COMPANIES_MISSING_UNRESOLVED_OBSERVATIONS','company_ids':missing_review[:100]})
unexpected=sorted(unresolved_company_ids-review_company_ids)
if unexpected:issues.append({'type':'UNRESOLVED_OBSERVATION_FOR_NONVERIFY_COMPANY','company_ids':unexpected[:100]})

summary={
 'companies_sha256':sha,'company_count':len(companies),'procurement_observation_ids':len(proc_owner),
 'verify_company_count':len(review_company_ids),'unresolved_observation_count':len(unresolved),
 'explicit_dba_alias_count':sum(1 for c in companies for a in c.get('aliases') or [] if a.get('resolution_method')=='EXPLICIT_SOURCE_DBA_ALIAS'),
 'confirmed_alias_count':sum(1 for c in companies for a in c.get('aliases') or [] if a.get('confidence')=='CONFIRMED'),
 'base_names_with_multiple_strict_companies':sum(len(v)>1 for v in by_base.values()),
 'issue_count':len(issues),'issue_type_counts':dict(Counter(x['type'] for x in issues)),
 'identity_invariants_clean':not issues,
 'boundary':'Served company-identity invariant audit. It proves the generated company graph obeys conservative strict-label/DBA rules; it does not independently verify corporate parentage or external company-master enrichment.'
}
(OUT/'company-identity-summary.json').write_text(json.dumps(summary,indent=2))
(OUT/'company-identity-issues.json').write_text(json.dumps(issues,indent=2))
print(json.dumps(summary,indent=2))
