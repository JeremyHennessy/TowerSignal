# Build 016H — Procurement Coverage and Identity Diagnostic

Status: evidence-only diagnostic. No production scoring, Priority Score, account ranking, or hosted deployment behavior is changed by this document.

## Objective

Determine why acquisition-cohort companies remain unobserved after Build 016G before adding more sources or changing entity resolution. Separate:

1. true source-coverage gaps;
2. source records that exist but lack defensible service classification;
3. source records that contain explicit company identity relationships which the current exact-label model does not yet preserve.

The purpose is to improve TowerSignal's commercial relationship graph without weakening evidence standards.

## Locked product boundaries

- Priority Score 1.0 remains unchanged.
- Procurement values remain source-reported public purchasing/contract values, not company revenue or enterprise value.
- Vendor labels do not imply parent/sponsor ownership.
- Generic procurement descriptions do not become water-treatment evidence because the vendor is known to operate in the market.
- No fuzzy company matching is introduced.
- Opportunity Score 2.0 and deal-driven Home ranking remain blocked.

## Diagnostic A — New Jersey YourMoney Agency Purchasing

Official dataset: `ubnu-tqu7`.

Observed schema:
- fiscal_year
- fy_through_date
- department_agency_desc
- commodity_sector_desc
- vendor_name
- ytd_amt

Important semantic boundary: rows are fiscal-year purchasing aggregates/snapshots by public buyer/vendor/commodity context. They are not automatically individual contracts. Repeated year-to-date snapshots must not be counted as independent contract observations.

### Exact findings

#### Tower Cleaning Plus / Tower Water

Query `TOWER CLEANING PLUS` returned 15 rows under vendor label `TOWER CLEANING PLUS INC`.

The records include FY2025 and FY2026 purchasing across multiple New Jersey agencies including Corrections, Health, Human Services, Military and Veterans Affairs, Transportation, and NJ Interdepartmental. The commodity sector is `Public Works And Related Services`.

This is useful public buyer/vendor relationship evidence, but the commodity description alone is not specialized water-treatment proof.

Query `TOWER WATER` returned zero direct rows.

#### Barclay Water Management

Query `BARCLAY WATER` returned 15 rows under `BARCLAY WATER MANAGEMENT INC`, including Water and Sewer Treatment Equipment, Supplies, and Services; Testing and Sampling Equipment and Services; Laboratory Equipment, Supplies, and Services; Maintenance and Repair; and other source categories from FY2018 through FY2022.

This is strong historical public purchasing context. Source categories still require TowerSignal's service-taxonomy rules rather than automatic promotion based on vendor identity.

#### Rochester Midland

Query `ROCHESTER MIDLAND` returned one row under `ROCHESTER MIDLAND CORP` from FY2004. It adds historical vendor evidence but by itself does not solve the current multi-buyer relationship-density miss.

#### Industrial Water Technologies

Query `INDUSTRIAL WATER TECHNOLOGIES` returned three full-text search hits, but none were the target company. The rows were vendors `MARSHALL INDUSTRIAL TECHNOLOGI ES` and `KAMAN INDUSTRIAL TECHNOLOGIES` in water/sewer commodity context.

Conclusion: YourMoney does not currently provide exact Industrial Water Technologies evidence from this diagnostic. Do not treat the three full-text hits as company matches.

#### OCS Chemical Engineering / ClarityChem

No rows were returned for `OCS CHEMICAL` or `CLARITYCHEM`.

### NJ source decision

The dataset is valuable for broader company/public-buyer intelligence and can materially expand the market graph, especially for Tower Cleaning Plus and Barclay. If ingested:

- preserve source identity and fiscal-year/YTD semantics;
- deduplicate cumulative snapshots for relationship-density analysis using a deterministic key such as fiscal year + agency + vendor + commodity sector, retaining the latest source-through date for a period;
- label monetary values as source-reported purchasing aggregates, not contract value or revenue;
- do not infer specialized service from a generic commodity sector;
- do not use NJ evidence to alter Priority Score 1.0.

## Diagnostic B — Existing NYS ABO sources

The four Build 016G sources were queried directly for cohort aliases.

### OCS Chemical Engineering

