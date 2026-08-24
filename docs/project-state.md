# TowerSignal — Canonical Project State

Last reconstructed and verified: **2026-08-24**

This file is the engineering custody record for TowerSignal. Before a consequential production change, compare the intended change against this state and the current repository rather than reconstructing project history from memory or the nearest commit.

## 1. Current verified production baseline

| Item | Verified state |
| --- | --- |
| Repository | `JeremyHennessy/TowerSignal` |
| Default branch | `main` |
| Verified commercial UI / production baseline | `dfec21e063c75f077b33879044113515d89e11ff` |
| Verification date | 2026-08-24 |
| Production Pages workflow | run #33 / `32766611745` |
| Build | SUCCESS |
| GitHub Pages deployment | SUCCESS |
| Hosted desktop Chromium | SUCCESS |
| Hosted iPhone/WebKit | SUCCESS |
| Verified history persistence | SUCCESS |
| Live URL | `https://jeremyhennessy.github.io/TowerSignal/` |

`dfec21e063c75f077b33879044113515d89e11ff` is the **current engineering regression baseline** for the commercial interface. It contains the task-first commercial redesign plus the two proven responsive fixes and the final hosted-test correction. Treat the existing Prospect / Monitor / Map / NYS Market / NYS Changes architecture and visual system as the reference state during unrelated fixes.

This engineering verification does not substitute for a separate explicit user design-approval statement if one is later given. A later explicit user approval must be recorded as a harder checkpoint.

### Baseline lineage

- `3f6e44e0a191e3f5d2aadd7deb7f3869a119ca58` — merged Build 012 NYS expansion baseline.
- `8d7911aab60b6521891398efc5a2957247218ceb` — PR #44 commercial account-intelligence UI redesign merge.
- `a773dcbca9a7c038408f7f990a9c567db65be813` — PR #52 narrow responsive closeout fixes: mobile NYS navigation and desktop NYS workspace shrink behavior; production code otherwise unchanged.
- `dfec21e063c75f077b33879044113515d89e11ff` — PR #54 test-only mobile Map hosted-verification correction; **current verified baseline**.

### Closeout evidence

The first independent redesign live proof correctly failed and exposed two real regressions:

1. mobile CSS explicitly hid NYS Market / NYS Changes;
2. the legacy NYS workspace minimum grid tracks exceeded the redesigned desktop content shell at 1280px.

PR #52 corrected only those boundaries. Production run #32 then passed desktop but exposed a test defect on iPhone: the test required the Map summary to be visible even though responsive CSS intentionally hides `.map-summary` at `max-width:1200px`. PR #54 changed only that test expectation. Production run #33 subsequently passed the complete build/deploy/hosted-verification/persistence chain.

Diagnostic PR #45 was closed **unmerged** after closeout.

### Custody note: reverted temporary file

During closeout, an unintended `docs/DO-NOT-COMMIT.txt` file was briefly created on `main` in commit `ddbf1bfe1cd0942737f2ec451d093d270492e20e` and immediately deleted in `ea2083da53f07ccaaf7b189cfa00f1da3082ce8c`. A compare against the pre-incident product tree confirmed no surviving file-content difference before the production responsive-fix merge. These commits remain in history as transparent no-op/revert lineage; do not treat them as product baselines.

## 2. Product purpose and target users

TowerSignal is a commercial timing and account-intelligence product for specialist cooling-tower markets. Its current product job is:

> Identify which accounts deserve investigation now, explain why, expose the public evidence behind the signal, and preserve changes that create a reason to revisit an account.

Primary intended users:

- water-treatment service providers;
- Legionella testing / laboratory organizations;
- cooling-tower maintenance specialists;
- HVAC / mechanical service and project organizations;
- industrial hygiene and environmental consulting firms.

The product is **not** an owner compliance-management system, health-risk model, legal determination engine or automated outreach system.

## 3. Build history

