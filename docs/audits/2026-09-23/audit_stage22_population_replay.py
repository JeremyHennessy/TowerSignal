from __future__ import annotations
import concurrent.futures as cf
import datetime as dt
import hashlib,json,time
from collections import Counter,defaultdict
from pathlib import Path
import urllib.parse as up
import urllib.request as ur

OUT=Path('.audit-stage22');OUT.mkdir(exist_ok=True)
LIVE='https://jeremyhennessy.github.io/TowerSignal/'
UA={'User-Agent':'TowerSignal-independent-population-audit/20260923'}
reqs=[]

def save(name,obj):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2,default=str))

def get(url,timeout=90):
    last=None
    for i in range(3):
        rec={'url':url,'attempt':i+1,'at':dt.datetime.now(dt.timezone.utc).isoformat()}
        try:
            with ur.urlopen(ur.Request(url,headers=UA),timeout=timeout) as r:b=r.read();rec.update(status=r.status,bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
            reqs.append(rec);return json.loads(b)
        except Exception as ex:
            rec['error']=str(ex);reqs.append(rec);last=ex;time.sleep(1+i)
    raise RuntimeError(f'{url}: {last}')

def socrata(host,id,where=None,select='*',order=None,page=50000):
    root=f'https://{host}/resource/{id}.json'
    meta0=get(f'https://{host}/api/views/{id}.json')
    rows=[];offset=0
    while True:
        q={'$select':select,'$limit':page,'$offset':offset}
        if where:q['$where']=where
        if order:q['$order']=order
        part=get(root+'?'+up.urlencode(q),120)
        if not isinstance(part,list):raise RuntimeError(f'{id} non-list')
        rows.extend(part)
        if len(part)<page:break
        offset+=page
    meta1=get(f'https://{host}/api/views/{id}.json')
    return rows,{'rows':len(rows),'rows_updated_before':meta0.get('rowsUpdatedAt'),'rows_updated_after':meta1.get('rowsUpdatedAt'),'stable':meta0.get('rowsUpdatedAt')==meta1.get('rowsUpdatedAt')}

systems=get(LIVE+'data/systems.json')['systems']
bins=sorted({str(s.get('bin')) for s in systems if s.get('bin') and str(s.get('bin'))[1:]!='000000'})
bbls=sorted({str(s.get('bbl')) for s in systems if s.get('bbl')})
water=get(LIVE+'data/domestic-water-market.json')
signals=get(LIVE+'data/nyc-water-signals.json')
city=get(LIVE+'data/procurement-city-record.json')

def in_clauses(field,vals,n=150):
    return [f"{field} in ({','.join(repr(v) for v in vals[i:i+n])})" for i in range(0,len(vals),n)]

def scoped_union(host,id,clauses,select,order):
    out=[]; metas=[]
    for w in clauses:
        r,m=socrata(host,id,w,select,order);out.extend(r);metas.append(m)
    return out,{'rows':len(out),'stable':all(m['stable'] for m in metas),'partitions':len(metas)}

results={}

# DOB approved permits: exact collector scope
terms=("lower(job_description) like '%water%' OR lower(job_description) like '%plumb%' OR lower(job_description) like '%backflow%' OR lower(job_description) like '%rpz%' OR lower(job_description) like '%booster%' OR lower(job_description) like '%pump%' OR lower(job_description) like '%tank%'")
where="issued_date >= '2024-01-01T00:00:00.000' AND work_type in ('Plumbing','Mechanical Systems','Boiler Equipment') AND ("+terms+")"
permit_rows,permit_meta=socrata('data.cityofnewyork.us','rbx6-tga4',where,'work_permit,job_filing_number,sequence_number,issued_date,bbl,bin','job_filing_number,work_permit,sequence_number')
served_permits=signals.get('dob_water_permits') or []
src_ids=Counter(str(r.get('work_permit') or '') for r in permit_rows if r.get('work_permit'))
served_ids=Counter(str(r.get('source_record_id') or '') for r in served_permits if r.get('source_record_id'))
results['rbx6-tga4']={'retrieval':permit_meta,'source_rows':len(permit_rows),'served_rows':len(served_permits),'source_rows_with_work_permit':sum(src_ids.values()),'source_unique_work_permits':len(src_ids),'served_unique_source_record_ids':len(served_ids),'work_permit_multiset_equal':src_ids==served_ids,'source_only_ids':list((src_ids-served_ids).elements())[:50],'served_only_ids':list((served_ids-src_ids).elements())[:50]}

# exact-bin DWT self reports and compliance; compare counts by valid BIN
dwt_source_counts={}
for id,key in [('gjm4-k24g','tank_inspections'),('rytv-g5ui','compliance_activity')]:
    rows,meta=scoped_union('data.cityofnewyork.us',id,in_clauses('bin',bins), '*', 'bin')
    source_counts=Counter(str(r.get('bin')) for r in rows if r.get('bin'))
    dwt_source_counts[id]=source_counts
    served=water.get(key) or []
    served_counts=Counter(str(r.get('bin')) for r in served if r.get('bin') and str(r.get('bin')) in set(bins))
    results[id]={'retrieval':meta,'source_rows':len(rows),'served_rows':len(served),'source_bin_count':len(source_counts),'served_bin_count':len(served_counts),'bin_count_maps_equal':source_counts==served_counts,'source_only_count_delta':sum((source_counts-served_counts).values()),'served_only_count_delta':sum((served_counts-source_counts).values()),'delta_bins':sorted(set((source_counts-served_counts)|(served_counts-source_counts)))[:100]}

# façade exact-bin source. Hosted detail comparison is expensive but bounded/current.
facade_rows,facade_meta=scoped_union('data.cityofnewyork.us','xubg-57si',in_clauses('bin',bins),'bin,control_no,sequence_no,filing_type','bin,control_no,sequence_no')
source_facade=Counter(str(r.get('bin')) for r in facade_rows if r.get('bin'))

# Planimetric tower exact-bin source
plan_rows,plan_meta=scoped_union('data.cityofnewyork.us','x748-37q7',in_clauses('bin',bins),'bin,globalid','bin,globalid')
source_plan=Counter(str(r.get('globalid')) for r in plan_rows if r.get('globalid'))

def detail(s):
    sid=str(s['system_id']);return get(LIVE+f"data/details/{sid[:2].lower()}/{sid}.json",60)
with cf.ThreadPoolExecutor(max_workers=10) as pool:
    details=list(pool.map(detail,systems))
# Compare one detail payload per assigned BIN so multiple cooling-tower systems in one building
# do not multiply a single building-level source record.
detail_by_bin={}
for d in details:
    b=str((d.get('identity') or {}).get('bin') or '')
    if b and b not in detail_by_bin:
        detail_by_bin[b]=d

served_facade=Counter()
served_plan=Counter()
served_compliance=Counter()
for b,d in detail_by_bin.items():
    pe=d.get('property_enforcement_context') or {}
    facade=((pe.get('facade_compliance') or {}).get('records') or [])
    served_facade[b]=len(facade)
    for r in d.get('planimetric_building_tower_features') or []:
        gid=str(r.get('global_id') or '')
        if gid:served_plan[gid]+=1
    domestic=d.get('domestic_water') or {}
    served_compliance[b]=len(domestic.get('compliance_history') or [])

results['xubg-57si']={'retrieval':facade_meta,'source_rows':len(facade_rows),'served_unique_bin_context_rows':sum(served_facade.values()),'bin_count_maps_equal':source_facade==served_facade,'delta_source':sum((source_facade-served_facade).values()),'delta_served':sum((served_facade-source_facade).values())}
results['x748-37q7']={'retrieval':plan_meta,'source_rows':len(plan_rows),'served_unique_features':sum(served_plan.values()),'globalid_multiset_equal':source_plan==served_plan,'source_only':list((source_plan-served_plan).elements())[:50],'served_only':list((served_plan-source_plan).elements())[:50]}

# Correct DWT compliance comparison: this source is attached directly to account details,
# not published in the citywide provider/lab market cache.
source_compliance_counts=dwt_source_counts['rytv-g5ui']
results['rytv-g5ui'].update({
  'served_detail_record_count':sum(served_compliance.values()),
  'served_detail_bin_count':sum(1 for v in served_compliance.values() if v),
  'detail_bin_count_maps_equal':source_compliance_counts==served_compliance,
  'detail_source_only_count_delta':sum((source_compliance_counts-served_compliance).values()),
  'detail_served_only_count_delta':sum((served_compliance-source_compliance_counts).values()),
})

# DEC 7G registered businesses
dec_rows,dec_meta=socrata('data.ny.gov','h8u2-6ejg',"lower(pesticide_category_code)='7g'",'*','registration_number')
src_dec=Counter((str(r.get('registration_number') or ''),str(r.get('business_agency_name') or '').strip()) for r in dec_rows)
served_dec=Counter((str(r.get('registration_number') or ''),str(r.get('provider_name') or '').strip()) for r in (water.get('dec_7g_businesses') or []))
results['h8u2-6ejg']={'retrieval':dec_meta,'source_rows':len(dec_rows),'served_rows':sum(served_dec.values()),'registration_name_multiset_equal':src_dec==served_dec,'source_only':list((src_dec-served_dec).elements())[:30],'served_only':list((served_dec-src_dec).elements())[:30]}

# Lead/copper current full sources vs product source-health counts and retained arrays.
for id,key in [('k5us-nav4','free_lead_copper_samples'),('3wxk-qa8q','compliance_lead_copper_samples')]:
    rows,meta=socrata('data.cityofnewyork.us',id,None,'*',None)
    served=water.get(key) or []
    health=next((x for x in water.get('source_health') or [] if x.get('dataset_id')==id),{})
    results[id]={'retrieval':meta,'source_rows':len(rows),'published_raw_array_rows':len(served),'raw_array_published':bool(served),'product_source_health_count':health.get('source_record_count'),'health_count_equal':health.get('source_record_count')==len(rows),'population_acceptance_basis':'SOURCE_HEALTH_COUNT' if not served else 'RAW_ARRAY_AND_SOURCE_HEALTH'}

# City Record declared scopes: reproduce IDs independent of production code.
today=dt.date(2026,9,23)
start=(today-dt.timedelta(days=730)).isoformat()
scopes=[
 ("OPEN",f"type_of_notice_description = 'Solicitation' AND due_date >= '{today.isoformat()}T00:00:00.000' AND due_date < '2099-01-01T00:00:00.000'"),
 ("SENTINEL","type_of_notice_description = 'Solicitation' AND due_date >= '2099-01-01T00:00:00.000'"),
 ("AWARD",f"type_of_notice_description = 'Award' AND start_date >= '{start}T00:00:00.000'")
]
city_rows=[];city_meta=[]
for name,w in scopes:
    r,m=socrata('data.cityofnewyork.us','dg92-zbpx',w,'request_id,type_of_notice_description,start_date,due_date,short_title,category_description,additional_description_1,other_info_1,printout_1','request_id')
    city_rows.extend(r);city_meta.append(m)
src_city_ids=Counter(str(r.get('request_id')) for r in city_rows if r.get('request_id'))
served_city_ids=Counter(str(r.get('source_record_id') or r.get('notice_id') or '') for r in city.get('notices') or [] if r.get('source_record_id') or r.get('notice_id'))
# Served artifact is relevance-filtered, so subset is expected; require every served ID in reproduced scoped universe.
results['dg92-zbpx']={'retrieval':{'rows':len(city_rows),'stable':all(m['stable'] for m in city_meta),'scopes':3},'source_scope_ids':len(src_city_ids),'served_relevant_notice_ids':len(served_city_ids),'served_ids_subset_of_reproduced_scope':not bool(served_city_ids-src_city_ids),'served_ids_outside_scope':list((served_city_ids-src_city_ids).elements())[:50]}

save('population-replay-results.json',results)
save('requests.json',reqs)
summary={'sources_tested':len(results),'all_source_snapshots_stable':all((v.get('retrieval') or {}).get('stable',False) for v in results.values()),'results':{k:{kk:vv for kk,vv in v.items() if kk not in {'source_only_ids','served_only_ids','source_only','served_only','delta_bins'}} for k,v in results.items()}}
save('population-replay-summary.json',summary)
print(json.dumps(summary,indent=2))
