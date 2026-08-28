# TowerSignal Toronto Market Build

Status: experimental, isolated from production.

Preserved Toronto POC baseline: `a3c5d16e093b0df0914de953452c46ed7ef15f43` on `agent/toronto-poc-20260828`.

Continuation branch: `agent/toronto-market-20260828`.

## Hard contracts

1. **Canonical property identity is the City of Toronto Address Points `GEO_ID`.** TowerSignal represents it as `toronto-geoid:<GEO_ID>`.
2. Address reconciliation is deterministic canonical street-address equality only. Fuzzy matching is disabled. Ambiguous or missing exact matches remain unresolved.
3. Existing cooling-tower semantics are unchanged. Identity, planning, health, relationship and aerial layers do not silently create or upgrade a confirmed cooling-tower property.
4. AIC document text mentioning a cooling tower is retained as an evidence candidate. Promotion into the core confirmation contract requires a separate reviewed change.
5. Aerial analysis is a weak-label research layer. Documentary confirmed properties are not assumed to be pixel-confirmed current towers, and supporting-only properties are not true negatives.
6. No true Toronto market-coverage percentage is emitted until a defensible tower-population denominator exists.

## Pipeline

### Core identity and official-source layer

`scripts/toronto_market_core.py core`

The core stage:

- pulls the current City of Toronto Address Points WGS84 source and makes `GEO_ID` the property key;
- reconciles the original 177 POC properties where exact City identity can be established;
- expands the candidate property universe from deterministic property addresses present in open/licensed Toronto and Ontario sources;
- pulls the official Toronto AIC application catalogue;
- adds the Toronto Highrise Residential Health Hazards open dataset;
- joins historical ChemTRAC, Ontario EWRB, Ontario Environmental Compliance Reports, health records and AIC applications to the GeoID spine only when a deterministic property address exists;
- records the Construction Act publisher reuse boundary.

Outputs include:

- `property_spine.json`
- `reconciliation_summary.json`
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
- energy studies/reports
- planning reports
- noise/acoustic studies
- equipment plans/schedules

Signals include cooling tower, evaporative condenser, chiller, condenser water, water treatment and Legionella terminology. Labelled owner/manager/engineer/consultant/contractor names are retained only as review-required relationship candidates.

Raw AIC PDFs are not committed to Git. This pass does not OCR scanned/image-only PDFs; the OCR gap is measured explicitly.

### Construction Act certificates and notices

All three websites designated by Ontario's current Construction Act regulation are `PERMISSION_REQUIRED` for automated TowerSignal ingestion under their publisher terms:

- Daily Commercial News / ConstructConnect
- Link2Build
- Ontario Construction News

The legal obligation to publish a certificate does not itself grant TowerSignal a commercial bulk-reuse licence to the publisher's database/site content. No scraping adapter is enabled without written permission, an API agreement, licensed feed or another source with compatible reuse rights.

The entity schema is ready for licensed owner, contractor, payment-certifier and subcontractor fields without redesign.

### Relationship graph

`scripts/toronto_market_core.py finalize`

The graph preserves source roles rather than collapsing every named organization into an owner:

- explicit RentSafe property-management company → `PROPERTY_MANAGER_OF`
- exact-address TOBids successful supplier → `CONTRACTOR_AT_PROPERTY`
- BPS organization → `FACILITY_OPERATOR_OR_REPORTER_AT`
- AIC extracted labelled roles → candidate owner/manager/engineer/architect/consultant/contractor relationships requiring review

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

- original POC GeoID reconciliation rate;
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

This build does not modify the production NYC interface, production scoring, or approved UI. It runs only on `agent/toronto-market-20260828` until separately reviewed and authorized.
