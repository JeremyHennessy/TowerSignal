from __future__ import annotations
import json,re
from collections import Counter,defaultdict
from pathlib import Path

BASE=Path('docs/audits/2026-09-23/stage13-application-register')
OUT=Path('.audit-stage14');OUT.mkdir(exist_ok=True)
records=json.loads((BASE/'application-field-register.json').read_text())

workflow_tokens=re.compile(r'\b(workflow|savedViews|watchlists|memberships|watchedSystemIds|session|auth|user|viewName|localStorage)\b',re.I)
routing_tokens=re.compile(r'\b(mode|navigate|route|hash|currentShareUrl|shareUrl|nysMode|location\.hash)\b')
source_health_tokens=re.compile(r'\b(sourceHealth|healthyHealth|metadata|generated_at|retrieved_at|source_updated|acrisMetadata|coverage|verification)\b',re.I)
data_tokens=re.compile(r'\b(detail|system|systems|payload|nysPayload|context|row|record|company|firm|owner|portfolio|procurement|inspection|violation|permit|job|benchmark|sample|contact|acris|oath|pluto|hpd|dob|water|tower)\b',re.I)
aggregate_tokens=re.compile(r'(\.length\b|\.filter\(|\.reduce\(|\.some\(|\.every\(|\.find\(|\.map\(|toLocaleString\(|\b(count|total|ready|followup|recent|score|priority|healthy|registered)\b)',re.I)
interaction_attrs={'onClick','onChange','onSubmit','onBlur','onFocus','onKeyDown','onToggle'}
presentation_attrs={'className','style','role','id','type','placeholder','open','aria-label','aria-selected','aria-current','data-testid'}
routing_attrs={'href','to','url'}
source_field_kinds={'REPORT_EXPORT_FIELD','EXPORT_FIELD','REPORT_FIELD'}

classified=[]
counts=Counter();by_file=defaultdict(Counter);unresolved=[]
for r in records:
    expr=str(r.get('expression') or '')
    chains=' '.join(r.get('property_chains') or [])
    text=' '.join([expr,chains,str(r.get('label') or ''),str(r.get('attribute') or '')])
    attr=str(r.get('attribute') or '')
    direct=bool(r.get('source_lineage_candidates'))
    reasons=[]
    if direct:
        cls='DIRECT_CORE_SOURCE_LINEAGE'
        reasons.append('Stage13 direct normalized-field candidate')
    elif r.get('field_kind') in source_field_kinds or 'report/export' in str(r.get('field_kind','')).lower():
        cls='REPORT_OR_EXPORT_MAPPING'
        reasons.append('Explicit report/export mapping record')
    elif attr in interaction_attrs or re.match(r'^on[A-Z]',attr):
        cls='INTERACTION_HANDLER'
        reasons.append('Event/callback expression rather than displayed business field')
    elif workflow_tokens.search(text):
        cls='WORKFLOW_OR_USER_STATE'
        reasons.append('Expression depends on private workflow/auth/user state')
    elif source_health_tokens.search(text):
        cls='SOURCE_HEALTH_OR_PROVENANCE'
        reasons.append('Expression reports source/build/retrieval/coverage provenance')
    elif routing_tokens.search(text) and not data_tokens.search(text):
        cls='ROUTING_OR_PRESENTATION_STATE'
        reasons.append('Route/mode/navigation state without direct source payload')
    elif attr in presentation_attrs and not data_tokens.search(text):
        cls='PRESENTATION_OR_CONTROL'
        reasons.append('Presentation/control attribute with no source-like data reference')
    elif aggregate_tokens.search(text) and (data_tokens.search(text) or re.search(r'\b(outreachReady|samplingFollowUp|contactReady|recentDob|registered|filtered|counts?|summary|metrics?)\b',text,re.I)):
        cls='DERIVED_DATA_METRIC_NEEDS_BACKTRACE'
        reasons.append('Derived count/aggregate/formatting expression over runtime data')
    elif data_tokens.search(text):
        cls='DATA_PAYLOAD_FIELD_NEEDS_BACKTRACE'
        reasons.append('Runtime data-bearing expression without a direct core normalized-field candidate')
    elif attr in routing_attrs:
        cls='ROUTING_OR_LINK_TARGET'
        reasons.append('Navigation/link target')
    elif not r.get('property_chains') and len(expr)<120:
        cls='LOCAL_DERIVED_OR_PRESENTATION'
        reasons.append('Local expression with no detected runtime data/property chain')
    else:
        cls='UNRESOLVED_APPLICATION_EXPRESSION'
        reasons.append('No reliable static category assigned')
    row={**r,'application_lineage_class':cls,'classification_reasons':reasons}
    classified.append(row)
    counts[cls]+=1;by_file[r['file']][cls]+=1
    if cls in {'DATA_PAYLOAD_FIELD_NEEDS_BACKTRACE','DERIVED_DATA_METRIC_NEEDS_BACKTRACE','UNRESOLVED_APPLICATION_EXPRESSION'}:
        unresolved.append(row)

summary={
 'records':len(classified),
 'class_counts':dict(counts),
 'needs_backtrace_count':len(unresolved),
 'files':len(by_file),
 'files_with_needs_backtrace':sum(any(k in {'DATA_PAYLOAD_FIELD_NEEDS_BACKTRACE','DERIVED_DATA_METRIC_NEEDS_BACKTRACE','UNRESOLVED_APPLICATION_EXPRESSION'} for k in c) for c in by_file.values()),
 'top_needs_backtrace_files':Counter(r['file'] for r in unresolved).most_common(30),
 'boundary':'Static application-expression classification. DIRECT_CORE_SOURCE_LINEAGE means at least one direct candidate exists, not that the visible value is fully source-verified. NEEDS_BACKTRACE expressions require explicit derivation tracing or browser/state verification.'
}
(OUT/'application-lineage-classified.json').write_text(json.dumps(classified,indent=2))
(OUT/'application-lineage-needs-backtrace.json').write_text(json.dumps(unresolved,indent=2))
(OUT/'application-lineage-summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
