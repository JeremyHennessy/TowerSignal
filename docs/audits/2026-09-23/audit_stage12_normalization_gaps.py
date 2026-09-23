from __future__ import annotations
import hashlib, json, re, time, urllib.parse as up, urllib.request as ur
from collections import defaultdict
from pathlib import Path

OUT=Path('.audit-stage12'); OUT.mkdir(exist_ok=True)
LIVE='https://jeremyhennessy.github.io/TowerSignal/'
UA={'User-Agent':'TowerSignal-stage12-normalization-audit/20260923','Accept':'application/json'}

def clean(v):
    return re.sub(r'\s+',' ',str(v or '').strip())

def stable_id(prefix,*parts):
    material='|'.join(clean(p) for p in parts)
    return f"{prefix}-{hashlib.sha256(material.encode()).hexdigest()[:20]}"

def get(url,timeout=120):
    last=None
    for attempt in range(4):
        try:
            with ur.urlopen(ur.Request(url,headers=UA),timeout=timeout) as r:
                return json.load(r)
        except Exception as e:
            last=e
            if attempt<3: time.sleep(2**attempt)
    raise RuntimeError(f'{url}: {last}')

def first(row,*keys):
    for k in keys:
        v=row.get(k)
        if v not in (None,''): return v
    return None

def abo_fingerprint(dataset_id,row):
    material=[
      dataset_id,
      first(row,'authority_name'),
      first(row,'fiscal_year_end_date'),
      first(row,'vendor_name'),
      first(row,'procurement_description'),
      first(row,'award_date'),
      first(row,'contract_begin_date','contract_start_date','begin_date','start_date'),
      first(row,'contract_end_date','end_date'),
      first(row,'contract_amount','amount','procurement_amount'),
      first(row,'procurement_number','contract_number','contract_id'),
    ]
    return stable_id('nys-abo-row',*material)

def person_name(row):
    return clean(' '.join(x for x in (
      clean(row.get('first_name')),
      clean(row.get('middle_initial') or row.get('middle_name')),
      clean(row.get('last_name')),
      clean(row.get('suffix')),
    ) if x))

# ---- DEC 7G applicator region ----
market=get(LIVE+'data/domestic-water-market.json')
applicators=market.get('dec_7g_applicators') or []
served_by_key={(clean(r.get('cert_number')),clean(r.get('name'))):r for r in applicators}
root='https://data.ny.gov/resource/c7db-kwpj.json'
params={'$where':"lower(category)='7g'",'$order':'cert_number','$limit':50000}
source=get(root+'?'+up.urlencode(params))
if len(source)>=50000:
    raise RuntimeError('DEC 7G source reached query cap; refusing incomplete census')
dec_rows=[]
mismatches=[]
for row in source:
    key=(clean(row.get('cert_number')),person_name(row))
    served=served_by_key.get(key)
    source_region=clean(row.get('region')) or None
    normalized_region=(clean(served.get('dec_region')) or None) if served else None
    rec={'cert_number':key[0],'name':key[1],'source_region':source_region,
         'served_found':served is not None,'served_dec_region':normalized_region}
    dec_rows.append(rec)
    if served is None or source_region!=normalized_region:
        mismatches.append(rec)
dec_summary={
  'source_rows':len(source),'served_applicators':len(applicators),
  'exact_key_matches':sum(r['served_found'] for r in dec_rows),
  'source_nonblank_region':sum(r['source_region'] is not None for r in dec_rows),
  'served_nonblank_dec_region':sum(r['served_dec_region'] is not None for r in dec_rows),
  'mismatch_count':len(mismatches),'mismatches':mismatches[:100],
  'diagnosis':('CONFIRMED_NORMALIZATION_DEFECT' if source and all(r['served_found'] for r in dec_rows)
               and any(r['source_region'] and r['served_dec_region'] is None for r in dec_rows) else 'UNRESOLVED'),
  'first_failing_stage':'scripts/towersignal/domestic_water_market.py normalize_dec_applicator',
  'source_field':'region','normalized_field':'dec_region'
}
(OUT/'dec-applicator-region-audit.json').write_text(json.dumps(dec_summary,indent=2))

