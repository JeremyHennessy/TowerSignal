from __future__ import annotations
import json
from collections import Counter
from pathlib import Path

B=Path('docs/audits/2026-09-23')
OUT=Path('.audit-stage20');OUT.mkdir(exist_ok=True)

stage14=json.loads((B/'stage14-application-lineage/application-lineage-classified.json').read_text())
stage16={r['application_field_id']:r for r in json.loads((B/'stage16-application-backtrace/application-backtrace-results.json').read_text())}
stage17={r['application_field_id']:r for r in json.loads((B/'stage17-callback-lineage/callback-lineage-results.json').read_text())}
stage18={r['application_field_id']:r for r in json.loads((B/'stage18-expanded-application-lineage/expanded-application-lineage.json').read_text())}
stage19={r['application_field_id']:r for r in json.loads((B/'stage19-typed-application-lineage/typed-application-lineage.json').read_text())}
manual=json.loads((B/'stage19-typed-application-lineage/manual-remaining-review.json').read_text())
manual_by={r['application_field_id']:r for r in manual['records']}

needs14={'DATA_PAYLOAD_FIELD_NEEDS_BACKTRACE','DERIVED_DATA_METRIC_NEEDS_BACKTRACE','UNRESOLVED_APPLICATION_EXPRESSION'}
final=[]
unresolved=[]

for base in stage14:
    fid=base['application_field_id']
    cls=base['application_lineage_class']
    source_stage='stage14'
    reason='Stage14 direct/static classification'
    domain=None

    if cls in needs14:
        s16=stage16.get(fid)
        if not s16:
            unresolved.append((fid,'missing_stage16'));continue
        c16=s16['stage16_class']
        if c16!='STILL_UNRESOLVED':
            cls=c16;source_stage='stage16';reason=s16['stage16_reason']
        else:
            s17=stage17.get(fid)
            if not s17:
                unresolved.append((fid,'missing_stage17'));continue
            c17=s17['stage17_class']
            if c17 in {'CALLBACK_FROM_SOURCE_OR_ARTIFACT_COLLECTION','CALLBACK_FROM_WORKFLOW_STATE'}:
                cls=c17;source_stage='stage17';reason=s17['stage17_reason']
            else:
                s18=stage18.get(fid)
                if not s18:
                    unresolved.append((fid,'missing_stage18'));continue
                c18=s18['stage18_class']
                if c18 not in {'STILL_UNRESOLVED','COMPONENT_SCOPED_DATA_DERIVATION'}:
                    cls=c18;source_stage='stage18';reason=s18['stage18_reason']
                else:
                    s19=stage19.get(fid)
                    if not s19:
                        unresolved.append((fid,'missing_stage19'));continue
                    if s19['stage19_class']=='TYPE_BACKTRACED_DATA_FIELD':
                        cls='TYPE_BACKTRACED_DATA_FIELD'
                        source_stage='stage19'
                        reason=s19['stage19_reason']
                        domain=s19.get('chosen_domain')
                    else:
                        m=manual_by.get(fid)
                        if not m:
                            unresolved.append((fid,'missing_manual'));continue
                        cls=m['manual_lineage_class']
                        source_stage='manual_stage20'
                        reason=m['manual_lineage_reason']
                        domain=m.get('manual_domain')

    final.append({
      **base,
      'final_lineage_class':cls,
      'final_lineage_stage':source_stage,
      'final_lineage_reason':reason,
      'final_domain':domain,
      'final_status':'RESOLVED'
    })

if unresolved:
    raise RuntimeError(f'Application reconciliation unresolved: {unresolved[:20]} total={len(unresolved)}')

classes=Counter(r['final_lineage_class'] for r in final)
stages=Counter(r['final_lineage_stage'] for r in final)
domains=Counter(r['final_domain'] for r in final if r.get('final_domain'))
summary={
 'application_expression_records':len(final),
 'resolved_records':len(final),
 'unresolved_records':0,
 'final_class_counts':dict(classes),
 'resolution_stage_counts':dict(stages),
 'manual_domain_counts':dict(domains),
 'route_literals':json.loads((B/'stage13-application-register/application-field-summary.json').read_text()).get('route_literals',[]),
 'denominator_definition':'The same 3,021 deduplicated runtime JSX/report-export expression records established in stage13.',
 'acceptance_boundary':'Application expression lineage is classified for every denominator record. This does not mean every visible state was exercised in a browser, nor that every source-derived value is correct; source-field correctness, relationship joins, hosted state coverage and PDF/visual acceptance remain separate gates.'
}
(OUT/'final-application-lineage-register.json').write_text(json.dumps(final,indent=2))
(OUT/'final-application-lineage-summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
