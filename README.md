# TowerSignal

TowerSignal is a source-backed commercial timing and account-intelligence product for cooling-tower service providers. It converts authoritative public records into transparent reasons to identify, prioritize, monitor and investigate cooling-tower accounts without presenting commercial signals as regulatory determinations.

## Live product

GitHub Pages: `https://jeremyhennessy.github.io/TowerSignal/`

The current commercial workspace provides five task-oriented modes:

- **Prospect** — filter and prioritize NYC cooling-tower accounts using current signals, source-backed property/contact context and recent activity.
- **Monitor** — review deterministic public-record changes preserved by TowerSignal history.
- **Map** — explore the same filtered NYC opportunity set geographically.
- **NYS Market** — explore the separate New York State Cooling Tower Registry evidence regime.
- **NYS Changes** — review preserved NYS equipment/status/compliance changes.

Current source-backed enrichment includes NYC registrations and inspections, OATH case lifecycle, PLUTO property context, HPD registered contacts, DOB NOW project activity and separate statewide NYS registry intelligence. Build 013 ACRIS property-timing intelligence remains unmerged pending reconciliation with the commercial UI and a green exact-head production gate.

See [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md) for the canonical current state and [`docs/BUILD_HISTORY.md`](docs/BUILD_HISTORY.md) for the build lineage.

## Current custody status

