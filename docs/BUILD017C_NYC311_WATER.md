# TowerSignal Build 017C — NYC 311 Water / Lead Service Requests

Date: 2026-09-04

## Baseline

Build 017C is a stacked data-only increment on exact verified Build 017B head `bec7bce18794c029fc5d83848fcdf0004cf6a0df`.

Builds 017A and 017B remain independently verified. This increment does not modify their adapters, the production UI, Priority Score 1.0, procurement classification or deployment paths.

## Sources

Official NYC 311 Service Requests open-data partitions:

- 2010–2019: `76ig-c548`
- 2020–present: `erm2-nwe9`

The two datasets are queried independently and retain independent source-health/count proof.

## Source scope

The live source query is:

`agency='DEP' AND (complaint_type like '%Water%' OR complaint_type='Lead')`

This intentionally starts from DEP-owned water/lead requests rather than downloading the full multi-agency 311 corpus. The adapter verifies the current schema for each partition and selects only fields that actually exist in that partition.

## Evidence boundary

A 311 row is a `REPORTED_SERVICE_REQUEST` and `UNVERIFIED_REPORTED_CONDITION`.

It must not be represented as:

- confirmed contamination;
- confirmed lead presence;
- confirmed plumbing failure;
- a violation;
- a responsible contractor/provider assignment.

A source-reported BBL provides location identity only and is labelled `CONFIRMED_LOCATION_IDENTIFIER`.

## Classification

The deterministic classifier separates:

- `LEAD_TEST_KIT_ACTIVITY`: lead kit/test-kit activity; never treated as proof of lead detection;
- `LEAD_DRINKING_WATER_REQUEST`: other DEP lead-related drinking-water requests;
- `DRINKING_WATER_QUALITY`: dirty/discolored/taste/odor/cloudy/particle-type water reports;
- `WATER_SUPPLY_PRESSURE`: no-water / low-pressure reports;
- `WATER_LEAK_REPORTED`: leak reports where public-vs-private location is not proven;
- `PUBLIC_WATER_INFRASTRUCTURE`: hydrants, water mains, main breaks and street-water infrastructure;
- `OTHER_WATER_RELATED_REQUEST`: remaining DEP Water complaint types that lack enough wording for a narrower classification.

This prevents hydrant/main work from being silently turned into a building domestic-water opportunity.

## Artifacts

The workflow produces three temporary verification artifacts:

1. `requests.ndjson.gz` — every normalized source row from both exact query partitions;
2. `properties.ndjson.gz` — BBL-level aggregates for rows where the authoritative 311 source reports a valid BBL;
3. `summary.json` — exact source counts, category/source/year counts, BBL coverage and source health.

Property aggregates contain request counts, category/source counts, first/latest request dates and the latest reported request context. They remain reported-history summaries, not confirmed property-condition records.

## Fail-closed rules

For each 311 partition TowerSignal:

- retrieves source metadata;
- verifies common required fields;
- intersects optional selected fields against the actual current schema;
- retrieves the exact source count for the exact query scope;
- pages deterministically by `unique_key`;
- requires fetched rows to equal the source count;
- refuses partial output.

The validator then re-reads every compressed request and property row, verifies source/category/evidence semantics, validates every retained BBL, and reconciles all artifact counts back to the source-health record.

## Production boundary

Build 017C is ingestion/processing only. The verified artifacts are not wired into Pages or the application UI. No production deployment or data persistence is authorized by this increment.
