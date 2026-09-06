# TowerSignal Build 017D — Provider Identity Review Queue

Date: 2026-09-04

## Baseline

This increment starts from verified NYC water-data head `56b6765fb3b9272035ede41bd03147ab93c29edb` and is isolated on `agent/provider-resolution-20260904`.

It does not modify production UI, Priority Score 1.0, existing cooling-tower behavior, procurement scoring/classification, ACRIS, authentication/RLS or deployment behavior.

## Objective

Turn provider-name fragmentation in the verified NYC drinking-water-tank inspection data into an auditable review queue without silently changing company identities or publishing unsupported market-share metrics.

## Rules

- Raw provider names and existing deterministic provider keys remain untouched.
- Candidate generation may suggest a dominant observed provider key for review, but every candidate remains `identity_confidence = VERIFY`.
- `recommended_action` is always `REVIEW`.
- `merge_applied` must always remain `false` in this increment.
- Exact normalized-name overlap with NYS DEC Category 7G registrations is `CROSS_SOURCE_NAME_MATCH_ONLY`, not authoritative company identity proof.
- No revenue, complete-customer-book or market-share metric is calculated.

## Candidate classes

The processor emits review candidates for:

- formatting/token-equivalent names;
- probable typo variants with very high character similarity;
- probable naming variants with high token/character overlap;
- short-form/related names where one token set is a subset of the other.

Service-line differentiators such as `LINING`, `LABORATORY`, `PLUMBING`, `HEATING`, `ENVIRONMENTAL`, `MANAGEMENT` and `SERVICES` prevent a superficially similar pair from receiving the strongest typo-review class.

This is intended to surface cases such as misspellings of American Pipe & Tank, Rosenwach and Atlantank, while keeping potentially distinct businesses like American Pipe & Tank Lining separate pending evidence.

## DEC 7G cross-source matching

The verified domestic-water cache contains observed inspection providers and current DEC Category 7G business registrations. Build 017D reports exact normalized-name overlaps only. Because the match is name-only and may lack an authoritative legal identifier/address join, every match remains `VERIFY` under TowerSignal's existing company-identity evidence rules.

## Live verification

The Build 017D workflow rebuilds and validates the authoritative domestic-water/provider cache, builds the review queue, validates that zero merges were applied, runs focused provider-resolution tests, uploads the review artifact, then runs the full repository integration gate.

## Next step after review

A later increment can create an approved alias map with explicit evidence per alias (source name, legal identifier, address, contract/vendor identifier, or manually approved equivalence). Only approved alias records may be used for consolidated provider footprint or market-share calculations.
