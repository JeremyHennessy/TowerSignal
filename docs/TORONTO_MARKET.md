# TowerSignal Toronto Market Build

Status: experimental, isolated from production.

Preserved Toronto POC baseline: `a3c5d16e093b0df0914de953452c46ed7ef15f43` on `agent/toronto-poc-20260828`.

Continuation branch: `agent/toronto-market-20260828`.

## Hard contracts

1. **Canonical civic-address identity is the City of Toronto One Address Repository `ADDRESS_POINT_ID`.** TowerSignal represents it as `toronto-address-point:<ADDRESS_POINT_ID>`.
2. Historical Toronto Building Permit `GEO_ID` values were directly compared with the current Address Points source and correspond to `ADDRESS_POINT_ID` where that historical identifier is still represented. They are retained as legacy provenance/backward-mapping values, not mislabeled as a current `GEO_ID` field.
3. `ADDRESS_ID`, `ADDRESS_STRING_ID`, `CENTRELINE_ID`, `ADDRESS_POINT_ID_LINK`, and `ADDRESS_ID_LINK` are retained as municipal identity/provenance attributes. Link fields are not assumed to mean parcel ownership or a parent property unless the City explicitly defines that semantics.
4. Address reconciliation is deterministic. Fuzzy matching is disabled. Ambiguous or missing exact matches remain unresolved.
5. Existing cooling-tower semantics are unchanged. Identity, planning, health, relationship and aerial layers do not silently create or upgrade a confirmed cooling-tower property.
6. AIC document text mentioning a cooling tower is retained as an evidence candidate. Promotion into the core confirmation contract requires a separately reviewed evidence decision.
7. Aerial analysis is a weak-label research layer. Documentary confirmed properties are not assumed to be pixel-confirmed current towers, and supporting-only properties are not true negatives.
8. No true Toronto cooling-tower market-coverage percentage is emitted until a defensible tower-population denominator exists.

## Municipal identity contract

Toronto's current Address Point schema exposes `ADDRESS_POINT_ID`, `ADDRESS_ID`, `ADDRESS_STRING_ID`, `CENTRELINE_ID`, civic-address text, coordinates, status/effective dates, and optional link fields. The current public Address Points file does not expose a `GEO_ID`-named field.

For TowerSignal Toronto:

- canonical property/address key: `toronto-address-point:<ADDRESS_POINT_ID>`;
- `ADDRESS_POINT_ID`: canonical civic-address identifier for this phase;
- `ADDRESS_ID`: retained related municipal address identifier;
- `ADDRESS_POINT_ID_LINK` / `ADDRESS_ID_LINK`: retained City-provided link relationships without inventing parent/ownership semantics;
- Building Permit `GEO_ID`: retained in `legacy_geo_ids` where present;
- exact civic-address reconciliation: allowed when it produces one unique current Address Point;
- ambiguous exact addresses: unresolved;
- fuzzy matching: prohibited.

The pipeline writes `identity_contract.json` and a 177-record `reconciliation_details.json` ledger so every original POC property receives an explicit resolution status.

## Pipeline

### Core identity and official-source layer

`scripts/toronto_market_core.py core`

followed by:

`scripts/toronto_identity_normalize.py`

The core and identity-normalization stages:

- pull the current City of Toronto Address Points WGS84 source;
- reconcile every original 177 POC record with an explicit status;
- normalize canonical IDs to `toronto-address-point:<ADDRESS_POINT_ID>`;
- retain legacy permit GeoIDs and City address/link identifiers;
- expand the candidate property universe from deterministic property addresses present in open/licensed Toronto and Ontario sources;
- pull the official Toronto AIC application catalogue;
- add the Toronto Highrise Residential Health Hazards open dataset;
- join historical ChemTRAC, Ontario EWRB, Ontario Environmental Compliance Reports, health records and AIC applications only when a deterministic property address exists;
- record the Construction Act publisher reuse boundary.

