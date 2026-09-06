# TowerSignal Build 017 — Domestic Water / Provider Intelligence

Date: 2026-09-04

## Exact starting baseline

This increment starts from exact `main@142c53580d9619e7aac06295ba37aac21e3231a1`.

The current cooling-tower Priority Score 1.0, NYC/NYS production payloads, application UI, procurement evidence rules, ACRIS integration, workflow/RLS behavior and deployment paths are outside this increment and must remain unchanged.

## Objective

Build an independently verifiable domestic-water and provider-intelligence domain before exposing it in the product UI.

The first live source set is:

1. NYC DOHMH Self-Reported Drinking Water Tank Inspection Results (`gjm4-k24g`).
2. NYC DOHMH Drinking Water Tank Inspections and Audits Compliance Results (`rytv-g5ui`).
3. NYS DEC Currently Registered Pesticide Businesses and Agencies (`h8u2-6ejg`), restricted to Category `7g` / Cooling Towers.
4. NYS DEC Current Certified Pesticide Applicators (`c7db-kwpj`), restricted to Category `7g` / Cooling Towers.
5. NYC DEP Free Residential at-the-tap Lead and Copper Data (`k5us-nav4`).
6. NYC DEP Compliance at-the-tap Lead and Copper Data (`3wxk-qa8q`).
7. NYC DEP Lead Service Line Location Coordinates (`jqfp-uff7`) in a separate large-source cache with geometry deliberately excluded.

At discovery time, the DOHMH self-reported tank source contained 62,802 annual inspection rows. The DEC metadata showed 83 current 7G business-registration rows and 1,696 current 7G applicator certification rows. These are source observations, not fixed product constants; live workflows re-count the sources and fail closed on incomplete retrieval.

## Source-field correction: inspector firm

The NYC metadata descriptions for `inspection_by_firm` and `inspection_performed` are internally inconsistent with their actual values:

- `inspection_by_firm` contains company names (for example the source metadata's frequency statistics show Rosenwach Tank Co. LLC, ISSEKS BROS INC, American Pipe and Tank and others);
- `inspection_performed` contains `Y`/`N` flags.

TowerSignal therefore uses `inspection_by_firm` as the observed firm name, preserves `inspection_performed` as the source flag, and preserves the complete source row under `raw` for auditability. Numeric/placeholder values in the firm field are preserved but quarantined from canonical provider profiles.

## Evidence model

Provider relationships are explicit and must not be inferred from mere qualification:

- `CONFIRMED_ASSET`: a source row directly identifies the building/tank associated with an observed service;
- `OBSERVED_SERVICE`: an inspection/test/service event names the provider at the asset;
- `CONFIRMED_CONTRACT`: a contract/work order specifically identifies the facility/asset;
- `PORTFOLIO_CONTRACT`: a contract covers an agency/campus/portfolio but does not identify an individual asset;
- `QUALIFIED_PROVIDER`: a credential supports eligibility only, not an incumbent relationship;
- `VERIFY`: unresolved or ambiguous relationship requiring more evidence.

The first cache emits `OBSERVED_SERVICE` / `CONFIRMED_ASSET` for DOHMH tank-inspection firms and laboratories, and `QUALIFIED_PROVIDER` for DEC 7G businesses/applicators. It does not connect an applicator to a business unless a future authoritative source provides that relationship.

## Provider normalization

Raw names are always retained. Canonical comparison keys are deterministic and conservative:

- uppercase;
- normalize whitespace and punctuation;
- normalize `&` to `AND`;
- remove trailing legal suffixes only for the comparison key;
- preserve every observed raw alias and count;
- reject numeric/placeholder names from provider aggregation while retaining the raw source value;
- never fuzzy-merge different normalized names in this increment.

This safely collapses legal/punctuation variants such as `American Pipe & Tank` versus `AMERICAN PIPE AND TANK INC`, while leaving abbreviations such as `EBS` separate from `Environmental Building Solutions LLC` until stronger identity evidence exists.

## Provider metrics

The cache calculates source-observed:

- inspection count;
- unique building count;
- unique building/tank count;
- observed aliases;
- reporting years;
- first/latest observed inspection dates.

These are not represented as revenue, complete customer counts or definitive market share. Market-share calculations remain blocked until canonical company resolution and denominator definitions are validated.

## Property profiles

DOHMH tank records are keyed primarily by BIN, with derived BBL where borough/block/lot permit an exact deterministic BBL. Property profiles expose:

- observed tank count;
- inspection history count;
- observed provider/laboratory identities;
- latest observed provider/laboratory;
- compliance/audit activity count;
- violation count and latest violation date.

The two at-the-tap lead/copper sources expose borough/ZIP rather than a property identifier. They are retained as `ZIP_BOROUGH_ONLY` evidence with `UNLINKED` property confidence and are not force-matched to buildings.

## Lead service line cache

`jqfp-uff7` is approximately 857K rows and is deliberately isolated from the standard domestic-water JSON cache. The workflow:

- retrieves the current exact source count;
- verifies the required schema;
- pages deterministically by `objectid`;
- requests only `objectid,tbbl,address,material,record_ty,city_owned`;
- excludes geometry to avoid unnecessary payload volume;
- writes compressed NDJSON;
- requires written row count to exactly match source count;
- records unique BBL, material, record-type and city-owned counts;
- independently re-reads the compressed cache and verifies every row before accepting the artifact.

No Pages build depends on this large source in Build 017A.

## Fail-closed requirements

Every complete-source adapter:

- fetches authoritative metadata and verifies required fields;
- fetches the source count for the exact query scope;
- paginates deterministically;
- requires fetched rows to equal the expected count;
- records source dataset ID, retrieval timestamp and source-update timestamp;
- refuses to publish partial retrieval.

## Next source waves

After the first live source proof is green, additional adapters should be added independently rather than stacking unverified changes:

- recent NYC 311 DEP water/lead complaints from the official 311 source, with street-main/hydrant events separated from building-water complaints;
- HPD water/hot-water/plumbing violations via bounded server-side filtering rather than downloading the 11M-row full violation corpus;
- DOB domestic-water tank, pump, backflow, plumbing, filtration and mechanical work with exact BIN/BBL/contractor linkage;
- LL84 water consumption and meter fields for covered buildings;
- ELAP laboratory qualification and analyte scope after exact source/API verification;
- NYS public-water-system/facility/operator/water-quality/compliance/lead-inventory data after exact source/API verification;
- Open Book NY contract expansion;
- PASSPort awards/solicitations;
- the known NYCHA Checkbook procurement gap, using its separate release/line-item source contract.

## Acceptance boundary

Build 017A is data/backend only. It does not change application UI, navigation, styling, cooling-tower scoring, existing procurement classification or production relationship displays. The live cache artifacts are verification inputs only until their workflows and counts are reviewed.
