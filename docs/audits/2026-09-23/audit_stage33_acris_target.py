from __future__ import annotations
import concurrent.futures as cf
import datetime as dt
import hashlib,json,re,time
from collections import Counter,defaultdict
from pathlib import Path
import urllib.parse as up
import urllib.request as ur

OUT=Path('.audit-stage33');OUT.mkdir(exist_ok=True)
LIVE='https://jeremyhennessy.github.io/TowerSignal/'
API='https://data.cityofnewyork.us'
UA={'User-Agent':'TowerSignal-independent-acris-replay/20260923'}
MASTER='bnx9-e6tj';LEGALS='8h5j-fqxa';PARTIES='636b-3b5g'
DOC_TYPES=("DEED","DEED COR","MTGE","ASST","ASSTO","SAT","SAGE","AALR","AL&R","LEAS","MLEA","REL")
REQ=[]
DIR={'NORTH':'N','SOUTH':'S','EAST':'E','WEST':'W','NORTHEAST':'NE','NORTHWEST':'NW','SOUTHEAST':'SE','SOUTHWEST':'SW'}
SUF={'STREET':'ST','ST':'ST','AVENUE':'AVE','AVE':'AVE','BOULEVARD':'BLVD','BLVD':'BLVD','ROAD':'RD','RD':'RD','PLACE':'PL','PL':'PL','DRIVE':'DR','DR':'DR','LANE':'LN','LN':'LN','COURT':'CT','CT':'CT','HIGHWAY':'HWY','HWY':'HWY','PARKWAY':'PKWY','PKWY':'PKWY','TERRACE':'TER','TER':'TER'}

def save(n,x):(OUT/n).write_text(json.dumps(x,indent=2,default=str))
def get(url,timeout=180):
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
def meta(id):return get(f'{API}/api/views/{id}.json')
def resource(id,params):
    return get(f'{API}/resource/{id}.json?{up.urlencode(params)}')
def qquote(v):return "'" + str(v).replace("'","''") + "'"
def norm_bbl(v):
    s=str(v or '').strip()
    if s.endswith('.0'):s=s[:-2]
    d=''.join(c for c in s if c.isdigit())
    return d if len(d)==10 and d[0] in '12345' else None
def bbl_parts(v):
    b=norm_bbl(v)
    if not b:return None
    return int(b[0]),int(b[1:6]),int(b[6:])
def legal_bbl(r):
    try:b=int(float(str(r.get('borough'))));block=int(float(str(r.get('block'))));lot=int(float(str(r.get('lot'))))
    except Exception:return None
    if b not in range(1,6) or block<0 or lot<0:return None
    return f'{b}{block:05d}{lot:04d}'
def nnum(v):
    s=re.sub(r'\s+','',str(v or '').strip().upper())
    return (s.lstrip('0') or '0') if s else None
def nstreet(v):
    cleaned=re.sub(r'[^A-Z0-9 ]+',' ',str(v or '').strip().upper())
    out=[]
    for t in cleaned.split():
        m=re.fullmatch(r'(\d+)(?:ST|ND|RD|TH)',t)
        if m:t=m.group(1)
        out.append(SUF.get(DIR.get(t,t),DIR.get(t,t)))
    return ' '.join(out) or None
def legal_address_key(r):
    try:b=int(float(str(r.get('borough'))));block=int(float(str(r.get('block'))))
    except Exception:return None
    num=nnum(r.get('street_number'));street=nstreet(r.get('street_name'))
    return (b,block,num,street) if b in range(1,6) and block>0 and num and street else None
def page(id,where,select,order,limit=50000):
    rows=[];off=0
    while True:
        p=resource(id,{'$select':select,'$where':where,'$order':order,'$limit':limit,'$offset':off})
        if not isinstance(p,list):raise RuntimeError(f'{id} non-list')
        rows.extend(p)
        if len(p)<limit:break
        off+=limit
    return rows
def batch(values,n):
    values=list(values)
    for i in range(0,len(values),n):yield values[i:i+n]

