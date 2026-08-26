# TowerSignal Build 015 — Product-wide redesign and end-state page map

Date: 2026-08-26

Baseline branch point: `25cfd58e40856a87e5e33de121b1842b3f65eabd`

Reference basis: user-supplied TowerSignal desktop mockups plus the August 2026 Complete Product Feature Catalogue & Data Source Inventory.

## Product rule

TowerSignal is a commercial account, timing, procurement, property and mechanical-intelligence product for the cooling-tower market. Product UI must answer, with explicit evidence where available:

- Who should we pursue?
- Why now?
- How valuable might the account be?
- What might the property need?
- Is somebody actively buying?
- Who can we contact?
- What changed?
- What should the salesperson do next?

Priority Score remains the deterministic **WHY NOW** timing model. Commercial enrichment must not silently alter that score.

## Global product architecture

Build 015 moves TowerSignal from a collection of modes in a left-side navigation shell to one consistent commercial-intelligence application shell:

- dark global top navigation
- compact global account/location search
- source-health status control
- login/private-workspace account control
- persistent page identity and actions
- dense light commercial workspaces
- shareable hash routes compatible with GitHub Pages
- full-page account/equipment profiles rather than transient drawer-only navigation

Public-source pages and account profiles are linkable. Private workflow state remains private to the signed-in user under the existing RLS model.

## Page and feature matrix

| Workspace | Build 015 | Current evidence used | End-state additions still required |
| --- | --- | --- | --- |
| Prospect | Redesigned | NYC registration, score/signals, sample timing, inspections, OATH, PLUTO match, DOB summary, HPD contacts, ACRIS summary | Opportunity Score, facility classes, richer mechanical/capital dimensions, portfolio filters |
| Monitor | Redesigned | Preserved NYC change events including sample, inspection/violation, OATH, HPD, PLUTO and DOB lifecycle events | procurement changes, LL84/87/97 changes, physical-inventory changes |
| Map | Redesigned | Current filtered NYC account set and source coordinates | Opportunity overlay, facility/procurement/mechanical overlays, portfolio concentrations |
| NYS Market | Reframed in new shell | NYS registry weekly extract, source-native status/compliance/sample/location | statewide commercial enrichment where authoritative sources support it |
| NYS Changes | Reframed in new shell | Preserved source-native NYS change history | additional authoritative NYS account/property enrichment |
| Opportunities | New first-class workspace | Current timing score, sample signals, HPD contact readiness, DOB activity, OATH, ACRIS | City Record solicitations, Checkbook NYC awards/spend/vendors; deterministic procurement linkage; Opportunity Score |
| Portfolios | New first-class workspace | PLUTO match readiness, HPD contact readiness, ACRIS timing, watched-account context | deterministic owner-group index built from PLUTO + HPD + ACRIS evidence with confidence labels |
| Workflow | New first-class workspace | Existing private saved views, watchlists, disposition, notes and next-action dates | organization/workspace membership, assignments, shared private notes/tasks, audit trail, role permissions |
| Source Health & Coverage | New first-class workspace | current source-health payload, coverage/freshness/count/status diagnostics | health entries for every future source and deterministic history of source-health regressions |
| NYC Account Profile | Full-page, deep-linkable | complete current detailed account payload and private workflow section | Opportunity Score, portfolio block, mechanical profile, procurement, sustainability/capital context, linked facility intelligence |
| NYS Equipment Profile | Full-page, deep-linkable | current source-native NYS equipment record | commercial enrichment only where evidence can be linked without projecting NYC rules |
| Login/Profile | Promoted to global shell | existing Neon authentication and user-private workflow state | organization/team workspace model and administrative controls |

## Shareability model

Build 015 uses GitHub-Pages-safe hash routes rather than adding a router dependency:

- `#/prospect`
- `#/monitor`
- `#/map`
- `#/nys`
- `#/nys-changes`
- `#/opportunities`
- `#/portfolios`
- `#/workflow`
- `#/source-health`
- `#/account/:systemId`
- `#/nys-account/:systemId`

Prospect and map links can carry current filter state. Account/equipment links carry stable source-derived TowerSignal IDs.

### What a shared link means

A public-source link shares the public evidence view. It does **not** disclose another user's private notes, disposition, watchlist membership or next-action state.

A future team-private sharing model requires an explicit workspace security model, not a URL-only change.

## Team-workspace end state

Do not retrofit team sharing by weakening the existing user-level RLS rules. The correct future implementation is a separate migration with at least:

1. `workspaces`
2. `workspace_members`
3. role/permission model (`owner`, `admin`, `member`, possibly `viewer`)
4. workspace-scoped watchlists
5. workspace-scoped account assignments
6. shared notes/tasks/comments with author and timestamps
7. activity/audit log
8. invitation and member-removal lifecycle
9. RLS policies that require active workspace membership
10. explicit separation of personal/private and shared workspace data

Only after that model is tested should TowerSignal offer “share with team” for private workflow content.

## Evidence and data-integrity guardrails

### Opportunities

Current production account payloads do not yet contain live City Record or Checkbook NYC opportunity objects. Build 015 therefore displays current timing opportunities and labels procurement as **ROADMAP DATA** rather than inserting illustrative bids into the live product.

### Portfolios

The detailed NYC account records contain PLUTO owner context, but the current summary payload does not emit an owner-group index. Build 015 does not fetch thousands of detail files in the browser or infer corporate parents from similar names. Until a deterministic portfolio index is generated, the page shows the gap and safe individual research candidates.

### Opportunity Score

No Opportunity Score formula is invented in Build 015. It remains separate from Priority Score and should be implemented only when its commercial inputs, weights, missing-data behavior, explanations and tests are defined.

### Responsible use

Public-source mismatches and gaps remain leads for verification, not legal/compliance conclusions. Historical permittees, contractors and recorded parties are context, not proof of a current service relationship.

## Recommended data implementation sequence after UI sign-off

1. Emit portfolio-ready owner/property fields into the normalized summary payload and build a confidence-labelled portfolio index.
2. Ingest City Record and Checkbook NYC into a normalized procurement model with exact identifiers and conservative property linkage.
3. Add facility intelligence and classification.
4. Add LL84, LL87 and LL97 commercial/mechanical/capital context.
5. Add planimetric cooling-tower reconciliation as a separate verification layer.
6. Define and test Opportunity Score 2.0 after the required inputs exist.
7. Build team workspaces as a dedicated authenticated database/security increment.

Each source/data increment should preserve Priority Score 1.0 unless a separately approved scoring-model version explicitly changes it.
