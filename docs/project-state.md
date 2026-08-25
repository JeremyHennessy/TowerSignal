# TowerSignal — Canonical Project State

Last reconstructed and verified: **2026-08-25**

This file is the engineering custody record for TowerSignal. Before a consequential production change, compare the intended change against this state and the current repository rather than reconstructing project history from memory or the nearest commit.

## 1. Current verified production baseline

| Item | Verified state |
| --- | --- |
| Repository | `JeremyHennessy/TowerSignal` |
| Default branch | `main` |
| Verified production baseline | `56fd31300d4d5f128c751e75f3607438073da0ab` |
| Verification date | 2026-08-25 |
| Build 013 ACRIS workflow | run #25 / `32845745013` — SUCCESS |
| Required-cache production Pages workflow | run #40 / `32848763862` — SUCCESS |
| Required verified ACRIS attachment | SUCCESS |
| NYC + NYS source/data/history gates | SUCCESS |
| GitHub Pages deployment | SUCCESS |
| Hosted desktop Chromium | SUCCESS |
| Hosted iPhone/WebKit | SUCCESS |
| Verified history persistence | SUCCESS |
| Live URL | `https://jeremyhennessy.github.io/TowerSignal/` |

`56fd31300d4d5f128c751e75f3607438073da0ab` is the current **verified product/production baseline**. The mandatory `require_acris=true` Pages run #40 proved that a verified ACRIS cache actually attached to the current TowerSignal BBL universe and then passed the full production chain through hosted desktop/iPhone verification and post-verification history persistence.

The commercial visual/layout regression lineage still originates from the verified redesign closeout at `dfec21e063c75f077b33879044113515d89e11ff`; subsequent Build 013 product work adds ACRIS timing intelligence inside the existing Prospect/account workflow and does not authorize an unrelated redesign.

This engineering verification does not substitute for a later explicit user visual approval. Any explicit user statement such as “approved”, “perfect”, “keep this”, or “don’t change this” must be recorded as a harder checkpoint for the behavior it approves.

### Baseline lineage

- `3f6e44e0a191e3f5d2aadd7deb7f3869a119ca58` — Build 012 NYS expansion baseline.
- `8d7911aab60b6521891398efc5a2957247218ceb` — PR #44 commercial account-intelligence redesign.
- `a773dcbca9a7c038408f7f990a9c567db65be813` — PR #52 narrow responsive closeout fixes.
- `dfec21e063c75f077b33879044113515d89e11ff` — PR #54 hosted Map-test alignment; commercial UI closeout baseline.
- `78650ad3a3c6b6752e99cdd03f4c8d869a4b9c02` — PR #59 Build 013 ACRIS implementation merge from exact green head `24938072fb17b0a121b80ef074868a20f4e8e9ec`.
- `a8cdc7b582de34c84641f2cdb208eb1fe1bf388b` — PR #63 test-only mobile fallback hosted-assertion correction.
- `bdb22a48a095e876766aa5a8bf94612cfb430721` — PR #67 test-only enriched ACRIS hosted-selector correction.
- `56fd31300d4d5f128c751e75f3607438073da0ab` — PR #64 Build 013.1 required-cache Pages dispatch fix; **current verified production baseline**.

### Build 013 production closeout evidence

The final acceptance chain is deliberately stronger than “merged”:

1. bounded ACRIS cache construction passed;
2. production-volume validation passed;
3. five deterministic cached documents were independently reproduced from live ACRIS Master, Legals and Parties;
4. verified cache artifact was persisted to `data/towersignal-acris`;
5. ACRIS workflow #25 successfully dispatched `pages.yml` with `require_acris=true`;
6. required-cache Pages #40 on exact `main@56fd3130…` passed cache attachment and cache-required assertion;
7. current NYC and NYS generation, source health, histories, history-size guards and independent source verification passed;
8. Python/frontend tests, lint, typecheck and production build passed;
9. Pages deployment passed;
10. hosted Chromium and iPhone/WebKit passed;
11. only after hosted verification did verified history persistence pass.

Build 013 issue #46 and Pages-source issue #53 are closed as completed.

### Historical closeout notes

