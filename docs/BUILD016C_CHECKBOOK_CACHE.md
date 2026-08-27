# TowerSignal Build 016C1 — Checkbook NYC verified procurement cache

Date: 2026-08-26

## Exact engineering baseline

Build 016C1 starts from exact `main@da89eae394d7dad72e33de783b3653805292640a`, after Build 016B City Record source retrieval, production deployment and hosted browser verification succeeded.

This is an engineering baseline. It is not a claim of user visual approval for the Build 015 interface.

## Scope

Build 016C1 adds a durable, independently verified Checkbook NYC contract cache. It does **not** connect the cache to the public UI yet.

The source adapter covers:

- Citywide registered expense contracts (`type_of_data=Contracts`);
- NYCEDC registered expense contracts through the Other Government Entities domain (`type_of_data=Contracts_OGE`, code `z81`);
- prime contract evidence;
- relevant subcontract evidence when the subcontract's own purpose text supports TowerSignal's service taxonomy;
- exact source-side counts and fail-closed pagination;
- source-reported original/current contract amounts and spend-to-date;
- explicit source health and raw source provenance.

NYCHA is explicitly deferred to a separate adapter because Checkbook exposes NYCHA at release/line-item granularity with a materially different source contract.

## API safety contract

The Checkbook API is a POST/XML interface. The adapter:

- serializes outbound requests process-wide;
- spaces requests by at least 1.2 seconds;
- uses at most 20,000 records per call;
- does not follow redirects;
- retries only transient network/5xx failures;
- never turns API/transport failures into an empty source;
- requires the source-reported `record_count` to remain stable across pagination;
- requires the final retrieved source transaction count to exactly equal that count.

The Citywide all-years response-column set intentionally excludes `year`, `prime_contract_registration_date`, and `sub_contract_registration_date` because recent live API verification shows those documented fields are not accepted consistently by the production endpoint in this query shape.

## Evidence boundaries

Priority Score 1.0 is unchanged.

All monetary fields are represented as observed source-reported public contract/subcontract values or spending-to-date. They are not represented as company revenue, total customer value, or a complete customer book.

Vendor strings remain unresolved company evidence in this increment. No fuzzy vendor merge is performed.

Facility and cooling-tower account linkage remain `UNLINKED`. No institution-level contract is promoted to property-level evidence.

Subcontractors do not inherit the prime contractor's service classification. A subcontract is retained only when its own source text classifies as relevant.

## Durable-cache workflow

`.github/workflows/checkbook-cache.yml`:

1. builds the bounded Checkbook cache from the live API;
2. validates structure, freshness, production volume and evidence boundaries;
3. independently re-queries sampled prime contracts by exact contract ID;
4. runs the standard Python/frontend/build integration gate on pull requests;
5. persists only a verified cache to `data/towersignal-checkbook:data/checkbook/cache.json` after non-PR runs.

The cache-only increment does not modify `pages.yml`, product routing, opportunities UI, source-health UI, auth/RLS, or scoring.

## Acceptance

Build 016C1 is accepted only after:

- standard CI is green on the exact pull-request head;
- the Checkbook cache workflow is green on the exact pull-request head, including live source build, validation and independent sampled verification;
- the diff remains confined to the Checkbook adapter/cache workflow/tests/docs;
- the exact green head is merged;
- the post-merge Checkbook workflow successfully persists a verified durable cache.

Only after that gate should Build 016C2 attach the verified cache to the Pages build and expose source-backed procurement intelligence in the product.
