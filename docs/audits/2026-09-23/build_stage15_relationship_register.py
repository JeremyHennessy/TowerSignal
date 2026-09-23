from __future__ import annotations
import ast,json,re
from collections import Counter,defaultdict
from pathlib import Path

OUT=Path('.audit-stage15');OUT.mkdir(exist_ok=True)
REL_KEYS={
 'match_basis','matchBasis','property_link_confidence','tower_link_confidence','facility_match_confidence',
 'company_match_confidence','identity_confidence','relationship','relationship_evidence','service_assignment_confidence',
 'resolution_method','cross_source_resolution_method','relationship_class','evidence_class','factClass','confidence'
}
records=[]

for p in Path('scripts').rglob('*.py'):
    try:text=p.read_text(); tree=ast.parse(text)
    except Exception:continue
    lines=text.splitlines()
    for node in ast.walk(tree):
        if isinstance(node,ast.Dict):
            for k,v in zip(node.keys,node.values):
                if not isinstance(k,ast.Constant) or not isinstance(k.value,str) or k.value not in REL_KEYS:continue
                value=None
                if isinstance(v,ast.Constant) and isinstance(v.value,(str,int,float,bool)):value=v.value
                elif isinstance(v,ast.Name):value=f'VARIABLE:{v.id}'
                elif isinstance(v,ast.JoinedStr):value='DYNAMIC_FSTRING'
                else:value=type(v).__name__
                records.append({'language':'python','file':str(p),'line':getattr(node,'lineno',None),'key':k.value,'value':value,'source_line':lines[getattr(node,'lineno',1)-1].strip()[:700]})
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in {'stable_id'}:
            pass

# TS/TSX object literals and type unions.
key_re=re.compile(r'\b('+'|'.join(re.escape(k) for k in sorted(REL_KEYS,key=len,reverse=True))+r')\s*:\s*([^,\n}]+)')
for p in Path('src').rglob('*'):
    if not p.is_file() or p.suffix not in {'.ts','.tsx'} or '.test.' in p.name:continue
    text=p.read_text();lines=text.splitlines()
    for i,line in enumerate(lines,1):
        for m in key_re.finditer(line):
            raw=m.group(2).strip()
            lit=re.match(r"['\"]([^'\"]+)['\"]",raw)
            value=lit.group(1) if lit else ('DYNAMIC_EXPRESSION:'+raw[:160])
            records.append({'language':'typescript','file':str(p),'line':i,'key':m.group(1),'value':value,'source_line':line.strip()[:700]})

# Join/index mechanism inventory, kept separate from claims.
join_records=[]
join_patterns=[
 ('BIN',re.compile(r'\b(?:by_bin|bin_to_|systems_by_bin|_by_bin)\b',re.I)),
 ('BBL',re.compile(r'\b(?:by_bbl|bbl_to_|systems_by_bbl|_by_bbl)\b',re.I)),
 ('SYSTEM_ID',re.compile(r'\b(?:systems_by_id|by_system|system_id)\b',re.I)),
 ('REGISTRATION_ID',re.compile(r'\bregistration(?:_?id)?\b',re.I)),
 ('SUMMONS_TICKET',re.compile(r'\b(?:summons|ticket_number)\b',re.I)),
 ('SOURCE_RECORD_ID',re.compile(r'\bsource_record_id\b',re.I)),
 ('COMPANY_FIRM',re.compile(r'\b(?:company_id|firm_id|provider_id|lab_id)\b',re.I)),
]
for base in ['scripts','src']:
    for p in Path(base).rglob('*'):
        if not p.is_file() or p.suffix not in {'.py','.ts','.tsx'} or '.test.' in p.name:continue
        try:lines=p.read_text().splitlines()
        except Exception:continue
        for i,line in enumerate(lines,1):
            hits=[name for name,pat in join_patterns if pat.search(line)]
            if hits and any(token in line for token in ['get(','setdefault','[','].','Map(','lookup','match','attach','resolve','index','where=',' in (',' in {']):
                join_records.append({'file':str(p),'line':i,'join_key_classes':hits,'text':line.strip()[:700]})

# Contract semantics.
def semantic(value):
    s=str(value).upper()
    if any(x in s for x in ['UNLINKED','UNRESOLVED','VERIFY','ADDRESS_CONTEXT','CONTEXT_ONLY','NOT_PROOF']):
        return 'NONCONFIRMING_OR_BOUNDARY'
    if any(x in s for x in ['EXACT','CONFIRMED','STRONG','OBSERVED_SERVICE','RECORDED_ROLE','QUALIFIED_PROVIDER']):
        return 'CONFIRMING_OR_OBSERVED'
    if s.startswith('VARIABLE:') or s.startswith('DYNAMIC') or s.endswith('EXPRESSION'):
        return 'DYNAMIC_REQUIRES_TRACE'
    return 'OTHER'

for r in records:r['semantic_class']=semantic(r['value'])
unique_contracts=Counter((r['key'],str(r['value']),r['semantic_class']) for r in records)
summary={
 'contract_occurrences':len(records),
 'unique_key_value_contracts':len(unique_contracts),
 'semantic_counts':dict(Counter(r['semantic_class'] for r in records)),
 'keys':dict(Counter(r['key'] for r in records)),
 'join_mechanism_occurrences':len(join_records),
 'join_key_class_counts':dict(Counter(k for r in join_records for k in r['join_key_classes'])),
 'boundary':'Static contract inventory. A CONFIRMING_OR_OBSERVED literal is not independently validated merely by appearing in code; each relationship still depends on the upstream join and source-population evidence.'
}
contracts=[{'key':k,'value':v,'semantic_class':s,'occurrences':n} for (k,v,s),n in sorted(unique_contracts.items())]
(OUT/'relationship-contract-occurrences.json').write_text(json.dumps(records,indent=2))
(OUT/'relationship-contracts.json').write_text(json.dumps(contracts,indent=2))
(OUT/'join-mechanism-inventory.json').write_text(json.dumps(join_records,indent=2))
(OUT/'relationship-register-summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
