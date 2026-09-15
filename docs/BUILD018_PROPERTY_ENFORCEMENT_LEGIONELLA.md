# Build 018 — Property Enforcement and Legionella Intelligence

## Status

This work is isolated on `agent/property-enforcement-ingest-20260915`, created from verified `main` commit `a015a2702e37d85525f8aeb2ef4f63d79e5dfa4c` and tracked in draft PR #243.

`main` subsequently advanced to `ca2d272130ffff34095a0760bc7862e115c06815` through a hosted Account UI acceptance-test change. That delta does not touch the property-enforcement, public-health source, scoring, or generated-data surfaces introduced here; it still must be reconciled through the normal exact-head release process before merge.

The branch adds source adapters, cache builders, validators, exact-key attachment logic, alert-history retention, tests, and read-only live source proofs. It intentionally does **not** change production scoring or UI layout. The production Azure Blob refresh workflow remains unchanged until full-universe coverage proof is complete.

## Property enforcement sources

### HPD Housing Maintenance Code Violations

- NYC Open Data dataset: `wvxf-dwi5`
- Agency: NYC Department of Housing Preservation and Development
- Join: canonical 10-digit BBL only
- Retained fields include violation ID, class, inspection date, NOV text/date, current status, published violation status, rent-impairing flag, BIN and BBL.
- Open/closed state is derived only from the source `violationstatus` field. TowerSignal does not infer closure from narrative or workflow status text.

### DOB Stop Work Order evidence

- NYC Open Data dataset: `eabe-havv` (`DOB Complaints Received`)
- Agency: NYC Department of Buildings
- Join: BIN only
- The adapter restricts the source to official DOB complaint disposition codes related to Stop Work Orders:
  - `A3` full SWO served
  - `K4` cranes/derricks SWO without associated address
  - `K6` letter of deficiency with partial SWO
  - `L1` partial SWO
  - `L2` SWO fully rescinded
  - `L3` SWO partially rescinded
  - `U4` CSC full SWO issued
  - `U5` CSC partial SWO issued
  - `V3` SWO violation served
- Evidence boundary: this dataset exposes complaint disposition records. It is useful SWO evidence but is **not represented as a reconstructed complete stop-work-order history ledger**. Current active/rescinded state must not be inferred beyond what the published disposition evidence supports.

### DOB NOW Safety — Facades Compliance Filings

- NYC Open Data dataset: `xubg-57si`
- Agency: NYC Department of Buildings
- Program: Facade Inspection and Safety Program / Local Law 11
- Join: BIN only
- Retained fields include control/TR6 identifiers, filing type, cycle, submission date, current status, QEWI, QEWI business, and property identity.
- Published compliance values such as `SAFE`, `SWARMP`, `UNSAFE`, and `No Report Filed` are preserved without reinterpretation.

This implements the confirmed **Local Law 11 / FISP** filing source. It should not be described as a general New York State Labor Law filing feed. If a separate literal Labor Law dataset is required, it remains a separate sourcing workstream.

## Legionella / Legionnaires public-health sources

The collector currently monitors twelve official channels:

1. NYC Health — Legionnaires' Disease health topic
2. NYC Health — provider Legionnaires' Disease and Legionellosis guidance
3. NYC Health — Health Alert Network
4. NYC Health — recent press releases
5. NYC Health — Cooling Tower Registration and Maintenance
6. NYC Mayor's Office — news index
7. Notify NYC / NYC Emergency Management — live Recent Notifications
8. NYC311 — Legionnaires' Disease
9. NYC311 — Cooling Tower Complaint
10. NYSDOH — Legionnaires' disease topic
11. NYSDOH — cooling-tower requirements
12. NYSDOH — Protection Against Legionella regulatory hub

The collector follows relevant official child links only when they explicitly reference `Legionnaires`, `Legionella`, or `legionellosis`. This prevents generic cooling-tower forms/templates from being misclassified as outbreak news. High-value current NYC Health cluster-response pages are explicit seeds so a lagging index cannot hide a newly published response page.

Each source snapshot stores URL, agency, channel, retrieved timestamp, content length and SHA-256 digest. Per-item retrieval failures are preserved as failures rather than interpreted as zero alerts.

### Notify NYC transport and retention

The historically documented Notify NYC RSS endpoint (`/RSS/NotifyNYC?lang=en`) was tested in the live GitHub Actions environment. It returned HTTP 200 with an empty body and therefore is **not** treated as a usable feed.

