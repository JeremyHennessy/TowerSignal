from __future__ import annotations
import json,re
from collections import Counter
from pathlib import Path

BASE=Path('docs/audits/2026-09-23')
OUT=Path('.audit-stage17');OUT.mkdir(exist_ok=True)
rows=json.loads((BASE/'stage16-application-backtrace/application-backtrace-unresolved.json').read_text())

sourceish=re.compile(r'\b(detail|context|payload|nysPayload|systems?|sourceHealth|sources?|signals?|oath|acris|pluto|hpd|dob|water|tower|company|firm|procurement|inspection|violation|permit|jobs?|samples?|benchmark|contacts?|alerts?)\b',re.I)
workflow=re.compile(r'\b(workflow|savedViews|watchlists|memberships|watchedSystemIds|user|auth|session)\b',re.I)
ident=re.compile(r'\b[A-Za-z_$][\w$]*\b')

cache={}
def callbacks(file):
    text=Path(file).read_text()
    lines=text.splitlines()
    out=[]
    # Common direct and parenthesized collection expressions.
    patterns=[
      re.compile(r'(?P<collection>[A-Za-z_$][\w$]*(?:\??\.[A-Za-z_$][\w$]*|\[[^\]]+\])*)\.(?:map|filter|find|some|every)\(\s*\(?\s*(?P<param>[A-Za-z_$][\w$]*)'),
      re.compile(r'\((?P<collection>[^()\n]{1,240})\)\.(?:map|filter|find|some|every)\(\s*\(?\s*(?P<param>[A-Za-z_$][\w$]*)'),
    ]
    for lineno,line in enumerate(lines,1):
        for pat in patterns:
            for m in pat.finditer(line):
                out.append({'line':lineno,'param':m.group('param'),'collection':m.group('collection').strip(),'text':line.strip()[:700]})
    return out

def root_identifier(expr):
    m=re.match(r'\s*([A-Za-z_$][\w$]*)\b',expr or '')
    return m.group(1) if m else None

results=[];counts=Counter()
for r in rows:
    file=r['file']; line=int(r.get('line') or 0)
    if file not in cache:cache[file]=callbacks(file)
    root=root_identifier(str(r.get('expression') or ''))
    candidates=[c for c in cache[file] if c['param']==root and c['line']<=line and line-c['line']<=120]
    if not candidates:
        # Some JSX child records are on the same long line but root appears nested later; consider nearest +/- 3 lines.
        candidates=[c for c in cache[file] if c['param']==root and abs(line-c['line'])<=3]
    candidates=sorted(candidates,key=lambda c:(abs(line-c['line']),-c['line']))
    cb=candidates[0] if candidates else None
    if cb:
        col=cb['collection']
        if workflow.search(col):
            cls='CALLBACK_FROM_WORKFLOW_STATE'
        elif sourceish.search(col):
            cls='CALLBACK_FROM_SOURCE_OR_ARTIFACT_COLLECTION'
        else:
            cls='CALLBACK_FROM_LOCAL_COLLECTION_NEEDS_TRACE'
        reason=f"Callback parameter {root} iterates over {col}"
    else:
        cls='STILL_UNRESOLVED'
        reason='No nearby callback collection established'
    counts[cls]+=1
    results.append({**r,'stage17_class':cls,'stage17_reason':reason,'callback_trace':cb})

unresolved=[r for r in results if r['stage17_class'] in {'STILL_UNRESOLVED','CALLBACK_FROM_LOCAL_COLLECTION_NEEDS_TRACE'}]
summary={
 'input_records':len(rows),'class_counts':dict(counts),
 'resolved_source_or_workflow_callbacks':sum(1 for r in results if r['stage17_class'] in {'CALLBACK_FROM_SOURCE_OR_ARTIFACT_COLLECTION','CALLBACK_FROM_WORKFLOW_STATE'}),
 'still_needing_trace':len(unresolved),
 'top_remaining_files':Counter(r['file'] for r in unresolved).most_common(30),
 'boundary':'Callback-parameter to iterated-collection static trace. Source/artifact collection classification establishes data lineage class, not source correctness or hosted rendering.'
}
(OUT/'callback-lineage-results.json').write_text(json.dumps(results,indent=2))
(OUT/'callback-lineage-unresolved.json').write_text(json.dumps(unresolved,indent=2))
(OUT/'callback-lineage-summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
