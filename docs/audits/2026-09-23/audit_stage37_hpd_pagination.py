from __future__ import annotations
import datetime as dt,hashlib,json,time
from collections import Counter
from pathlib import Path
import urllib.parse as up
import urllib.request as ur

OUT=Path('.audit-stage37');OUT.mkdir(exist_ok=True)
HOST='https://data.cityofnewyork.us';ID='wvxf-dwi5'
BOROUGHS=("MANHATTAN","BRONX","BROOKLYN","QUEENS","STATEN ISLAND")
TERMS=("hot water","water supply","potable","plumbing","faucet","sink","toilet","shower","bathtub","water closet")
UA={'User-Agent':'TowerSignal-hpd-pagination-parity-audit/20260923'}
REQ=[]
def save(n,x):(OUT/n).write_text(json.dumps(x,indent=2))
def get(url,timeout=120):
    last=None
    for i in range(4):
        try:
            with ur.urlopen(ur.Request(url,headers=UA),timeout=timeout) as r:
                b=r.read();REQ.append({'url':url,'status':r.status,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()});return json.loads(b)
        except Exception as ex:
            REQ.append({'url':url,'error':type(ex).__name__});last=ex;time.sleep(min(2**i,8))
    raise RuntimeError(str(last))
def meta():return get(f'{HOST}/api/views/{ID}.json')
def req(params):return get(f'{HOST}/resource/{ID}.json?'+up.urlencode(params))
def where(b):
    tc=' OR '.join(f"novdescription like '%{t.upper()}%'" for t in TERMS)
    return f"violationstatus='Open' AND boro='{b}' AND ({tc})"
def offset(b):
    rows=[];off=0
    while True:
        p=req({'$select':'violationid','$where':where(b),'$order':'violationid','$limit':5000,'$offset':off})
        rows.extend(p)
        if len(p)<5000:break
        off+=5000
    return [str(r['violationid']) for r in rows]
def seek(b):
    rows=[];cursor=None
    while True:
        w=where(b)
        if cursor is not None:w=f"({w}) AND violationid > {cursor}"
        p=req({'$select':'violationid','$where':w,'$order':'violationid','$limit':5000})
        rows.extend(p)
        if len(p)<5000:break
        raw=str(p[-1].get('violationid') or '')
        if not raw.isdigit():raise RuntimeError(f'non numeric cursor {raw}')
        next_=int(raw)
        if cursor is not None and next_<=cursor:raise RuntimeError('cursor did not advance')
        cursor=next_
    return [str(r['violationid']) for r in rows]
m0=meta()
result={}
for b in BOROUGHS:
    a=offset(b);s=seek(b)
    result[b]={'offset_count':len(a),'seek_count':len(s),'sets_equal':set(a)==set(s),'order_unique_offset':len(a)==len(set(a)),
               'order_unique_seek':len(s)==len(set(s)),'offset_only':sorted(set(a)-set(s),key=int)[:1000],'seek_only':sorted(set(s)-set(a),key=int)[:1000]}
m1=meta()
summary={'rows_updated_before':m0.get('rowsUpdatedAt'),'rows_updated_after':m1.get('rowsUpdatedAt'),
 'source_version_stable':m0.get('rowsUpdatedAt')==m1.get('rowsUpdatedAt'),
 'boroughs':result,'all_seek_offset_sets_equal':all(x['sets_equal'] for x in result.values()),
 'offset_total':sum(x['offset_count'] for x in result.values()),'seek_total':sum(x['seek_count'] for x in result.values()),
 'boundary':'Direct parity test of the current production seek-pagination semantics versus independent offset pagination under the same source filter/version. Equality disproves current seek-page loss but cannot retroactively prove publisher snapshot consistency during the earlier build.'}
save('hpd-pagination-parity-summary.json',summary);save('requests.json',REQ)
print(json.dumps(summary,indent=2))
