from __future__ import annotations
import json
from collections import Counter,defaultdict
from pathlib import Path

BASE=Path('docs/audits/2026-09-23/stage29-relationship-resolution')
OUT=Path('.audit-stage31');OUT.mkdir(exist_ok=True)
rows=json.loads((BASE/'relationship-contract-resolved-occurrences.json').read_text())

def classify(r):
    f=r['file']
    # Non-relationship-creating surfaces.
    if f.startswith('src/types/'):
        return 'TYPE_DECLARATION_ONLY','NOT_A_RUNTIME_RELATIONSHIP_CREATOR'
    if f.startswith('src/components/'):
        return 'UI_PROPAGATION_OR_PRESENTATION','UPSTREAM_RELATIONSHIP_REQUIRED'
    if f.startswith('src/domain/'):
        if f.endswith('procurementFirmRoles.ts'):
            return 'CLIENT_DERIVED_RELATIONSHIP','NEEDS_UPSTREAM_PROCUREMENT_LINK_PROOF'
        if f.endswith('accountEvidence.ts'):
            return 'CLIENT_DERIVED_RELATIONSHIP','KNOWN_DOB_PROVENANCE_DEFECT_ON_CURRENT_MAIN'
        return 'CLIENT_DERIVED_RELATIONSHIP','UPSTREAM_RELATIONSHIP_REQUIRED'
    if f.startswith('scripts/verify_'):
        return 'VERIFIER_ONLY','NOT_A_PRODUCTION_RELATIONSHIP_CREATOR'

    # Runtime creators with evidence from completed audit stages.
    if f.endswith('hpd_identity.py'):
        return 'PRODUCTION_RELATIONSHIP_CREATOR','FULL_TARGET_POPULATION_AND_IDENTITY_RULE_VALIDATED'
    if f.endswith('historical_311_context.py'):
        return 'PRODUCTION_RELATIONSHIP_CREATOR','TARGET_POPULATION_EXACT_BBL_PROFILE_REPLAY_MATCH'
    if f.endswith('planimetrics.py') or f.endswith('building_footprints.py') or f.endswith('domestic_water.py'):
        return 'PRODUCTION_RELATIONSHIP_CREATOR','TARGET_BIN_POPULATION_REPLAY_OR_IDENTITY_CENSUS_VALIDATED'
    if f.endswith('nyc_water_signals.py'):
        return 'PRODUCTION_RELATIONSHIP_CREATOR','SOURCE_POPULATION_AND_TRANSFORM_EVIDENCE_AVAILABLE_WITH_PRESENTATION_DEFECT_SEPARATE'
    if f.endswith('known_firms.py'):
        return 'PRODUCTION_RELATIONSHIP_CREATOR','KNOWN_PLACEHOLDER_BIN_SITE_COLLAPSE_DEFECT_ON_CURRENT_MAIN'
    if f.endswith('nys_authority_procurement.py'):
        return 'PRODUCTION_RELATIONSHIP_CREATOR','PROCUREMENT_CANDIDATE_POPULATION_REPLAYED_BUT_TOWER_LINK_INTENTIONALLY_UNLINKED'
    if f.endswith('procurement.py'):
        return 'PRODUCTION_RELATIONSHIP_CREATOR','DYNAMIC_COMPANY_FACILITY_TOWER_LINKS_REQUIRE_RELATIONSHIP_LEVEL_REPLAY'
    if f.endswith('openbook_water.py') or f.endswith('checkbook_nycha.py'):
        return 'PRODUCTION_RELATIONSHIP_CREATOR','PROCUREMENT_LINK_CONFIDENCE_RULES_REQUIRE_RELATIONSHIP_LEVEL_REPLAY'
    if f.endswith('company_intelligence.py'):
        return 'PRODUCTION_RELATIONSHIP_CREATOR','COMPANY_IDENTITY_RESOLUTION_REQUIRES_RELATIONSHIP_LEVEL_REPLAY'
    if f.endswith('provider_resolution.py'):
        return 'PRODUCTION_RELATIONSHIP_CREATOR','NAME_MATCH_IS_EXPLICITLY_VERIFY_ONLY'
    if f.endswith('acris.py'):
        return 'PRODUCTION_RELATIONSHIP_CREATOR','SCHEMA_AND_JOIN_REVIEWED_CURRENT_TARGET_POPULATION_REPLAY_STILL_OPEN'
    if f.endswith('labor_law.py'):
        return 'PRODUCTION_RELATIONSHIP_CREATOR','PUBLISHED_ADDRESS_MATCH_PARTIAL_COVERAGE_REQUIRES_TARGET_REPLAY'
    if f.endswith('cms_institutional.py'):
        return 'PRODUCTION_RELATIONSHIP_CREATOR','PAD_EXACT_ADDRESS_BBL_RULE_REVIEWED_TARGET_POPULATION_REPLAY_OPEN'
    if f.endswith('legionella_matching.py'):
        return 'PRODUCTION_RELATIONSHIP_CREATOR','NORMALIZED_ADDRESS_SINGLE_BIN_RULE_REQUIRES_RELATIONSHIP_REPLAY'
    if f.endswith('nys_public_water.py') or f.endswith('nys_lsli_detail.py'):
        return 'PRODUCTION_RELATIONSHIP_CREATOR','NYS_RELATIONSHIP_SCOPE_REQUIRES_SEPARATE_REPLAY'
    if f.endswith('dob_activity.py') or f.endswith('property_enforcement.py'):
        return 'PRODUCTION_RELATIONSHIP_CREATOR','EXACT_BBL_BIN_SOURCE_CONTRACT_REVIEWED_AND_REPLAY_EVIDENCE_PARTIAL'
    if f.endswith('nyc_distribution_water.py'):
        return 'PRODUCTION_RELATIONSHIP_CREATOR','EXPLICITLY_UNLINKED_SAMPLE_SITE'
    return 'OTHER_RUNTIME_CONTRACT','REQUIRES_MANUAL_DOMAIN_REVIEW'

out=[]
for r in rows:
    role,evidence=classify(r)
    out.append({**r,'relationship_runtime_role':role,'audit_evidence_status':evidence})

summary={
 'occurrences':len(out),
 'runtime_role_counts':dict(Counter(r['relationship_runtime_role'] for r in out)),
 'evidence_status_counts':dict(Counter(r['audit_evidence_status'] for r in out)),
 'production_relationship_creator_occurrences':sum(r['relationship_runtime_role']=='PRODUCTION_RELATIONSHIP_CREATOR' for r in out),
 'production_creator_files':sorted({r['file'] for r in out if r['relationship_runtime_role']=='PRODUCTION_RELATIONSHIP_CREATOR'}),
 'open_relationship_replay_files':sorted({r['file'] for r in out if 'REPLAY' in r['audit_evidence_status'] and not any(x in r['audit_evidence_status'] for x in ['VALIDATED','MATCH','REPLAYED_BUT'])}),
 'known_defect_creator_files':sorted({r['file'] for r in out if 'KNOWN_' in r['audit_evidence_status']}),
 'boundary':'Evidence status is attached to the relationship creator, not merely the display label. Population replay can validate source coverage without proving a company/facility/tower relationship unless the relationship keys themselves were replayed.'
}
(OUT/'relationship-evidence-matrix.json').write_text(json.dumps(out,indent=2))
(OUT/'relationship-evidence-summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
