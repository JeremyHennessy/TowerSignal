from __future__ import annotations
import datetime as dt, hashlib,json,re,time
from collections import Counter,defaultdict
from pathlib import Path
import urllib.parse as up
import urllib.request as ur

OUT=Path('.audit-stage24');OUT.mkdir(exist_ok=True)
LIVE='https://jeremyhennessy.github.io/TowerSignal/'
UA={'User-Agent':'TowerSignal-independent-historical-population-audit/20260923'}
REQ=[]
def save(n,x):
    p=OUT/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,default=str))
def get(url,timeout=150):
    last=None
    for i in range(4):
        rec={'url':url,'attempt':i+1,'at':dt.datetime.now(dt.timezone.utc).isoformat()}
        try:
            with ur.urlopen(ur.Request(url,headers=UA),timeout=timeout) as r:b=r.read();rec.update(status=r.status,bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
            REQ.append(rec);return json.loads(b)
        except Exception as ex:
            rec['error']=str(ex);REQ.append(rec);last=ex;time.sleep(min(2**i,8))
    raise RuntimeError(f'{url}: {last}')
def metadata(id):
    return get(f'https://data.cityofnewyork.us/api/views/{id}.json')
def pages(id,where,select,order,page=5000):
    root=f'https://data.cityofnewyork.us/resource/{id}.json';rows=[];off=0
    while True:
        q={'$select':select,'$where':where,'$order':order,'$limit':page,'$offset':off}
        part=get(root+'?'+up.urlencode(q),180)
        if not isinstance(part,list):raise RuntimeError(f'{id} non-list')
        rows.extend(part)
        if len(part)<page:break
        off+=page
        if off>500000:raise RuntimeError(f'{id} partition too large')
    return rows
def norm_bbl(v):
    s=''.join(c for c in str(v or '') if c.isdigit())
    return s if len(s)==10 and s[0] in '12345' and int(s[1:6])>0 and int(s[6:])>0 else None

systems_payload=get(LIVE+'data/systems.json')
systems=systems_payload['systems']
aliases=sorted({b for s in systems for v in (s.get('bbl_aliases') or [s.get('bbl')]) if (b:=norm_bbl(v))},key=int)
alias_set=set(aliases)
snapshot_date=dt.date.fromisoformat(str((systems_payload.get('metadata') or {}).get('snapshot_date') or '2026-09-23')[:10])
results={}

# Legacy DOB/BIS exact BBL population + independent retention.
BORO={'1':'MANHATTAN','2':'BRONX','3':'BROOKLYN','4':'QUEENS','5':'STATEN ISLAND'}
def clause(b):
    return f"(borough='{BORO[b[0]]}' AND block='{b[1:6]}' AND lot='{int(b[6:]):05d}')"
def text(v):
    s=str(v or '').strip();return s or None
def flag(v):return str(v or '').strip().upper() in {'X','Y','YES','TRUE','1'}
def dateval(v):
    s=text(v)
    if not s:return None
    for fmt in ('%m/%d/%Y','%Y-%m-%dT%H:%M:%S.%f','%Y-%m-%dT%H:%M:%S','%Y-%m-%d'):
        try:return dt.datetime.strptime(s,fmt).date().isoformat()
        except ValueError:pass
    return None
def row_bbl(r):
    br=str(r.get('borough') or '').strip().upper()
    code=next((k for k,v in BORO.items() if v==br), br if br in BORO else None)
    bd=''.join(c for c in str(r.get('block') or '') if c.isdigit())
    ld=''.join(c for c in str(r.get('lot') or '') if c.isdigit())
    if not code or not bd or not ld:return None
    return norm_bbl(f'{code}{int(bd):05d}{int(ld):04d}')
sel="job_s1_no,job__,doc__,borough,block,lot,bin__,job_type,job_status,job_status_descrp,latest_action_date,plumbing,mechanical,boiler,equipment,other,other_description,applicant_s_first_name,applicant_s_last_name,applicant_professional_title,applicant_license__,pre__filing_date,approved,fully_permitted,signoff_date,initial_cost,owner_s_business_name,job_description"
m0=metadata('ic3t-wcy2');raw=[];matched_bbl=set()
for i in range(0,len(aliases),30):
    batch=aliases[i:i+30]
    part=pages('ic3t-wcy2',' OR '.join(clause(b) for b in batch),sel,'borough,block,lot,job_s1_no',50000)
    raw.extend(part)
m1=metadata('ic3t-wcy2')
retained=defaultdict(dict)
for r in raw:
    b=row_bbl(r)
    if b not in alias_set:continue
    matched_bbl.add(b)
    desc=text(r.get('job_description'));other=text(r.get('other_description'))
    explicit=bool(re.search(r'\bcooling\s+towers?\b',' '.join(x for x in [desc,other] if x),re.I))
    mech,boil,plumb,equip=map(flag,[r.get('mechanical'),r.get('boiler'),r.get('plumbing'),r.get('equipment')])
    dates=[x for x in [dateval(r.get('pre__filing_date')),dateval(r.get('approved')),dateval(r.get('fully_permitted')),dateval(r.get('signoff_date')),dateval(r.get('latest_action_date'))] if x]
    activity=max(dates) if dates else None
    recent=False
    if activity:
        age=(snapshot_date-dt.date.fromisoformat(activity)).days
        recent=0<=age<=1095 and (mech or boil or plumb or equip)
    if not explicit and not recent:continue
    ident=text(r.get('job_s1_no')) or f"{text(r.get('job__'))}:{text(r.get('doc__'))}"
    retained[b][str(ident)]={'activity_date':activity,'explicit':explicit,'recent':recent}
served_legacy=get(LIVE+'data/legacy-dob-projects.json')
served_ids=Counter()
for b,v in (served_legacy.get('by_bbl') or {}).items():
    for r in v.get('records') or []:
        ident=str(r.get('source_row_id') or f"{r.get('job_number')}:{r.get('document_number')}")
        served_ids[(b,ident)]+=1
src_ids=Counter((b,i) for b,m in retained.items() for i in m)
results['ic3t-wcy2']={
 'source_snapshot_stable':m0.get('rowsUpdatedAt')==m1.get('rowsUpdatedAt'),'requested_bbl_aliases':len(aliases),
 'source_exact_bbl_rows':len(raw),'source_matched_bbls':len(matched_bbl),'independently_retained_rows':sum(src_ids.values()),
 'served_retained_rows':sum(served_ids.values()),'retained_identity_multiset_equal':src_ids==served_ids,
 'source_only_retained_count':sum((src_ids-served_ids).values()),'served_only_retained_count':sum((served_ids-src_ids).values()),
 'source_only_examples':[list(x) for x in list((src_ids-served_ids).elements())[:50]],
 'served_only_examples':[list(x) for x in list((served_ids-src_ids).elements())[:50]]
}

# Historical 311 exact-BBL aggregation 2010-2024.
water="(lower(complaint_type) like '%water%' OR lower(descriptor) like '%water%' OR lower(descriptor_2) like '%water%' OR lower(complaint_type) like '%lead%' OR lower(descriptor) like '%lead%' OR lower(descriptor_2) like '%lead%')"
periods=[('76ig-c548','2010-01-01T00:00:00.000','2020-01-01T00:00:00.000'),('erm2-nwe9','2020-01-01T00:00:00.000','2025-01-01T00:00:00.000')]
metas={id:metadata(id) for id,_,_ in periods};profiles=defaultdict(lambda:{'request_count':0,'categories':Counter(),'years':set(),'first':None,'latest':None});seen=set();source_rows=0;building_rows=0
def q(v):return "'"+v+"'"
def cat(r):
    t=' '.join(str(r.get(k) or '') for k in ['complaint_type','descriptor','descriptor_2']).lower()
    if any(x in t for x in ('sewer','catch basin','stormwater','storm water')):return 'SEWER_STORMWATER_CONTEXT'
    if 'hydrant' in t:return 'HYDRANT_CONTEXT'
    if any(x in t for x in ('water main','main break','street leak','street flooding')):return 'STREET_WATER_MAIN_CONTEXT'
    if any(x in t for x in ('water quality','dirty water','discolored','discolour','taste','odor','odour','cloudy','lead')):return 'BUILDING_WATER_QUALITY'
    if any(x in t for x in ('no water','low water','water pressure','low pressure')):return 'BUILDING_NO_WATER_OR_PRESSURE'
    if 'leak' in t:return 'BUILDING_WATER_LEAK'
    return 'OTHER_DEP_WATER'
for id,start,end in periods:
    for i in range(0,len(aliases),200):
        batch=aliases[i:i+200];bs=set(batch)
        where=" AND ".join(["agency='DEP'",f"bbl in ({','.join(q(x) for x in batch)})",f"created_date >= '{start}'",f"created_date < '{end}'",water])
        rows=pages(id,where,'unique_key,created_date,closed_date,agency,agency_name,complaint_type,descriptor,descriptor_2,bbl,borough','unique_key',5000)
        source_rows+=len(rows)
        for r in rows:
            b=norm_bbl(r.get('bbl'));rid=str(r.get('unique_key') or '')
            if b not in bs:raise RuntimeError(f'historical unexpected bbl {b}')
            if not rid or rid in seen:continue
            seen.add(rid)
            c=cat(r)
            if not c.startswith('BUILDING_'):continue
            building_rows+=1
            p=profiles[b];p['request_count']+=1;p['categories'][c]+=1
            created=str(r.get('created_date') or '')[:10]
            if len(created)>=4:p['years'].add(created[:4])
            if created and (p['first'] is None or created<p['first']):p['first']=created
            if created and (p['latest'] is None or created>p['latest']):p['latest']=created
metas_after={id:metadata(id) for id,_,_ in periods}
source_profiles={}
for b,p in profiles.items():
    ys=sorted(p['years']);n=p['request_count']
    source_profiles[b]={'bbl':b,'request_count':n,'category_counts':dict(sorted(p['categories'].items())),'years':ys,'year_count':len(ys),'first_reported_date':p['first'],'latest_reported_date':p['latest'],'recurrent_history':n>=3 and len(ys)>=2,'has_2024_activity':'2024' in ys,'property_link_confidence':'CONFIRMED_SOURCE_BBL','evidence_semantics':'REPORTED_SERVICE_REQUEST'}
served_hist=get(LIVE+'data/historical-311-context.json')
served_profiles=served_hist.get('by_bbl') or {}
diff=[b for b in sorted(set(source_profiles)|set(served_profiles)) if source_profiles.get(b)!=served_profiles.get(b)]
results['historical-311']={
 'source_snapshots_stable':all(metas[id].get('rowsUpdatedAt')==metas_after[id].get('rowsUpdatedAt') for id,_,_ in periods),
 'requested_bbl_aliases':len(aliases),'source_rows':source_rows,'building_water_rows':building_rows,
 'independent_matched_bbls':len(source_profiles),'served_matched_bbls':len(served_profiles),'profile_maps_equal':not diff,
 'differing_bbl_count':len(diff),'differing_bbl_examples':diff[:100]
}
save('historical-population-results.json',results);save('requests.json',REQ)
save('historical-population-summary.json',{'results':results,'all_snapshots_stable':results['ic3t-wcy2']['source_snapshot_stable'] and results['historical-311']['source_snapshots_stable']})
print(json.dumps({'legacy':{k:v for k,v in results['ic3t-wcy2'].items() if 'examples' not in k},'historical311':{k:v for k,v in results['historical-311'].items() if 'examples' not in k}},indent=2))
