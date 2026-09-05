# TowerSignal Build 017J — ELAP Public Search Source-Contract Probe

Date: 2026-09-04

## Baseline

This source-discovery increment starts from `main@8b100d86635eeee4daa0ee876b4cc8a2d480e0de` and does not modify application behavior or production data.

## Objective

TowerSignal already observes laboratory names in NYC domestic-water inspection records. NYSDOH/Wadsworth ELAP is the authoritative source for whether a laboratory is currently accredited for environmental analyses such as potable water.

The public ELAP search page exposes a complete laboratory-name selector plus state/country/county/type and category/analyte/method filters. Before building an accreditation crawler, this increment proves the actual machine-readable keys embedded in the current public search form.

## Why this probe exists

Do not brute-force ELAP laboratory IDs and do not derive lab IDs from names. A safe crawler needs an authoritative enumeration source.

The probe:

- fetches the current public ELAP search page;
- parses form/select/option HTML without browser automation;
- identifies the laboratory selector from its actual form metadata and source volume;
- records option-value shape counts and a bounded sample;
- requires at least 250 populated lab options;
- fails if populated lab option values have an unsupported shape.

No lab identity merge or accreditation claim is produced by this branch. It is only a source-contract proof.

## Acceptance

Advance to a full ELAP potable-water scope crawler only if the live public page exposes stable option keys that can be deterministically mapped to the laboratory-detail endpoint. If the option values are session-specific, empty, JavaScript-generated, or otherwise non-durable, stop and use another authoritative enumeration route rather than guessing or brute-forcing IDs.