OCS is already present in the State Authorities dataset `ehig-g5x3` under exact vendor name `OCS CHEMICAL ENGINEERING`.

Confirmed examples from the Power Authority of the State of New York:
- FY2023 transaction `CC-R01403`, amount expended for fiscal year 22,788.00;
- FY2024 transaction `CC-00082`, amount expended for fiscal year 18,269.75.

The procurement description is `Various` / `VARIOUS` and the type is `Other Professional Services`.

Conclusion: OCS is not a source-coverage miss. The current classifier is correct not to treat these rows as specialized water-treatment evidence. Do not promote them merely because OCS is a known water-treatment company. A different source with explicit service scope is required if OCS is to contribute specialized relationship evidence.

### Tower Water

Tower Water is already represented in the Local Development Corporations dataset `d84c-dk28` through explicit DBA source labels:
- `Tower Cleaning Plus D/B/A/ Tower Water`
- `Tower Cleaning Plus D/B/A Tower Water`
- `Tower Cleaning Plus dba Tower Water`

Governors Island Corporation records explicitly describe `Water treatment services`, including source-reported contract records in FY2022, FY2023, and FY2024.

Conclusion: Tower Water is not a procurement-source miss. It is an explicit identity-resolution gap. The raw source itself states the DBA relationship, so TowerSignal can preserve this relationship without fuzzy matching.

### Rochester Midland

The State Authorities feed contains direct Rochester Midland procurement evidence, including an explicit `HVAC water treatment` record for Rochester Midland Corp. The current Build 016G backtest already observes Rochester Midland but fails the locked relationship screen because current pre-outcome evidence does not provide two public buyers.

### ClarityChem

No direct `CLARITYCHEM` rows were found in the four ABO datasets in this diagnostic. This remains a source/history gap.

## Build decisions

### 016H-A — explicit DBA identity evidence

Implement a generic source-identity rule that recognizes only explicit DBA syntax such as `DBA` / `D/B/A` and exposes the component identity names as evidence-bearing aliases.

Requirements:
- preserve the full raw source vendor label;
- no fuzzy matching;
- no general legal-suffix collapse;
- the rule must be generic, not Tower-Water-specific;
- ambiguous or multi-target mappings fail closed;
- company and validation output must identify the resolution method as explicit source DBA evidence.

This should allow existing NYS Tower Water evidence to be recognized without changing service classification.

### 016H-B — NJ YourMoney purchasing layer

After 016H-A is independently green, build a bounded, versioned NJ purchasing source layer for company/market intelligence.

Requirements:
- deterministic retrieval and source counts;
- cumulative-snapshot deduplication;
- explicit purchasing-aggregate value semantics;
- conservative service classification;
- source health and live proof;
- company/public-buyer integration;
- no facility/tower linkage unless separately evidenced;
- no Priority Score change.

### Later coverage work

- Industrial Water Technologies: identify a different official New Jersey procurement source, likely contract/award-level rather than YourMoney purchasing aggregate.
- OCS: locate source evidence with explicit water-treatment/service scope rather than reclassifying `VARIOUS`.
- ClarityChem: recover bounded historical NYC/state procurement evidence where already documented but outside the current recent Checkbook window.

## Deal-validation guardrail after this diagnostic

The current validation gate was evaluated before these diagnostic findings. A later source/identity revision may improve the numerical backtest. That improvement must not automatically authorize Opportunity Score 2.0 merely because the old threshold becomes satisfied after methodology/source adjustments informed by the cohort.

Before enabling predictive/deal scoring after Build 016H:
- freeze the revised identity/source methodology;
- rerun the full retrospective report transparently;
- add an independent holdout, expanded cohort, or other pre-specified validation check not selected solely because it improves the known cohort;
- continue to keep monetary amounts out of the relationship-density screen unless a separately approved model explicitly changes that rule.

## Current conclusion

The highest-value next work is not a broad scoring model. It is improving the evidence graph:

1. preserve explicit DBA relationships already present in public records;
2. add high-quality adjacent procurement coverage with correct source semantics;
3. seek explicit service-scope evidence for remaining companies;
4. only revisit scoring after source and identity coverage are independently adequate.