During the earlier UI closeout, an unintended `docs/DO-NOT-COMMIT.txt` was briefly created on `main` in `ddbf1bfe1cd0942737f2ec451d093d270492e20e` and immediately deleted in `ea2083da53f07ccaaf7b189cfa00f1da3082ce8c`. No product file difference survived.

Stale pre-redesign ACRIS PR #43 was closed **unmerged**. Duplicate closeout PR #66 was also closed **unmerged** after the already-existing authoritative PR #64 was recovered. Do not use either as a restoration source.

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
| Commercial UI redesign | #44 | Prospect / Monitor / Map / NYS Market / NYS Changes commercial workspace; browser-local saved views; task-first hierarchy | Complete |
| UI live closeout | #52, #54 | responsive boundary fixes + production hosted-test alignment | Complete |
| Build 013 | #59, #63, #67, #64 | bounded verified ACRIS recent property-activity timing intelligence, commercial workspace integration, durable verified cache, required-cache production gate | **Complete / production verified** |

Disposable diagnostics are excluded from the product build sequence unless they established an architectural decision documented here.

## 4. Current source inventory and health

Latest persisted source-health snapshot: **2026-08-25T12:43:18.295145Z**.

All **nine** current source models are `HEALTHY`.

| Source key | Authoritative dataset | Current requested / represented context | Coverage | Health |
| --- | --- | --- | ---: | --- |
| registrations | NYC Cooling Tower Registrations `y4fw-iqfr` | 4,894 normalized NYC systems / 4,894 represented | 100.00% | HEALTHY |
| inspections | NYC Cooling Tower System Inspection Results `f9wb-g8mb` | 4,835 current systems with exact inspection history / 4,894 systems | 98.79% | HEALTHY |
| OATH | OATH Hearings Division Case Status `jz4z-kudi` | 54,746 exact summons/ticket matches / 55,036 requested | 99.47% | HEALTHY |
| PLUTO | PLUTO `64uk-42ks` | 2,866 exact BBL matches / 2,991 requested; 3,669 displayed systems | 95.82% | HEALTHY |
| DOB NOW | Job Application Filings `w9ak-ipjd` | 2,742 exact BBL matches / 2,991 requested; 3,535 displayed systems | 91.68% | HEALTHY |
| HPD registrations | Multiple Dwelling Registrations `tesw-yqqr` | 1,492 exact BBL matches / 2,991 requested | 49.88% | HEALTHY / scope-limited |
| HPD contacts | Registration Contacts `feu5-w2e2` | 1,482 matched registration BBLs with contact rows / 1,492 matched registrations | 99.33% | HEALTHY |
| NYS registry | Weekly Extract `24a4-muw7` | 6,236 unique `Equipment_ID` rows / 6,236 represented | 100.00% | HEALTHY |
| ACRIS recent | Master `bnx9-e6tj` + Legals `8h5j-fqxa` + Parties `636b-3b5g` | 296 exact tower BBLs with relevant 365-day activity / 2,991 requested; 386 displayed systems | 9.90% observed prevalence | HEALTHY |

Coverage percentage is source-contract specific. HPD registration coverage is scope-limited. ACRIS 9.9% is observed recent-activity prevalence, **not** a completeness target; no cached recent match is not evidence that no historical property transaction exists.

## 5. Exact identity / join contracts

These contracts are part of the evidence model. Do not replace them with fuzzy matching merely to increase coverage.

### NYC cooling-tower core

- current system identity: exact published `system_id`;
- inspections: exact `system_id` to current system;
- source registration deduplication is deterministic.

### OATH

`NYC Health summons_number → OATH ticket_number`

- exact identifier equality only;
- no respondent/address/BBL fuzzy fallback;
- OATH outcome/monetary context remains separate from Priority Score 1.0.

### PLUTO

`cooling-tower BBL → PLUTO BBL`

- exact normalized BBL only;
- integral Socrata numeric representations may be normalized without altering the identifier;
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

### ACRIS recent property activity

Exact chain:

`cooling-tower exact BBL → ACRIS Legals exact borough/block/lot BBL → exact document_id → ACRIS Master + Parties exact document_id`

Datasets:

- Legals `8h5j-fqxa`;
- Master `bnx9-e6tj`;
- Parties `636b-3b5g`.

Architecture and evidence boundaries:

