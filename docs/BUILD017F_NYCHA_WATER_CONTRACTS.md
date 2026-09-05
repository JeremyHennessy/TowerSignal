# TowerSignal Build 017F — NYCHA Water Contract Release/Line Intelligence

Date: 2026-09-04

## Exact starting baseline

This increment starts from exact `main@4f95b150dda1d69288e7b7d8e32955b887fc30ce`.

It is isolated from the verified NYC domestic-water/provider, statewide-PWS, provider-resolution and Open Book branches. No production UI, Priority Score 1.0, auth/RLS, ACRIS or deployment behavior is modified.

## Source contract

Checkbook NYC exposes NYCHA contracts through the distinct `Contracts_NYCHA` API domain. This source is not treated as the same schema as citywide registered contracts.

NYCHA rows are release/line-item observations. The adapter preserves source fields including contract ID, release/line/shipment identity, purpose, item description, vendor, NYCHA location, responsibility center, funding source, program/project, dates, procurement metadata, and separate line/release/contract amount and invoiced fields.

## Bounded retrieval

The first proof uses the latest five NYC fiscal years. Each fiscal year is queried independently through the existing paced Checkbook XML transport. Every partition must retain a stable source-reported record count throughout pagination and the retrieved row count must exactly match that count.

## Classification

Purpose and item description are classified together. The shared TowerSignal procurement taxonomy handles explicit cooling-tower, water-treatment, Legionella, chiller, condenser/boiler water and related mechanical scopes. A separate domestic-water layer adds explicit potable/domestic/drinking water, storage/roof tanks, backflow/RPZ, monochloramine/chlorination, water sampling, domestic/booster pumps and review-level plumbing work.

Generic wastewater, stormwater, public water-main, hydrant, pool and fire-protection context is excluded unless explicit protected cooling-tower/Legionella/condenser/boiler/water-management language independently establishes relevance.

## Evidence boundaries

- `vendor` is the source-reported NYCHA vendor; no fuzzy company resolution occurs in this increment.
- `location` is preserved as NYCHA source context. It is not automatically represented as an exact TowerSignal building, development asset, cooling tower or domestic-water tank.
- Line, release and contract amount fields remain separate. Contract-level amounts repeated on many release/line rows are never summed across those rows.
- Source invoiced values are preserved as invoiced values; they are not called company revenue.
- A release/line source identity is deterministic across fiscal year + contract + release + line + shipment + approved date + item/amount context.

## Acceptance

Do not merge based on code alone. The live workflow must prove the current `Contracts_NYCHA` response vocabulary, exact pagination for all five fiscal years, realistic source/relevant volumes, unique release-line identities, evidence boundaries, artifact revalidation, and the complete existing Python/frontend/lint/typecheck/build gate.
