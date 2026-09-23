from __future__ import annotations
import datetime as dt, hashlib, json, re, time
from collections import Counter
from pathlib import Path
import urllib.parse as up
import urllib.request as ur

OUT=Path('.audit-stage23');OUT.mkdir(exist_ok=True)
LIVE='https://jeremyhennessy.github.io/TowerSignal/'
UA={'User-Agent':'TowerSignal-heavy-source-audit/20260923'}
REQ=[]

def save(n,x):
    p=OUT/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,default=str))
def get(url,timeout=120):
    last=None
    for i in range(4):
        rec={'url':url,'attempt':i+1,'at':dt.datetime.now(dt.timezone.utc).isoformat()}
        try:
            with ur.urlopen(ur.Request(url,headers=UA),timeout=timeout) as r:b=r.read();rec.update(status=r.status,bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
            REQ.append(rec);return json.loads(b)
        except Exception as ex:
            rec['error']=str(ex);REQ.append(rec);last=ex;time.sleep(min(2**i,8))
    raise RuntimeError(f'{url}: {last}')
def meta(id):
    return get(f'https://data.cityofnewyork.us/api/views/{id}.json')
def query(id,where,select,order,page=50000):
    root=f'https://data.cityofnewyork.us/resource/{id}.json'
    m0=meta(id); rows=[];off=0
    while True:
        q={'$select':select,'$where':where,'$order':order,'$limit':page,'$offset':off}
        part=get(root+'?'+up.urlencode(q),150)
        if not isinstance(part,list):raise RuntimeError(f'{id} nonlist')
        rows.extend(part)
        if len(part)<page:break
        off+=page
    m1=meta(id)
    return rows,{'rows':len(rows),'stable':m0.get('rowsUpdatedAt')==m1.get('rowsUpdatedAt'),'rows_updated_before':m0.get('rowsUpdatedAt'),'rows_updated_after':m1.get('rowsUpdatedAt')}

signals=get(LIVE+'data/nyc-water-signals.json')
systems=get(LIVE+'data/systems.json')
results={}

# 311 current scope, monthly independent partitions.
def month_iter(start,end):
    y,m=start.year,start.month
    while (y,m)<=(end.year,end.month):
        s=dt.date(y,m,1)
        if m==12:n=dt.date(y+1,1,1)
        else:n=dt.date(y,m+1,1)
        yield s,n
        y,m=n.year,n.month
clauses=[]
water="(lower(complaint_type) like '%water%' OR lower(descriptor) like '%water%' OR lower(descriptor_2) like '%water%' OR lower(complaint_type) like '%lead%' OR lower(descriptor) like '%lead%' OR lower(descriptor_2) like '%lead%')"
all311=[]; parts=[]
for s,n in month_iter(dt.date(2025,1,1),dt.date(2026,9,23)):
    where=f"agency='DEP' AND created_date >= '{s.isoformat()}T00:00:00.000' AND created_date < '{n.isoformat()}T00:00:00.000' AND {water}"
    rows,m=query('erm2-nwe9',where,'unique_key,created_date,complaint_type,descriptor,descriptor_2,bbl','created_date,unique_key')
    all311.extend(rows);parts.append(m)
src311=Counter(str(r.get('unique_key')) for r in all311 if r.get('unique_key'))
served311=Counter(str(r.get('request_id')) for r in signals.get('water_311_requests') or [] if r.get('request_id'))
results['erm2-nwe9']={
 'source_rows':len(all311),'source_unique_ids':len(src311),'served_rows':sum(served311.values()),'served_unique_ids':len(served311),
 'partitions':len(parts),'all_partitions_stable':all(x['stable'] for x in parts),
 'id_multiset_equal':src311==served311,'source_only_count':sum((src311-served311).values()),'served_only_count':sum((served311-src311).values()),
 'source_only_ids':list((src311-served311).elements())[:100],'served_only_ids':list((served311-src311).elements())[:100]
}

# HPD current open water/plumbing scope by borough.
terms=("hot water","water supply","potable","plumbing","faucet","sink","toilet","shower","bathtub","water closet")
allhpd=[];hparts=[]
for borough in ("MANHATTAN","BRONX","BROOKLYN","QUEENS","STATEN ISLAND"):
    tc=' OR '.join(f"novdescription like '%{t.upper()}%'" for t in terms)
    where=f"violationstatus='Open' AND boro='{borough}' AND ({tc})"
    rows,m=query('wvxf-dwi5',where,'violationid,bbl,bin,inspectiondate,currentstatus,currentstatusdate,violationstatus','violationid',5000)
    allhpd.extend(rows);hparts.append(m)
srchpd=Counter(str(r.get('violationid')) for r in allhpd if r.get('violationid'))
servedhpd=Counter(str(r.get('violation_id')) for r in signals.get('hpd_open_water_violations') or [] if r.get('violation_id'))
results['wvxf-dwi5']={
 'source_rows':len(allhpd),'source_unique_ids':len(srchpd),'served_rows':sum(servedhpd.values()),'served_unique_ids':len(servedhpd),
 'partitions':len(hparts),'all_partitions_stable':all(x['stable'] for x in hparts),
 'id_multiset_equal':srchpd==servedhpd,'source_only_count':sum((srchpd-servedhpd).values()),'served_only_count':sum((servedhpd-srchpd).values()),
 'source_only_ids':list((srchpd-servedhpd).elements())[:100],'served_only_ids':list((servedhpd-srchpd).elements())[:100]
}

# OATH complete cooling-tower agency slice. Seek-style pagination by ticket number.
id='jz4z-kudi';where="issuing_agency='COOLING TOWERS - DOHMH'"
root=f'https://data.cityofnewyork.us/resource/{id}.json';m0=meta(id);rows=[];cursor=None
for page_no in range(200):
    w=where if cursor is None else where+" AND ticket_number > '"+cursor.replace("'","''")+"'"
    q={'$select':'ticket_number,violation_date,hearing_status,hearing_result,hearing_date,decision_date,compliance_status,total_violation_amount,balance_due','$where':w,'$order':'ticket_number','$limit':10000}
    part=get(root+'?'+up.urlencode(q),150)
    if not isinstance(part,list):raise RuntimeError('OATH nonlist')
    rows.extend(part)
    if len(part)<10000:break
    nxt=str(part[-1].get('ticket_number') or '')
    if not nxt or nxt==cursor:raise RuntimeError('OATH cursor failed')
    cursor=nxt
else: raise RuntimeError('OATH page bound exceeded')
m1=meta(id)
def nt(v):return ''.join(ch for ch in str(v or '').strip().upper() if ch.isalnum())
source_oath=Counter(nt(r.get('ticket_number')) for r in rows if nt(r.get('ticket_number')))

# Served OATH cases are in details, but systems summary may carry ticket refs. Fetch details only for accounts reporting OATH/violations.
served_oath=Counter()
def detail_path(sid):return LIVE+f"data/details/{sid[:2].lower()}/{sid}.json"
# sequential is safer for 4893; only fetch likely cases where summary fields indicate violations if possible
candidates=[]
for s in systems.get('systems') or []:
    if any((s.get(k) or 0) for k in ['oath_case_count','oath_cases_count','violation_count','recent_violation_count']):
        candidates.append(str(s['system_id']))
if not candidates:
    candidates=[str(s['system_id']) for s in systems.get('systems') or []]
for idx,sid in enumerate(candidates):
    d=get(detail_path(sid),60)
    for c in d.get('oath_cases') or []:
        t=nt(c.get('ticket_number'))
        if t:served_oath[t]+=1
results['jz4z-kudi']={
 'source_agency_rows':len(rows),'source_unique_normalized_tickets':len(source_oath),'source_snapshot_stable':m0.get('rowsUpdatedAt')==m1.get('rowsUpdatedAt'),
 'served_accounts_checked':len(candidates),'served_oath_rows':sum(served_oath.values()),'served_unique_tickets':len(served_oath),
 'served_ticket_set_subset_of_current_agency_source':not bool(served_oath-source_oath),
 'served_tickets_outside_source':list((served_oath-source_oath).elements())[:100],
 'current_source_tickets_not_served_count':len(set(source_oath)-set(served_oath)),
 'note':'Current agency source includes cases beyond TowerSignal requested summons universe; source-not-served is not a defect.'
}

save('heavy-population-results.json',results)
save('requests.json',REQ)
summary={'sources':3,'all_snapshots_stable':all([results['erm2-nwe9']['all_partitions_stable'],results['wvxf-dwi5']['all_partitions_stable'],results['jz4z-kudi']['source_snapshot_stable']]),'results':{k:{kk:vv for kk,vv in v.items() if not kk.endswith('_ids') and not kk.endswith('_source')} for k,v in results.items()}}
save('heavy-population-summary.json',summary)
print(json.dumps(summary,indent=2))
