# TowerSignal Build 017B — NYC Building-Water Signals

Date: 2026-09-04

## Baseline and preservation boundary

Build 017B continues PR #102 from verified Build 017A head `400434201cf1992ac982ab11604401dafe01b252`.

It does not change application UI, navigation, styles, Priority Score 1.0, existing cooling-tower source processing, procurement classification, ACRIS, authentication/RLS or production deployment behavior.

## Objective

Add a second independently verified NYC domestic-water cache covering building-condition, building-work and water-consumption signals without conflating street infrastructure, regulatory applicant roles or multi-property benchmarking rows with confirmed provider assignments.

## Source scope

1. Official NYC 311 Service Requests from 2020 to Present (`erm2-nwe9`): DEP water/lead requests from 2025-01-01 forward, retrieved by deterministic server-side filter.
2. Authoritative HPD Housing Maintenance Code Violations (`wvxf-dwi5`): current `Open` violations fetched through explicit hot-water, water-supply, potable-water, plumbing or plumbing-fixture keyword partitions.
3. DOB NOW Job Application Filings (`w9ak-ipjd`): water/plumbing/tank/pump/backflow-related filings from 2024-01-01 forward where the source marks plumbing, mechanical or boiler work.
4. DOB NOW Approved Permits (`rbx6-tga4`): similarly bounded approved/issued water-related permits from 2024-01-01 forward.
5. Local Law 84 consolidated energy/water disclosure (`5zyy-y8am`): all current 2022-present rows, selecting only identity and water-related fields.

All source adapters use exact query-scope count checks and fail closed on incomplete pagination or missing required schema fields.

## 311 evidence boundary

311 is observational demand/condition evidence, not a violation or confirmed contractor relationship.

Water requests are classified before property linkage:

- `BUILDING_WATER_QUALITY`
- `BUILDING_NO_WATER_OR_PRESSURE`
- `BUILDING_WATER_LEAK`
- `STREET_WATER_MAIN_CONTEXT`
- `HYDRANT_CONTEXT`
- `SEWER_STORMWATER_CONTEXT`
- `OTHER_DEP_WATER`

Only `BUILDING_*` classifications may receive building-level property linkage. Street-main, hydrant and sewer/stormwater rows remain `CONTEXT_ONLY` even if the source happens to contain a nearby BBL.

## HPD evidence boundary

The authoritative HPD source contains more than eight million violation records,
so Build 017B does not copy the entire corpus. It requests current `Open`
violations through bounded source-description keyword partitions and preserves
HPD's source BBL/BIN, violation class, inspection date, current status and
description.

The cache records the HPD fetch strategy explicitly as
`UPPERCASE_KEYWORD_PARTITIONS`. HPD descriptions are standardized uppercase text,
so the source query avoids `lower(novdescription)` scans that can time out on
hosted runners. Each term partition uses `violationid` keyset pagination instead
of high-offset pagination, must still fetch exactly its source-reported count,
then the cache de-duplicates overlapping partition matches by `violationid` and
records the duplicate count explicitly.

An HPD record is a confirmed housing-code violation observation; it is not evidence of which contractor currently services the property.

## DOB evidence boundary

DOB filings and permits provide highly useful building-work and company-role observations, but an applicant or permit applicant is not automatically an incumbent water-treatment/service contractor.

Build 017B therefore records:

- exact BBL/BIN and source job/permit identifiers;
- applicant business/name/license fields;
- owner business context;
- filing/approval/issue/signoff/expiration dates;
- source work type and job description;
- deterministic water-work category;
- relationship role as `JOB_APPLICANT_OF_RECORD` or `PERMIT_APPLICANT_OF_RECORD`;
- relationship evidence as `RECORDED_DOB_ROLE`;
- service assignment confidence as `NOT_PROOF_OF_SERVICE_CONTRACT`.

Observed DOB business profiles aggregate aliases, source record counts, unique BBLs, licenses and work categories, but do not claim contract awards or market share.

## LL84 water-consumption boundary

LL84 is self-reported benchmarking data for covered buildings. It provides all-water and municipally supplied potable-water use plus water-meter fields.

A Portfolio Manager property can contain multiple BBLs and/or BINs. Build 017B therefore uses:

- `EXACT_SINGLE_BBL` when exactly one valid BBL is supplied;
- `EXACT_SINGLE_BIN` only when there is no BBL and exactly one valid BIN;
- `MULTI_IDENTIFIER_CONTEXT` when multiple property identifiers are present;
- `UNLINKED` when no usable identifier exists.

Multi-identifier rows never receive a single TowerSignal property key.

## Water-work taxonomy

DOB descriptions are deterministically separated into:

- domestic water systems;
- domestic/roof/storage tanks;
- backflow/RPZ work;
- hot-water systems;
- water/booster pumps;
- plumbing water-related work;
- boiler-water adjacent work;
- cooling-tower/condenser-water adjacent work;
- fire-water context;
- other water/mechanical work.

Fire-suppression-only work is kept as context and is not silently represented as domestic-water work.

## Acceptance

Build 017B is accepted only when its PR workflow proves:

- live source schema validity for all five datasets;
- exact filtered source count equals fetched count for every source;
- deterministic normalization and evidence rules pass tests;
- production-volume sanity floors pass;
- the generated artifact revalidates after download;
- the repository's existing Python tests, frontend lint, typecheck, frontend tests and production build remain green.

No production merge or UI exposure is implied by a green data proof.

## Integration note

This integration branch keeps the standalone 017B data proof unchanged and adds
`scripts/attach_nyc_water_signals.py` as a later account-detail attach step. The
attach step only promotes exact source BBL/BIN rows into NYC Account and
Technician Field Pack context; address-only, street-infrastructure and LL84
multi-identifier rows remain outside account detail.
