# Build 018 — Property Enforcement and Legionella Intelligence

## Status

This work is isolated on `agent/property-enforcement-ingest-20260915`, created from verified `main` commit `a015a2702e37d85525f8aeb2ef4f63d79e5dfa4c`.

The branch adds source adapters, cache builders, validators, exact-key attachment logic, tests, and a read-only live source proof. It intentionally does **not** change production scoring, UI layout, or the production Azure Blob refresh workflow yet.

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

The alert collector monitors official channels rather than relying on one page:

1. NYC Health — Legionnaires' Disease health topic
2. NYC Health — provider Legionnaires' Disease and Legionellosis guidance
3. NYC Health — Health Alert Network
4. NYC Health — recent press releases
5. NYC Health — Cooling Tower Registration and Maintenance
6. NYC Mayor's Office — news index
7. NYSDOH — Legionnaires' disease topic
8. NYSDOH — cooling-tower requirements
9. NYSDOH — Protection Against Legionella regulatory hub

The collector also follows relevant official child links whose link text or URL contains `Legionnaires`, `Legionella`, `legionellosis`, or `cooling tower`. High-value current NYC Health cluster response pages are explicit seeds so a lagging index cannot hide a newly published response page.

Each snapshot stores source URL, agency, channel, retrieved timestamp, content length and SHA-256 digest. Per-item retrieval failures are preserved as failures rather than interpreted as zero alerts.

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
- evidence semantics

This alert cache remains a global/public-health feed in this build; there is no unsupported property-level join.

## Validation and release sequence

Before production integration:

1. Run normalization/unit tests.
2. Run the read-only GitHub Actions source proof against current authoritative source contracts.
3. Inspect live source counts and any retrieval errors.
4. Build a complete current TowerSignal NYC `systems.json`.
5. Run:

```text
python scripts/build_property_enforcement_cache.py --systems public/data/systems.json --output public/data/property-enforcement.json
python scripts/validate_property_enforcement_cache.py --cache public/data/property-enforcement.json --max-age-days 1 --require-production-universe
python scripts/attach_property_enforcement.py --output public/data --cache public/data/property-enforcement.json
python scripts/build_legionella_alert_cache.py --output public/data/legionella-alerts.json
python scripts/validate_legionella_alert_cache.py --cache public/data/legionella-alerts.json --max-age-days 1
```

6. Verify the generated contract, exact-key attachment counts, source freshness and browser data transport.
7. Only after that proof is green should the same build/validate/attach sequence be added to `.github/workflows/azure-data-refresh.yml`.
8. Scoring and UI treatment remain separate decisions. Neither should change merely because these datasets are available.

## Non-goals of this branch

- no Priority Score modification
- no UI redesign or layout changes
- no fuzzy/address/ZIP joins
- no claim that complaint disposition rows are a complete DOB SWO event-history source
- no claim that FISP is a generic Labor Law filing dataset
- no production workflow mutation before live source proof
