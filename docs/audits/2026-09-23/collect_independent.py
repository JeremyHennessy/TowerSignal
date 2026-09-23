"""Read-only audit evidence collector; never imports production normalizers or writes production.
Run from repository root with AUDIT_OUTPUT and optional GH_TOKEN. Every failed read is
recorded as failure, never zero. Official rows retain publisher :id and selected '*'.
"""
from __future__ import annotations
import concurrent.futures as cf
import datetime as dt
from decimal import Decimal, InvalidOperation
import gzip, hashlib, json, os, re, threading, time
from pathlib import Path
import urllib.request as ur
import urllib.parse as up
E=Path(os.getenv('AUDIT_OUTPUT','.audit-stage2')); E.mkdir(parents=True,exist_ok=True)
LIVE='https://jeremyhennessy.github.io/TowerSignal/'
API='https://api.github.com/repos/JeremyHennessy/TowerSignal'
requests=[]; lock=threading.Lock()
def save(name,obj):
    p=E/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str))
def gz(name,obj):
    with gzip.open(E/name,'wt') as f: json.dump(obj,f,ensure_ascii=False)
def get(url,timeout=75,raw=False):
    headers={'User-Agent':'TowerSignal-independent-audit/20260923'}
    if url.startswith('https://api.github.com/') and os.getenv('GH_TOKEN'):
        headers['Authorization']='Bearer '+os.environ['GH_TOKEN']
    for attempt in range(3):
        rec={'url':url,'requested_at':dt.datetime.now(dt.timezone.utc).isoformat(),'attempt':attempt+1}
        try:
            with ur.urlopen(ur.Request(url,headers=headers),timeout=timeout) as r:
                data=r.read();rec.update(status=r.status,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),headers={k:v for k,v in r.headers.items() if k.lower() in ('date','etag','last-modified','content-type','cache-control')})
            with lock: requests.append(rec)
            return data if raw else json.loads(data)
        except Exception as ex:
            code=getattr(ex,'code',None);rec.update(error=str(ex),status=code)
            with lock: requests.append(rec)
            if code not in (429,500,502,503,504) or attempt==2:return {'_audit_error':str(ex),'url':url}
            time.sleep(2*(attempt+1))
def numeric(v,length=None):
    try:
        n=Decimal(str(v).strip())
        if not n.is_finite() or n!=n.to_integral_value() or n<=0:return None
        s=str(int(n));return s if length is None or len(s)==length else None
    except (InvalidOperation,ValueError):return None
def assigned_bin(v):
    s=numeric(v,7);return s if s and s[0] in '12345' and s[1:]!='000000' else None
def bbl(v):
    s=numeric(v,10);return s if s and s[0] in '12345' and int(s[1:6])>0 and int(s[6:])>0 else None
def full_source(ident,clauses=None,domain='data.cityofnewyork.us'):
    base=f'https://{domain}/resource/{ident}.json';q=lambda p:base+'?'+up.urlencode(p)
    before=get(f'https://{domain}/api/views/{ident}.json'); save(f'{ident}-metadata-before.json',before)
    rows=[]; scopes=[]
    for where in clauses or ['1=1']:
        count=get(q({'$select':'count(*) as n','$where':where})); found=[]; offset=0; completed=True
        while True:
            page=get(q({'$select':'*,:id as audit_row_id','$where':where,'$order':':id','$limit':50000,'$offset':offset}),timeout=100)
            if not isinstance(page,list):completed=False;break
            found.extend(page)
            if len(page)<50000:break
            offset+=50000
        after_count=get(q({'$select':'count(*) as n','$where':where}))
        n=int(count[0]['n']) if isinstance(count,list) and count else None
        n2=int(after_count[0]['n']) if isinstance(after_count,list) and after_count else None
        ids=[r.get('audit_row_id') for r in found]
        scopes.append({'where':where,'expected_before':n,'expected_after':n2,'retrieved':len(found),'pagination_completed':completed,'unique_row_ids':len(set(ids)),'count_and_ids_pass':completed and n==n2==len(found)==len(set(ids))})
        rows.extend(found)
    after=get(f'https://{domain}/api/views/{ident}.json');save(f'{ident}-metadata-after.json',after)
    unique={r.get('audit_row_id') or json.dumps(r,sort_keys=True):r for r in rows}
    rows=list(unique.values());gz(f'{ident}-raw.json.gz',rows)
    result={'dataset_id':ident,'domain':domain,'scopes':scopes,'unique_rows':len(rows),'source_updated_before':before.get('rowsUpdatedAt'),'source_updated_after':after.get('rowsUpdatedAt'),'retrieval':'COMPLETE' if all(s['count_and_ids_pass'] for s in scopes) and before.get('rowsUpdatedAt')==after.get('rowsUpdatedAt') and 'columns' in before else 'PARTIAL_OR_UNSTABLE'}
    save(f'{ident}-retrieval.json',result);print('OFFICIAL',ident,len(rows),result['retrieval'],flush=True)
    return rows
