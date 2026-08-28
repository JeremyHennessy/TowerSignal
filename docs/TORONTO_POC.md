# TowerSignal Toronto — Public-Record POC

Status: **experimental / isolated**

Branch: `agent/toronto-poc-20260828`

Base commit: `145f13169300264de55f3f3a2e0e316cdd79a962`

This work is intentionally separate from the NYC/NYS production data paths. It does not alter `scripts/build_data.py`, `config/rules/nyc.json`, NYC Priority Score 1.0, the production UI, or the existing NYS product.

## Objective

Measure what Toronto cooling-water account intelligence can be recovered from real public records when no NYC-equivalent citywide cooling-tower registry is available.

The first extraction answers a narrow question:

> How many properties can be identified from explicit public-source cooling-tower text, and what current mechanical/renewal timing context can be retained without converting inference into fact?

This is a proof of data feasibility, not a coverage claim for the full Toronto cooling-tower market.

## Phase 1 sources

### City of Toronto building permits

- Active Permits CKAN datastore resource: `6d0229af-bc54-46de-9c2b-26759b01dd05`
- Cleared Permits CKAN datastore resource: `a96c0ba4-3026-402b-b09d-5b1268b8f810`
- Public source pages:
  - https://open.toronto.ca/dataset/building-permits-active-permits/
  - https://open.toronto.ca/dataset/building-permits-cleared-permits/

The POC queries both live datastores for cooling-water/mechanical terms and then independently checks the returned source text before retaining evidence.

### Toronto District School Board facility-condition / renewal pages

- TDSB school-list pages are used to discover current school numbers.
- Each discovered School FCI page is retrieved.
- A school is retained as a confirmed cooling-tower property only if its own public FCI/renewal text explicitly contains `cooling tower` or `cooling towers`.
- Related chiller, condenser-water, evaporative-condenser, and chemical-feed rows are retained only as separate equipment/mechanical context.

The extractor fails if fewer than 400 unique school IDs are discovered or if more than 10% of discovered FCI pages fail to retrieve. This prevents a partial crawl from being mistaken for a complete result.

## Evidence contract

### `CONFIRMED`

Reserved in Phase 1 for source text that explicitly says `cooling tower` or `cooling towers`.

A matching property receives:

`tower_status = CONFIRMED`

### `CONFIRMED_RELATED_EQUIPMENT`

Used for an explicit `evaporative condenser` reference. The equipment is real source-backed equipment, but TowerSignal does **not** relabel it as a cooling tower.

### `SUPPORTING`

Used for contextual mechanical references such as:

- chiller;
- condenser water;
- chemical feed.

Supporting evidence must never create a `CONFIRMED` cooling-tower property by itself.

### Absence

No matching public record means only:

`NO_TOWER_ASSERTION`

It does **not** mean that the property lacks a cooling tower.

## Commercial-signal separation

Equipment truth and sales timing are represented separately.

Examples:

- `ACTIVE_COOLING_TOWER_PERMIT`
- `COOLING_TOWER_PROJECT_HISTORY`
- `ACTIVE_MECHANICAL_PERMIT`
- `HISTORICAL_MECHANICAL_PROJECT`
- `TDSB_COOLING_TOWER_RENEWAL`
- `TDSB_RELATED_MECHANICAL_RENEWAL`

A commercial signal does not change equipment confidence.

## Generated files

A successful workflow writes only to the experiment branch under:

`data/toronto/poc/current/`

Files:

- `summary.json` — extraction counts, source retrieval metadata, query terms, evidence contract;
- `properties.json` — grouped property-level records;
- `properties.csv` — analyst-friendly property export;
- `evidence.json` — full retained evidence rows;
- `evidence.csv` — analyst-friendly evidence export.

The workflow uploads the same directory as a 30-day GitHub Actions artifact before committing the successful snapshot to the experiment branch.

## Fail-closed behavior

The extractor must fail rather than publish a misleading snapshot when:

- a required Toronto permit datastore query fails;
- the CKAN endpoint does not return a valid successful response;
- TDSB school discovery returns fewer than 400 unique schools;
- more than 10% of TDSB FCI pages fail to retrieve;
- duplicate evidence/property identifiers are generated;
- a property is labeled `CONFIRMED` without explicit cooling-tower evidence.

## What Phase 1 does not establish

This POC does not establish:

- total Toronto cooling-tower market size;
- absence of a cooling tower at unmatched properties;
- Legionella sample recency;
- Toronto cooling-tower compliance status;
- service-provider identity;
- current ownership unless the source explicitly provides it;
- market coverage percentage.

## Next source layers after Phase 1 is measured

If Phase 1 produces defensible signal density, the next isolated additions should be tested one at a time:

1. Ontario Environmental Compliance Approvals / Access Environment;
2. Construction Act / Certificate of Substantial Performance records;
3. public procurement and award records;
4. Toronto planning/application documents and mechanical plans;
5. institutional energy/capital plans;
6. RentSafeTO/property-manager context;
7. 2025 Toronto aerial imagery as a candidate-generation layer only.

No source should be promoted into the production product until its access/reuse terms, identity/join contract, extraction stability, and evidence semantics are independently verified.
