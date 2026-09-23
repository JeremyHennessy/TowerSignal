from __future__ import annotations
import ast, json, re, urllib.request as ur, urllib.parse as up
from pathlib import Path
from collections import defaultdict

ROOT=Path('.')
OUT=Path('.audit-stage5');OUT.mkdir(exist_ok=True)
SOURCES={
 'y4fw-iqfr':('data.cityofnewyork.us','NYC cooling-tower registrations'),
 'f9wb-g8mb':('data.cityofnewyork.us','NYC cooling-tower inspections'),
 'tesw-yqqr':('data.cityofnewyork.us','HPD multiple-dwelling registrations'),
 'feu5-w2e2':('data.cityofnewyork.us','HPD registration contacts'),
 '64uk-42ks':('data.cityofnewyork.us','MapPLUTO'),
 '24a4-muw7':('health.data.ny.gov','NYS cooling-tower registry weekly extract'),
}
REQ={'User-Agent':'TowerSignal-stage5-field-ledger-audit/20260923'}

def get(url):
    with ur.urlopen(ur.Request(url,headers=REQ),timeout=60) as r:return json.load(r)

# Exact production source-code references, without interpreting arbitrary prose.
code_files=[]
for base in ['scripts','src']:
    for p in Path(base).rglob('*'):
        if p.is_file() and p.suffix in {'.py','.ts','.tsx'}:
            try:text=p.read_text()
            except Exception:continue
            code_files.append((str(p),text))

# Known explicit select/query contracts from current product.
select_contracts={}
for path,text in code_files:
    # Python constants such as PLUTO_SELECT, REGISTRATION_SELECT, CONTACT_SELECT.
    if path.endswith('.py'):
        try:tree=ast.parse(text)
        except SyntaxError:continue
        env={}
        for node in tree.body:
            if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
                name=node.targets[0].id
                try:value=ast.literal_eval(node.value)
                except Exception:continue
                env[name]=value
        # Handle ",".join(("a","b")) AST explicitly.
        for node in tree.body:
            if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
                name=node.targets[0].id
                v=node.value
                if isinstance(v,ast.Call) and isinstance(v.func,ast.Attribute) and v.func.attr=='join' and isinstance(v.func.value,ast.Constant) and v.func.value.value==',' and v.args:
                    try:parts=ast.literal_eval(v.args[0]); env[name]=','.join(parts)
                    except Exception:pass
        for k,v in env.items():
            if isinstance(v,str) and ',' in v and ('SELECT' in k or k.endswith('_FIELDS')):
                select_contracts[(path,k)]={x.strip() for x in v.split(',') if x.strip()}

# Source-specific current retrieval semantics established from inspected builders.
retrieval={
 'y4fw-iqfr':{'mode':'FULL_ROW_FETCH','collector':'scripts/towersignal/build_data_live.py -> fetch_dataset','selected':'ALL_PUBLISHED_FIELDS'},
 'f9wb-g8mb':{'mode':'FULL_ROW_FETCH','collector':'scripts/towersignal/build_data_live.py -> fetch_dataset','selected':'ALL_PUBLISHED_FIELDS'},
 'tesw-yqqr':{'mode':'EXPLICIT_SELECT','collector':'scripts/towersignal/hpd_identity.py','select_key':('scripts/towersignal/hpd.py','REGISTRATION_SELECT')},
 'feu5-w2e2':{'mode':'EXPLICIT_SELECT','collector':'scripts/towersignal/hpd_identity.py','select_key':('scripts/towersignal/hpd.py','CONTACT_SELECT')},
 '64uk-42ks':{'mode':'EXPLICIT_SELECT','collector':'scripts/towersignal/pluto.py','select_key':('scripts/towersignal/pluto.py','PLUTO_SELECT')},
 '24a4-muw7':{'mode':'FULL_ROW_FETCH','collector':'scripts/towersignal/nys_registry.py -> fetch_dataset','selected':'ALL_PUBLISHED_FIELDS'},
}