TowerSignal instead parses individual notification records from the live Notify NYC Recent Notifications page. That page is intentionally short-lived and only exposes a small recent window. The cache builder therefore supports `--previous-cache` and retains prior verified records by stable `item_id`; current observations replace prior versions with the same identity. This is required so a Legionnaires alert does not disappear from TowerSignal when it rolls off the live Notify NYC page.

A durable production polling/persistence workflow is still required to make this retention effective across runs. Until that workflow is activated, `previous_cache_available: false` accurately means the current build is a fresh snapshot rather than a complete Notify NYC history.

### Property matching boundary

A public-health alert is **not** attached to a TowerSignal property merely because the property shares a ZIP code or neighborhood with an outbreak. Property attribution requires an explicit published building/tower identity and a separate deterministic resolver. No geographic/fuzzy attachment is included in this build.

## Generated contracts

### `property-enforcement.json`

Domain: `NYC_PROPERTY_ENFORCEMENT_CONTEXT`

- `by_bbl`: HPD violation evidence
- `by_bin`: DOB SWO disposition evidence and FISP facade filings
- source metadata and coverage counts
- evidence semantics and exact-key match boundaries

After validation, `attach_property_enforcement.py` can add compact summary columns to `systems.json` and full evidence to each system detail record under `property_enforcement_context`.

### `legionella-alerts.json`

Domain: `LEGIONELLA_PUBLIC_HEALTH_ALERTS`

- required official source-channel snapshots
- discovered relevant official items
- retrieval errors
- deterministic content hashes
- `history_merge` accounting for prior/current/new/retained records
- evidence semantics

This alert cache remains a global/public-health feed in this build; there is no unsupported property-level join.

## Verified live source proof

The read-only source proof has successfully exercised the authoritative source contracts against live data.

Observed in the clean proof on September 15, 2026:

- HPD Housing Maintenance Code Violations: `11,236,606` source rows at proof time; exact-BBL seed query returned records.
- DOB Complaints Received: `3,131,800` source rows at proof time; SWO-related exact-BIN seed query returned records.
- DOB NOW Safety Facades Compliance Filings: `87,162` source rows at proof time; exact-BIN seed query returned records.
- Legionella/public-health collection: `12` required official channels, `98` relevant official items in the current collection, `0` retrieval errors.

These source counts are observations from that proof run, not hard-coded expected totals and may change as agencies update their datasets.

The source-proof gate now requires `--require-clean-retrieval`; a broken required source or unresolved child retrieval is not accepted as an empty source.

## Validation and release sequence

Before production integration:

1. Run normalization/unit/history tests.
2. Run the read-only GitHub Actions source proof against current authoritative source contracts and require zero retrieval errors.
3. Build a complete current TowerSignal NYC `systems.json` without publishing it.
4. Build and validate `property-enforcement.json` against that full production-scale universe and inspect exact attachment counts.
5. Run the attachment logic against the generated temp data and verify the resulting contract.
6. Design the production cadence separately:
   - HPD/SWO/FISP can ride the existing daily Azure data refresh.
   - Notify NYC/public-health alerts need a more frequent collector plus durable previous-cache persistence.
7. Only after those proofs are green should production Azure workflows be changed.
8. Scoring and UI treatment remain separate decisions. Neither changes merely because these datasets are available.

Representative commands:

```text
python scripts/build_property_enforcement_cache.py --systems public/data/systems.json --output public/data/property-enforcement.json
python scripts/validate_property_enforcement_cache.py --cache public/data/property-enforcement.json --max-age-days 1 --require-production-universe
python scripts/attach_property_enforcement.py --output public/data --cache public/data/property-enforcement.json
python scripts/build_legionella_alert_cache.py --output public/data/legionella-alerts.json --previous-cache <prior-cache-if-available>
python scripts/validate_legionella_alert_cache.py --cache public/data/legionella-alerts.json --max-age-days 1 --require-clean-retrieval
```

## Non-goals of this branch

- no Priority Score modification
- no UI redesign or layout changes
- no fuzzy/address/ZIP outbreak-to-property joins
- no claim that complaint disposition rows are a complete DOB SWO event-history source
- no claim that FISP is a generic Labor Law filing dataset
- no production workflow mutation before full-universe and persistence proofs
