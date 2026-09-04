# TowerSignal Build 017B — NYC LL84 Building Water

Date: 2026-09-04

## Baseline

Build 017B is a stacked data-only increment on the exact verified Build 017A head `400434201cf1992ac982ab11604401dafe01b252`.

Build 017A has independent green proof for its domestic-water/provider cache, lead-service-line cache, and normal repository CI. Build 017B does not alter those adapters, the current production UI, Priority Score 1.0, existing procurement intelligence, or any deployment path.

## Source

NYC Building Energy and Water Data Disclosure for Local Law 84 2023 to Present (`5zyy-y8am`).

The source is annual benchmarking disclosure for covered buildings. It is not a complete inventory of all NYC buildings and must not be represented as one.

TowerSignal retrieves the current exact row count and only the fields needed for building identity, water demand and water-data quality:

- report year and EPA property ID;
- property name/type/address;
- source-reported BBL and BIN strings;
- building gross floor area;
- metered areas for water;
- all-source total/indoor/outdoor water use;
- municipally supplied potable mixed/total/indoor/outdoor water use;
- estimated-water flags;
- short-year water-meter alert;
- last-modified date for water meters.

## Identity rules

An LL84 property can contain multiple tax lots and/or multiple buildings. TowerSignal therefore:

- extracts every valid 10-digit source-reported BBL into a `bbls` array;
- extracts every valid 7-digit source-reported BIN into a `bins` array;
- never chooses a single BBL/BIN when the source reports multiple values;
- treats EPA property ID as the longitudinal LL84 identity;
- marks rows with at least one BBL/BIN as `CONFIRMED_IDENTIFIER` and otherwise `UNLINKED`.

## Water metrics

All numeric water values are kept in the source unit of thousand gallons (kgal). Missing and `Not Available` values remain null.

For a single effective municipal-potable metric, the source's `Municipally Supplied Potable Water - Total Use (All Meter Types)` value is used when present; the mixed indoor/outdoor field is only a fallback. Both original fields remain separately preserved.

## Longitudinal processing

For each EPA property ID, TowerSignal retains every annual observation and also builds a latest-property profile. Year-over-year change is computed only where:

- the EPA property ID is identical;
- both latest and immediately prior observations have numeric effective municipal potable-water values.

No cross-property imputation occurs.

## Verification

The cache must prove:

- required source fields still exist;
- exact source count equals fetched row count;
- deterministic complete pagination;
- normalized observation count equals the source count;
- BBL/BIN arrays contain only valid-length numeric identifiers;
- every latest-property record points to a retained observation;
- production volume remains plausible.

The PR workflow then reruns all Python tests, frontend tests, lint, typecheck and the production build. The verified cache remains a workflow artifact only in this increment.
