from __future__ import annotations
import concurrent.futures as cf
import hashlib,json,re,time
from collections import Counter
from pathlib import Path
import urllib.parse as up
import urllib.request as ur

OUT=Path('.audit-stage35');OUT.mkdir(exist_ok=True)
LIVE='https://jeremyhennessy.github.io/TowerSignal/'
CMS='https://data.cms.gov/provider-data/api/1/datastore/query'
GEO='https://geosearch.planninglabs.nyc/v2/search'
HOSP='xubh-q36u';NURS='4pq5-n9py'
UA={'User-Agent':'TowerSignal-independent-cms-replay/20260923'}
REQ=[]

def save(n,x):(OUT/n).write_text(json.dumps(x,indent=2,default=str))
def get(url,timeout=90):
    last=None
    for i in range(4):
        try:
            with ur.urlopen(ur.Request(url,headers={'Accept':'application/json',**UA}),timeout=timeout) as r:
                b=r.read();REQ.append({'url':url,'status':r.status,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()});return json.loads(b)
        except Exception as ex:
            REQ.append({'url':url,'error':type(ex).__name__});last=ex;time.sleep(min(2**i,8))
    raise RuntimeError(f'{url}: {last}')
def space(v):return re.sub(r'\s+',' ',str(v or '').strip())
def digits(v):return re.sub(r'\D','',space(v))
def zip5(v):
    d=digits(v);return d[:5] if len(d)>=5 else None
def nyc_zip(v):
    z=zip5(v)
    if not z:return False
    n=int(z)
    return 10001<=n<=10292 or 10301<=n<=10314 or 10451<=n<=10475 or 11004<=n<=11005 or 11101<=n<=11109 or 11201<=n<=11256 or 11351<=n<=11451 or 11691<=n<=11697
def first(r,*keys):
    for k in keys:
        if r.get(k) not in (None,''):return r[k]
    return None
def fetch(id):
    rows=[];off=0;expected=None
    while expected is None or off<expected:
        p=get(f'{CMS}/{id}/0?'+up.urlencode({'offset':off,'limit':1500}))
        if not isinstance(p,dict) or not isinstance(p.get('results'),list):raise RuntimeError(f'CMS {id} shape')
        if expected is None:expected=int(p['count'])
        rows.extend(p['results'])
        if len(p['results'])<1500:break
        off+=1500
    if len(rows)!=expected:raise RuntimeError(f'CMS {id} incomplete {len(rows)}/{expected}')
    return rows,expected
def norm(source,r):
    if source=='HOSPITAL':
        sid=space(first(r,'facility_id'));name=space(first(r,'facility_name'));addr=space(first(r,'address'))
        city=space(first(r,'citytown','city_town','city'));state=space(first(r,'state')).upper();z=zip5(first(r,'zip_code','zip'))
    else:
        sid=space(first(r,'cms_certification_number_ccn','federal_provider_number','ccn'));name=space(first(r,'provider_name','federal_provider_name'));addr=space(first(r,'provider_address','address'))
        city=space(first(r,'citytown','provider_city','city'));state=space(first(r,'state','provider_state')).upper();z=zip5(first(r,'zip_code','provider_zip_code','zip'))
    if not sid or not addr or not z or state!='NY' or not nyc_zip(z):return None
    return {'source_kind':source,'source_facility_id':sid,'facility_name':name or None,'address':addr,'city':city or None,'zip':z}
def address_parts(a):
    m=re.match(r'^\s*([0-9]+[A-Z]?(?:-[0-9]+[A-Z]?)?)\s+(.+?)\s*$',a.upper())
    if not m:return None,None
    return space(m.group(1)).upper(),space(re.sub(r'[^A-Z0-9 ]+',' ',m.group(2))).upper()
def nstreet(v):return space(re.sub(r'[^A-Z0-9 ]+',' ',space(v).upper()))
def walk(v,key):
    out=[]
    if isinstance(v,dict):
        for k,x in v.items():
            if str(k).lower()==key.lower():out.append(x)
            out.extend(walk(x,key))
    elif isinstance(v,list):
        for x in v:out.extend(walk(x,key))
    return out
def bbl(v):
    d=digits(v);return d if len(d)==10 and d[0] in '12345' else None
def bin7(v):
    d=digits(v)
    return d if len(d)==7 and d[0] in '12345' and d[1:]!='000000' else None
