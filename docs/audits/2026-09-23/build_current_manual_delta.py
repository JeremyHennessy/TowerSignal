from __future__ import annotations
import json
from collections import Counter,defaultdict
from pathlib import Path

BASE=Path('docs/audits/2026-09-23')
CURRENT=BASE/'stage19-typed-application-lineage/typed-application-lineage-remaining.json'
PRIOR=BASE/'manual-review-baselines/pre-company-admin-manual-review.json'
OUT=Path('.audit-current-manual');OUT.mkdir(exist_ok=True)

current=json.loads(CURRENT.read_text())
prior=json.loads(PRIOR.read_text())['records']

def sig(r):
    return (
        r.get('file'), r.get('field_kind'), r.get('attribute'),
        r.get('expression'), tuple(r.get('property_chains') or [])
    )

prior_by=defaultdict(list)
for r in prior:
    prior_by[sig(r)].append(r)

records=[];unmatched=[];ambiguous=[]
for r in current:
    candidates=prior_by.get(sig(r),[])
    if len(candidates)==1:
        p=candidates[0]
        records.append({
            **r,
            'manual_lineage_class':p['manual_lineage_class'],
            'manual_lineage_reason':p['manual_lineage_reason'],
            'manual_domain':p.get('manual_domain'),
            'manual_review_status':'RESOLVED',
            'manual_reuse_basis':'EXACT_FILE_KIND_ATTRIBUTE_EXPRESSION_PROPERTY_CHAINS',
            'prior_application_field_id':p.get('application_field_id'),
        })
    elif len(candidates)>1:
        ambiguous.append({'current':r,'prior_matches':candidates})
    else:
        unmatched.append(r)

summary={
  'current_manual_records':len(current),
  'prior_manual_records':len(prior),
  'reused_exact_signature':len(records),
  'unmatched_current_records':len(unmatched),
  'ambiguous_signature_records':len(ambiguous),
  'unmatched_by_file':Counter(r['file'] for r in unmatched).most_common(),
  'ambiguous_by_file':Counter(x['current']['file'] for x in ambiguous).most_common(),
  'boundary':'Prior manual classifications are reused only for exact file/kind/attribute/expression/property-chain signatures. New or ambiguous current-main expressions remain explicitly unclassified for fresh review.'
}
(OUT/'manual-reuse-summary.json').write_text(json.dumps(summary,indent=2))
(OUT/'manual-reused-records.json').write_text(json.dumps(records,indent=2))
(OUT/'manual-unmatched-current.json').write_text(json.dumps(unmatched,indent=2))
(OUT/'manual-ambiguous-current.json').write_text(json.dumps(ambiguous,indent=2))
print(json.dumps(summary,indent=2))
