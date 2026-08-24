# TowerSignal

TowerSignal is a source-backed commercial timing and account-intelligence product for cooling-tower service providers. It turns public cooling-tower, regulatory, property, construction and contact records into an explainable workspace for finding, prioritizing, monitoring and investigating accounts.

## Live product

Live demo: `https://jeremyhennessy.github.io/TowerSignal/`

**Verified production baseline:** `dfec21e063c75f077b33879044113515d89e11ff` — August 24, 2026.

Production GitHub Pages run #33 (`32766611745`) passed the complete gated chain on this exact baseline:

- current NYC and NYS authoritative-source generation
- source-health and join-coverage validation
- deterministic NYC and NYS history generation
- independent source verification
- Python and frontend tests, lint, TypeScript and production build
- GitHub Pages deployment
- hosted desktop Chromium verification
- hosted iPhone/WebKit verification
- post-verification durable-history persistence

The canonical engineering/project state, build history, source contracts and roadmap are maintained in [`docs/project-state.md`](docs/project-state.md).

## Product workspace

The commercial interface is organized around user tasks rather than datasets:

- **Prospect** — search, filter and prioritize NYC cooling-tower accounts; save browser-local filter views; inspect source-backed account evidence; export the current account set.
- **Monitor** — review deterministic changes observed across preserved NYC public-record history.
- **Map** — explore the same filtered NYC opportunity set geographically.
- **NYS Market** — explore the separate New York State Cooling Tower Registry evidence regime without projecting NYC rules or Priority Score semantics onto NYS records.
- **NYS Changes** — review deterministic changes in the preserved NYS Equipment_ID history.

Account detail can include registration identity, sampling, NYC Health inspections, exact-matched OATH cases, PLUTO building/owner context, HPD registration contacts, DOB NOW project activity, historical profile and TowerSignal change history.

## Current authoritative sources

| Source | Dataset | Product use | Join / identity contract |
| --- | --- | --- | --- |
| NYC Cooling Tower Registrations | `y4fw-iqfr` | NYC system inventory, reported sample dates, equipment | exact `system_id` identity |
| NYC Cooling Tower System Inspection Results | `f9wb-g8mb` | NYC Health inspection/violation evidence | exact `system_id` |
| OATH Hearings Division Case Status | `jz4z-kudi` | case lifecycle and monetary context | exact NYC Health `summons_number` → OATH `ticket_number` |
| PLUTO | `64uk-42ks` | property/building/owner context | exact BBL |
| DOB NOW: Build – Job Application Filings | `w9ak-ipjd` | construction/mechanical/cooling-tower timing context | exact quoted BBL |
| HPD Multiple Dwelling Registrations | `tesw-yqqr` | qualifying-property registration context | exact BBL |
| HPD Registration Contacts | `feu5-w2e2` | public registered-contact context | exact HPD `registration_id` after exact-BBL registration match |
| NYS Cooling Tower Registry Weekly Extract | `24a4-muw7` | statewide equipment/status/compliance market intelligence | exact source `Equipment_ID`; conservative exact normalized address + city + ZIP property grouping |

No fuzzy address, owner, respondent, property or contact matching is used merely to increase coverage.

The most recently persisted source-health snapshot (2026-08-24T19:14:30Z) reports all eight current source models **HEALTHY**. Current coverage includes 4,894 NYC systems, 98.79% inspection-history coverage, 99.47% exact OATH ticket coverage, 96.29% exact PLUTO BBL coverage, 91.68% exact DOB NOW BBL coverage, 99.33% HPD-contact coverage among matched HPD registrations, and 6,236/6,236 NYS Equipment_ID records represented.

## Priority Score 1.0 — locked semantics

NYC Priority Score is a deterministic **commercial research-priority score**, not a health-risk score, regulatory-risk score, safety rating or probability of noncompliance. Evidence confidence is represented separately.

Model `1.0` currently assigns:

- **+40** confirmed recent violation
- **+10** additional points when a recent violation is described as critical or a public health hazard
- **+18** when there is no usable public sample date
- for a potential sampling-gap signal: **+20** at 32–45 days, **+25** at 46–60 days, or **+30** above 60 days since the latest usable public sample
- multiple active tower units: **+6** per unit above the first, capped at **+18**
- **+10** recent NYC Health regulatory activity
- total capped at **100**

