from __future__ import annotations
import json
from collections import Counter
from pathlib import Path

BASE=Path('docs/audits/2026-09-23')
DELTA=BASE/'current-main-manual-delta'
OUT=Path('.audit-current-manual-final');OUT.mkdir(exist_ok=True)

reused=json.loads((DELTA/'manual-reused-records.json').read_text())
unmatched=json.loads((DELTA/'manual-unmatched-current.json').read_text())
ambiguous=json.loads((DELTA/'manual-ambiguous-current.json').read_text())

manual_new={
 'dd5eaf2ad4137bb5a60c':('AUTH_FORM_STATE','Local sign-in form validation state; not a public-source or database evidence field.','AUTH'),
 '124b8ad26eeff79a02bf':('DIRECT_OATH_CASE_FIELD','OATH hearing-result field rendered through the account client report/PDF case model.','OATH'),
 'f0877ba39eb2a3172aed':('DIRECT_OATH_CASE_FIELD','OATH balance-due field rendered through the account client report/PDF case model.','OATH'),
 '0331378b3243bc0d6b56':('DIRECT_OATH_CASE_FIELD','OATH decision-date field rendered through the account client report/PDF case model.','OATH'),
 'ff44e2ea7a7395b1f055':('PRIVATE_ADMIN_SAVE_STATE','Private Company Admin local save timestamp/presentation state; not public-source evidence.','PRIVATE_COMPANY_ADMIN'),
 'fc5eada1188952f36386':('PRIVATE_ADMIN_SAVE_STATE','Private Company Admin local save timestamp formatting; not public-source evidence.','PRIVATE_COMPANY_ADMIN'),
 'b3e2802c62645d497a6f':('PRIVATE_ADMIN_ENUM_PRESENTATION','Private Company Admin relationship-status option list defined by the admin client model.','PRIVATE_COMPANY_ADMIN'),
 '3c781162e9813a90c7e1':('PRIVATE_ADMIN_FORM_STATE','Private Company Admin contact-form validation state.','PRIVATE_COMPANY_ADMIN'),
 'b4e06b6695e353e51897':('PRIVATE_ADMIN_DATABASE_AGGREGATE','Count of private Company Admin activity records returned by the admin-only persistence layer.','PRIVATE_COMPANY_ADMIN'),
 '500a1496f1bc2bddcba1':('PRIVATE_ADMIN_DATABASE_AGGREGATE','Count of private Company Admin notes returned by the admin-only persistence layer.','PRIVATE_COMPANY_ADMIN'),
 '2513b352f9ed44626cd5':('PRIVATE_ADMIN_FORM_STATE','Private Company Admin note-form validation state.','PRIVATE_COMPANY_ADMIN'),
 'd70f43e4111c4845eaa7':('SOURCE_METHODOLOGY_CONTRACT','Static Source Health production-refresh contract note defined in SourceHealthExpansion, not a publisher field.','SOURCE_HEALTH'),
}

records=list(reused)
new_resolved=[]
missing=[]
for r in unmatched:
    spec=manual_new.get(r['application_field_id'])
    if not spec:
        missing.append(r['application_field_id']);continue
    cls,reason,domain=spec
    row={**r,'manual_lineage_class':cls,'manual_lineage_reason':reason,'manual_domain':domain,
         'manual_review_status':'RESOLVED','manual_reuse_basis':'CURRENT_MAIN_FRESH_MANUAL_REVIEW'}
    records.append(row);new_resolved.append(row)

amb_resolved=[];amb_fail=[]
for item in ambiguous:
    current=item['current']; priors=item['prior_matches']
    triples={(p.get('manual_lineage_class'),p.get('manual_lineage_reason'),p.get('manual_domain')) for p in priors}
    if len(triples)!=1:
        amb_fail.append({'application_field_id':current['application_field_id'],'prior_options':sorted(map(str,triples))})
        continue
    cls,reason,domain=next(iter(triples))
    row={**current,'manual_lineage_class':cls,'manual_lineage_reason':reason,'manual_domain':domain,
         'manual_review_status':'RESOLVED','manual_reuse_basis':'AMBIGUOUS_SIGNATURE_ALL_PRIOR_DECISIONS_IDENTICAL',
         'prior_application_field_ids':[p.get('application_field_id') for p in priors]}
    records.append(row);amb_resolved.append(row)

if missing or amb_fail:
    raise RuntimeError(f'Current manual review incomplete missing={missing} ambiguous={amb_fail}')

# Must exactly cover every current stage19 remaining ID.
current_remaining=json.loads((BASE/'stage19-typed-application-lineage/typed-application-lineage-remaining.json').read_text())
expected={r['application_field_id'] for r in current_remaining}
actual={r['application_field_id'] for r in records}
if expected!=actual:
    raise RuntimeError(f'Manual ID coverage mismatch missing={sorted(expected-actual)[:20]} extra={sorted(actual-expected)[:20]}')

records=sorted(records,key=lambda r:(r['file'],r['line'],r['application_field_id']))
summary={
 'reviewed_records':len(records),'unresolved_records':0,
 'reused_exact_signature':sum(r.get('manual_reuse_basis')=='EXACT_FILE_KIND_ATTRIBUTE_EXPRESSION_PROPERTY_CHAINS' for r in records),
 'reused_ambiguous_but_identical_prior_decision':len(amb_resolved),
 'fresh_current_main_manual_reviews':len(new_resolved),
 'class_counts':dict(Counter(r['manual_lineage_class'] for r in records)),
 'domain_counts':dict(Counter(r.get('manual_domain') for r in records if r.get('manual_domain'))),
 'current_main_new_domains':dict(Counter(r.get('manual_domain') for r in new_resolved)),
 'boundary':'Current-main manual application-lineage closure. Prior decisions are reused only by exact signature or unanimous prior classification; new Company Admin/auth/OATH/Source Health records are freshly classified. This is provenance classification, not live rendering or database-policy proof.'
}
payload={'summary':summary,'records':records}
(OUT/'manual-remaining-review.json').write_text(json.dumps(payload,indent=2))
(OUT/'current-main-manual-review-summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
