from __future__ import annotations
import concurrent.futures as cf
import datetime as dt
import hashlib,json,re,time
from collections import Counter,defaultdict
from pathlib import Path
import urllib.parse as up
import urllib.request as ur

OUT=Path('.audit-stage27');OUT.mkdir(exist_ok=True)
LIVE='https://jeremyhennessy.github.io/TowerSignal/'
UA={'User-Agent':'TowerSignal-delta-adjudication/20260923'}
REQ=[]

def save(n,x):
    (OUT/n).write_text(json.dumps(x,indent=2,default=str))

def get(url,timeout=120):
    last=None
    for i in range(4):
        rec={'url':url,'attempt':i+1,'at':dt.datetime.now(dt.timezone.utc).isoformat()}
        try:
            with ur.urlopen(ur.Request(url,headers=UA),timeout=timeout) as r:
                b=r.read();rec.update(status=r.status,bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
            REQ.append(rec);return json.loads(b)
        except Exception as ex:
            rec['error']=str(ex);REQ.append(rec);last=ex;time.sleep(min(2**i,8))
    raise RuntimeError(f'{url}: {last}')

def query(id,where,select,order=None,page=50000):
    root=f'https://data.cityofnewyork.us/resource/{id}.json'
    rows=[];off=0
    while True:
        q={'$select':select,'$where':where,'$limit':page,'$offset':off}
        if order:q['$order']=order
        p=get(root+'?'+up.urlencode(q))
        if not isinstance(p,list):raise RuntimeError(f'{id} non-list')
        rows.extend(p)
        if len(p)<page:break
        off+=page
    return rows

def in_clauses(field,vals,n=150):
    return [f"{field} in ({','.join(repr(v) for v in vals[i:i+n])})" for i in range(0,len(vals),n)]

systems_payload=get(LIVE+'data/systems.json')
systems=systems_payload['systems']
bins=sorted({str(s.get('bin')) for s in systems if s.get('bin') and len(str(s.get('bin')))==7 and str(s.get('bin'))[1:]!='000000'})
binset=set(bins)
signals=get(LIVE+'data/nyc-water-signals.json')
water=get(LIVE+'data/domestic-water-market.json')
served_generated=str(signals.get('generated_at') or '')
served_date=served_generated[:10]
prior_hpd=json.loads(Path('docs/audits/2026-09-23/stage23-heavy-populations/heavy-population-results.json').read_text())['wvxf-dwi5']

# HPD: inspect current records for every delta ID, without the open/water filter.
delta_ids=sorted(set(prior_hpd['source_only_ids'])|set(prior_hpd['served_only_ids']),key=int)
hpd=[]
for clause in in_clauses('violationid',delta_ids,100):
    hpd.extend(query('wvxf-dwi5',clause,'violationid,bbl,bin,boro,inspectiondate,approveddate,novissueddate,novdescription,currentstatus,currentstatusdate,violationstatus,rentimpairing','violationid',5000))
by_id={str(r.get('violationid')):r for r in hpd}
water_terms=('HOT WATER','WATER SUPPLY','POTABLE','PLUMBING','FAUCET','SINK','TOILET','SHOWER','BATHTUB','WATER CLOSET')
def still_water(r):
    d=str(r.get('novdescription') or '').upper()
    return any(t in d for t in water_terms)
def dates(r):
    return [str(r.get(k) or '')[:10] for k in ('inspectiondate','approveddate','novissueddate','currentstatusdate') if str(r.get(k) or '')[:10]]
def after_build(r):
    return any(d>served_date for d in dates(r)) if served_date else False

hpd_class=Counter();hpd_records=[]
for vid in delta_ids:
    r=by_id.get(vid)
    prior_side='SOURCE_ONLY_CURRENT_OPEN' if vid in set(prior_hpd['source_only_ids']) else 'SERVED_ONLY'
    if not r:
        cls='REMOVED_FROM_CURRENT_SOURCE'
    elif prior_side=='SERVED_ONLY':
        if str(r.get('violationstatus') or '').upper()!='OPEN':
            cls='SERVED_SNAPSHOT_NOW_CLOSED'
        elif not still_water(r):
            cls='SERVED_SNAPSHOT_NO_LONGER_MATCHES_WATER_FILTER'
        elif after_build(r):
            cls='SERVED_SNAPSHOT_CURRENT_ROW_CHANGED_AFTER_BUILD'
        else:
            cls='SERVED_ONLY_UNEXPLAINED_CURRENT_OPEN_WATER'
    else:
        if after_build(r):
            cls='CURRENT_OPEN_ADDED_OR_CHANGED_AFTER_BUILD_BY_SOURCE_DATE'
        else:
            cls='CURRENT_ONLY_EVENT_DATES_NOT_AFTER_BUILD'
    hpd_class[cls]+=1
    hpd_records.append({'violation_id':vid,'prior_side':prior_side,'classification':cls,'served_build_generated_at':served_generated,'source_row':r})

# DWT: exact target-bin identities, not citywide served-array total.
source_dwt=[]
for clause in in_clauses('bin',bins):
    source_dwt.extend(query('gjm4-k24g',clause,'*','bin,reporting_year,tank_num,inspection_date'))
def norm_space(v): return re.sub(r'\s+',' ',str(v or '').strip())
BORO={'MANHATTAN':'1','NEW YORK':'1','BRONX':'2','BROOKLYN':'3','QUEENS':'4','STATEN ISLAND':'5'}
def bbl(row):
    b=BORO.get(norm_space(row.get('borough')).upper())
    block=re.sub(r'\D','',norm_space(row.get('block')));lot=re.sub(r'\D','',norm_space(row.get('lot')))
    if not b or not block or not lot:return None
    x,y=int(block),int(lot)
    if not (1<=x<=99999 and 1<=y<=9999):return None
    return f'{b}{x:05d}{y:04d}'
def sid(prefix,*parts):
    material='|'.join(norm_space(x) for x in parts)
    return f"{prefix}-{hashlib.sha256(material.encode()).hexdigest()[:20]}"
def dwt_id(r):
    bb=bbl(r)
    return sid('dwt-inspection',r.get('bin'),bb,norm_space(r.get('reporting_year')) or None,norm_space(r.get('tank_num')) or None,
               r.get('inspection_date'),norm_space(r.get('inspection_by_firm')) or None,norm_space(r.get('lab_name')) or None)

src_dwt={dwt_id(r):r for r in source_dwt if str(r.get('bin') or '') in binset}
served_target={str(r.get('inspection_id')):r for r in (water.get('tank_inspections') or []) if str(r.get('bin') or '') in binset and r.get('inspection_id')}
src_only=sorted(set(src_dwt)-set(served_target));served_only=sorted(set(served_target)-set(src_dwt))
dwt_missing=[]
for ident in src_only:
    r=src_dwt[ident]
    date=str(r.get('inspection_date') or '')[:10]
    dwt_missing.append({'inspection_id':ident,'bin':r.get('bin'),'reporting_year':r.get('reporting_year'),'tank_num':r.get('tank_num'),
                        'inspection_date':r.get('inspection_date'),'after_served_build_date':bool(date and served_date and date>served_date),
                        'source_row':r})

# Facade: prove raw-row delta is composite-identity dedupe or expose real set difference.
source_facade=[]
for clause in in_clauses('bin',bins):
    source_facade.extend(query('xubg-57si',clause,'bin,control_no,sequence_no,filing_type,submitted_on,current_status','bin,control_no,sequence_no,filing_type'))
def facade_id(r):
    return f"{r.get('bin') or ''}|{r.get('control_no') or ''}|{r.get('sequence_no') or ''}|{r.get('filing_type') or ''}"
src_facade=Counter(facade_id(r) for r in source_facade)
src_unique=set(src_facade)
dup_extra=sum(n-1 for n in src_facade.values() if n>1)

def detail(s):
    x=str(s['system_id']);return get(LIVE+f"data/details/{x[:2].lower()}/{x}.json",60)
detail_by_bin={}
with cf.ThreadPoolExecutor(max_workers=10) as pool:
    for d in pool.map(detail,systems):
        b=str((d.get('identity') or {}).get('bin') or '')
        if b and b not in detail_by_bin:detail_by_bin[b]=d
served_facade={}
for b,d in detail_by_bin.items():
    recs=(((d.get('property_enforcement_context') or {}).get('facade_compliance') or {}).get('records') or [])
    for r in recs:
        served_facade[f"{b}|{r.get('control_no') or ''}|{r.get('sequence_no') or ''}|{r.get('filing_type') or ''}"]=r
facade_src_only=sorted(src_unique-set(served_facade));facade_served_only=sorted(set(served_facade)-src_unique)

summary={
 'served_build_generated_at':served_generated,
 'hpd':{
   'delta_ids':len(delta_ids),'current_records_found':len(by_id),'class_counts':dict(hpd_class),
   'fully_explained_by_lifecycle_or_post_build':all(k not in hpd_class for k in ['SERVED_ONLY_UNEXPLAINED_CURRENT_OPEN_WATER','CURRENT_ONLY_EVENT_DATES_NOT_AFTER_BUILD'])
 },
 'dwt':{
   'source_target_rows':len(source_dwt),'source_unique_normalized_ids':len(src_dwt),
   'served_citywide_rows':len(water.get('tank_inspections') or []),'served_target_rows':len(served_target),
   'source_only_ids':len(src_only),'served_only_ids':len(served_only),
   'source_only_after_build_by_inspection_date':sum(1 for r in dwt_missing if r['after_served_build_date'])
 },
 'facade':{
   'source_raw_rows':len(source_facade),'source_unique_composite_identities':len(src_unique),'duplicate_raw_row_excess':dup_extra,
   'served_unique_composite_identities':len(served_facade),'identity_sets_equal':src_unique==set(served_facade),
   'source_only_identities':len(facade_src_only),'served_only_identities':len(facade_served_only)
 }
}
save('delta-adjudication-summary.json',summary)
save('hpd-delta-lifecycle.json',hpd_records)
save('dwt-target-identity-delta.json',{'source_only':dwt_missing,'served_only':[served_target[x] for x in served_only[:100]],'source_only_ids':src_only,'served_only_ids':served_only})
save('facade-identity-delta.json',{'duplicate_examples':[{'identity':k,'count':v} for k,v in src_facade.items() if v>1][:200],
                                  'source_only':facade_src_only[:500],'served_only':facade_served_only[:500]})
save('requests.json',REQ)
print(json.dumps(summary,indent=2))
