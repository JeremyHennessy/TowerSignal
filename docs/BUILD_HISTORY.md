# TowerSignal Build History

This file records the major production build lineage and the engineering decisions that must survive future work. Diagnostic-only PRs are included only where they established an architectural or root-cause decision.

## Build 001 — NYC public-data foundation

**Production capability**

- NYC Cooling Tower Registrations (`y4fw-iqfr`).
- NYC Cooling Tower System Inspection Results (`f9wb-g8mb`).
- registration deduplication by source `system_id`;
- inspection/violation aggregation;
- deterministic commercial signals;
- NYC Priority Score 1.0;
- React/TypeScript/Vite interface;
- filtering, map, system evidence detail and filtered CSV export;
- independent sampled source verification;
- Pages deployment and desktop/iPhone hosted browser checks.

**Important correction**

Invalid source coordinates such as `0.0/0.0` are retained as provenance but quarantined from mapping rather than causing records to disappear.

## Build 002 — OATH case lifecycle

Added NYC OATH Hearings Division Case Status (`jz4z-kudi`) using only exact NYC Health `summons_number` → OATH `ticket_number` joins.

OATH outcome/penalty/payment state is evidence/context and does not modify Priority Score 1.0.

## Build 003 — PLUTO property context

Added PLUTO (`64uk-42ks`) via exact normalized BBL with property/owner/building context.

Later source-health testing exposed a decimal-form Socrata BBL normalization defect. The normalization boundary was repaired without changing score/signal semantics, and the broad recovery was baselined so restored enrichment did not manufacture false owner-change events.

## Build 004 — HPD registered contacts

Added:

- Multiple Dwelling Registrations (`tesw-yqqr`) by exact BBL;
- Registration Contacts (`feu5-w2e2`) by exact `registration_id` after the BBL match.

HPD coverage is scope-limited; missing HPD registration is not evidence that a property lacks an owner/operator/contact relationship outside HPD's scope.

## Build 005 — actionable contact-bearing leads

Added contact-availability filtering and contact-related export context using the already source-backed HPD/PLUTO enrichment.

## Build 006 — copied source-backed lead brief

Enriched the copied lead summary with loaded PLUTO/HPD context and prevented copying before source-backed detail was available.

Public owner/contact context is not represented as cooling-tower procurement responsibility.

## Build 007 — durable history and Changes

Added:

- persisted observation history on `data/towersignal-history`;
- deterministic snapshot-to-snapshot event generation;
- detection time vs source observation date;
- first/last-seen semantics;
- first-class Changes UI;
- TowerSignal History in detail;
- persistence only after hosted deployment verification.

### Build 007 compact-history correction

The first functionally correct representation produced a ~76.65 MB snapshot and was rejected. Production history was redesigned into compact schema 1.1 without relaxing the guardrail.

Current NYC history hard ceiling: **25 MiB**.

Schema migration establishes a baseline without synthetic events. Unsupported enrichment disappearance is suppressed rather than interpreted as a real-world removal.

## Build 008 — historical intelligence profile

Added source-backed historical summaries for:

- registration/public-evidence age;
- reported sample history and intervals;
- NYC Health inspection/violation history;
- exact-matched OATH penalty/payment/balance aggregates.

Scoring and current signal semantics remained unchanged.

## Build 009 — source-health and join-coverage QA

Added machine-readable source-health accounting across retrieval → normalization → matching → attachment → display.

Key safeguards include:

- attachment/display integrity checks;
- previous verified coverage comparison;
- hard failure on material collapse;
- production deployment gating;
- source-health visibility in the product.

This layer later caught the PLUTO BBL attachment regression that ordinary successful retrieval would not have exposed.

### Build 009 hosted UI corrections

Two isolated UI defects were proven and fixed:

- Leaflet panes escaping the map stacking context and intercepting controls;
- expensive Leaflet teardown/remount during mode switching on iPhone/WebKit.

The latter was fixed by retaining the map subtree while hiding its inactive mode, not by redesigning the map.

## Build 010 — DOB NOW property project activity

Added DOB NOW: Build – Job Application Filings (`w9ak-ipjd`) by exact quoted BBL.

Semantics:

- published lifecycle dates preserved;
- latest lifecycle date may be used as property activity date;
- explicit cooling-tower context only when published job description says `cooling tower`/`cooling towers`;
- mechanical/boiler work-type flags remain broader property context and are not automatically cooling-tower work;
- DOB does not change Priority Score 1.0.

Verified production-scale coverage at introduction was approximately 91.68% of usable cooling-tower BBLs.

## Build 010.1 — mobile WebKit Changes filter stability

A hosted iPhone/WebKit hang was isolated to intrinsic minimum sizing in the mobile Changes filter grid. The production correction changed only the relevant CSS grid tracks to `minmax(0,1fr)`.

## Build 011 — DOB lifecycle change intelligence

Promoted DOB from static property context into deterministic longitudinal events after an initial baseline:

- `DOB_JOB_FILED`;
- `DOB_STATUS_CHANGED`;
- `DOB_PERMIT_ISSUED`;
- `DOB_JOB_APPROVED`;
- `DOB_JOB_SIGNED_OFF`;
- `DOB_COOLING_TOWER_MENTION_ADDED`.