| Build / checkpoint | Primary PR(s) | Production capability added | State |
| --- | --- | --- | --- |
| Build 001 | #1, #4, #6, #8 | NYC registrations + inspections, deterministic signals, Priority Score 1.0, filters, map, evidence detail, CSV, source verification, Pages/browser gate | Complete |
| Build 002 | #10 | exact NYC Health summons → OATH ticket lifecycle enrichment | Complete |
| Build 003 | #12 | exact-BBL PLUTO property/building/owner context | Complete |
| Build 004 | #14 | exact-BBL HPD registration + exact-registration contact context | Complete |
| Build 005 | #16 | contact-availability filtering and contact-bearing CSV fields | Complete |
| Build 006 | #18 | source-backed copied lead brief with PLUTO/HPD context | Complete |
| Build 007 | #20, #21 | durable observation/change engine, Changes view, compact schema 1.1, history-size guard | Complete |
| Build 008 | #23, #24 | descriptive historical intelligence profile and hosted proof | Complete |
| Build 009 | #25, #27–#30 | source-health/join-coverage QA plus PLUTO normalization and map/mobile regression repairs | Complete |
| Build 010 | #31 | exact-BBL DOB NOW project/activity intelligence | Complete |
| Build 010.1 | #33 | narrow mobile WebKit Changes filter-grid repair | Complete |
| Build 011 | #34 | DOB NOW lifecycle change events in durable NYC history | Complete |
| Build 011.1 | #36 | verified-history artifact persistence path repair | Complete |
| Build 012 | #38 | separate NYS Cooling Tower Registry product/history/source-health regime | Complete |
| Commercial UI redesign | #44 | Prospect / Monitor / Map / NYS Market / NYS Changes commercial workspace; saved local views; task-first hierarchy | Complete |
| UI live closeout | #52, #54 | proven responsive boundary fixes + production hosted-test alignment | Complete / verified at `dfec21e…` |
| Build 013 | #43 | bounded recent ACRIS property transaction timing intelligence | **Open / not merged** |

Disposable diagnostic PRs are intentionally excluded from the product build sequence unless they established an architectural decision documented below.

## 4. Current source inventory and health

Latest persisted source-health snapshot: **2026-08-24T19:14:30.555406Z**.

All eight current source models are `HEALTHY`.

| Source key | Authoritative dataset | Current requested / represented context | Coverage | Health |
| --- | --- | --- | ---: | --- |
| registrations | NYC Cooling Tower Registrations `y4fw-iqfr` | 4,894 normalized NYC systems / 4,894 represented | 100.00% | HEALTHY |
| inspections | NYC Cooling Tower System Inspection Results `f9wb-g8mb` | 4,835 current systems with exact inspection history / 4,894 systems | 98.79% | HEALTHY |
| OATH | OATH Hearings Division Case Status `jz4z-kudi` | 54,746 exact matched summons/tickets / 55,036 requested | 99.47% | HEALTHY |
| PLUTO | PLUTO `64uk-42ks` | 2,880 exact BBL matches / 2,991 requested | 96.29% | HEALTHY |
| DOB NOW | Job Application Filings `w9ak-ipjd` | 2,742 exact BBL matches / 2,991 requested | 91.68% | HEALTHY |
| HPD registrations | Multiple Dwelling Registrations `tesw-yqqr` | 1,492 exact BBL matches / 2,991 requested | 49.88% | HEALTHY / scope-limited |
| HPD contacts | Registration Contacts `feu5-w2e2` | 1,482 matched HPD-registration BBLs with contact rows / 1,492 matched registrations | 99.33% | HEALTHY |
| NYS registry | Weekly Extract `24a4-muw7` | 6,236 unique Equipment_ID rows / 6,236 represented | 100.00% | HEALTHY |

Coverage percentage is source-contract specific. Low HPD registration coverage is not itself a failure because HPD registration applies only to qualifying properties.

## 5. Exact identity / join contracts

These contracts are part of the current evidence model. Do not replace them with fuzzy matching merely to increase coverage.

### NYC cooling-tower core

- current system identity: exact published `system_id`;
- inspections: exact `system_id` to current system;
- source registration deduplication is deterministic.

### OATH

`NYC Health summons_number → OATH ticket_number`

- exact identifier equality only;
- no respondent/address/BBL fuzzy fallback;
- OATH outcome/monetary context is separate from Priority Score 1.0.

### PLUTO

`cooling-tower BBL → PLUTO BBL`

- exact normalized BBL only;
- integral Socrata numeric representations are normalized without altering the identifier;
- owner text is public property context, not cooling-tower procurement identity.

### HPD

`cooling-tower BBL → HPD registration BBL → exact registration_id → HPD contacts`

- qualifying-property scope must remain explicit;
- HPD role/contact records do not establish cooling-tower service responsibility.

### DOB NOW

`cooling-tower BBL → DOB NOW published BBL`

- exact quoted BBL query/join;
- `Cooling tower mention` requires explicit `cooling tower` / `cooling towers` text in the published job description;
- mechanical/boiler flags alone are broader property-project context;
- DOB does not affect Priority Score 1.0.

### NYS Cooling Tower Registry

