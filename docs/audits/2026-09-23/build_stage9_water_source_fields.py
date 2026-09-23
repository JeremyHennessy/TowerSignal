from __future__ import annotations
import ast,json,re,urllib.request as ur
from pathlib import Path
from collections import defaultdict

OUT=Path('.audit-stage9');OUT.mkdir(exist_ok=True)
SOURCES={
 'erm2-nwe9':('data.cityofnewyork.us','NYC 311 service requests'),
 'wvxf-dwi5':('data.cityofnewyork.us','NYC HPD violations'),
 'w9ak-ipjd':('data.cityofnewyork.us','NYC DOB NOW job application filings'),
 'rbx6-tga4':('data.cityofnewyork.us','NYC DOB NOW approved permits'),
 '5zyy-y8am':('data.cityofnewyork.us','NYC LL84 benchmarking'),
}
selected={
 'erm2-nwe9':{
  'unique_key','created_date','closed_date','agency','agency_name','complaint_type','descriptor','descriptor_2',
  'incident_zip','incident_address','street_name','status','resolution_description','bbl','borough'
 },
 'wvxf-dwi5':{
  'violationid','buildingid','registrationid','boro','housenumber','streetname','zip','class','inspectiondate',
  'novdescription','currentstatus','currentstatusdate','violationstatus','rentimpairing','bin','bbl'
 },
 'w9ak-ipjd':{
  'job_filing_number','filing_status','house_no','street_name','borough','bin','bbl','applicant_professional_title',
  'applicant_license','applicant_first_name','applicants_middle_initial','applicant_last_name','applicant_business_name',
  'owner_s_business_name','plumbing_work_type','boiler_equipment_work_type_','mechanical_systems_work_type_',
  'filing_date','approved_date','signoff_date','job_description'
 },
 'rbx6-tga4':{
  'job_filing_number','work_permit','sequence_number','filing_reason','house_no','street_name','borough','bin','bbl',
  'work_type','permittee_s_license_type','applicant_license','applicant_first_name','applicant_last_name',
  'applicant_business_name','approved_date','issued_date','expired_date','job_description','estimated_job_costs',
  'owner_business_name','permit_status'
 },
 '5zyy-y8am':{
  'report_year','property_id','property_name','year_ending','nyc_borough_block_and_lot','nyc_building_identification',
  'address_1','city','postal_code','metered_areas_water','water_use_all_water_sources','indoor_water_use_all_water',
  'outdoor_water_use_all_water','municipally_supplied_potable','municipally_supplied_potable_1',
  'municipally_supplied_potable_2','municipally_supplied_potable_3','estimated_values_water',
  'alert_water_meter_has_less','last_modified_date_water'
 }
}
normalizer='scripts/towersignal/nyc_water_signals.py'
text=Path(normalizer).read_text()

# Exact source-field references inside source-specific normalizers/classifiers.
source_funcs={
 'erm2-nwe9':{'normalize_311','classify_311','_dedupe_311_rows'},
 'wvxf-dwi5':{'normalize_hpd','classify_hpd','_dedupe_hpd_rows'},
 'w9ak-ipjd':{'normalize_dob_job','classify_dob_work','_applicant_name'},
 'rbx6-tga4':{'normalize_dob_permit','classify_dob_work','_applicant_name'},
 '5zyy-y8am':{'normalize_ll84'},
}
tree=ast.parse(text)
refs=defaultdict(set)
for node in ast.walk(tree):
    if isinstance(node,ast.FunctionDef):
        for sid,funcs in source_funcs.items():
            if node.name not in funcs:continue
            for x in ast.walk(node):
                if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr=='get' and isinstance(x.func.value,ast.Name) and x.func.value.id=='row' and x.args and isinstance(x.args[0],ast.Constant) and isinstance(x.args[0].value,str):
                    refs[sid].add(x.args[0].value)

def get(url):
    with ur.urlopen(ur.Request(url,headers={'User-Agent':'TowerSignal-stage9-source-field-audit'}),timeout=60) as r:return json.load(r)

rows=[];summary={}
for sid,(host,label) in SOURCES.items():
    meta=get(f'https://{host}/api/views/{sid}.json')
    cols=meta.get('columns') or []
    counts=defaultdict(int)
    for col in cols:
        field=col.get('fieldName')
        if not field:continue
        requested=field in selected[sid]
        used=field in refs[sid]
        if used:
            disposition='USED'
            reason='Explicit source-specific normalization/classification/identity reference.'
        elif requested:
            disposition='RETAINED_NOT_DISPLAYED'
            reason='Explicitly requested and retained in normalized/raw evidence but no source-specific semantic reference was detected beyond storage.'
        else:
            disposition='UNRESOLVED'
            reason='Published by source but not requested by current scoped collector; requires field-level usefulness/exclusion review.'
        counts[disposition]+=1
        rows.append({
          'source_id':sid,'source_label':label,'publisher_name':meta.get('name'),'source_updated_at':meta.get('rowsUpdatedAt'),
          'official_field':field,'official_name':col.get('name'),'description':col.get('description'),'datatype':col.get('dataTypeName'),
          'requested':requested,'semantic_reference_detected':used,'disposition':disposition,'reason':reason,
          'collector':'scripts/towersignal/nyc_water_signals.py'
        })
    summary[sid]={'label':label,'published_fields':len(cols),'requested_fields':len(selected[sid] & {c.get('fieldName') for c in cols}),
                  'semantic_referenced_fields':len(refs[sid] & {c.get('fieldName') for c in cols}),
                  'dispositions':dict(counts),'source_updated_at':meta.get('rowsUpdatedAt')}
out={'field_rows':len(rows),'sources':summary,
     'boundary':'Schema/collector/normalizer field audit. UNRESOLVED means not yet field-reviewed, not missing data. Scope filters remain separately audited.'}
(OUT/'water-signal-source-field-ledger.json').write_text(json.dumps(rows,indent=2))
(OUT/'water-signal-source-field-summary.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
