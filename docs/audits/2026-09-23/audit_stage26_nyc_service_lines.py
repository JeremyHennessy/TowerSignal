from __future__ import annotations
import concurrent.futures as cf, datetime as dt, hashlib,json,time
from collections import Counter
from pathlib import Path
import urllib.parse as up
import urllib.request as ur

OUT=Path('.audit-stage26');OUT.mkdir(exist_ok=True)
LIVE='https://jeremyhennessy.github.io/TowerSignal/'
UA={'User-Agent':'TowerSignal-independent-service-line-audit/20260923'}
REQ=[]
def save(n,x):(OUT/n).write_text(json.dumps(x,indent=2,default=str))
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
def norm_bbl(v):
    s=''.join(c for c in str(v or '') if c.isdigit())
    return s if len(s)==10 and s[0] in '12345' else None
systems=get(LIVE+'data/systems.json')
aliases=sorted({b for s in systems['systems'] for v in (s.get('bbl_aliases') or [s.get('bbl')]) if (b:=norm_bbl(v))},key=int)
alias_set=set(aliases)
id='jqfp-uff7';host='data.cityofnewyork.us';root=f'https://{host}/resource/{id}.json'
m0=get(f'https://{host}/api/views/{id}.json')
full_count=get(root+'?'+up.urlencode({'$select':'count(*) as n'}))
full_count=int(full_count[0]['n'])
source=[]
for i in range(0,len(aliases),150):
    batch=aliases[i:i+150]
    where="tbbl in ("+','.join("'"+b+"'" for b in batch)+")"
    off=0
    while True:
        q={'$select':'objectid,tbbl,address,material,record_ty,city_owned','$where':where,'$order':'objectid','$limit':50000,'$offset':off}
        part=get(root+'?'+up.urlencode(q),150)
        source.extend(part)
        if len(part)<50000:break
        off+=50000
m1=get(f'https://{host}/api/views/{id}.json')
src=Counter((str(r.get('objectid') or ''),norm_bbl(r.get('tbbl')) or '') for r in source if r.get('objectid') and norm_bbl(r.get('tbbl')) in alias_set)

def detail(s):
    sid=str(s['system_id']);return get(LIVE+f"data/details/{sid[:2].lower()}/{sid}.json",60)
with cf.ThreadPoolExecutor(max_workers=10) as pool:details=list(pool.map(detail,systems['systems']))
served=Counter()
for d in details:
    ctx=d.get('nyc_lead_service_lines') or {}
    for r in ctx.get('records') or []:
        rid=str(r.get('record_id') or '')
        b=norm_bbl(r.get('bbl'))
        if rid and b:served[(rid,b)]+=1
# Same record can attach to multiple systems sharing an alias. Compare unique source record identities, not attachment multiplicity.
served_unique=set(served);src_unique=set(src)
summary={
 'dataset_id':id,'source_snapshot_stable':m0.get('rowsUpdatedAt')==m1.get('rowsUpdatedAt'),
 'publisher_full_record_count':full_count,'requested_bbl_aliases':len(aliases),'source_target_rows':len(source),
 'source_target_unique_records':len(src_unique),'served_unique_records':len(served_unique),
 'served_identity_set_equal':src_unique==served_unique,
 'source_only_count':len(src_unique-served_unique),'served_only_count':len(served_unique-src_unique),
 'source_only_examples':[list(x) for x in sorted(src_unique-served_unique)[:100]],
 'served_only_examples':[list(x) for x in sorted(served_unique-src_unique)[:100]],
 'attachment_rows':sum(served.values()),
 'boundary':'Exact source-reported BBL/alias target population; record identity is objectid + source BBL. Attachment multiplicity across systems is not compared to publisher row count.'
}
save('service-line-population-summary.json',summary);save('requests.json',REQ)
print(json.dumps({k:v for k,v in summary.items() if not k.endswith('examples')},indent=2))
