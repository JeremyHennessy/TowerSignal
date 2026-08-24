# TowerSignal Canonical Project State

Last reconstructed: 2026-08-24

This file is the canonical engineering/product custody record. It is intentionally more conservative than marketing copy: a feature is marked production-verified only when the required evidence exists.

## 1. Product objective

TowerSignal is evolving from a public cooling-tower data interface into commercial timing and account intelligence for water-treatment, Legionella, HVAC/mechanical and environmental service teams.

The core user questions are:

1. What changed?
2. Why may it matter commercially?
3. What source-backed property/contact context is available?
4. How valuable/timely may the account be?
5. Why should a user investigate it now?

The product must preserve the distinction between **commercial priority**, **source evidence** and **regulatory conclusions**.

## 2. Current baseline custody

### Product/UI lineage

- PR #44 commercial redesign merged at `8d7911aab60b6521891398efc5a2957247218ceb`.
- Live diagnostics found two responsive regressions in that exact UI:
  - NYS Market desktop overflow at 1280px due to inherited workspace minimum widths.
  - NYS Market/NYS Changes navigation hidden at <=430px.
- PR #52 applied the proven responsive corrections and merged at `a773dcbca9a7c038408f7f990a9c567db65be813`.
- PR #54 is hosted-test-only and merged at `dfec21e063c75f077b33879044113515d89e11ff`; it does not change application/UI code.

### Approval state

**Candidate UI code baseline:** `a773dcbca9a7c038408f7f990a9c567db65be813`.

Do not mark this as the approved production baseline until the post-correction `pages.yml` run proves:

- production build green;
- Pages artifact deployment green;
- hosted desktop Chromium green;
- hosted iPhone/WebKit green;
- verified history persistence green.

When that proof exists, record:

- Approved UI code SHA: `a773dcbca9a7c038408f7f990a9c567db65be813`.
- QA-only main SHA at approval: `dfec21e063c75f077b33879044113515d89e11ff` or later test/documentation-only descendant.
- What is approved: Prospect / Monitor / Map / NYS Market / NYS Changes commercial workspace and the responsive corrections from PR #52.
- What is not implied by approval: Build 013 ACRIS, persistent multi-device workflow, Opportunity Score, SaaS infrastructure.

## 3. Current product modes

### Prospect

Commercial NYC account-discovery workspace with:

- commercial timing hero/summary;
- priority/timing/contact/OATH/violation/geography/equipment filters;
- removable filter state;
- browser-local saved views (`towersignal.savedViews.v1`);
- sales-oriented account table;
- filtered CSV export;
- source-backed slide-over detail.

### Monitor

Deterministic longitudinal public-record changes with source/detection-time semantics and system drill-through.

### Map

Geographic view of the same filtered NYC account set. Map content must remain semantically synchronized with Prospect filters.

### NYS Market

Separate source regime based on the official NYS weekly registry. It does not inherit NYC Priority Score or NYC-specific OATH/PLUTO/HPD semantics.

### NYS Changes

Separate preserved NYS observation/change history.

## 4. Current authoritative source inventory

### NYC

| Source key | Dataset | Contract | Current verified coverage snapshot |
| --- | --- | --- | ---: |
| registrations | `y4fw-iqfr` | exact `system_id` | 4,894 / 100% represented |
| inspections | `f9wb-g8mb` | exact `system_id` | 98.79% systems with published inspection history |
| oath | `jz4z-kudi` | exact `summons_number` → `ticket_number` | 99.47% requested summons/ticket match coverage |
| pluto | `64uk-42ks` | exact normalized BBL | 96.29% requested BBL coverage |
| dob_now_jobs | `w9ak-ipjd` | exact quoted BBL | 91.68% requested BBL coverage |
| hpd_registrations | `tesw-yqqr` | exact normalized BBL | 49.88%; scope-limited, not expected universal coverage |
| hpd_contacts | `feu5-w2e2` | exact registration ID after exact-BBL registration match | 99.33% of matched HPD registration BBLs |

### NYS

| Source key | Dataset | Contract | Current verified coverage snapshot |
| --- | --- | --- | ---: |
| nys_registry | `24a4-muw7` | exact `Equipment_ID` | 6,236 / 100% represented |

NYS property grouping is normalized exact published street address + city + ZIP only. Missing coordinates do not remove equipment from inventory.

### ACRIS Build 013 candidate — not production

| Source | Dataset | Contract |
| --- | --- | --- |
| Real Property Legals | `8h5j-fqxa` | exact borough/block/lot → BBL |
| Master | `bnx9-e6tj` | exact `document_id` |
| Parties | `636b-3b5g` | exact `document_id` |

No fuzzy ACRIS property or party matching is authorized.

## 5. Priority Score 1.0 — immutable current model

Model constant: `PRIORITY_MODEL_VERSION = "1.0"`.

Deterministic components:

- recent confirmed violation: +40;
- recent critical/public-health-hazard violation wording: additional +10;
- no usable public sample date: +18;
- potential sampling gap: +20 (>31 days), +25 (>45 days), +30 (>60 days);
- active tower units: +6 per unit above one, capped +18;
- recent NYC Health regulatory activity: +10;
- total capped at 100.

Interpretation boundary:

- commercial research priority only;
- not health risk;
- not regulatory risk;
- not safety rating;
- not probability of noncompliance.

