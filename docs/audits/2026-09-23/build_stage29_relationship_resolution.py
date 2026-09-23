from __future__ import annotations
import ast,json,re
from collections import Counter,defaultdict
from pathlib import Path

BASE=Path('docs/audits/2026-09-23/stage15-relationship-register')
OUT=Path('.audit-stage29');OUT.mkdir(exist_ok=True)
occ=json.loads((BASE/'relationship-contract-occurrences.json').read_text())

REL_KEYS={
 'match_basis','matchBasis','property_link_confidence','tower_link_confidence','facility_match_confidence',
 'company_match_confidence','identity_confidence','relationship','relationship_evidence','service_assignment_confidence',
 'resolution_method','cross_source_resolution_method','relationship_class','evidence_class','factClass','confidence'
}

def module_constants(tree):
    out={}
    for n in tree.body:
        if isinstance(n,(ast.Assign,ast.AnnAssign)):
            targets=n.targets if isinstance(n,ast.Assign) else [n.target]
            v=n.value
            for t in targets:
                if isinstance(t,ast.Name):
                    try:out[t.id]=ast.literal_eval(v)
                    except Exception:pass
    return out

def literal_strings(node):
    return sorted({x.value for x in ast.walk(node) if isinstance(x,ast.Constant) and isinstance(x.value,str)})

def enclosing_functions(tree,line):
    hits=[]
    for n in ast.walk(tree):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
            end=getattr(n,'end_lineno',n.lineno)
            if n.lineno<=line<=end:hits.append(n)
    return sorted(hits,key=lambda n:(getattr(n,'end_lineno',n.lineno)-n.lineno))

def local_assignments(fn,line):
    result={}
    if not fn:return result
    for n in ast.walk(fn):
        if getattr(n,'lineno',10**9)>=line:continue
        if isinstance(n,ast.Assign):
            for t in n.targets:
                if isinstance(t,ast.Name):result[t.id]=ast.unparse(n.value)
        elif isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name) and n.value:
            result[n.target.id]=ast.unparse(n.value)
    return result

py_cache={}
def resolve_python(rec):
    path=rec['file'];line=int(rec['line']);key=rec['key']
    if path not in py_cache:
        text=Path(path).read_text();tree=ast.parse(text)
        py_cache[path]=(text,tree,module_constants(tree))
    text,tree,consts=py_cache[path]
    candidates=[]
    for n in ast.walk(tree):
        if not isinstance(n,ast.Dict):continue
        start=getattr(n,'lineno',0);end=getattr(n,'end_lineno',start)
        if not (start<=line<=end):continue
        for k,v in zip(n.keys,n.values):
            if isinstance(k,ast.Constant) and k.value==key:
                candidates.append((n,v))
    if not candidates:
        return {'expression':None,'literal_options':[],'resolved_module_constant':None,'local_trace':None,'resolution_status':'AST_ENTRY_NOT_FOUND'}
    # Prefer the narrowest dict span.
    n,v=min(candidates,key=lambda x:getattr(x[0],'end_lineno',x[0].lineno)-x[0].lineno)
    expr=ast.unparse(v)
    lits=literal_strings(v)
    resolved=None;local_trace=None
    if isinstance(v,ast.Name):
        if v.id in consts:
            resolved=consts[v.id]
        else:
            fns=enclosing_functions(tree,line)
            assigns=local_assignments(fns[0] if fns else None,line)
            local_trace=assigns.get(v.id)
            if local_trace:
                try:
                    ex=ast.parse(local_trace,mode='eval').body
                    lits=sorted(set(lits)|set(literal_strings(ex)))
                except Exception:pass
    status='STATIC_LITERAL' if isinstance(v,ast.Constant) else (
        'MODULE_CONSTANT_RESOLVED' if resolved is not None else
        'LOCAL_ASSIGNMENT_TRACED' if local_trace else
        'STATIC_BRANCH_OPTIONS' if lits else
        'DYNAMIC_EXPRESSION_TRACED'
    )
    return {'expression':expr,'literal_options':lits,'resolved_module_constant':resolved,'local_trace':local_trace,'resolution_status':status}

