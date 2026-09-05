# TowerSignal Build 017G — NYSDOH Lead Service Line Inventory Detail Crawl

Date: 2026-09-04

## Verified parent checkpoint

This increment starts from exact verified statewide PWS branch head `f75589a63db3ba0fb1c1e03007f535e23119516f` (Build 017C). The parent source proof established the current NYSDOH LSLI index at 2,927 unique PWS IDs and passed full source/integration validation.

This is a layered data-source proof. It does not modify production UI, scoring, cooling-tower behavior, procurement, auth/RLS or deployment behavior.

## Source

Every current PWS ID in the authoritative NYSDOH Lead Service Line Inventory index is associated with a deterministic detail URL:

`https://www.health.ny.gov/environmental/water/drinking/service_line/{PWSID}.htm`

The workflow re-fetches the current index, requires unique PWS IDs, then requests every detail URL with a bounded worker pool and paced submission. Parsed pages must contain the same PWS ID as the index and all required inventory/method fields. Output remains sorted by index order, and validation still requires complete current-index coverage.

### Current-index detail 404s

The live source proved that the NYSDOH index can contain a PWS whose indexed deterministic detail URL returns HTTP 404 (first observed example: `NY0117224`). This is a source inconsistency, not evidence that the PWS should disappear.

Build 017G therefore distinguishes **index coverage** from **parsed detail coverage**:

- a normally retrieved detail must still fully parse or the build fails;
- transport errors other than explicit HTTP 404 still fail;
- a current-index PWS whose primary/fallback detail retrieval ends in explicit HTTP 404 is retained as `DETAIL_UNAVAILABLE_404` with PWS/name/county/source URL/error evidence and no inferred inventory values;
- the total of parsed details plus explicit unavailable records must exactly equal the current index count;
- more than 25 explicit current-index 404s fails the production guard rather than normalizing widespread source breakage.

## Captured detail fields

### Section I — system identity
- Water System Name
- PWS ID Number

### Section II — source-labeled form contact
- Contact Name
- Contact Phone Number
- Contact Email Address

NYSDOH labels this section `Contact Information for Owner / Licensed Operator of Record Completing the Form`. TowerSignal preserves that combined role as `OWNER_OR_LICENSED_OPERATOR_OF_RECORD_FORM_CONTACT`; it does not decide whether the named person is the owner versus licensed operator.

### Section III — inventory
- total service lines
- identified service lines
- lead service lines
- GSLRR
- non-LSL
- unknown service lines
- PWS-side/customer-side material matrix
- Historical Records
- Field Inspection
- Customer Identification with Photo or other Verification
- Excavation
- Sequential Sampling
- Statistical Analysis/Predictive Model

The validator independently evaluates:

`identified = lead + GSLRR + non-lead`

and

`total = identified + unknown`.

When a NYSDOH page's own aggregate fields do not reconcile, TowerSignal preserves
the source-reported values, records `inventory_reconciliation` deltas, and marks
the affected aggregate evidence as `SOURCE_REPORTED_RECONCILIATION_MISMATCH`.
Those rows remain parsed source records; no aggregate count is silently replaced
with a computed value.

### Section IV — public availability
Public-access text and external inventory links are retained where source-present.

### Section V — certification
Name/title/date are retained when structurally present in the source form. Blank certification cells remain blank and are not synthesized.

## Evidence and source integrity

Each parsed detail keeps the official detail URL and SHA-256 of the exact HTML used. The source proof requires exact current-index identity coverage across parsed + explicitly unavailable records, no duplicate/mismatched PWS IDs, and every expected identification-method row on parsed pages.

The aggregate `source_reported_total_service_lines_sum` is only the arithmetic sum of successfully parsed PWS summary totals. It excludes explicit unavailable detail records and is not represented as a single-date statewide engineering inventory because individual source submissions may have different certification/update dates.

## Acceptance

Do not advance this increment unless every current-index PWS is accounted for as either a fully parsed detail or a narrowly evidenced `DETAIL_UNAVAILABLE_404`, no other errors are hidden, any source-reported inventory arithmetic mismatches are explicitly counted with reconciliation deltas, the artifact revalidates after download, and the full repository test/build gate is green against the verified Build 017C parent branch.