systems_payload=get(LIVE+'data/systems.json')
systems=systems_payload['systems'];md=systems_payload.get('metadata') or {}
cutoff=str(md.get('acris_cache_cutoff') or '')
if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',cutoff):raise RuntimeError(f'No usable served ACRIS cutoff: {cutoff!r}')
served_generated=md.get('acris_cache_generated_at')
targets={}
for s in sorted(systems,key=lambda x:str(x.get('system_id') or '')):
    b=norm_bbl(s.get('bbl'))
    if not b:continue
    aliases=set((targets.get(b) or {}).get('aliases') or [])
    for a in s.get('bbl_aliases') or [b]:
        x=norm_bbl(a)
        if x:aliases.add(x)
    targets[b]={'aliases':sorted(aliases),'number':s.get('number'),'street':s.get('street'),'system_id':s.get('system_id')}

tower=set(targets)
alias_index=defaultdict(set)
for b,t in targets.items():
    for a in t['aliases']:
        if a!=b:alias_index[a].add(b)
condo_index=defaultdict(set)
for b,t in targets.items():
    parts=bbl_parts(b)
    if not parts:continue
    bor,block,lot=parts
    if 7500<=lot<=7999:
        num=nnum(t.get('number'));street=nstreet(t.get('street'))
        if num and street:condo_index[(bor,block,num,street)].add(b)

types=','.join(qquote(x) for x in DOC_TYPES)
master_where=f"recorded_datetime >= '{cutoff}T00:00:00.000' AND doc_type in ({types})"
m0={x:meta(x) for x in (MASTER,LEGALS,PARTIES)}
count=resource(MASTER,{'$select':'count(*) as count','$where':master_where})
expected=int(count[0]['count'])
master_rows=page(MASTER,master_where,'document_id,record_type,crfn,recorded_borough,doc_type,document_date,document_amt,recorded_datetime,modified_date,percent_trans,good_through_date','document_id,recorded_datetime,modified_date')
if len(master_rows)!=expected:raise RuntimeError(f'Master incomplete {len(master_rows)}/{expected}')
master_by=defaultdict(list)
for r in master_rows:
    if r.get('document_id'):master_by[str(r['document_id'])].append(r)
def canonical(rows):
    return sorted(rows,key=lambda r:(str(r.get('recorded_datetime') or ''),str(r.get('modified_date') or ''),str(r.get('record_type') or ''),json.dumps(r,sort_keys=True)),reverse=True)[0]
masters={d:canonical(rows) for d,rows in master_by.items()}
docids=sorted(masters)

def fetch_legal(b):
    where='document_id in ('+','.join(qquote(x) for x in b)+')'
    rows=page(LEGALS,where,'document_id,borough,block,lot,property_type,street_number,street_name,unit,good_through_date','document_id,borough,block,lot',50000)
    if len(rows)>=50000:raise RuntimeError('Legal batch cap')
    return rows
legal=[]
with cf.ThreadPoolExecutor(max_workers=8) as pool:
    for rows in pool.map(fetch_legal,batch(docids,300)):legal.extend(rows)

docs_by_bbl=defaultdict(set); legal_by=defaultdict(list);basis={}
for r in legal:
    sb=legal_bbl(r);did=str(r.get('document_id') or '')
    if not did or did not in masters:continue
    if sb in tower:
        k=(sb,did);docs_by_bbl[sb].add(did);legal_by[k].append(r);basis[k]='BBL_EXACT_DOCUMENT_ID_EXACT'
    for target in alias_index.get(sb or '',set()):
        k=(target,did);docs_by_bbl[target].add(did);legal_by[k].append(r)
        if basis.get(k)!='BBL_EXACT_DOCUMENT_ID_EXACT':basis[k]='BBL_ALIAS_EXACT_DOCUMENT_ID_EXACT'
    ak=legal_address_key(r)
    for target in condo_index.get(ak,set()) if ak else set():
        if target==sb:continue
        k=(target,did);docs_by_bbl[target].add(did);legal_by[k].append(r)
        if basis.get(k)!='BBL_EXACT_DOCUMENT_ID_EXACT':basis[k]='CONDO_BILLING_BBL_BLOCK_ADDRESS_EXACT'

matched_docs=sorted({d for s in docs_by_bbl.values() for d in s})
def fetch_party(b):
    where='document_id in ('+','.join(qquote(x) for x in b)+')'
    rows=page(PARTIES,where,'document_id,record_type,party_type,name,address_1,address_2,country,city,state,zip,good_through_date','document_id,party_type,name',50000)
    if len(rows)>=50000:raise RuntimeError('Party batch cap')
    return rows
