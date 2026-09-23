from __future__ import annotations
import json,hashlib,time
from collections import Counter
from pathlib import Path
import urllib.request as ur

OUT=Path('.audit-stage32');OUT.mkdir(exist_ok=True)
LIVE='https://jeremyhennessy.github.io/TowerSignal/'
UA={'User-Agent':'TowerSignal-procurement-relationship-audit/20260923'}
REQ=[]
def get(path,optional=False):
    url=LIVE+'data/'+path
    try:
        with ur.urlopen(ur.Request(url,headers=UA),timeout=120) as r:
            b=r.read();REQ.append({'url':url,'status':r.status,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()});return json.loads(b)
    except Exception as ex:
        if optional:
            REQ.append({'url':url,'error':type(ex).__name__});return None
        raise

systems=get('systems.json'); system_ids={str(x['system_id']) for x in systems['systems']}
companies=get('companies.json'); company_ids={str(x['company_id']) for x in companies.get('companies') or []}
artifacts=[
 ('NYC_CITY_RECORD',get('procurement-city-record.json').get('notices') or []),
 ('CHECKBOOK_NYC',get('procurement-checkbook.json').get('contracts') or []),
 ('NYS_AUTHORITIES',(get('procurement-nys-authorities.json',True) or {}).get('contracts') or []),
 ('OPEN_BOOK_NY',(get('procurement-openbook-water.json',True) or {}).get('contracts') or []),
 ('NYCHA',(get('procurement-nycha-water.json',True) or {}).get('records') or []),
]

issues=[];stats={};role_edges=[]
for source,rows in artifacts:
    c=Counter()
    for r in rows:
        c['rows']+=1
        conf=str(r.get('tower_link_confidence') or 'MISSING')
        ids=[str(x) for x in (r.get('tower_account_system_ids') or []) if x]
        ids_unique=sorted(set(ids))
        if conf in {'CONFIRMED','STRONG'}:
            c['tower_link_positive']+=1
            if not ids_unique:
                issues.append({'source':source,'type':'POSITIVE_TOWER_CONFIDENCE_WITHOUT_EXPLICIT_SYSTEM_IDS','record_id':r.get('procurement_id') or r.get('source_record_id'),'confidence':conf})
            missing=sorted(set(ids_unique)-system_ids)
            if missing:
                issues.append({'source':source,'type':'TOWER_SYSTEM_ID_NOT_IN_CURRENT_SYSTEM_UNIVERSE','record_id':r.get('procurement_id') or r.get('source_record_id'),'missing':missing})
            if r.get('vendor_raw'):
                for sid in ids_unique:
                    role_edges.append((source,str(r.get('procurement_id') or r.get('source_record_id')),sid,str(r.get('vendor_raw')),conf))
        elif ids_unique:
            c['explicit_ids_without_positive_confidence']+=1
        comp_conf=str(r.get('company_match_confidence') or '')
        company_id=str(r.get('company_id') or '')
        if comp_conf in {'CONFIRMED','STRONG'}:
            c['company_link_positive']+=1
            if not company_id:
                issues.append({'source':source,'type':'POSITIVE_COMPANY_CONFIDENCE_WITHOUT_COMPANY_ID','record_id':r.get('procurement_id') or r.get('source_record_id'),'confidence':comp_conf})
            elif company_id not in company_ids:
                issues.append({'source':source,'type':'COMPANY_ID_NOT_IN_CURRENT_COMPANY_MASTER','record_id':r.get('procurement_id') or r.get('source_record_id'),'company_id':company_id})
        # Strong invariant: a record cannot claim explicit tower linkage to a system outside current universe.
        if len(ids)!=len(ids_unique):
            issues.append({'source':source,'type':'DUPLICATE_TOWER_SYSTEM_IDS','record_id':r.get('procurement_id') or r.get('source_record_id'),'ids':ids})
    stats[source]=dict(c)

summary={
 'artifacts':len(artifacts),
 'system_universe':len(system_ids),
 'company_master_count':len(company_ids),
 'records_checked':sum(len(rows) for _,rows in artifacts),
 'source_stats':stats,
 'procurement_role_edges_emittable':len(role_edges),
 'unique_role_edges':len(set(role_edges)),
 'issue_count':len(issues),
 'issue_type_counts':dict(Counter(x['type'] for x in issues)),
 'system_id_explicit_gate_valid':not any(x['type'] in {'POSITIVE_TOWER_CONFIDENCE_WITHOUT_EXPLICIT_SYSTEM_IDS','TOWER_SYSTEM_ID_NOT_IN_CURRENT_SYSTEM_UNIVERSE'} for x in issues),
 'company_link_gate_valid':not any(x['type'] in {'POSITIVE_COMPANY_CONFIDENCE_WITHOUT_COMPANY_ID','COMPANY_ID_NOT_IN_CURRENT_COMPANY_MASTER'} for x in issues),
 'boundary':'Artifact relationship invariant audit. This proves explicit IDs/confidence are internally consistent in served artifacts; it does not independently prove how every upstream procurement facility/tower link was derived from publisher records.'
}
(OUT/'procurement-relationship-summary.json').write_text(json.dumps(summary,indent=2))
(OUT/'procurement-relationship-issues.json').write_text(json.dumps(issues,indent=2))
(OUT/'procurement-role-edge-sample.json').write_text(json.dumps([{'source':a,'record_id':b,'system_id':c,'vendor_raw':d,'confidence':e} for a,b,c,d,e in role_edges[:1000]],indent=2))
(OUT/'requests.json').write_text(json.dumps(REQ,indent=2))
print(json.dumps(summary,indent=2))