- Commercial redesign merge: `8d7911aab60b6521891398efc5a2957247218ceb` (PR #44).
- Responsive production correction: `a773dcbca9a7c038408f7f990a9c567db65be813` (PR #52).
- Hosted-test-only correction on verified `main`: `dfec21e063c75f077b33879044113515d89e11ff` (PR #54).
- **Approved UI code baseline:** `a773dcbca9a7c038408f7f990a9c567db65be813`.
- **Verified production descendant:** `dfec21e063c75f077b33879044113515d89e11ff`.
- **Approval checkpoint:** 2026-08-24 16:17 America/Moncton, after Pages run `32766611745` passed current NYC/NYS generation, source health, both history guards, independent NYC/NYS source verification, Python/frontend/build gates, Pages deployment, desktop Chromium, iPhone/WebKit and post-verification history persistence.
- **Approved visual/product state:** Prospect / Monitor / Map / NYS Market / NYS Changes commercial workspace, including the responsive corrections from PR #52. PR #54 changes hosted-test expectations only, so the approved UI code itself remains `a773dcb...`.
- Known deployment-infrastructure issue: repository Pages configuration is still legacy branch publishing (`main` `/`) even though TowerSignal uses a custom Actions Pages artifact workflow. See issue #53. This can temporarily expose raw repository source between a push and the custom artifact deployment.

Do not describe a merge, a CI pass or a successful deploy step alone as a verified production baseline. TowerSignal considers a release verified only after the hosted browser gate passes.

## Authoritative source inventory

### NYC product regime

| Source | Dataset | Join / identity contract | Role |
| --- | --- | --- | --- |
| NYC Cooling Tower Registrations | `y4fw-iqfr` | source `system_id` | current NYC system inventory and reported sample/equipment context |
| NYC Cooling Tower System Inspection Results | `f9wb-g8mb` | exact `system_id` | NYC Health inspection/violation evidence |
| OATH Hearings Division Case Status | `jz4z-kudi` | exact NYC Health `summons_number` → OATH `ticket_number` | OATH case lifecycle and penalty/payment context |
| Primary Land Use Tax Lot Output (PLUTO) | `64uk-42ks` | exact normalized BBL | public property/owner/building context |
| Multiple Dwelling Registrations | `tesw-yqqr` | exact normalized BBL | HPD registration context |
| Registration Contacts | `feu5-w2e2` | exact HPD `registration_id` after exact-BBL registration match | public HPD registered contacts |
| DOB NOW: Build – Job Application Filings | `w9ak-ipjd` | exact quoted BBL | property project/mechanical activity and explicit cooling-tower job-description context |

### NYS product regime

| Source | Dataset | Identity / grouping contract | Role |
| --- | --- | --- | --- |
| New York State Cooling Tower Registry Weekly Extract | `24a4-muw7` | exact source `Equipment_ID`; TowerSignal ID `NYS-<Equipment_ID>` | statewide source-native compliance/status/sample/operation intelligence |

NYS property grouping is conservative: normalized exact published street address + city + ZIP. Published county is preserved as provenance but is not treated as a reliable NYC discriminator. NYC Priority Score and NYC-specific evidence semantics are not projected onto NYS equipment.

### Build 013 candidate sources — not yet production

| ACRIS source | Dataset | Candidate join contract |
| --- | --- | --- |
| Real Property Legals | `8h5j-fqxa` | exact borough/block/lot → cooling-tower BBL |
| ACRIS Master | `bnx9-e6tj` | exact `document_id` |
| ACRIS Parties | `636b-3b5g` | exact `document_id` |

Build 013 intentionally uses a bounded recent/relevant ACRIS cache rather than a full historical crawl. Recorded parties are document parties only and must not be inferred to be the current owner, cooling-tower operator, procurement contact, service provider or vendor.

## Priority Score 1.0 — frozen semantics

NYC Priority Score is a deterministic **commercial research-priority** score, not a health-risk score, regulatory-risk score, safety rating or probability of noncompliance. Model version is `1.0`.

Current components are:

- +40 confirmed recent violation.
- +10 additional points when a recent violation type includes critical/public-health-hazard wording.
- +18 when no usable public sample date is available.
- Potential sampling-gap points: +20 when over 31 days, +25 when over 45 days, +30 when over 60 days since the latest public sample.
- Active equipment: +6 per active unit above one, capped at +18.
- +10 recent NYC Health regulatory activity.
- Total capped at 100.

The future Opportunity Score described in issue #48 must remain a separate commercial model. It must not silently alter Priority Score 1.0 or evidence confidence.

## Signal / regulatory boundaries

NYC rule configuration is versioned in `config/rules/nyc.json`; current rules version is `nyc-2026-05-08`.

- Legionella culture sampling is modeled with a maximum 31-day interval while the system is operating.
- A public sample-date gap is a **verification signal**, not proof of noncompliance, because TowerSignal does not establish continuous operating status from the public record.
- NYC Health BWSO government inspections are not represented as the owner's required 90-day qualified-person compliance inspections.
- Evidence confidence is kept separate from commercial priority.
- Public records may be incomplete, delayed or scope-limited. Users must verify current operating, testing, maintenance and compliance status before relying on a signal or contacting a property.

## Historical intelligence

TowerSignal maintains deterministic observation history only after successful production verification.

- NYC durable history: `data/towersignal-history`, schema 1.1, hard ceiling **25 MiB**.
- NYS durable history: separate `data/history/nys/*`, hard ceiling **8 MiB**.
- Initial baselines and source-repair baselines are designed not to manufacture synthetic events.
- DOB lifecycle state is compacted once per exact BBL rather than duplicated per cooling-tower system.
- ACRIS candidate state is intentionally excluded from NYC durable history.

## Production verification contract

`.github/workflows/pages.yml` runs on pushes to `main`, manual dispatch and a daily schedule. The intended release chain is:

1. Fetch/validate/generate current NYC data.
2. Fetch/validate/generate current NYS data.
3. Build and validate source-health coverage.
4. Build deterministic NYC and NYS history.
5. Enforce independent history-size/growth guards.
6. Independently re-query sampled NYC and NYS source evidence.
7. Run Python tests, ESLint, TypeScript, frontend regression tests and the Vite production build.
8. Upload and deploy the Pages artifact.
9. Verify the hosted product in desktop Chromium and iPhone/WebKit.
10. Persist the verified history only after hosted verification succeeds.

A failed authoritative-source retrieval, source-health gate, history guard, test, build or hosted browser check is a failed release. No fixture/demo dataset is substituted into production.

## Current roadmap

Tracked work is now represented in GitHub issues rather than only in conversation history:

- #46 — reconcile Build 013 ACRIS with the commercial UI and close its production gate.
- #47 — persistent prospect workflow: watchlists, account state, notes and digests.
- #48 — separate Opportunity Score 2.0.
- #49 — exact-source PLUTO owner portfolio intelligence.
- #50 — evaluate LL84/additional sources by commercial lift.
- #51 — SaaS productization after workflow validation.
- #53 — correct GitHub Pages publishing source to workflow-only deployment.

## Local development

```bash
python -m unittest discover -s tests/python -p 'test_*.py' -v
npm install
npm run dev
```

Current live-source product generation requires network access to the authoritative public sources. The production workflow is the release authority; local fixture success alone is not production verification.

## Responsible use

TowerSignal provides commercial intelligence derived from public records. It is not legal advice, health advice or a definitive determination of regulatory compliance. Public owner/contact/property fields are context from their named public source and do not by themselves establish cooling-tower procurement responsibility.