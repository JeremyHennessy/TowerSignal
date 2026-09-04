# TowerSignal Build 017G — NYSDOH Lead Service Line Inventory Detail Crawl

Date: 2026-09-04

## Verified parent checkpoint

This increment starts from exact verified statewide PWS branch head `f75589a63db3ba0fb1c1e03007f535e23119516f` (Build 017C). The parent source proof established the current NYSDOH LSLI index at 2,927 unique PWS IDs and passed full source/integration validation.

This is a layered data-source proof. It does not modify production UI, scoring, cooling-tower behavior, procurement, auth/RLS or deployment behavior.

## Source

Every current PWS ID in the authoritative NYSDOH Lead Service Line Inventory index has a deterministic detail URL:

`https://www.health.ny.gov/environmental/water/drinking/service_line/{PWSID}.htm`

The workflow re-fetches the current index, requires unique PWS IDs, then retrieves every detail URL sequentially with a bounded request delay. A detail page must parse successfully and its internal PWS ID must equal the index PWS ID; otherwise the cache fails rather than publishing partial coverage.

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

The validator independently requires:

`identified = lead + GSLRR + non-lead`

and

`total = identified + unknown`.

### Section IV — public availability
Public-access text and external inventory links are retained where source-present.

### Section V — certification
Name/title/date are retained when structurally present in the source form. Blank certification cells remain blank and are not synthesized.

## Evidence and source integrity

Each detail record keeps the official detail URL and SHA-256 of the exact HTML used. The source proof requires index count = detail count and no duplicate/mismatched PWS IDs. Every expected identification-method row must be present.

The aggregate `source_reported_total_service_lines_sum` is only the arithmetic sum of individual PWS summary totals. It is not represented as a single-date statewide engineering inventory because individual source submissions may have different certification/update dates.

## Acceptance

Do not advance this increment unless all 2,927-current-index detail pages (or whatever exact count the live index reports at run time) are retrieved and parsed with no silent omissions, inventory arithmetic reconciles, the artifact revalidates after download, and the full repository test/build gate is green against the verified Build 017C parent branch.
