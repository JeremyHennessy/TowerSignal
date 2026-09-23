from __future__ import annotations
import datetime as dt,hashlib,json,time
from collections import Counter
from pathlib import Path
import urllib.parse as up
import urllib.request as ur

OUT=Path('.audit-stage30');OUT.mkdir(exist_ok=True)
LIVE='https://jeremyhennessy.github.io/TowerSignal/'
UA={'User-Agent':'TowerSignal-complete-hpd-lifecycle-audit/20260923'}
REQ=[]
ID='wvxf-dwi5'
TERMS=("hot water","water supply","potable","plumbing","faucet","sink","toilet","shower","bathtub","water closet")
BOROUGHS=("MANHATTAN","BRONX","BROOKLYN","QUEENS","STATEN ISLAND")

def save(n,x):(OUT/n).write_text(json.dumps(x,indent=2,default=str))
def get(url,timeout=150):
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
def meta():return get(f'https://data.cityofnewyork.us/api/views/{ID}.json')
def query(where,select,order='violationid',page=5000):
    root=f'https://data.cityofnewyork.us/resource/{ID}.json';rows=[];off=0
    while True:
        q={'$select':select,'$where':where,'$order':order,'$limit':page,'$offset':off}
        p=get(root+'?'+up.urlencode(q))
        if not isinstance(p,list):raise RuntimeError('non-list')
        rows.extend(p)
        if len(p)<page:break
        off+=page
    return rows
def iso_epoch(v):
    if v is None:return None
    return dt.datetime.fromtimestamp(int(v),tz=dt.timezone.utc).isoformat().replace('+00:00','Z')
def in_clauses(vals,n=120):
    return [f"violationid in ({','.join(vals[i:i+n])})" for i in range(0,len(vals),n)]

signals=get(LIVE+'data/nyc-water-signals.json')
served={str(r.get('violation_id')):r for r in signals.get('hpd_open_water_violations') or [] if r.get('violation_id')}
health=[x for x in signals.get('source_health') or [] if x.get('dataset_id')==ID]
served_versions=sorted({str(x.get('source_last_updated_at')) for x in health if x.get('source_last_updated_at')})
served_retrieved=sorted({str(x.get('retrieved_at')) for x in health if x.get('retrieved_at')})
m0=meta()
current=[]
for b in BOROUGHS:
    tc=' OR '.join(f"novdescription like '%{t.upper()}%'" for t in TERMS)
    current.extend(query(f"violationstatus='Open' AND boro='{b}' AND ({tc})",
        'violationid,bbl,bin,boro,inspectiondate,approveddate,novissueddate,novdescription,currentstatus,currentstatusdate,violationstatus,rentimpairing'))
m1=meta()
if m0.get('rowsUpdatedAt')!=m1.get('rowsUpdatedAt'):raise RuntimeError('HPD source changed during complete replay')
cur={str(r['violationid']):r for r in current}
source_only=sorted(set(cur)-set(served),key=int)
served_only=sorted(set(served)-set(cur),key=int)

delta_all={}
for clause in in_clauses(sorted(set(source_only)|set(served_only),key=int)):
    for r in query(clause,'violationid,bbl,bin,boro,inspectiondate,approveddate,novissueddate,novdescription,currentstatus,currentstatusdate,violationstatus,rentimpairing'):
        delta_all[str(r['violationid'])]=r

current_version=iso_epoch(m1.get('rowsUpdatedAt') or m1.get('dataUpdatedAt'))
max_served_version=max(served_versions) if served_versions else None
publisher_advanced=bool(current_version and max_served_version and current_version>max_served_version)
class_counts=Counter();records=[]
for vid in source_only:
    r=delta_all.get(vid)
    cls='CURRENT_OPEN_FROM_NEWER_PUBLISHER_VERSION' if publisher_advanced else 'CURRENT_OPEN_UNEXPLAINED_VERSION_EQUAL'
    class_counts[cls]+=1;records.append({'violation_id':vid,'side':'CURRENT_ONLY','classification':cls,'source_row':r})
for vid in served_only:
    r=delta_all.get(vid)
    if not r:cls='SERVED_SNAPSHOT_ROW_REMOVED_FROM_CURRENT_PUBLISHER'
    elif str(r.get('violationstatus') or '').upper()!='OPEN':cls='SERVED_SNAPSHOT_NOW_CLOSED'
    else:cls='SERVED_SNAPSHOT_NO_LONGER_IN_OPEN_WATER_SCOPE'
    class_counts[cls]+=1;records.append({'violation_id':vid,'side':'SERVED_ONLY','classification':cls,'source_row':r})

summary={
 'served_build_generated_at':signals.get('generated_at'),
 'served_source_health_entries':len(health),
 'served_source_versions':served_versions,
 'served_source_retrieved_at':served_retrieved,
 'current_source_version':current_version,
 'current_rows_updated_epoch':m1.get('rowsUpdatedAt'),
 'publisher_version_advanced_since_served_snapshot':publisher_advanced,
 'current_open_water_rows':len(current),'current_unique_ids':len(cur),
 'served_open_water_rows':len(served),
 'source_only_count':len(source_only),'served_only_count':len(served_only),
 'class_counts':dict(class_counts),
 'identity_sets_equal':set(cur)==set(served),
 'delta_fully_attributable_to_publisher_version_or_lifecycle':publisher_advanced and all(
     r['classification']!='SERVED_SNAPSHOT_NO_LONGER_IN_OPEN_WATER_SCOPE' for r in records)
}
save('complete-hpd-lifecycle-summary.json',summary)
save('complete-hpd-lifecycle-delta.json',records)
save('requests.json',REQ)
print(json.dumps(summary,indent=2))