def resolve_ts(rec):
    raw=str(rec.get('value') or '')
    if raw.startswith('DYNAMIC_EXPRESSION:'):expr=raw.split(':',1)[1]
    else:expr=raw
    lits=sorted(set(re.findall(r"['\"]([A-Z][A-Z0-9_ -]{2,})['\"]",expr)))
    status='STATIC_BRANCH_OPTIONS' if lits else ('PROPAGATED_RUNTIME_VALUE' if '.' in expr else 'DYNAMIC_EXPRESSION_TRACED')
    return {'expression':expr,'literal_options':lits,'resolved_module_constant':None,'local_trace':None,'resolution_status':status}

resolved=[]
for rec in occ:
    detail=resolve_python(rec) if rec['language']=='python' else resolve_ts(rec)
    value=detail.get('resolved_module_constant')
    if value is None and len(detail.get('literal_options') or [])==1 and detail['resolution_status'] in {'STATIC_BRANCH_OPTIONS','STATIC_LITERAL'}:
        value=detail['literal_options'][0]
    resolved.append({**rec,**detail,'resolved_value_if_single':value})

# Evidence classes based on exact semantics, not whether code uses positive-sounding words.
for r in resolved:
    opts=set(str(x) for x in (r.get('literal_options') or []))
    if r.get('resolved_module_constant') is not None:opts.add(str(r['resolved_module_constant']))
    s=' '.join(opts|{str(r.get('value') or ''),str(r.get('expression') or '')}).upper()
    if any(x in s for x in ['UNLINKED','UNRESOLVED','VERIFY','ADDRESS_CONTEXT','CONTEXT_ONLY','NOT_PROOF','NAME_MATCH_ONLY']):
        r['resolved_semantic']='BOUNDARY_OR_NONCONFIRMING'
    elif any(x in s for x in ['BBL_EXACT','BIN_EXACT','SUMMONS_NUMBER_EXACT','BBL_ALIAS_EXACT','CONFIRMED_SOURCE','OBSERVED_SERVICE','RECORDED_ROLE','QUALIFIED_PROVIDER','CONFIRMED_FACT']):
        r['resolved_semantic']='CONFIRMING_OR_OBSERVED'
    elif r['resolution_status'] in {'MODULE_CONSTANT_RESOLVED','STATIC_BRANCH_OPTIONS','STATIC_LITERAL'}:
        r['resolved_semantic']='STATIC_OTHER'
    else:
        r['resolved_semantic']='RUNTIME_OR_DERIVED'

summary={
 'occurrences':len(resolved),
 'resolution_status_counts':dict(Counter(r['resolution_status'] for r in resolved)),
 'resolved_semantic_counts':dict(Counter(r['resolved_semantic'] for r in resolved)),
 'formerly_dynamic_occurrences':sum(r.get('semantic_class')=='DYNAMIC_REQUIRES_TRACE' for r in resolved),
 'formerly_dynamic_with_static_resolution':sum(r.get('semantic_class')=='DYNAMIC_REQUIRES_TRACE' and r['resolution_status'] in {'MODULE_CONSTANT_RESOLVED','LOCAL_ASSIGNMENT_TRACED','STATIC_BRANCH_OPTIONS','STATIC_LITERAL'} for r in resolved),
 'still_runtime_or_derived':sum(r['resolved_semantic']=='RUNTIME_OR_DERIVED' for r in resolved),
 'boundary':'This resolves code expressions/constants/options. It does not prove upstream source joins. Confirming labels require separate population/join evidence.'
}
(OUT/'relationship-contract-resolved-occurrences.json').write_text(json.dumps(resolved,indent=2))
(OUT/'relationship-contract-resolution-summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
