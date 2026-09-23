from __future__ import annotations
import ast,json,re,sys,urllib.request as ur
from pathlib import Path
from collections import defaultdict

ROOT=Path('.');sys.path.insert(0,str(ROOT/'scripts'))
OUT=Path('.audit-stage10');OUT.mkdir(exist_ok=True)

from towersignal.oath import OATH_SELECT
from towersignal.historical_311_context import DESIRED_FIELDS as HIST311_FIELDS
from towersignal.domestic_water import SELF_REPORT_DATASET_ID
from towersignal.property_enforcement import FACADE_SELECT
import build_legacy_dob_project_cache as legacy

SOURCES={
 'ic3t-wcy2':('data.cityofnewyork.us','Legacy DOB/BIS job applications','scripts/build_legacy_dob_project_cache.py',set(legacy.SELECT.split(',')),'EXPLICIT_SELECT'),
 'jz4z-kudi':('data.cityofnewyork.us','OATH Hearings case status','scripts/towersignal/oath.py',set(OATH_SELECT.split(',')),'EXPLICIT_SELECT'),
 '76ig-c548':('data.cityofnewyork.us','Historical NYC 311 2010-2019','scripts/towersignal/historical_311_context.py',set(HIST311_FIELDS),'EXPLICIT_SELECT'),
 'gjm4-k24g':('data.cityofnewyork.us','DOHMH self-reported drinking-water tank inspections','scripts/towersignal/domestic_water.py',None,'FULL_ROW_EXACT_BIN'),
 'xubg-57si':('data.cityofnewyork.us','DOB NOW façade compliance filings','scripts/towersignal/property_enforcement.py',set(FACADE_SELECT.split(',')),'EXPLICIT_SELECT'),
}
functions={
 'ic3t-wcy2':{'normalize_job','_source_bbl','_applicant'},
 'jz4z-kudi':{'normalize_case','_charges','normalize_ticket_number'},
 '76ig-c548':{'build_historical_context','_add_request'},
 'gjm4-k24g':{'normalize_self_report_row'},
 'xubg-57si':{'normalize_facade_filing'},
}

def get(url):
    with ur.urlopen(ur.Request(url,headers={'User-Agent':'TowerSignal-stage10-field-audit'}),timeout=60) as r:return json.load(r)

def row_refs(path, names):
    text=Path(path).read_text();tree=ast.parse(text);found=set()
    for node in ast.walk(tree):
        if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) or node.name not in names:continue
        for x in ast.walk(node):
            if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr=='get' and isinstance(x.func.value,ast.Name) and x.func.value.id in {'row','record'} and x.args and isinstance(x.args[0],ast.Constant) and isinstance(x.args[0].value,str):
                found.add(x.args[0].value)
            # Dynamic OATH charge fields are handled separately below.
    return found

refs={sid:row_refs(path,functions[sid]) for sid,(_,_,path,_,_) in SOURCES.items()}
# Explicit OATH charge tuple contract.
for i in range(1,11):
    refs['jz4z-kudi'].update({f'charge_{i}_code',f'charge_{i}_code_section',f'charge_{i}_code_description',f'charge_{i}_infraction_amount'})
# Historical 311 delegates normalization to normalize_311, whose selected fields are semantically consumed.
refs['76ig-c548'].update(set(HIST311_FIELDS))

rows=[];summary={}
for sid,(host,label,path,selected,mode) in SOURCES.items():
    meta=get(f'https://{host}/api/views/{sid}.json')
    cols=meta.get('columns') or []
    published={c.get('fieldName') for c in cols if c.get('fieldName')}
    requested=published if selected is None else (selected & published)
    counts=defaultdict(int)
    for col in cols:
        field=col.get('fieldName')
        if not field:continue
        req=field in requested
        semantic=field in refs[sid]
        if semantic and req:
            disposition='USED';reason='Requested and semantically consumed by the current collector/normalizer.'
        elif req:
            disposition='RETAINED_NOT_DISPLAYED';reason='Retrieved by current collector but no source-specific semantic reference detected in audited normalization path.'
        else:
            disposition='UNRESOLVED';reason='Published by official source but not requested by current scoped collector; requires field-level usefulness/exclusion review.'
        counts[disposition]+=1
        rows.append({'source_id':sid,'source_label':label,'publisher_name':meta.get('name'),'source_updated_at':meta.get('rowsUpdatedAt'),
          'official_field':field,'official_name':col.get('name'),'description':col.get('description'),'datatype':col.get('dataTypeName'),
          'requested':req,'semantic_reference_detected':semantic,'retrieval_mode':mode,'collector':path,
          'disposition':disposition,'reason':reason})
    summary[sid]={'label':label,'published_fields':len(cols),'requested_fields':len(requested),
                  'semantic_used_fields':sum(1 for x in rows if x['source_id']==sid and x['disposition']=='USED'),
                  'dispositions':dict(counts),'source_updated_at':meta.get('rowsUpdatedAt')}
result={'field_rows':len(rows),'sources':summary,
 'boundary':'Source-schema/collector audit only. FULL_ROW_EXACT_BIN means fields arrive in source responses; fields not semantically normalized are not assumed durably retained. UNRESOLVED is not a missing-data finding.'}
(OUT/'top-five-source-field-ledger.json').write_text(json.dumps(rows,indent=2))
(OUT/'top-five-source-field-summary.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
