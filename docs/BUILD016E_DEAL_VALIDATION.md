# Build 016E — Empirical Deal Intelligence Validation

Base: `main@2d84b5503ead23d9c9491ce3bbdf47a4568902bc`

## Purpose

Determine whether TowerSignal's current source-backed procurement/company intelligence provides enough acquisition-target evidence to justify building Opportunity Score 2.0. This build is an experiment and evidence report, not a deal score.

## Locked before outcome

The validation gate is fixed before the production report is generated:

- at least 3 independently acquired cohort targets must be exactly observable in the current source universe;
- at least 2 observed acquisition outcomes must pass the relationship-density screen;
- no fuzzy company matching;
- no monetary values in the screen;
- Priority Score 1.0 remains unchanged.

The relationship-density screen requires all of:

- at least 2 source-dated relevant procurement observations before the cutoff;
- at least 2 public buyers;
- at least 1 repeat buyer;
- at least 1 cooling/water/Legionella-specific service observation.

Broad generic laboratory/HVAC classifications are deliberately excluded from the specialized service criterion.

## Cohort

The curated positive-outcome cohort contains:

- Rochester Midland Corporation / Peak Rock Capital;
- Norkem Group;
- Industrial Water Technologies;
- Barclay Water Management;
- OCS Chemical Engineering;
- Comprehensive Chemical and Water Treatment;
- Decon Water Technologies;
- Solid Blend Technologies;
- Tower Water;
- ClarityChem / Chemasters / Chematrix.

Every acquisition outcome includes a primary acquirer/company evidence URL and exact curated aliases. Similar names are not treated as matches. For example, Industrial Water Management is not Industrial Water Technologies, and Clarity Water Technologies is not ClarityChem.

## Retrospective limitation

This is a `RETROSPECTIVE_SOURCE_DATE_BACKTEST`: the current City Record and Checkbook snapshots are filtered by source-reported historical dates. It does **not** prove that TowerSignal possessed a given row at that historical time. Results therefore measure whether the currently available public-source structure contains retrospective signal, not a historical production forecast.

## Comparison semantics

Source-observed vendors that pass the locked screen but do not map to a curated acquisition outcome are labeled `NO_CURATED_OUTCOME_COMPARISON`. They are not called non-acquired companies unless a separate outcome-verification process proves that negative.

## Source-coverage diagnostic

The report distinguishes:

- `OBSERVED_IN_CURRENT_SOURCES`;
- `IN_MARKET_NOT_OBSERVED`;
- `OUTSIDE_CURRENT_NYC_PROCUREMENT_SCOPE`.

Tower Water also includes an external pre-outcome NJSTART contract as a documented source-expansion example. It is not counted as evidence from TowerSignal's current NYC source universe.

## Output and gate

Production Pages builds generate `public/data/deal-validation.json` after verified City Record, Checkbook and company aggregation. `validate_deal_validation.py` verifies methodology, exact counts, no score emission, primary outcome evidence URLs, and the pre-specified gate calculation.

If the gate fails, Build 016E explicitly blocks Opportunity Score 2.0 and the deal-driven Home/Command Center. The next action becomes source-coverage expansion rather than score engineering.
