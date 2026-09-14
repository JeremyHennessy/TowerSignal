# NYC DOHMH Legionnaires outbreak integration

Status: implementation branch only; do not treat as deployed or verified until full acceptance passes.

## Scope

Add NYC Department of Health and Mental Hygiene Legionnaires' disease community-cluster evidence as a separate source regime. Preserve source-native PCR, culture and remediation semantics. Match only where exact existing TowerSignal tower/property identity can be established. Backfill the 2026 Upper East Side investigation from official DOHMH publications and ingest the current South Bronx investigation.

## Hard boundaries

- Do not change Priority Score 1.0.
- Do not infer that a PCR-positive or culture-positive tower caused illness unless DOHMH explicitly establishes that fact.
- Do not infer culture positivity from PCR positivity.
- Do not infer remediation completion unless the source states it.
- Do not use fuzzy address matching merely to increase coverage.
- Preserve current approved layout and unrelated application behavior.
- Source failure must remain visible/unverified rather than becoming a negative/zero signal.

## Initial authoritative sources

- DOHMH Legionnaires' Disease health topic page (current cluster state and aggregate UES status)
- DOHMH South Bronx September 13, 2026 press release (10 PCR-positive cooling-tower addresses, remediation order and 31-day reporting context)
- DOHMH Upper East Side PCR-positive cooling-tower systems PDF
- DOHMH Upper East Side confirmatory culture-results PDF

## Acceptance

1. deterministic parse/normalization tests;
2. exact-match reconciliation report against current NYC cooling-tower registrations;
3. no Priority Score mutation;
4. generated source-health coverage and provenance;
5. focused frontend evidence rendering tests;
6. full Python/frontend/lint/typecheck/build gates;
7. PR from the exact tested head;
8. deployment and hosted verification reported separately after merge.
