from __future__ import annotations
import json,re
from pathlib import Path

OUT=Path('.audit-stage7');OUT.mkdir(exist_ok=True)
lineage=json.loads(Path('docs/audits/2026-09-23/stage6-consumer-lineage/core-normalized-consumer-lineage.json').read_text())
targets=sorted({r['normalized_field'] for r in lineage if r.get('consumer_count')==0})
origin_files={r['normalized_field']:set() for r in lineage}
for r in lineage:origin_files.setdefault(r['normalized_field'],set()).add(r['normalizer_file'])

files=[]
for base in ['scripts','src']:
    for p in Path(base).rglob('*'):
        if not p.is_file() or p.suffix not in {'.py','.ts','.tsx','.mjs'}:continue
        if '/tests/' in str(p) or p.name.endswith(('.test.ts','.test.tsx','.test.py')):continue
        try:text=p.read_text()
        except Exception:continue
        files.append((str(p),text))

rows=[]
for field in targets:
    occ=[]
    for path,text in files:
        if path in origin_files.get(field,set()):continue
        patterns=[
          re.compile(r'\b'+re.escape(field)+r'\b'),
          re.compile(r'''["']'''+re.escape(field)+r'''["']'''),
        ]
        for i,line in enumerate(text.splitlines(),1):
            if any(p.search(line) for p in patterns):
                # Ignore type-only declarations when possible; record separately.
                kind='TYPE_DECLARATION' if re.search(r'\b'+re.escape(field)+r'\??\s*:',line) and path.startswith('src/types/') else 'DOWNSTREAM_CODE_REFERENCE'
                occ.append({'path':path,'line':i,'kind':kind,'text':line.strip()[:500]})
    code=[o for o in occ if o['kind']=='DOWNSTREAM_CODE_REFERENCE']
    rows.append({'normalized_field':field,'origin_files':sorted(origin_files.get(field,set())),
                 'downstream_code_reference_count':len(code),'type_declaration_count':len(occ)-len(code),
                 'downstream_references':code,'type_references':[o for o in occ if o['kind']=='TYPE_DECLARATION'],
                 'status':'DOWNSTREAM_USED' if code else 'NO_DOWNSTREAM_CODE_REFERENCE'})

summary={'target_fields':len(rows),'downstream_used':sum(r['status']=='DOWNSTREAM_USED' for r in rows),
         'no_downstream_code_reference':sum(r['status']=='NO_DOWNSTREAM_CODE_REFERENCE' for r in rows),
         'boundary':'Exact-name static scan across non-test scripts/src excluding each field normalizer origin. Dynamic access, generated files and semantic use under renamed keys require separate tracing.'}
(OUT/'retained-field-downstream-usage.json').write_text(json.dumps(rows,indent=2))
(OUT/'retained-field-downstream-summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