start=dt.datetime.now(dt.timezone.utc).isoformat()
systems_bytes=get(LIVE+'data/systems.json',raw=True)
if not isinstance(systems_bytes,bytes):raise RuntimeError('Hosted system universe unavailable; do not infer empty universe')
(E/'systems-before.json').write_bytes(systems_bytes)
systems=json.loads(systems_bytes)['systems']; bins={v for s in systems if (v:=assigned_bin(s.get('bin')))}
bbls={v for s in systems for x in [s.get('bbl'),s.get('registry_bbl'),s.get('property_bbl'),*(s.get('bbl_aliases') or [])] if (v:=bbl(x))}
summary={'started_at':start,'system_count':len(systems),'assigned_bins':len(bins),'bbls_including_aliases':len(bbls),'systems_before_sha256':hashlib.sha256(systems_bytes).hexdigest()}
# Capture all currently served NYC details, plus actual API root datasets discovered in source.
def fetch_hosted(rel):
    value=get(LIVE+rel,raw=True)
    if isinstance(value,bytes):
        p=E/'hosted'/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(value)
        return {'path':rel,'sha256':hashlib.sha256(value).hexdigest(),'bytes':len(value),'status':'FETCHED'}
    return {'path':rel,'status':'FAILED','error':value}
roots={'data/systems.json','data/metadata.json','data/nys-systems.json','data/nys-metadata.json','data/source-health.json','data/coverage-audit.json','data/verification.json','data/changes.json','data/nys-changes.json','data/companies.json','data/known-firms.json','data/property-enforcement.json','data/nyc-water-signals.json','data/domestic-water-market.json','data/cms-institutional-context.json','data/legacy-dob-projects.json','data/legionella-alerts.json','data/legionella-property-matches.json','data/procurement-city-record.json','data/procurement-checkbook.json','data/procurement-nys-authorities.json','data/procurement-openbook-water.json','data/procurement-nycha-water.json','data/nyc-distribution-water.json','data/nys-public-water.json','data/nys-lsli-details.json','data/nys-service-line-inventory-summary.json','data/provider-resolution-review.json','data/labor-law-decisions.json','data/elap-source-probe.json','data/historical-311-context.json','data/priority-model-review.json','data/deal-validation.json'}
rels=sorted(roots)+[f"data/details/{str(s['system_id'])[:2].lower()}/{s['system_id']}.json" for s in systems]
# Independent per-source jobs can proceed while the hosted crawl runs.
def host_all():
    with cf.ThreadPoolExecutor(max_workers=8) as pool:out=list(pool.map(fetch_hosted,rels))
    save('hosted-manifest.json',out);print('HOSTED_FULL_POPULATION',len(out),'failed',sum(r['status']=='FAILED' for r in out),flush=True)
    return out
def identity_sources():
    regs=full_source('tesw-yqqr');eligible=[];registration_ids=set()
    for row in regs:
        try: rbbl=bbl(f"{int(row.get('boroid',0))}{int(row.get('block',0)):05d}{int(row.get('lot',0)):04d}")
        except (ValueError,TypeError):rbbl=None
        if assigned_bin(row.get('bin')) in bins or rbbl in bbls:
            eligible.append(row)
            if rid:=numeric(row.get('registrationid')):registration_ids.add(rid)
    gz('hpd-all-exact-candidate-registrations.json.gz',eligible)
    ids=sorted(registration_ids,key=int)
    save('hpd-queried-identity-universe.json',{'bins':sorted(bins),'bbls':sorted(bbls),'registration_ids':ids,'candidate_registration_rows':len(eligible),'basis':'UNION of all independently valid exact building and parcel keys; not a production selection; not all candidates are safe confirmed attachments'})
    clauses=[f"registrationid in ({','.join(ids[i:i+250])})" for i in range(0,len(ids),250)]
    if clauses:full_source('feu5-w2e2',clauses)
def properties():
    bs=sorted(bins);ps=sorted(bbls)
    full_source('5zhs-2jue',[f"bin in ({','.join(bs[i:i+150])})" for i in range(0,len(bs),150)])
    full_source('64uk-42ks',[f"bbl in ({','.join(ps[i:i+150])})" for i in range(0,len(ps),150)])
with cf.ThreadPoolExecutor(max_workers=3) as pool:
    futures={pool.submit(host_all):'hosted',pool.submit(identity_sources):'hpd',pool.submit(properties):'properties'}
    for f,name in list(futures.items()):
        try:f.result();summary[name]='COLLECTION_FINISHED'
        except Exception as ex:summary[name]={'error':str(ex)}
after=get(LIVE+'data/systems.json',raw=True)
if isinstance(after,bytes):
    (E/'systems-after.json').write_bytes(after);summary['systems_after_sha256']=hashlib.sha256(after).hexdigest();summary['hosted_summary_stable']=after==systems_bytes
else:summary['hosted_summary_stable']=False
for name,path in [('main','/branches/main'),('active-runs','/actions/runs?status=in_progress&per_page=100'),('deployments','/deployments?per_page=10')]:save(name+'.json',get(API+path))
summary['finished_at']=dt.datetime.now(dt.timezone.utc).isoformat();save('collection-summary.json',summary);save('requests.json',requests)
print('COLLECTION_SUMMARY',json.dumps(summary),flush=True)