- equipment identity: exact source `Equipment_ID`;
- TowerSignal ID: `NYS-<Equipment_ID>`;
- source-native `Reg_Comp`, `CT_Status`, sample/result, operation duration and location are represented directly;
- property grouping: case/whitespace-normalized exact published street address + city + ZIP;
- published county is provenance, not a safe NYC classifier by itself;
- no NYC Priority Score is projected onto NYS equipment.

### Pending ACRIS contract

Planned Build 013 exact chain:

`cooling-tower exact BBL → ACRIS Legals exact borough/block/lot BBL → exact document_id → ACRIS Master + Parties exact document_id`

Datasets:

- Legals `8h5j-fqxa`
- Master `bnx9-e6tj`
- Parties `636b-3b5g`

No ACRIS party may be inferred to be the current owner, cooling-tower operator, procurement contact, service provider or vendor solely from the recorded document.

## 6. NYC Priority Score 1.0 — immutable current contract

Model constant: `PRIORITY_MODEL_VERSION = "1.0"`.

The current implementation in `scripts/towersignal/scoring.py` is:

| Component | Points |
| --- | ---: |
| confirmed recent violation | +40 |
| recent critical/public-health-hazard violation | additional +10 |
| no usable public sample date | +18 |
| potential sampling gap, 32–45 days | +20 |
| potential sampling gap, 46–60 days | +25 |
| potential sampling gap, >60 days | +30 |
| active equipment above first unit | +6/unit, max +18 |
| recent NYC Health regulatory activity | +10 |
| total | capped at 100 |

Rules version at this baseline: `nyc-2026-05-08`.

Interpretation contract:

- Priority Score is a commercial research-priority score.
- It is not a health-risk score, regulatory-risk score, safety rating, compliance probability or legal conclusion.
- Evidence confidence is separate from score.
- DOB, PLUTO, HPD and OATH outcome fields do not silently alter model 1.0.
- Pending ACRIS must not alter model 1.0.
- A future Opportunity Score must be a separate, explicitly versioned model rather than a silent rewrite of Priority Score.

## 7. Historical-state architecture and storage guardrails

Durable history branch: `data/towersignal-history`.

### NYC history

- schema: compact durable observation representation introduced in Build 007;
- hard snapshot ceiling: **25 MiB / 26,214,400 bytes**;
- current `latest.json`: **22,323,020 bytes / 21.29 MiB**;
- current ceiling utilization: **85.16%**;
- current retained `events.json`: **436,161 bytes**;
- relative-growth anomaly guard remains active;
- DOB baseline is deduplicated by exact BBL at top level rather than duplicated per system.

Because the NYC snapshot is already at ~85% of its hard ceiling, new high-volume source state must not be added casually. ACRIS is intentionally excluded from this history store.

### NYS history

- physically separate under `data/history/nys/`;
- hard snapshot ceiling: **8 MiB / 8,388,608 bytes**;
- current `latest.json`: **3,451,744 bytes / 3.29 MiB**;
- current ceiling utilization: **41.15%**;
- current `events.json`: 13 bytes at this observed snapshot (no retained NYS events in the current file);
- ignores routine movement in source-relative counters such as `lastupdate` / `last_sampled_days` when those would manufacture daily changes.

### Persistence invariant

The normal Pages pipeline stages generated history during build but persists it to `data/towersignal-history` **only after the deployed Pages application passes hosted verification**. A failed hosted build must not advance the durable observation baseline.

## 8. Source-health invariant

Source health measures the path:

`requested → retrieved → normalized → matched → attached → displayed/represented`

Key safeguards include:

- matched-but-not-attached regression detection;
- attached-but-not-represented regression detection;
- material relative coverage-collapse guards;
- persisted previous verified coverage for comparison;
- explicit scope notes where low absolute coverage is expected rather than anomalous.

A pipeline run is not considered successful merely because an upstream query returned rows.

## 9. Current UI / workflow contract

Current navigation:

1. **Prospect**
2. **Monitor**
3. **Map**
4. **NYS Market**
5. **NYS Changes**

Current commercial behaviors include:

- NYC prospect filtering by search, timing/evidence/contact/OATH/violation/geography/equipment/priority criteria;
- commercial signal summary metrics;
- account-priority table emphasizing timing/evidence/contact/activity context;
- detail slide-over retaining source-backed evidence and historical context;
- CSV export;
- copied source-backed lead brief;
- browser-local saved filter views under `towersignal.savedViews.v1`;
- same filtered NYC set shared between Prospect and Map;
- separate NYS source regime and NYS change view;
- compact source-health/provenance trust surfaces.

### Known workflow limitation

Saved views are currently `localStorage` only. There is no durable cross-device watchlist, account disposition, note, next-action or alert/digest system. This is the highest-priority product-depth gap after Build 013.