# Explicit row.get references by source family files.
family_files={
 'y4fw-iqfr':['scripts/towersignal/normalize.py','scripts/towersignal/build_data_live.py'],
 'f9wb-g8mb':['scripts/towersignal/inspections.py','scripts/towersignal/build_data_live.py'],
 'tesw-yqqr':['scripts/towersignal/hpd_identity.py','scripts/towersignal/hpd.py'],
 'feu5-w2e2':['scripts/towersignal/hpd_identity.py','scripts/towersignal/hpd.py'],
 '64uk-42ks':['scripts/towersignal/pluto.py'],
 '24a4-muw7':['scripts/towersignal/nys_registry.py'],
}
field_refs=defaultdict(lambda:defaultdict(list))
for sid,paths in family_files.items():
    for path in paths:
        text=Path(path).read_text()
        for m in re.finditer(r"(?:row|record)\.get\(["']([^"']+)["']\)",text):
            field_refs[sid][m.group(1)].append({'path':path,'offset':m.start()})

rows=[]
source_summary={}
for sid,(host,label) in SOURCES.items():
    meta=get(f'https://{host}/api/views/{sid}.json')
    cols=meta.get('columns') or []
    contract=retrieval[sid]
    if contract['mode']=='FULL_ROW_FETCH':
        requested={c.get('fieldName') for c in cols if c.get('fieldName')}
    else:
        requested=select_contracts.get(tuple(contract['select_key']),set())
    counts=defaultdict(int)
    for col in cols:
        field=col.get('fieldName')
        if not field:continue
        refs=field_refs[sid].get(field,[])
        is_requested=field in requested
        # Conservative disposition: code-used is USED; requested but not referenced is RETAINED_NOT_DISPLAYED
        # only for full-row fetches where the field is actually in fetched raw rows during normalization.
        # Explicit-select fields not referenced are still retained transiently but not stored; call them INTENTIONALLY_EXCLUDED
        # only when they are metadata/geometry system columns with no business use is not safe, so leave UNRESOLVED.
        if refs:
            disposition='USED'
            reason='Explicit production normalization/identity reference'
        elif is_requested and contract['mode']=='FULL_ROW_FETCH':
            disposition='RETAINED_NOT_DISPLAYED'
            reason='Fetched in complete source row but no explicit normalized-field reference found in audited family code; raw row is transient unless another cache retains it'
        elif is_requested:
            disposition='UNRESOLVED'
            reason='Explicitly selected by collector but no audited row.get reference found; requires storage/consumer trace before classification'
        else:
            disposition='UNRESOLVED'
            reason='Not requested by current collector; usefulness/exclusion reason requires field-level review'
        counts[disposition]+=1
        rows.append({
          'source_id':sid,'source_label':label,'publisher_name':meta.get('name'),'source_updated_at':meta.get('rowsUpdatedAt'),
          'official_field':field,'official_name':col.get('name'),'description':col.get('description'),'datatype':col.get('dataTypeName'),
          'requested':is_requested,'retrieval_mode':contract['mode'],'collector':contract['collector'],
          'production_references':refs,'disposition':disposition,'disposition_reason':reason
        })
    source_summary[sid]={'label':label,'published_fields':len(cols),'requested_fields':len(requested & {c.get("fieldName") for c in cols}),
                         'dispositions':dict(counts),'source_updated_at':meta.get('rowsUpdatedAt'),'metadata_url':f'https://{host}/api/views/{sid}.json'}
Path(OUT/'source-field-ledger-batch.json').write_text(json.dumps(rows,indent=2))
Path(OUT/'source-field-ledger-batch-summary.json').write_text(json.dumps({'sources':source_summary,'field_rows':len(rows)},indent=2))
print(json.dumps({'sources':source_summary,'field_rows':len(rows)},indent=2))
