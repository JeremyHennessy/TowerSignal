# TowerSignal Build 017H — NYC DEP Distribution Drinking-Water Quality

Date: 2026-09-04

## Starting baseline

This source proof starts from exact `main@4f95b150dda1d69288e7b7d8e32955b887fc30ce` and is independent of the domestic-water tank, statewide PWS, provider-normalization, Open Book and NYCHA branches.

No production UI, scoring, cooling-tower behavior, auth/RLS or deployment behavior is changed.

## Source

NYC DEP publishes `Drinking Water Quality Distribution Monitoring Data` as NYC Open Data dataset `bkwf-xfky`. Each row is a distribution-system sample with sample number/date/time/site/class and residual free chlorine, turbidity, fluoride, coliform and E. coli result fields.

The workflow verifies the current authoritative schema, retrieves the exact source count with deterministic pagination ordered by sample number, and refuses partial snapshots.

## Measurement semantics

The source measurement columns are text. TowerSignal retains the exact raw source text and separately parses a numeric value only when one is present. Comparison/non-detect semantics are retained explicitly:

- `EQ` — unqualified numeric source value;
- `LT` — source value prefixed by `<`;
- `GT` — source value prefixed by `>`;
- `ND` — source reports non-detect;
- `TEXT` — non-numeric source text not otherwise classified;
- `MISSING` — empty source field.

`ND` is never converted to zero, and `<1` is never represented as an exact measurement of 1.

## Site profiles

The cache calculates per-source-sampling-site sample count, sample-class counts, first/latest sample dates and latest source measurements. These are distribution sampling-site profiles only.

TowerSignal does **not** link `sample_site` to a building/property in this increment. Every sample/site is explicitly `UNLINKED_SAMPLE_SITE` until an authoritative sampling-site crosswalk provides defensible location identifiers.

## Acceptance

Do not merge based on code alone. The live workflow must prove the current schema, exact source count, realistic sample/site volume, unique sample identities, measurement qualifier preservation, artifact revalidation and the complete existing Python/frontend/lint/typecheck/build gate.
