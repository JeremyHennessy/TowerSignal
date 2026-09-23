from __future__ import annotations
import json,re
from collections import Counter
from pathlib import Path

BASE=Path('docs/audits/2026-09-23')
OUT=Path('.audit-stage18');OUT.mkdir(exist_ok=True)
rows=json.loads((BASE/'stage17-callback-lineage/callback-lineage-unresolved.json').read_text())

source_re=re.compile(r'\b(detail|context|payload|nysPayload|systems?|sourceHealth|sources?|signals?|oath|acris|pluto|hpd|dob|water|tower|company|firm|procurement|inspection|violation|permit|jobs?|samples?|benchmark|contacts?|alerts?|coverage|history|enforcement)\b',re.I)
workflow_re=re.compile(r'\b(workflow|savedViews|watchlists|memberships|watchedSystemIds|user|auth|session)\b',re.I)
ident_re=re.compile(r'\b[A-Za-z_$][\w$]*\b')
ignore={'true','false','null','undefined','Math','Date','String','Number','Object','Array','JSON','Intl','React','console','window','document','event','index','key'}

DATA_FILES={
 'src/components/SourceHealthExpansion.tsx','src/components/ChangesView.tsx','src/components/LegionellaIntelligencePanel.tsx',
 'src/components/SourceHealthPage.tsx','src/components/AcrisActivitySection.tsx','src/components/PlanimetricTowerSection.tsx',
 'src/components/DetailPanel.tsx','src/components/DomesticWaterSection.tsx','src/components/NysRegistryView.tsx',
 'src/components/AccountDecisionSummary.tsx','src/components/AccountUnifiedTimeline.tsx','src/components/ClientSiteReport.tsx',
 'src/components/NysChangesView.tsx','src/components/PortfoliosPage.tsx','src/components/NysWaterMarketSubViews.tsx',
 'src/components/SalesPreCallPack.tsx','src/components/TechnicianFieldPack.tsx','src/components/WaterQualityPage.tsx',
 'src/components/CompanyProfilePage.tsx','src/components/AccountEvidenceWorkspace.tsx'
}
WORKFLOW_FILES={
 'src/components/WorkflowScaleWorkspace.tsx','src/components/WorkflowQuickEditor.tsx','src/components/WorkflowWorkspacePage.tsx',
 'src/components/WorkflowAccountSection.tsx','src/components/WorkflowPanel.tsx','src/components/WorkflowAuthPanel.tsx'
}
PRESENTATION_FILES={
 'src/components/Filters.tsx','src/components/PortalNavigation.tsx','src/components/TopNavigation.tsx',
 'src/components/AccountModeTabs.tsx','src/components/AccountSectionNavigator.tsx'
}

def defs(text):
    out={}
    # line-oriented definitions, intentionally conservative
    for m in re.finditer(r'\b(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*([^\n;]{1,1200})',text):
        out[m.group(1)]=m.group(2).strip()
    # multiline definition until next declaration/return
    pat=re.compile(r'\b(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*(.*?)(?=\n\s*(?:const|let|return|if|for|function|export)\b)',re.S)
    for m in pat.finditer(text):
        if len(m.group(2))<12000:out.setdefault(m.group(1),m.group(2).strip())
    return out

def expand(expr,d,depth=0,seen=None):
    seen=set() if seen is None else set(seen)
    if depth>=5:return expr,[]
    traces=[]; expanded=expr
    for name in dict.fromkeys(ident_re.findall(expr)):
        if name in ignore or name in seen or name not in d:continue
        if re.search(r'\.'+re.escape(name)+r'\b',expr) and not re.search(r'(?<!\.)\b'+re.escape(name)+r'\b',expr):continue
        seen.add(name)
        sub,subtr=expand(d[name],d,depth+1,seen)
        traces.append({'identifier':name,'definition':d[name][:3000],'expanded_definition':sub[:5000]})
        traces.extend(subtr)
        expanded += '\n/* '+name+' := '+sub+' */'
    return expanded,traces

cache={}
results=[];counts=Counter()
for r in rows:
    file=r['file']
    if file not in cache:
        cache[file]=defs(Path(file).read_text())
    d=cache[file]
    cb=r.get('callback_trace') or {}
    col=str(cb.get('collection') or '')
    col_exp,col_tr=expand(col,d) if col else ('',[])
    expr=str(r.get('expression') or '')
    expr_exp,expr_tr=expand(expr,d)
    combined=' '.join([col_exp,expr_exp,' '.join(r.get('property_chains') or [])])
    if workflow_re.search(combined):
        cls='RESOLVED_WORKFLOW_STATE';reason='Expanded callback/expression reaches workflow state'
    elif source_re.search(combined):
        cls='RESOLVED_SOURCE_OR_ARTIFACT_DERIVATION';reason='Expanded callback/expression reaches source/artifact data'
    elif file in WORKFLOW_FILES:
        cls='COMPONENT_SCOPED_WORKFLOW_STATE';reason='Unresolved expression is confined to a workflow-state component'
    elif file in PRESENTATION_FILES:
        cls='COMPONENT_SCOPED_PRESENTATION_STATE';reason='Unresolved expression is confined to navigation/filter/presentation component'
    elif file in DATA_FILES:
        cls='COMPONENT_SCOPED_DATA_DERIVATION';reason='Unresolved expression is confined to a data-bearing component; exact field derivation still requires local manual trace'
    elif file=='src/components/ScoreExplanation.tsx':
        cls='DERIVED_SCORE_MODEL_PRESENTATION';reason='Expression is confined to deterministic score-explanation component'
    else:
        cls='STILL_UNRESOLVED';reason='Mixed component with no reliable source/workflow/presentation resolution'
    counts[cls]+=1
    results.append({**r,'stage18_class':cls,'stage18_reason':reason,'expanded_collection':col_exp[:8000],'collection_definition_trace':col_tr,'expression_definition_trace':expr_tr})

remaining=[r for r in results if r['stage18_class'] in {'STILL_UNRESOLVED','COMPONENT_SCOPED_DATA_DERIVATION'}]
summary={
 'input_records':len(rows),'class_counts':dict(counts),
 'strictly_unresolved':sum(r['stage18_class']=='STILL_UNRESOLVED' for r in results),
 'component_scoped_data_needing_exact_field_trace':sum(r['stage18_class']=='COMPONENT_SCOPED_DATA_DERIVATION' for r in results),
 'remaining_for_manual_field_trace':len(remaining),
 'top_remaining_files':Counter(r['file'] for r in remaining).most_common(30),
 'boundary':'Expanded local collection definitions plus conservative component-scope classification. COMPONENT_SCOPED_DATA_DERIVATION still requires exact field/collection trace before full application-field acceptance.'
}
(OUT/'expanded-application-lineage.json').write_text(json.dumps(results,indent=2))
(OUT/'expanded-application-lineage-remaining.json').write_text(json.dumps(remaining,indent=2))
(OUT/'expanded-application-lineage-summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
