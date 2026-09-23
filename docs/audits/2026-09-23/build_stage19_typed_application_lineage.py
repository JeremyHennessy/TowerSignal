from __future__ import annotations
import json,re
from collections import Counter,defaultdict
from pathlib import Path

BASE=Path('docs/audits/2026-09-23')
OUT=Path('.audit-stage19');OUT.mkdir(exist_ok=True)
rows=json.loads((BASE/'stage18-expanded-application-lineage/expanded-application-lineage-remaining.json').read_text())

# Build a conservative property -> type index from src/types plus component-local exported types.
prop_index=defaultdict(list)
type_domains={}
domain_rules=[
 ('OATH',re.compile(r'oath',re.I)),('ACRIS',re.compile(r'acris',re.I)),('PLANIMETRIC',re.compile(r'planimetric|towerfeature|footprint',re.I)),
 ('DOMESTIC_WATER',re.compile(r'domestic|drinking|watertank',re.I)),('NYS',re.compile(r'\bnys|equipment',re.I)),
 ('COMPANY_FIRM',re.compile(r'company|firm|provider|laboratory',re.I)),('SOURCE_HEALTH',re.compile(r'sourcehealth|coverage|verification',re.I)),
 ('HISTORY_CHANGE',re.compile(r'history|change|event',re.I)),('LEGIONELLA',re.compile(r'legionella|alert',re.I)),
 ('PROCUREMENT',re.compile(r'procurement|contract|notice',re.I)),('ENFORCEMENT',re.compile(r'enforcement|violation|facade|swo',re.I)),
 ('SYSTEM_ACCOUNT',re.compile(r'system|detail|account',re.I)),('WORKFLOW',re.compile(r'workflow|watchlist|savedview',re.I)),
 ('WATER_QUALITY',re.compile(r'water|lead|copper|sample',re.I))
]
def domain(name):
    hits=[d for d,p in domain_rules if p.search(name)]
    return hits[0] if len(hits)==1 else ('MULTI:'+','.join(hits) if hits else 'UNKNOWN')

for p in list(Path('src/types').glob('*.ts'))+[x for x in Path('src/components').glob('*.tsx')]:
    text=p.read_text();lines=text.splitlines()
    current=None; depth=0
    for i,line in enumerate(lines,1):
        m=re.search(r'(?:export\s+)?(?:interface|type)\s+([A-Za-z_$][\w$]*)[^=]*=\s*{|(?:export\s+)?interface\s+([A-Za-z_$][\w$]*)\s*{',line)
        if m:
            current=m.group(1) or m.group(2);depth=line.count('{')-line.count('}')
            type_domains[current]=domain(current)
            continue
        if current:
            pm=re.match(r'\s*([A-Za-z_$][\w$]*)\??\s*:\s*([^;,\n]+)',line)
            if pm:
                prop_index[pm.group(1)].append({'type':current,'domain':type_domains[current],'file':str(p),'line':i,'declared_type':pm.group(2).strip()})
            depth += line.count('{')-line.count('}')
            if depth<=0:current=None;depth=0

method_names={'toLocaleString','replaceAll','map','filter','find','some','every','reduce','slice','sort','join','getTime','toString','trim','includes','startsWith','toUpperCase','toLowerCase'}
def properties(chains):
    out=[]
    for chain in chains or []:
        parts=[p for p in re.split(r'\.',chain) if p and p not in method_names]
        # Exclude root variable, keep all field-like suffixes.
        out.extend(parts[1:])
    return list(dict.fromkeys(out))

results=[];counts=Counter()
for r in rows:
    props=properties(r.get('property_chains'))
    candidates=[]
    for prop in props:
        for hit in prop_index.get(prop,[]):
            candidates.append({'property':prop,**hit})
    domains=Counter(c['domain'] for c in candidates if c['domain']!='UNKNOWN')
    # Prefer a single domain, or file-specific obvious domains.
    chosen=None
    if len(domains)==1:
        chosen=next(iter(domains))
    elif domains:
        file=r['file']
        hints=[
          ('SOURCE_HEALTH','SourceHealth'),('ACRIS','Acris'),('PLANIMETRIC','Planimetric'),('DOMESTIC_WATER','DomesticWater'),
          ('NYS','Nys'),('LEGIONELLA','Legionella'),('HISTORY_CHANGE','Changes'),('COMPANY_FIRM','Company'),
          ('PROCUREMENT','Opportunities'),('SYSTEM_ACCOUNT','Account')
        ]
        for d,h in hints:
            if h in file and d in domains:chosen=d;break
    if chosen:
        cls='TYPE_BACKTRACED_DATA_FIELD'
        reason=f'Property chains map to typed domain {chosen}'
    elif candidates:
        cls='TYPE_CANDIDATES_AMBIGUOUS'
        reason='Property names exist in multiple typed domains; manual disambiguation required'
    elif r['stage18_class']=='STILL_UNRESOLVED':
        cls='NO_TYPE_FIELD_TRACE'
        reason='No property-to-type candidate and prior trace unresolved'
    else:
        cls='NO_TYPE_FIELD_TRACE_IN_DATA_COMPONENT'
        reason='Data component known, but property chain did not map to a declared type field'
    counts[cls]+=1
    results.append({**r,'stage19_class':cls,'stage19_reason':reason,'field_properties':props,'type_candidates':candidates,'chosen_domain':chosen})

remaining=[r for r in results if r['stage19_class']!='TYPE_BACKTRACED_DATA_FIELD']
summary={
 'input_records':len(rows),'class_counts':dict(counts),
 'type_backtraced':sum(r['stage19_class']=='TYPE_BACKTRACED_DATA_FIELD' for r in results),
 'remaining_manual':len(remaining),
 'remaining_by_file':Counter(r['file'] for r in remaining).most_common(30),
 'chosen_domain_counts':dict(Counter(r['chosen_domain'] for r in results if r.get('chosen_domain'))),
 'boundary':'Property-name to declared TypeScript model trace. A typed domain identifies the application model lineage, not the original publisher field unless separately linked through source/normalizer ledgers.'
}
(OUT/'typed-application-lineage.json').write_text(json.dumps(results,indent=2))
(OUT/'typed-application-lineage-remaining.json').write_text(json.dumps(remaining,indent=2))
(OUT/'typed-application-lineage-summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