The model version is defined in `scripts/towersignal/__init__.py`; implementation is in `scripts/towersignal/scoring.py`. New commercial opportunity-ranking work must be a separate, explicitly versioned model and must not silently modify Priority Score 1.0.

## Signal and evidence semantics

- **Confirmed recent violation** — sourced from an official NYC Health inspection record. Evidence confidence: `CONFIRMED`.
- **Potential sampling gap** — the latest publicly reported Legionella sample date is beyond the configured operating-period interval. TowerSignal cannot prove continuous operating status from the public record; this is a verification signal rather than a definitive noncompliance finding. Evidence confidence: `VERIFY`.
- **No public sample date** — no usable reported sample date is present in the current public registration record. Evidence confidence: `VERIFY`.
- **DOB activity** — exact-BBL construction/project context. A `Cooling tower mention` is used only when the published DOB job description explicitly names cooling-tower work. Mechanical/boiler flags remain broader property context.
- **PLUTO / HPD context** — public property or registration context only. It does not establish cooling-tower procurement responsibility or a service-provider relationship.
- **NYS status/compliance** — represented using the NYS source-native evidence regime. NYC Priority Score and NYC regulatory inference are not projected onto NYS equipment.

NYC Health rules are versioned in [`config/rules/nyc.json`](config/rules/nyc.json). Current rules version: `nyc-2026-05-08`.

## Historical intelligence

TowerSignal maintains deterministic durable observation history separately from the generated browser payloads.

- NYC durable history branch: `data/towersignal-history`
- NYC history hard ceiling: **25 MiB**
- current NYC snapshot: **22,323,020 bytes / 21.29 MiB**
- NYS history hard ceiling: **8 MiB**
- current NYS snapshot: **3,451,744 bytes / 3.29 MiB**
- first baselines and schema/enrichment recoveries are guarded against synthetic change events
- history is persisted only after the deployed site passes hosted verification

Current change intelligence includes core system/source transitions, OATH case lifecycle evidence, PLUTO/HPD context changes where supported, DOB NOW lifecycle events, and separate NYS Equipment_ID status/compliance/sample/operation changes.

## Architecture

```text
Authoritative NYC + NYS public sources
        ↓
Python 3.12 retrieval / validation / normalization
        ↓
Exact-key enrichment + source-health accounting
        ↓
Deterministic signals / Priority Score 1.0
        ↓
Deterministic NYC + NYS historical change engines
        ↓
Optimized static summary/detail JSON
        ↓
React + TypeScript + Vite
        ↓
GitHub Pages
        ↓
Hosted Chromium + iPhone/WebKit verification
        ↓
Persist verified history state
```

A failed authoritative-source retrieval, incomplete pagination, schema anomaly, join/attachment/display regression, history-size anomaly, test, build, deployment or hosted-browser verification prevents the new run from becoming the verified state. The application does not intentionally substitute fixture/mock production records after a source failure.

## Current development frontier

**Build 013 — ACRIS recent property transaction timing intelligence** is not merged. The intended architecture is a bounded 365-day, separately refreshed verified cache using exact joins:

`cooling-tower BBL → ACRIS Legals borough/block/lot → document_id → Master + Parties`

A full decades-long ACRIS crawl was rejected after scale diagnostics. The bounded architecture has passed production-volume proof, but the current Build 013 branch must be reconciled manually with the verified commercial UI and its final ACRIS cache/integration gate must be green before merge. ACRIS must remain outside Priority Score 1.0 and outside the near-limit NYC durable history snapshot.

Roadmap issues are tracked in GitHub, beginning with Build 013 reconciliation and persistent prospect/watchlist workflow. See [`docs/project-state.md`](docs/project-state.md).

## Local development and tests

Fixture-based development:

```bash
npm install
npm run lint
npm run typecheck
npm test
python -m unittest discover -s tests/python -p 'test_*.py' -v
npm run build
```

Current live-source generation requires network access:

```bash
python scripts/build_data.py --output public/data
python scripts/build_nys_data.py --output public/data
python scripts/build_source_health.py --output public/data
python scripts/verify_live_data.py --sample-size 5
python scripts/verify_live_nys.py --sample-size 5
npm run build
```

## Responsible use

TowerSignal provides commercial intelligence derived from public records. Signals are not legal advice, health advice or definitive determinations of regulatory compliance. Public records may be incomplete, delayed or scoped to specific property/regulatory regimes. Verify current operating, testing, maintenance, ownership/contact and compliance status before relying on a signal or contacting a property.