def reconcile(f):
    q=' '.join(x for x in (space(f['address']),space(f.get('city')),'NY',f['zip']) if x)
    p=get(GEO+'?'+up.urlencode({'text':q,'size':5}),60)
    feats=p.get('features') if isinstance(p,dict) else None
    if not isinstance(feats,list):return {'status':'SOURCE_RESPONSE_INVALID'}
    house,street=address_parts(f['address']);z=f['zip'];cand=[]
    for feature in feats:
        props=feature.get('properties') if isinstance(feature,dict) and isinstance(feature.get('properties'),dict) else {}
        if z and zip5(first(props,'postalcode','postal_code','zip'))!=z:continue
        if house and space(first(props,'housenumber','house_number')).upper()!=house:continue
        if street and nstreet(first(props,'street'))!=street:continue
        add=props.get('addendum')
        bbls={x for raw in walk(add,'bbl') if (x:=bbl(raw))}
        bins={x for raw in walk(add,'bin') if (x:=bin7(raw))}
        if len(bbls)!=1:continue
        cand.append((next(iter(bbls)),next(iter(bins)) if len(bins)==1 else None))
    u=set(cand)
    if len(u)==1:
        bb,bi=next(iter(u));return {'status':'RESOLVED_UNIQUE_PAD_EXACT_ADDRESS','bbl':bb,'bin':bi,'candidate_count':len(cand)}
    return {'status':'UNRESOLVED_NO_EXACT_PAD_RESULT' if not u else 'UNRESOLVED_MULTIPLE_PAD_PROPERTIES','candidate_count':len(cand)}

served=get(LIVE+'data/cms-institutional-context.json')
systems=get(LIVE+'data/systems.json')
tower_aliases={bbl(a) for s in systems['systems'] for a in (s.get('bbl_aliases') or [s.get('bbl')]) if bbl(a)}
hr,hc=fetch(HOSP);nr,nc=fetch(NURS)
fac=[x for source,rows in [('HOSPITAL',hr),('NURSING_HOME',nr)] for r in rows if (x:=norm(source,r))]
if len({(x['source_kind'],x['source_facility_id']) for x in fac})!=len(fac):raise RuntimeError('Duplicate CMS identity')

resolved=[]
with cf.ThreadPoolExecutor(max_workers=4) as pool:
    fut={pool.submit(reconcile,x):x for x in fac}
    for f in cf.as_completed(fut):
        x=fut[f];res=f.result();resolved.append({**x,'resolution':res})

current_edges=set()
for x in resolved:
    res=x['resolution']
    if res.get('status')=='RESOLVED_UNIQUE_PAD_EXACT_ADDRESS' and res.get('bbl') in tower_aliases:
        current_edges.add((x['source_kind'],x['source_facility_id'],res['bbl']))

served_edges=set()
for bb,rows in (served.get('by_bbl') or {}).items():
    for r in rows:
        served_edges.add((str(r.get('source_kind')),str(r.get('source_facility_id')),str(bb)))
served_source={x.get('dataset_id'):x.get('source_record_count') for x in (served.get('source') or {}).get('datasets',[])}
summary={
 'served_generated_at':served.get('generated_at'),
 'current_source_counts':{HOSP:hc,NURS:nc},
 'served_source_counts':served_source,
 'source_counts_equal':served_source.get(HOSP)==hc and served_source.get(NURS)==nc,
 'nyc_candidate_facilities':len(fac),
 'resolution_status_counts':dict(Counter(x['resolution'].get('status') for x in resolved)),
 'current_tower_overlap_edges':len(current_edges),'served_tower_overlap_edges':len(served_edges),
 'relationship_sets_equal':current_edges==served_edges,
 'current_only_edges':len(current_edges-served_edges),'served_only_edges':len(served_edges-current_edges),
 'current_only_examples':[list(x) for x in sorted(current_edges-served_edges)[:100]],
 'served_only_examples':[list(x) for x in sorted(served_edges-current_edges)[:100]],
 'boundary':'Independent current CMS + NYC GeoSearch exact house/street/ZIP/single-BBL replay. Equality proves current relationship set when source populations are unchanged; source count drift is reported separately.'
}
save('cms-relationship-replay-summary.json',summary)
save('requests.json',REQ)
print(json.dumps(summary,indent=2))
