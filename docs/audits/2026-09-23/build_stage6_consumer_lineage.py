from __future__ import annotations
import ast, json, re
from pathlib import Path
from collections import defaultdict

OUT=Path('.audit-stage6');OUT.mkdir(exist_ok=True)

consumer_files=[
 'src/components/AccountEvidenceWorkspace.tsx',
 'src/components/ClientSiteReport.tsx',
 'src/components/CompanyProfilePage.tsx',
 'src/components/PortfoliosPage.tsx',
 'src/components/AccountUnifiedTimeline.tsx',
 'src/components/WorkflowAccountSection.tsx',
 'src/components/WorkflowPanel.tsx',
 'src/components/BuildingWaterSignalsSection.tsx',
 'src/components/salesKnownFirms.ts',
 'src/domain/accountEvidence.ts',
 'src/utils/accountReportModel.ts',
 'src/utils/prepareAccountReport.ts',
 'src/utils/workflowExport.ts',
 'src/components/UserAccountPage.tsx',
]
type_files=['src/types/data.ts','src/types/company.ts','src/types/history.ts','src/types/workflow.ts','src/types/procurement.ts']

def py_direct_mappings(path, functions):
    text=Path(path).read_text()
    tree=ast.parse(text)
    mappings=[]
    for node in ast.walk(tree):
        if not isinstance(node,ast.FunctionDef) or node.name not in functions:continue
        for d in ast.walk(node):
            if not isinstance(d,ast.Dict):continue
            for k,v in zip(d.keys,d.values):
                if not isinstance(k,ast.Constant) or not isinstance(k.value,str):continue
                # direct row.get or wrapper(row.get(...))
                gets=[]
                for x in ast.walk(v):
                    if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr=='get' and isinstance(x.func.value,ast.Name) and x.func.value.id in {'row','record'} and x.args and isinstance(x.args[0],ast.Constant) and isinstance(x.args[0].value,str):
                        gets.append(x.args[0].value)
                for source in sorted(set(gets)):
                    mappings.append({'normalizer_file':path,'function':node.name,'source_field':source,'normalized_field':k.value})
    return mappings

mappings=[]
mappings += py_direct_mappings('scripts/towersignal/normalize.py', {'normalize_registrations','normalize_coordinates','parse_sample_dates'})
mappings += py_direct_mappings('scripts/towersignal/pluto.py', {'normalize_pluto_record'})
mappings += py_direct_mappings('scripts/towersignal/hpd.py', {'normalize_contact'})
mappings += py_direct_mappings('scripts/towersignal/nys_registry.py', {'normalize_nys_registry','normalize_nys_coordinates'})
mappings += py_direct_mappings('scripts/towersignal/nyc_water_signals.py', {'normalize_dob_job','normalize_dob_permit','normalize_ll84'})

# inspection normalized fields are constructed incrementally; enumerate explicit source contracts separately.
for source,dest in {
 'inspection_date':'inspection_date','inspection_type':'inspection_type','status':'status','active_equip':'active_equipment_at_publication',
 'violation_code':'violation_code','law_section':'law_section','violation_text':'violation_text','violation_type':'violation_type',
 'citation_text':'citation_text','summons_number':'summons_number'
}.items():
    mappings.append({'normalizer_file':'scripts/towersignal/inspections.py','function':'aggregate_inspections','source_field':source,'normalized_field':dest})

# Remove duplicate mapping tuples.
uniq={}
for m in mappings:uniq[(m['normalizer_file'],m['function'],m['source_field'],m['normalized_field'])]=m
mappings=list(uniq.values())

consumer_text={p:Path(p).read_text() for p in consumer_files if Path(p).exists()}
type_text={p:Path(p).read_text() for p in type_files if Path(p).exists()}

def occurrences(field):
    patterns=[
      re.compile(r'\.'+re.escape(field)+r'\b'),
      re.compile(r'''[\["']'''+re.escape(field)+r'''["']\]'''),
      re.compile(r'''(?:text|sourceText|dateText|waterUse)\([^\n]*?["']'''+re.escape(field)+r'''["']'''),
    ]
    out=[]
    for path,text in consumer_text.items():
        lines=text.splitlines()
        for i,line in enumerate(lines,1):
            if any(p.search(line) for p in patterns):
                out.append({'path':path,'line':i,'text':line.strip()[:500]})
    return out

records=[]
for m in mappings:
    occ=occurrences(m['normalized_field'])
    type_occ=[]
    for path,text in type_text.items():
        for i,line in enumerate(text.splitlines(),1):
            if re.search(r'\b'+re.escape(m['normalized_field'])+r'\??\s*:',line):
                type_occ.append({'path':path,'line':i,'text':line.strip()})
    records.append({**m,'consumer_occurrences':occ,'consumer_count':len(occ),'type_occurrences':type_occ,
                    'consumer_disposition':'CONSUMED_IN_AUDITED_SURFACES' if occ else 'NO_REFERENCE_IN_AUDITED_SURFACES',
                    'limits':'Static reference scan; absence is not proof of no runtime use outside the audited consumer set.'})

# Inventory truncation/pagination/collapse mechanics in audited consumer files.
mechanics=[]
for path,text in consumer_text.items():
    for i,line in enumerate(text.splitlines(),1):
        if any(token in line for token in ['.slice(','.sort(','toSorted(','<details','pageSize','pagination','limit','hidden','collapsed']):
            mechanics.append({'path':path,'line':i,'text':line.strip()[:600]})

summary={
 'mapping_rows':len(records),
 'normalized_fields':len({r['normalized_field'] for r in records}),
 'source_fields':len({r['source_field'] for r in records}),
 'consumed_mapping_rows':sum(r['consumer_count']>0 for r in records),
 'unreferenced_mapping_rows':sum(r['consumer_count']==0 for r in records),
 'consumer_files_checked':list(consumer_text),
 'type_files_checked':list(type_text),
 'presentation_mechanics_count':len(mechanics),
 'boundary':'Static code-path trace, not authenticated browser proof. A no-reference result is scoped to listed consumers only.'
}
(OUT/'core-normalized-consumer-lineage.json').write_text(json.dumps(records,indent=2))
(OUT/'consumer-presentation-mechanics.json').write_text(json.dumps(mechanics,indent=2))
(OUT/'consumer-lineage-summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