# ---- NYS ABO State Authority spend/context fields ----
proc=get(LIVE+'data/procurement-nys-authorities.json')
contracts=proc.get('contracts') or []
state_contracts=[r for r in contracts if r.get('source_dataset_id')=='ehig-g5x3']
served_by_id={clean(r.get('source_record_id')):r for r in state_contracts if clean(r.get('source_record_id'))}
terms=(
    'cooling tower','water treatment','cooling water','condenser water','boiler water','legionella',
    'disinfection','water management','water quality','biocide','chiller','hvac maintenance',
    'mechanical maintenance','laboratory testing','chemical treatment'
)
# Add current normalized vendors as exact source-search terms to make the joined universe at least as broad
# as the served relevant-contract population, without using fuzzy matching.
vendors=sorted({clean(r.get('vendor_raw')) for r in state_contracts if clean(r.get('vendor_raw'))})
search_terms=list(dict.fromkeys([*terms,*vendors]))
candidate={}
for term in search_terms:
    offset=0
    while True:
        q={'$q':term,'$limit':50000,'$offset':offset}
        page=get('https://data.ny.gov/resource/ehig-g5x3.json?'+up.urlencode(q))
        for row in page:
            candidate[abo_fingerprint('ehig-g5x3',row)]=row
        if len(page)<50000: break
        offset+=50000
        if offset>1000000: raise RuntimeError('ABO search exceeded bounded audit pagination')

joined=[]
missing_source_ids=[]
for sid,served in served_by_id.items():
    row=candidate.get(sid)
    if row is None:
        missing_source_ids.append(sid); continue
    source_to_date=first(row,'amount_expended_to_date')
    source_fy=first(row,'amount_expended_for_fiscal_year')
    source_balance=first(row,'current_or_outstanding_balance')
    source_transaction=first(row,'transaction_number')
    joined.append({
      'source_record_id':sid,'vendor_raw':served.get('vendor_raw'),
      'source_amount_expended_to_date':source_to_date,
      'source_amount_expended_for_fiscal_year':source_fy,
      'source_current_or_outstanding_balance':source_balance,
      'source_transaction_number':source_transaction,
      'served_spend_to_date':served.get('spend_to_date'),
      'served_source_contract_id':served.get('source_contract_id'),
    })

def nonblank(v): return v not in (None,'')
abo_summary={
  'served_state_authority_contracts':len(state_contracts),
  'candidate_source_rows':len(candidate),
  'joined_exact_fingerprint_contracts':len(joined),
  'missing_source_ids':missing_source_ids,
  'source_nonblank_amount_expended_to_date':sum(nonblank(r['source_amount_expended_to_date']) for r in joined),
  'source_nonblank_amount_expended_for_fiscal_year':sum(nonblank(r['source_amount_expended_for_fiscal_year']) for r in joined),
  'source_nonblank_current_or_outstanding_balance':sum(nonblank(r['source_current_or_outstanding_balance']) for r in joined),
  'source_nonblank_transaction_number':sum(nonblank(r['source_transaction_number']) for r in joined),
  'served_nonblank_spend_to_date':sum(nonblank(r['served_spend_to_date']) for r in joined),
  'source_to_date_present_but_served_spend_missing':sum(nonblank(r['source_amount_expended_to_date']) and not nonblank(r['served_spend_to_date']) for r in joined),
  'source_fy_present_but_served_spend_missing':sum(nonblank(r['source_amount_expended_for_fiscal_year']) and not nonblank(r['served_spend_to_date']) for r in joined),
  'source_transaction_present_but_contract_id_missing':sum(nonblank(r['source_transaction_number']) and not nonblank(r['served_source_contract_id']) for r in joined),
  'examples':[r for r in joined if (nonblank(r['source_amount_expended_to_date']) or nonblank(r['source_amount_expended_for_fiscal_year']) or nonblank(r['source_transaction_number'])) and not nonblank(r['served_spend_to_date'])][:100],
  'diagnosis':'CONFIRMED_NORMALIZATION_GAP' if joined and any(nonblank(r['source_amount_expended_to_date']) and not nonblank(r['served_spend_to_date']) for r in joined) else 'UNRESOLVED',
  'first_failing_stage':'scripts/towersignal/nys_authority_procurement.py normalize_row',
  'boundary':'Exact source_record_id fingerprint joins only. Source values are procurement report values, never company revenue.'
}
(OUT/'abo-state-spend-audit.json').write_text(json.dumps(abo_summary,indent=2))
print(json.dumps({'dec':{k:v for k,v in dec_summary.items() if k not in {'mismatches'}},
                  'abo':{k:v for k,v in abo_summary.items() if k not in {'examples'}}},indent=2))