parties=defaultdict(list)
with cf.ThreadPoolExecutor(max_workers=8) as pool:
    for rows in pool.map(fetch_party,batch(matched_docs,300)):
        for r in rows:
            if r.get('document_id'):parties[str(r['document_id'])].append(r)
def unique_party_count(rows):
    return len({tuple(str(r.get(k) or '').strip() for k in ('party_type','name','address_1','address_2','city','state','zip','country')) for r in rows})
def rec_date(r):return str(r.get('recorded_datetime') or '')[:10] or None
independent={}
for b,docs in docs_by_bbl.items():
    ordered=sorted(docs,key=lambda d:(rec_date(masters[d]) or '',d),reverse=True)
    independent[b]={
      'recent_document_count':len(ordered),
      'recorded_party_count':sum(unique_party_count(parties[d]) for d in ordered),
      'top25':[(d,basis.get((b,d)),rec_date(masters[d])) for d in ordered[:25]],
    }

# One served detail per canonical BBL.
def detail(s):
    sid=str(s['system_id']);return get(LIVE+f"data/details/{sid[:2].lower()}/{sid}.json",60)
served_by_bbl={}
with cf.ThreadPoolExecutor(max_workers=10) as pool:
    for d in pool.map(detail,systems):
        b=norm_bbl((d.get('identity') or {}).get('bbl'))
        if b and b not in served_by_bbl:served_by_bbl[b]=d

count_mismatch=[];party_mismatch=[];top25_mismatch=[];served_activity_bbls=set()
for b in sorted(tower):
    d=served_by_bbl.get(b) or {}
    sysctx=next((s for s in systems if norm_bbl(s.get('bbl'))==b),{})
    src=independent.get(b,{'recent_document_count':0,'recorded_party_count':0,'top25':[]})
    served_count=int(sysctx.get('acris_recent_document_count') or 0)
    served_party=int(sysctx.get('acris_recorded_party_count') or 0)
    if served_count:served_activity_bbls.add(b)
    if served_count!=src['recent_document_count']:count_mismatch.append({'bbl':b,'served':served_count,'independent':src['recent_document_count']})
    if served_party!=src['recorded_party_count']:party_mismatch.append({'bbl':b,'served':served_party,'independent':src['recorded_party_count']})
    act=d.get('acris_activity') or {}
    served_top=[(str(x.get('document_id') or ''),str(x.get('match_basis') or ''),str(x.get('recorded_date') or '') or None) for x in act.get('documents') or []]
    if served_top!=src['top25']:top25_mismatch.append({'bbl':b,'served':served_top,'independent':src['top25']})

m1={x:meta(x) for x in (MASTER,LEGALS,PARTIES)}
stable=all(m0[x].get('rowsUpdatedAt')==m1[x].get('rowsUpdatedAt') for x in m0)
served_source_versions={str(x.get('dataset_id')):x.get('source_last_updated_at') for x in md.get('sources',[]) if x.get('dataset_id') in (MASTER,LEGALS,PARTIES)}
summary={
 'cutoff':cutoff,'served_cache_generated_at':served_generated,'requested_tower_bbl_count':len(tower),
 'master_source_rows':len(master_rows),'master_unique_documents':len(docids),'legal_rows':len(legal),
 'matched_unique_documents':len(matched_docs),'matched_bbl_count':len(independent),'party_rows':sum(len(v) for v in parties.values()),
 'source_snapshots_stable':stable,
 'current_rows_updated':{x:m1[x].get('rowsUpdatedAt') for x in m1},
 'served_source_last_updated':served_source_versions,
 'full_document_count_mismatch_bbls':len(count_mismatch),
 'party_count_mismatch_bbls':len(party_mismatch),
 'retained_top25_identity_mismatch_bbls':len(top25_mismatch),
 'all_current_target_relationships_equal':not count_mismatch and not party_mismatch and not top25_mismatch,
 'boundary':'Independent current replay of the served ACRIS cutoff and release property graph. Full counts compare system summary; retained browser identities compare exact top-25 document/match-basis/date tuples.'
}
save('acris-target-replay-summary.json',summary)
save('acris-target-replay-deltas.json',{'count_mismatches':count_mismatch[:1000],'party_mismatches':party_mismatch[:1000],'top25_mismatches':top25_mismatch[:500]})
save('requests.json',REQ)
print(json.dumps(summary,indent=2))
