# TowerSignal Build 016 — Procurement / Company Intelligence Architecture

Date: 2026-08-26

## Confirmed starting baseline

Build 016A was branched from exact `main@228756d9a9c6fac57638c0029bae2eecd1a87502` after confirming:

- recent Build 015 redesign PR #77 and hosted-verification corrections #78–#80 were merged;
- Pages run #49 / `33013787163` completed successfully on the exact starting SHA;
- build, deployment, desktop Chromium, iPhone/WebKit and durable-history persistence all passed;
- no newer `main` commit existed when Build 016A started;
- the existing `docs/project-state.md` still described the older Build 013 production baseline and therefore is historical/stale with respect to the actual Build 015 technical deployment;
- Build 015 public share routes and user-private Neon workflow/RLS remain the current application boundary.

This is an engineering baseline, not a claim of user visual approval for Build 015.

## Build 016A scope

Build 016A introduces the shared procurement/company domain contract only. It intentionally does **not** change UI, production source retrieval, Priority Score 1.0, RLS, current account linkage, or durable NYC/NYS history.

The new Python module `scripts/towersignal/procurement.py` defines:

- versioned procurement/company schema constants;
- the required service taxonomy;
- conservative procurement-description classification with source text, matching terms, reason and confidence;
- normalized company names and explicit alias records;
- company resolution precedence (`CONFIRMED`, `STRONG`, `VERIFY`, `UNRESOLVED`);
- normalized procurement contract and notice records;
- explicit facility/tower linkage confidence classes;
- procurement-specific source-health records;
- observable public-contract company metrics;
- deterministic procurement-history events with a first-baseline no-event guard.

## Evidence rules

### Priority Score 1.0 is unchanged

Procurement, spend, company ownership, M&A context and contract value do not enter Priority Score 1.0.

### Public procurement is not company revenue

The procurement domain uses terms such as:

- observed public contract value;
- observed public-sector customers;
- publicly evidenced contract history;
- observed spending to date.

It does not define those observations as total revenue, total customer count or a complete customer book.

### Company identity remains separate from contracts

A vendor string is not itself a company identity. Resolution precedence is:

1. exact authoritative vendor/legal identifier: `CONFIRMED`;
2. distinctive normalized name plus compatible identity/address evidence: `STRONG`;
3. name-only/acronym/partial evidence: `VERIFY`;
4. no safe match: `UNRESOLVED`.

Uncertain records are never silently merged.

### Facility/tower linkage remains conservative

Procurement records default to `UNLINKED`. Exact or strong facility/tower links must be added by a later linkage stage with explicit confidence; institution-level context must not be represented as property-level fact.

### Classification is evidence-bearing

Each classification retains:

- source text;
- matched terms;
- service category;
- classification reason;
- confidence.

Broad phrases such as `water services` remain `VERIFY`. Common false-positive contexts such as bottled-water delivery, water meters, stormwater and swimming pools are explicitly tested not to become cooling-tower intelligence.

## Initial normalized contract shape

`ProcurementContract` includes:

- stable TowerSignal procurement ID;
- source and source record/contract IDs;
- raw vendor and resolved company ID/confidence/method;
- buyer/agency/department/facility context;
- title/description/service category/confidence/reason;
- original/current amount and spend to date;
- start/end/amended/award/registration dates;
- award method/contract type/status;
- geography;
- facility and tower linkage confidence;
- source URL/retrieval/update metadata;
- preserved source row under `raw` for auditability.

`ProcurementNotice` uses the same evidence principles for solicitations/notices and preserves notice ID, agency, type/category, selection method, PIN, due dates, contact information, service classification and raw source data.

## Source-health contract

Every later procurement adapter must report at least:

- source;
- status;
- last success/attempt;
- record count;
- relevant-record count;
- normalized contract/notice counts;
- resolved/unresolved company counts;
- facility and exact tower link counts;
- pagination completeness;
- schema validity;
- freshness;
- explicit error/status reasons.

Incomplete pagination or invalid schema is `FAILED`, even when some rows were retrieved.

## History contract

The first procurement baseline emits no `*_ADDED` flood. Later deterministic comparisons support:

- `PROCUREMENT_NOTICE_ADDED`;
- `PROCUREMENT_DUE_DATE_CHANGED`;
- `CONTRACT_ADDED`;
- `CONTRACT_VALUE_CHANGED`;
- `CONTRACT_END_DATE_CHANGED`;
- `CONTRACT_SPEND_CHANGED`;
- `VENDOR_CHANGED`.

Additional award/expiry/renewal/corporate-relationship events are added when those normalized fields and sources are production-backed.

## Build 016A acceptance

The increment is accepted only after standard CI passes on the exact branch head and the PR diff remains confined to procurement architecture/tests/docs. No production UI/source behavior is changed in this increment.

Next increment: Build 016B — NYC City Record source adapter, deterministic pagination, service classification, source health, bounded production payload generation and tests.