Any future Opportunity Score must be a separate versioned model with separate UI/labeling and component explanations. It must not mutate Priority Score 1.0 silently.

## 6. Regulatory/signal semantics

Current rules version: `nyc-2026-05-08`.

- Sampling maximum interval modeled as 31 days while operating.
- Public sample-date gaps remain verification signals because TowerSignal cannot establish continuous operating status from the public source alone.
- Owner/operator qualified-person inspection interval is 90 days.
- NYC Health BWSO government inspections are not treated as that owner/operator qualified-person history.
- Recent violation lookback: 365 days.
- Recent regulatory activity lookback: 90 days.

## 7. Historical state / guardrails

### NYC

- compact durable history schema: 1.1;
- hard ceiling: 25 MiB;
- relative growth guard: 1.75x with 2 MiB absolute allowance;
- DOB state deduplicated per exact BBL;
- data-repair/source-recovery safeguards suppress unsupported synthetic events.

### NYS

- physically separate history at `data/history/nys/*`;
- hard ceiling: 8 MiB;
- relative growth guard: 1.75x with 1 MiB absolute allowance;
- first baseline emits zero synthetic events;
- daily movement in published relative counters is not itself treated as an event.

### ACRIS

ACRIS state is intentionally not added to NYC durable history in Build 013. Recent ACRIS context is a separately refreshed bounded cache.

## 8. Production verification contract

A production release is not approved because code merged or CI passed.

Required sequence:

1. Current NYC source generation.
2. Current NYS source generation.
3. Source-health validation.
4. NYC history generation.
5. NYS history generation.
6. Independent history size/growth gates.
7. Independent sampled NYC source re-verification.
8. Independent sampled NYS source re-verification.
9. Python tests.
10. ESLint.
11. TypeScript.
12. Frontend regression tests.
13. Production Vite build.
14. Pages artifact deployment.
15. Hosted desktop Chromium verification.
16. Hosted iPhone/WebKit verification.
17. Only after hosted verification: persist verified history.

Production must not substitute fixtures or mock records when an authoritative-source operation fails.

## 9. Confirmed infrastructure defect — Pages source mode

Issue #53 tracks a separate repository-setting defect.

Confirmed repository Pages configuration on 2026-08-24:

- `build_type: legacy`;
- source branch `main`;
- source path `/`;
- HTTPS enforced.

TowerSignal's intended publisher is the custom Actions `pages.yml` workflow. The legacy branch publisher has twice been observed temporarily serving raw repository `index.html` after a push, causing `/src/main.tsx` to 404 and the hosted application to be blank until the custom artifact deployment replaces it.

An isolated attempt to switch `build_type` to `workflow` using the workflow-scoped token failed with HTTP 403 `Resource not accessible by integration`. No repository setting changed.

The available GitHub connector does not expose the needed Pages administration mutation. Until issue #53 is corrected with repository-admin authority, avoid unnecessary pushes to `main` and never interpret the transient raw-branch site as the intended built release.

## 10. Build 013 ACRIS current state

PR #43 remains open/unmerged and is based on pre-redesign `main`.

Proven bounded-cache result from an earlier exact production gate:

- 2,991 verified cooling-tower BBLs requested;
- 296 BBLs with recent relevant ACRIS activity;
- 1,802 matched relevant documents;
- 4,654 party rows;
- 1,747,658-byte cache;
- 386 TowerSignal systems enriched;
- 9.9% observed recent-activity prevalence;
- five deterministic cached documents independently reproduced from live Master/Legals/Parties;
- full Python/frontend/build and NYC/NYS verification green on that proven head.

Current blocker on PR #43 head `c7b063f91b0c52c72604118f709b967bece38a55`:

- normal CI is green;
- ACRIS cache workflow is red;
- exact failure: Master metadata endpoint `https://data.cityofnewyork.us/api/views/bnx9-e6tj` timed out after five attempts in `_metadata()` / `_request_json()`;
- validation/integration did not run after that failure.

This failure is evidence of an upstream metadata-request timeout. It is not evidence that the bounded 365-day cache architecture is invalid.

Build 013 must be reconciled onto the approved commercial UI. Conflict resolution must not restore pre-redesign `App.tsx`, `Filters.tsx`, `SystemTable.tsx` or other old workspace structure.

## 11. Roadmap / tracked issues

Order after UI closeout:

1. #53 — correct Pages source mode when admin-capable action is available.
2. #46 — reconcile/finish Build 013 ACRIS.
3. #47 — persistent watchlists, saved views, account status, notes and change digests.
4. #48 — separate Opportunity Score 2.0.
5. #49 — source-backed PLUTO owner portfolio intelligence.
6. #50 — LL84/additional source evaluation based on commercial lift.
7. #51 — multi-user SaaS infrastructure only after workflow validation.

## 12. Change-control rules

- Approved UI is frozen against unrelated data/backend fixes.
- Diagnose data at the data layer before altering presentation.
- No opportunistic refactor during targeted fixes.
- One hypothesis/test at a time for difficult failures.
- Experiments belong on isolated branches/workflows and must be reversible.
- No fuzzy joins merely to improve apparent coverage.
- No source-backed public party/contact context may be upgraded into procurement responsibility without separate evidence.
- A green workflow is evidence only for the exact SHA that ran it.