## 10. Build 013 — current state and blocker

PR: **#43 — Build 013: verified ACRIS property timing intelligence**

Current old branch head: `c7b063f91b0c52c72604118f709b967bece38a55`.

Status: **open, unmerged; do not merge as-is**.

### Proven architecture

A full decades-long ACRIS-per-BBL crawl was rejected after scale diagnostics because it exceeded acceptable production latency and was sensitive to Socrata query planning/timeouts.

The replacement bounded strategy was proven at production scale:

- 365-day commercially relevant Master slice;
- exact document resolution into Legals;
- exact intersection with the 2,991 TowerSignal NYC BBL universe;
- Parties fetched only for matched tower-property documents;
- 296 BBLs with recent relevant ACRIS activity;
- 1,802 matched recent documents;
- 4,654 Party rows;
- 1,747,658-byte verified cache;
- 386 cooling-tower systems enriched across 296 matched BBLs;
- observed recent-activity prevalence 9.9%;
- deterministic sampled records independently reproduced from live Master, Legals and Parties.

### Current blocker

The latest required ACRIS cache workflow on PR #43 failed during `build-cache` because the Master metadata endpoint `https://data.cityofnewyork.us/api/views/bnx9-e6tj` timed out after five attempts. Normal repository CI passed; the required cache/integration gate did not.

Evidence therefore supports **upstream metadata-endpoint latency as the observed failure**, not rejection of the already-proven bounded-cache architecture.

### Reconciliation requirement

PR #43 was based on pre-commercial-redesign `main` and overlaps current commercial UI files including `App.tsx`, `Filters.tsx`, `SystemTable.tsx` and `main.tsx`. Do not resolve this by taking the old PR versions wholesale.

Required continuation:

1. branch from the current verified `dfec21e…` baseline;
2. selectively port the proven ACRIS backend/workflow/cache/types/detail components;
3. manually integrate ACRIS into the current Prospect/account workflow;
4. preserve Prospect / Monitor / Map / NYS Market / NYS Changes and current visual hierarchy;
5. diagnose the metadata endpoint separately, one hypothesis at a time;
6. merge only from an exact head with both normal CI and full ACRIS cache/integration green;
7. require normal Pages build/deploy/desktop+iPhone verification after merge.

ACRIS must remain outside Priority Score 1.0 and the NYC durable history store.

## 11. Current roadmap issues

The roadmap is now represented in GitHub issues rather than existing only in conversation history:

1. **#46 — Build 013: reconcile ACRIS with commercial UI and close production gate**
2. **#47 — Persistent prospect workflow: watchlists, account state, notes and digests**
3. **#48 — Opportunity Score 2.0: separate commercial ranking from regulatory evidence**
4. **#49 — Owner portfolio intelligence from exact PLUTO property context**
5. **#50 — Evaluate LL84 and additional data triggers by commercial lift**
6. **#51 — SaaS productization after workflow validation**

Target sequencing after Build 013:

`persistent workflow → separate Opportunity Score → portfolio intelligence → evidence-gated additional sources → SaaS infrastructure`

Additional sources should pass a commercial-lift test before implementation: does the source materially improve **who** to investigate/contact, **when** to act, or **why** the account is commercially valuable/timely?

## 12. Change-control rules for future work

Before changing production:

1. identify the exact verified/approved baseline relevant to the requested behavior;
2. compare current state against that baseline;
3. trace incorrect data through source → collection → processing → stored payload → client mapping → rendering → display before changing presentation;
4. test one hypothesis at a time on an isolated branch where practical;
5. keep experiments reversible and do not build on failed experiments;
6. do not relax source-health/history gates to make a build pass without evidence;
7. do not refactor unrelated working code during a targeted fix;
8. do not change approved/verified UI while fixing unrelated data or backend behavior;
9. merge only from an exact green head;
10. treat merge as distinct from deployment proof; require hosted verification for production claims.

## 13. What is not yet a finished commercial SaaS

TowerSignal currently has a strong technical/public-data intelligence foundation, but conventional SaaS infrastructure is intentionally deferred until the core workflow is proven useful. Not yet implemented as durable multi-user product capabilities:

- authentication;
- organizations/workspaces/users;
- server-side user state;
- durable cross-device saved accounts/watchlists;
- account notes/status/next-action;
- alert/digest delivery;
- CRM integration/handoff beyond exportable artifacts;
- subscriptions/billing;
- tenant authorization/isolation;
- customer support/admin tooling.

The next commercial-product challenge is therefore not simply adding more datasets. It is converting existing evidence and deterministic change intelligence into a repeatable prospecting/monitoring workflow.