- bounded 365-day commercially relevant Master slice;
- separately refreshed verified cache on `data/towersignal-acris`;
- current cache branch head at this reconstruction: `82d57a7b01fb9e6f3202f6a046c002414250b934`;
- Pages consumes the last verified cache rather than querying ACRIS live during ordinary deployment;
- ACRIS cache refresh independently re-verifies five deterministic cached documents against live Master, Legals and Parties before persistence;
- source metadata enrichment may record unavailable metadata explicitly, but hard resource data retrieval, exact joins and independent evidence verification remain fail-closed;
- no ACRIS party may be inferred to be the current owner, cooling-tower operator, procurement contact, service provider or vendor solely from a recorded document;
- ACRIS remains outside NYC durable history and outside Priority Score 1.0.

## 6. NYC Priority Score 1.0 — immutable current contract

Model constant: `PRIORITY_MODEL_VERSION = "1.0"`.

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

Rules version: `nyc-2026-05-08`.

Interpretation contract:

- Priority Score is a commercial research-priority score.
- It is not a health-risk score, regulatory-risk score, safety rating, compliance probability or legal conclusion.
- Evidence confidence is separate from score.
- DOB, PLUTO, HPD, OATH outcomes and ACRIS do not silently alter model 1.0.
- A future Opportunity Score must be a separate, explicitly versioned model.

## 7. Historical-state architecture and storage guardrails

Durable history branch: `data/towersignal-history`.

### NYC history

- compact durable observation representation introduced in Build 007;
- hard snapshot ceiling: **25 MiB / 26,214,400 bytes**;
- current `latest.json`: **22,321,255 bytes / ~21.29 MiB**;
- current ceiling utilization: **~85.15%**;
- current retained `events.json`: **498,803 bytes**;
- relative-growth anomaly guard remains active;
- DOB baseline is deduplicated by exact BBL at top level rather than duplicated per system;
- ACRIS is intentionally excluded from this near-limit history store.

### NYS history

- physically separate under `data/history/nys/`;
- hard snapshot ceiling: **8 MiB / 8,388,608 bytes**;
- current `latest.json`: **3,451,744 bytes / ~3.29 MiB**;
- current ceiling utilization: **~41.15%**;
- current `events.json`: **13 bytes** at this snapshot;
- routine source-relative counters such as `lastupdate` / `last_sampled_days` do not manufacture daily changes.

### Persistence invariant

The Pages pipeline stages history during build but persists it to `data/towersignal-history` **only after the deployed application passes hosted verification**. A failed hosted build must not advance the durable observation baseline.

## 8. Source-health invariant

Source health measures the full path:

`requested → retrieved → normalized → matched → attached → displayed/represented`

Key safeguards include:

- matched-but-not-attached regression detection;
- attached-but-not-represented regression detection;
- material relative coverage-collapse guards;
- persisted previous verified coverage for comparison;
- explicit scope notes where low absolute coverage is expected rather than anomalous;
- ACRIS cache freshness/availability represented explicitly.

A pipeline run is not successful merely because an upstream query returned rows.

## 9. Current UI / workflow contract

Current navigation:

1. **Prospect**
2. **Monitor**
3. **Map**
4. **NYS Market**
5. **NYS Changes**

Current commercial behaviors include:

- NYC prospect filtering by search, timing/evidence/contact/OATH/violation/geography/equipment/priority criteria;
- ACRIS recent-activity quick filter and explicit filter when a verified cache is available;
- commercial signal summary including recent ACRIS timing;
- account-priority table emphasizing timing/evidence/contact/activity context;
- detail slide-over retaining source-backed evidence, including ACRIS recorded property activity where exact matches exist;
- CSV export and copied source-backed lead brief;
- browser-local saved filter views under `towersignal.savedViews.v1`;
- same filtered NYC set shared between Prospect and Map;
- separate NYS source regime and NYS change view;
- compact source-health/provenance trust surfaces.

ACRIS is commercial timing/property-record context, not another raw-data workspace and not a new regulatory score.

### Known workflow limitation

Saved views are currently `localStorage` only. There is no durable cross-device watchlist, account disposition, note, next-action or alert/digest system. This is the next product-depth frontier, but it must not start before repository governance issue #65 is complete.

## 10. Build 013 — CLOSED

GitHub issue: **#46 — completed**.

Implementation/closeout lineage:

- PR #59 — reconciled bounded ACRIS implementation into the commercial Prospect/Monitor/Map architecture; merged exact green head `24938072fb17b0a121b80ef074868a20f4e8e9ec`;
- PR #63 — test-only mobile fallback hosted assertion alignment;
- PR #67 — test-only enriched ACRIS hosted selector scoping;
- PR #64 — explicit repository context for post-cache `require_acris=true` Pages dispatch;
- PR #43 — stale pre-redesign implementation branch, closed unmerged;
- PR #66 — duplicate dispatch closeout branch, closed unmerged.

Production envelope repeatedly reproduced:

- 2,991 TowerSignal cooling-tower BBLs requested;
- 296 BBLs with relevant recent ACRIS activity;
- 1,802 matched recent documents;
- 4,654 Party rows;
- approximately 1.75 MB verified cache;
- 386 cooling-tower systems displaying exact-BBL recent ACRIS context;
- observed recent-activity prevalence 9.9%;
- five deterministic sampled documents independently reproduced against all three authoritative ACRIS datasets.

The bounded strategy replaced an impractical decades-long per-BBL crawl after diagnostics showed unacceptable latency/query-planning sensitivity. Do not revert to the rejected full-history architecture without new evidence.

## 11. Current roadmap and hard start gates

Completed closeout/governance prerequisites:

- **#46 — Build 013 ACRIS production closeout — COMPLETE**;
- **#53 — GitHub Pages publishing source switched to GitHub Actions — COMPLETE**.

Next hard prerequisite:

- **#65 — Harden `main` branch protection after Build 013 closeout — OPEN**.

Current GitHub branch metadata at this reconstruction reports `main` as **not protected**. Build 014 must not start until #65 is enabled and verified.

After #65:

1. **#47 — Build 014: persistent prospect workflow** — durable watchlists/saved accounts, saved views, disposition, notes, next-action dates, source-backed watched-account activity feed, then digest/handoff;
2. **#48 — Opportunity Score 2.0** — a separate commercial-ranking model, never a silent Priority Score rewrite;
3. **#49 — owner portfolio intelligence** from exact PLUTO property context;
4. **#50 — evaluate LL84/additional triggers** by commercial lift rather than source count;
5. **#51 — broader SaaS productization** only after repeatable workflow value is proven.

Target sequencing:

`branch protection → persistent workflow → separate Opportunity Score → portfolio intelligence → evidence-gated sources → SaaS infrastructure`

Additional data sources should pass a commercial-lift test: does the source materially improve **who** to investigate/contact, **when** to act, or **why** the account is commercially valuable/timely?

## 12. Branch-protection contract for #65

Required before Build 014:

1. changes to `main` go through pull requests;
2. standard repository CI is a required merge check;
3. accidental direct pushes to production are blocked while preserving a deliberate owner/admin recovery path;
4. require branches to be up to date only if it does not create unnecessary merge churn;
5. verify the rule is actually active after configuration.

Do **not** blindly require the current path-filtered ACRIS workflow as a branch-protection check. Unrelated PRs may not emit it. If ACRIS later becomes repository-required, first create an always-reporting gate that returns `PASS` or `NOT_REQUIRED` deterministically.

## 13. Change-control rules for future work

Before changing production:

1. identify the exact verified/approved baseline relevant to the requested behavior;
2. compare current state against that baseline;
3. trace incorrect data through source → collection → processing → stored payload → client mapping → rendering → display before changing presentation;
4. test one hypothesis at a time on an isolated branch where practical;
5. keep experiments reversible and do not build on failed experiments;
6. do not relax source-health/history gates merely to make a build pass;
7. do not refactor unrelated working code during a targeted fix;
8. do not change approved/verified UI while fixing unrelated data or backend behavior;
9. merge only from an exact green head;
10. treat merge as distinct from deployment proof; require hosted verification for production claims.

## 14. What is not yet a finished commercial SaaS

TowerSignal has a strong public-data intelligence foundation but intentionally defers conventional SaaS infrastructure until the core workflow is proven useful. Not yet implemented as durable multi-user product capabilities:

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

The next commercial-product challenge is not simply adding more datasets. It is converting the existing source-backed evidence, ACRIS timing context and deterministic change intelligence into a repeatable prospecting/monitoring workflow.