A first implementation duplicated property-level DOB state per cooling-tower system and exceeded the unchanged history ceiling (~30.5 MB). Production was redesigned to compact each exact-BBL DOB baseline once at snapshot top level using compact filing state/milestone bits.

No history guardrail was relaxed.

## Build 011.1 — verified history persistence path repair

Build 011 itself deployed successfully, but durable `data/towersignal-history` did not update because `actions/upload-artifact` used `public/data` as the least common ancestor and the persist job copied the wrong extracted history paths.

The correction changed only the two history copy sources. No data, history semantics, score, join, UI or dependency changed.

## Build 012 — New York State registry expansion

Added the authoritative New York State Cooling Tower Registry Weekly Extract (`24a4-muw7`) as a **separate evidence regime**.

Identity and semantics:

- exact source `Equipment_ID`;
- TowerSignal global ID `NYS-<Equipment_ID>`;
- source-native `Reg_Comp`, `CT_Status`, latest Legionella sample/result, operation duration and published location/recency context;
- no NYC Priority Score on NYS equipment;
- no projection of NYC OATH/PLUTO/HPD semantics onto NYS;
- property grouping by normalized exact street address + city + ZIP only.

Live source-contract diagnostics found published county values that were inconsistent with physical location, so county remains provenance rather than an authoritative NYC discriminator.

### Separate NYS history

NYS history is physically separate under `data/history/nys/*` with an **8 MiB** hard ceiling.

The first baseline emitted zero synthetic events. Current event semantics include exact Equipment_ID compliance/status/sample/operation-duration changes, while normal daily movement in published relative counters is ignored.

Verified Build 012 introduction snapshot:

- 6,236 source rows / 6,236 represented equipment records;
- 6,231 mapped equipment records;
- 100% representation source health;
- separate NYS history ~3.45 MB;
- NYC history remained ~22.32 MB under its unchanged 25 MiB ceiling;
- desktop Chromium and iPhone/WebKit product proof passed.

## Commercial account-intelligence redesign — PR #44

Merged at `8d7911aab60b6521891398efc5a2957247218ceb`.

Repositioned the application from dataset-first navigation into:

- Prospect;
- Monitor;
- Map;
- NYS Market;
- NYS Changes.

Added commercial hero/KPIs, persistent filter rail, removable active filters, browser-local saved views, sales-oriented account table and dedicated territory-map workspace while preserving existing source schemas, scoring, history and detail evidence.

### Responsive closeout — PR #52

Live proof found two regressions in the exact redesign SHA:

1. NYS Market horizontal overflow at 1280px caused by inherited workspace minimum widths inside the new page shell.
2. NYS Market/NYS Changes nav buttons hidden at <=430px.

The corrections were isolated to responsive layout boundaries and merged at:

`a773dcbca9a7c038408f7f990a9c567db65be813`

### Hosted-test correction — PR #54

The post-correction iPhone/WebKit run reached the Map workspace with Leaflet visible but failed because the test expected the `.map-summary` sidebar to be visible. The redesign intentionally hides that sidebar at <=1200px.

PR #54 corrected only the test expectation and merged at:

`dfec21e063c75f077b33879044113515d89e11ff`

No application/UI code changed in PR #54.

The commercial UI is not considered a frozen production baseline until the exact post-correction Pages run completes all production gates.

## Build 013 — ACRIS property timing intelligence — OPEN / UNMERGED

Build 013 was developed from the verified Build 012 baseline before the commercial redesign and must therefore be reconciled rather than merged mechanically.

### Rejected architecture

A decades-long ACRIS crawl across all cooling-tower BBLs was tested and rejected because production query latency/timeout behavior made it unsuitable for the critical daily Pages path.

### Proven replacement architecture

- independent daily/manual ACRIS cache refresh;
- bounded 365-day commercially relevant Master slice;
- exact BBL → Legals;
- exact `document_id` → Master/Parties;
- keep only exact intersections with the TowerSignal BBL universe;
- persist last verified cache separately at `data/towersignal-acris`;
- normal Pages deployments consume the last verified cache rather than querying live ACRIS;
- 12 MiB cache ceiling;
- browser detail retains at most 25 most recent documents/property while aggregates retain full bounded-cache counts;
- explicit cache freshness.

A proven production gate returned:

- 296 matched BBLs from 2,991 cooling-tower BBLs;
- 1,802 relevant documents;
- 4,654 party rows;
- 1,747,658-byte cache;
- 386 enriched TowerSignal systems;
- 9.9% observed activity prevalence;
- five deterministic source reproductions;
- all existing NYC/NYS history/source/test/build gates green.

### Current blocker

PR #43 current head `c7b063f91b0c52c72604118f709b967bece38a55` has green normal CI but red ACRIS cache workflow. The exact observed failure is a timeout fetching Master metadata (`bnx9-e6tj`) after five attempts.

Do not interpret that as proof that the bounded-cache architecture failed. Diagnose the metadata request separately, reconcile the product UI onto the commercial workspace, and require an exact-head green ACRIS cache/integration gate before merge.

## Future tracked sequence

- #46 finish/reconcile Build 013.
- #47 persistent prospect/watchlist/account workflow.
- #48 separate commercial Opportunity Score 2.0.
- #49 PLUTO owner portfolio context.
- #50 LL84/additional sources only where commercial lift is demonstrated.
- #51 SaaS productization after workflow validation.
- #53 correct Pages from legacy branch publishing to workflow-only publishing.
