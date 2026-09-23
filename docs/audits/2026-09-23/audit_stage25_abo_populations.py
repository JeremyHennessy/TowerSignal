from __future__ import annotations
import datetime as dt,hashlib,json,time
from collections import Counter
from pathlib import Path
import urllib.parse as up
import urllib.request as ur

OUT=Path('.audit-stage25');OUT.mkdir(exist_ok=True)
LIVE='https://jeremyhennessy.github.io/TowerSignal/'
UA={'User-Agent':'TowerSignal-independent-abo-population-audit/20260923'}
REQ=[]
DATASETS=[
("NYS_ABO_STATE_AUTHORITIES","ehig-g5x3"),
("NYS_ABO_LOCAL_AUTHORITIES","8w5p-k45m"),
("NYS_ABO_LOCAL_DEVELOPMENT_CORPORATIONS","d84c-dk28"),
("NYS_ABO_INDUSTRIAL_DEVELOPMENT_AGENCIES","p3p6-xqr5")]
TERMS=["cooling tower","water treatment","cooling water","condenser water","boiler water","legionella","disinfection","water management","water quality","biocide","chiller","hvac maintenance","mechanical maintenance","laboratory testing","chemical treatment"]

def save(n,x): (OUT/n).write_text(json.dumps(x,indent=2,default=str))
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
def metadata(id):return get(f'https://data.ny.gov/api/views/{id}')
def query_search(id,term,page=50000):
    rows=[];off=0
    while True:
        q={'$limit':page,'$offset':off,'$q':term}
        p=get(f'https://data.ny.gov/resource/{id}.json?'+up.urlencode(q),150)
        if not isinstance(p,list):raise RuntimeError(f'{id} non-list')
        rows.extend(p)
        if len(p)<page:break
        off+=page
    return rows
def first(r,*keys):
    for k in keys:
        if r.get(k) not in (None,''):return r.get(k)
    return None
def fp(id,r):
    material=[id,first(r,'authority_name'),first(r,'fiscal_year_end_date'),first(r,'vendor_name'),
      first(r,'procurement_description'),first(r,'award_date'),
      first(r,'contract_begin_date','contract_start_date','begin_date','start_date'),
      first(r,'contract_end_date','end_date'),first(r,'contract_amount','amount','procurement_amount'),
      first(r,'procurement_number','contract_number','contract_id')]
    return hashlib.sha256('|'.join(str(x or '') for x in material).encode()).hexdigest() # audit-only identity, not product stable_id

cohort=json.loads(Path('data/fixtures/deal-validation-cohort.json').read_text())
aliases=[str(a).strip() for t in cohort.get('targets',[]) for a in t.get('aliases',[]) if str(a).strip()]
search_terms=list(dict.fromkeys(TERMS+aliases))
served=get(LIVE+'data/procurement-nys-authorities.json')
served_health={str(x.get('dataset_id')):x for x in served.get('source_health') or []}
results={}
for source,id in DATASETS:
    m0=metadata(id); unique={}; term_counts=Counter()
    for term in search_terms:
        rows=query_search(id,term)
        for r in rows:unique[fp(id,r)]=r
        term_counts[term]+=len(rows)
    m1=metadata(id)
    sh=served_health.get(id,{})
    results[id]={
      'source':source,'source_snapshot_stable':m0.get('rowsUpdatedAt')==m1.get('rowsUpdatedAt'),
      'independent_search_term_count':len(search_terms),'independent_unique_candidate_count':len(unique),
      'served_health_retrieved_candidate_count':sh.get('retrieved_candidate_count'),
      'candidate_count_equal':sh.get('retrieved_candidate_count')==len(unique),
      'served_relevant_record_count':sh.get('relevant_record_count'),
      'source_record_count_served_health':sh.get('record_count'),
      'rows_updated_before':m0.get('rowsUpdatedAt'),'rows_updated_after':m1.get('rowsUpdatedAt'),
      'independent_term_raw_match_counts':dict(term_counts)
    }
save('abo-population-results.json',results);save('requests.json',REQ)
summary={'datasets':4,'all_snapshots_stable':all(x['source_snapshot_stable'] for x in results.values()),'all_candidate_counts_equal':all(x['candidate_count_equal'] for x in results.values()),'results':results}
save('abo-population-summary.json',summary)
print(json.dumps(summary,indent=2))
