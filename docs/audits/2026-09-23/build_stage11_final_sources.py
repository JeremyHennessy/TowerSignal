from __future__ import annotations
import json,re,sys,urllib.request as ur
from pathlib import Path
from collections import defaultdict

ROOT=Path('.');sys.path.insert(0,str(ROOT/'scripts'))
OUT=Path('.audit-stage11');OUT.mkdir(exist_ok=True)

from towersignal.acris import MASTER_SELECT,LEGAL_SELECT,PARTY_SELECT
from towersignal.nys_service_line_inventory import SOURCE_FIELDS as NYS_LSLI_FIELDS
from towersignal.planimetrics import SELECT_FIELDS as PLANIMETRIC_SELECT
import build_lead_service_line_cache as nyc_lsl

SPECS={
 'dg92-zbpx':('data.cityofnewyork.us','NYC City Record','FULL_ROW',['scripts/towersignal/city_record.py'],None),
 'ehig-g5x3':('data.ny.gov','NYS ABO State Authorities procurement','FULL_ROW',['scripts/towersignal/nys_authority_procurement.py'],None),
 '8w5p-k45m':('data.ny.gov','NYS ABO Local Authorities procurement','FULL_ROW',['scripts/towersignal/nys_authority_procurement.py'],None),
 'd84c-dk28':('data.ny.gov','NYS ABO Local Development Corporations procurement','FULL_ROW',['scripts/towersignal/nys_authority_procurement.py'],None),
 'p3p6-xqr5':('data.ny.gov','NYS ABO Industrial Development Agencies procurement','FULL_ROW',['scripts/towersignal/nys_authority_procurement.py'],None),
 'j63k-4n92':('health.data.ny.gov','NYS lead service-line inventory','EXPLICIT',['scripts/towersignal/nys_service_line_inventory.py'],set(NYS_LSLI_FIELDS)),
 'rytv-g5ui':('data.cityofnewyork.us','DOHMH drinking-water tank compliance','FULL_ROW',['scripts/towersignal/domestic_water.py','scripts/towersignal/domestic_water_market.py'],None),
 '8h5j-fqxa':('data.cityofnewyork.us','ACRIS Real Property Legals','EXPLICIT',['scripts/towersignal/acris.py'],set(LEGAL_SELECT.split(','))),
 'bnx9-e6tj':('data.cityofnewyork.us','ACRIS Real Property Master','EXPLICIT',['scripts/towersignal/acris.py'],set(MASTER_SELECT.split(','))),
 '636b-3b5g':('data.cityofnewyork.us','ACRIS Real Property Parties','EXPLICIT',['scripts/towersignal/acris.py'],set(PARTY_SELECT.split(','))),
 'h8u2-6ejg':('data.ny.gov','DEC registered pesticide businesses','FULL_ROW',['scripts/towersignal/domestic_water_market.py'],None),
 'c7db-kwpj':('data.ny.gov','DEC certified pesticide applicators','FULL_ROW',['scripts/towersignal/domestic_water_market.py'],None),
 'k5us-nav4':('data.cityofnewyork.us','Free residential lead/copper samples','FULL_ROW',['scripts/towersignal/domestic_water_market.py'],None),
 '3wxk-qa8q':('data.cityofnewyork.us','Lead/copper compliance samples','FULL_ROW',['scripts/towersignal/domestic_water_market.py'],None),
 'jqfp-uff7':('data.cityofnewyork.us','NYC DEP service-line locations','EXPLICIT',['scripts/build_lead_service_line_cache.py','scripts/attach_nyc_service_lines.py'],set(nyc_lsl.SELECT.split(','))),
 'x748-37q7':('data.cityofnewyork.us','NYC planimetric cooling towers','EXPLICIT',['scripts/towersignal/planimetrics.py'],set(PLANIMETRIC_SELECT.split(','))),
}

def get(url):
    with ur.urlopen(ur.Request(url,headers={'User-Agent':'TowerSignal-stage11-field-audit'}),timeout=60) as r:return json.load(r)

file_text={}
for _,_,_,paths,_ in SPECS.values():
    for p in paths:
        if p not in file_text:file_text[p]=Path(p).read_text()

rows=[];summary={}
for sid,(host,label,mode,paths,explicit) in SPECS.items():
    meta=get(f'https://{host}/api/views/{sid}.json')
    cols=meta.get('columns') or []
    published={str(c.get('fieldName')) for c in cols if c.get('fieldName')}
    requested=published if mode=='FULL_ROW' else (explicit & published)
    counts=defaultdict(int)
    combined='\n'.join(file_text[p] for p in paths)
    for col in cols:
        field=str(col.get('fieldName') or '')
        if not field:continue
        req=field in requested
        # Exact literal reference in collector code. This intentionally does not infer semantic use from fuzzy names.
        literal=bool(re.search(r'''["']'''+re.escape(field)+r'''["']''',combined))
        # NYS LSLI deliberately preserves all 20 authoritative fields; computed-region fields are explicitly excluded.
        if sid=='j63k-4n92' and field in requested:
            literal=True
        # Explicit select contracts mean selected fields are retrieved; if not otherwise referenced they remain retained/source-provenance.
        if req and literal:
            disp='USED';reason='Requested and explicitly referenced/preserved by current collector/normalizer.'
        elif req:
            disp='RETAINED_NOT_DISPLAYED';reason='Requested by explicit source contract but no exact downstream semantic reference detected in audited collector files.'
        else:
            disp='UNRESOLVED';reason='Official published field not requested by current scoped collector; requires field-level usefulness/exclusion review.'
        counts[disp]+=1
        rows.append({'source_id':sid,'source_label':label,'publisher_name':meta.get('name'),'source_updated_at':meta.get('rowsUpdatedAt'),
          'official_field':field,'official_name':col.get('name'),'description':col.get('description'),'datatype':col.get('dataTypeName'),
          'requested':req,'exact_code_reference':literal,'retrieval_mode':mode,'collector_files':paths,'disposition':disp,'reason':reason})
    summary[sid]={'label':label,'published_fields':len(cols),'requested_fields':len(requested),'dispositions':dict(counts),'source_updated_at':meta.get('rowsUpdatedAt')}
result={'field_rows':len(rows),'sources':summary,
 'boundary':'Exact schema/collector literal scan. FULL_ROW means fields arrive in fetched source rows but are not called durably retained unless normalized/stored. Flexible source aliases may require manual review even when no exact literal is found.'}
(OUT/'final-source-field-ledger.json').write_text(json.dumps(rows,indent=2))
(OUT/'final-source-field-summary.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
