from __future__ import annotations
import json,re
from collections import Counter
from pathlib import Path

BASE=Path('docs/audits/2026-09-23')
OUT=Path('.audit-stage16');OUT.mkdir(exist_ok=True)
rows=json.loads((BASE/'stage14-application-lineage/application-lineage-needs-backtrace.json').read_text())
core=json.loads((BASE/'stage6-consumer-lineage/core-normalized-consumer-lineage.json').read_text())
normalized={str(r.get('normalized_field')) for r in core if r.get('normalized_field')}

source_root=re.compile(r'\b(payload|nysPayload|detail|context|system|systems|row|record|company|firm|owner|procurement|inspection|violation|permit|job|benchmark|sample|contact|acris|oath|pluto|hpd|dob|water|tower|sourceHealth|metadata)\b',re.I)
workflow=re.compile(r'\b(workflow|savedViews|watchlists|memberships|watchedSystemIds|session|auth|user|localStorage)\b',re.I)
ident=re.compile(r'\b[A-Za-z_$][\w$]*\b')
ignore={'true','false','null','undefined','Math','Date','String','Number','Object','Array','JSON','Intl','React','console','window','document','event','value','index','key','return','const','let','var','if','else','new'}

def definitions(text):
    out={}
    # Single-line and common multiline const/let definitions, bounded conservatively.
    pat=re.compile(r'\b(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*(.*?)(?=\n\s*(?:const|let|return|if|for|while|function|export|}\s*$)|;\s*\n)',re.S|re.M)
    for m in pat.finditer(text):
        expr=m.group(2).strip()
        if len(expr)<=12000:out[m.group(1)]=expr
    # Simple destructuring: const { a, b } = detail
    for m in re.finditer(r'\b(?:const|let)\s*{\s*([^}]+)\s*}\s*=\s*([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)',text):
        base=m.group(2)
        for part in m.group(1).split(','):
            piece=part.strip()
            if not piece:continue
            src=piece.split(':',1)[0].strip()
            dst=piece.split(':',1)[-1].strip()
            if re.fullmatch(r'[A-Za-z_$][\w$]*',dst):out[dst]=base+'.'+src
    return out

def typed_props(text):
    out={}
    # Function/component destructured props with nearby type annotation.
    for m in re.finditer(r'(?:function\s+\w+\s*\(|\()\s*{\s*([^}]+)\s*}\s*:\s*{\s*([^}]+)\s*}',text,re.S):
        names=m.group(1); types=m.group(2)
        type_map={}
        for tm in re.finditer(r'([A-Za-z_$][\w$]*)\??\s*:\s*([^;\n,}]+)',types):
            type_map[tm.group(1)]=tm.group(2).strip()
        for piece in names.split(','):
            name=piece.strip().split(':')[-1].strip()
            src=piece.strip().split(':')[0].strip()
            if re.fullmatch(r'[A-Za-z_$][\w$]*',name):out[name]=type_map.get(src,'PROP')
    return out

cache={}
def resolve(expr,defs,depth=0,seen=None):
    seen=set() if seen is None else set(seen)
    if depth>=6:return expr,[]
    expanded=expr; traces=[]
    for name in dict.fromkeys(ident.findall(expr)):
        if name in ignore or name in seen or name not in defs:continue
        # Ignore property tokens used only after a dot.
        if re.search(r'\.'+re.escape(name)+r'\b',expr) and not re.search(r'(?<!\.)\b'+re.escape(name)+r'\b',expr):continue
        seen.add(name)
        sub,subtr=resolve(defs[name],defs,depth+1,seen)
        traces.append({'identifier':name,'definition':defs[name][:3000],'expanded_definition':sub[:5000]})
        traces.extend(subtr)
        expanded += '\n/* '+name+' := '+sub+' */'
    return expanded,traces

def has_normalized(text):
    return any(re.search(r'(?:\.|\[["\']?)'+re.escape(f)+r'\b',text) for f in normalized)

results=[];counts=Counter()
for r in rows:
    file=r['file']
    if file not in cache:
        text=Path(file).read_text()
        cache[file]=(definitions(text),typed_props(text))
    defs,props=cache[file]
    expanded,traces=resolve(str(r.get('expression') or ''),defs)
    ids=set(ident.findall(str(r.get('expression') or '')))
    prop_hits=[{'name':x,'type':props[x]} for x in ids if x in props]
    joined=expanded+' '+' '.join(r.get('property_chains') or [])
    if workflow.search(joined):
        cls='RESOLVED_WORKFLOW_OR_USER_STATE';reason='Recursive definition trace reaches workflow/auth/user state'
    elif has_normalized(joined):
        cls='RESOLVED_NORMALIZED_SOURCE_DERIVATION';reason='Recursive trace reaches normalized source-field name'
    elif source_root.search(joined) or any(re.search(r'(System|Detail|Company|Firm|Nys|Water|Source|Procurement|History|Coverage|Enforcement)',x['type'],re.I) for x in prop_hits):
        cls='RESOLVED_SOURCE_PAYLOAD_OR_DERIVED_METRIC';reason='Recursive trace reaches source/artifact payload or typed data prop'
    elif traces:
        cls='RESOLVED_LOCAL_DERIVATION';reason='Expression resolves through local definitions without detected source/workflow root'
    else:
        cls='STILL_UNRESOLVED';reason='No recursive local definition or typed/source root established'
    counts[cls]+=1
    results.append({**r,'stage16_class':cls,'stage16_reason':reason,'typed_props':prop_hits,'resolved_definitions':traces,'resolved_text':expanded[:8000]})

unresolved=[r for r in results if r['stage16_class']=='STILL_UNRESOLVED']
summary={
 'input_records':len(rows),'class_counts':dict(counts),'resolved_count':len(rows)-len(unresolved),'still_unresolved':len(unresolved),
 'top_unresolved_files':Counter(r['file'] for r in unresolved).most_common(30),
 'boundary':'Recursive static local-definition and prop trace. Source-payload resolution does not prove rendered correctness or source completeness; STILL_UNRESOLVED requires deeper static trace or hosted state exercise.'
}
(OUT/'application-backtrace-results.json').write_text(json.dumps(results,indent=2))
(OUT/'application-backtrace-unresolved.json').write_text(json.dumps(unresolved,indent=2))
(OUT/'application-backtrace-summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