Outputs include:

- `property_spine.json`
- `identity_contract.json`
- `reconciliation_summary.json`
- `reconciliation_details.json`
- `property_source_links.json`
- `open_licensed/toronto_aic_applications.json`
- `open_licensed/toronto_highrise_residential_health_hazards.json`
- `construction_act_source_policy.json`

If a source does not expose a defensible property address, the limitation is recorded; organization names or proximity are not used to manufacture an identity join.

### AIC supporting-document corpus

`scripts/toronto_aic_corpus.py`

The full application catalogue is sharded across workers. Each shard visits the official AIC application page, discovers City-hosted supporting-document links, downloads PDF content to memory, extracts text, hashes the document and classifies relevant material.

Target classes:

- mechanical drawings
- mechanical schedules
- equipment plans/schedules
- energy studies/reports/models
- planning reports
- noise/acoustic studies
- HVAC/servicing reports

Signals include cooling tower, cooling towers, evaporative condenser, evaporative cooling, condenser water, cooling water, chiller, cooling plant, central plant, mechanical penthouse, water treatment, Legionella, tower replacement/installation, Marley, Baltimore Aircoil/BAC, Evapco and related terminology.

Raw AIC PDFs are not committed to Git. Image-only/scanned PDFs remain an explicit OCR gap unless an OCR phase is separately executed and validated.

### Construction Act certificates and notices

Current policy is conservative: Daily Commercial News / ConstructConnect, Link2Build and Ontario Construction News are `PERMISSION_REQUIRED` for automated TowerSignal ingestion unless a compatible API/licence/feed is established.

The legal obligation to publish a certificate does not itself grant TowerSignal a commercial bulk-reuse licence to the publisher's database/site content. This does not block the rest of the Toronto build.

The entity schema is ready for licensed owner, contractor, payment-certifier and subcontractor fields without redesign.

### Relationship graph

`scripts/toronto_market_core.py finalize`

The graph preserves source roles rather than collapsing every named organization into an owner:

- explicit RentSafe property-management company → `PROPERTY_MANAGER_OF`;
- exact-address TOBids successful supplier → `CONTRACTOR_AT_PROPERTY`;
- BPS organization → `FACILITY_OPERATOR_OR_REPORTER_AT`;
- AIC extracted labelled roles → review-required owner/manager/engineer/architect/consultant/contractor candidates.

Construction Act edges remain absent until permitted source data is available.

### Targeted 2025 aerial analysis

`scripts/toronto_aerial_detector.py`

The aerial stage uses the City of Toronto 2025 8 cm imagery export service. It builds a deterministic weak-label visual-similarity model from reconciled documentary-confirmed properties and original POC properties without tower confirmation as weak controls.

Outputs:

- `aerial_model_report.json`
- `aerial_candidates.json`

Top candidate crops and confirmed-property reference crops are artifact-only. Model scores are a review queue, not cooling-tower evidence and never change tower confirmation.

### Coverage

The final stage writes `coverage_report.json`, separating:

- original POC Address Point reconciliation;
- expanded canonical candidate-property count;
- deterministic property-link coverage by source family;
- AIC application/document scan coverage and OCR gap;
- aerial screening coverage;
- source-backed relationship-role coverage;
- known documentary confirmed cooling-tower properties.

`true_cooling_tower_market_coverage.coverage_percent` remains `null` with `UNKNOWN_DENOMINATOR` unless a validated Toronto cooling-tower denominator is established.

## Rights and persistence boundaries

Open/licensed City and Ontario datasets can be persisted subject to their source licences.

Third-party Construction Act publisher content is not scraped into TowerSignal without compatible permission.

Raw AIC PDFs and aerial crops are processed as ephemeral/review artifacts and removed before public Git persistence.

## Production boundary

This build does not modify the production NYC/NYS interface, scoring or approved UI. It runs only on `agent/toronto-market-20260828` until separately reviewed and authorized.
