# TowerSignal Build 017E — Open Book NY Water Contract Transactions

Date: 2026-09-04

## Starting baseline

This source proof starts from exact production `main@dd802dde23cfd67290eda0d4cc9b37b1b9559bf4`.

It is isolated from the earlier domestic-water, provider-resolution and statewide-PWS branches. No existing application UI, Priority Score 1.0, cooling-tower behavior, auth/RLS or Pages deployment behavior is modified.

## Source

The Office of the State Comptroller Open Book New York contract search exposes a CSV export from `https://wwe2.osc.state.ny.us/transparency/contracts/contractresults.cfm`.

The export query requests contract/original/amendment transactions approved/filed before the current date. TowerSignal verifies the current CSV schema and hashes the exact source bytes used for every build.

## Transaction history

The CSV contains original contracts and amendments. TowerSignal does not collapse a transaction into an unsupported current-spend claim.

For every relevant contract identity it preserves vendor, Department/Facility, contract number, every source transaction and source-row ordinal, transaction type, transaction amount, contract start/end dates where supplied, description, and transaction approved/filed date.

The contract-level `net_transaction_amount` is only the arithmetic sum of source transaction amounts. It is explicitly not company revenue or spending-to-date.

## Classification

The existing TowerSignal procurement classifier remains the first layer. A separate Open Book domestic-water layer only adds explicit building-water contexts the cooling-tower classifier intentionally does not promote: potable/domestic/drinking water; water-storage/roof tanks; backflow/cross-connection/RPZ; monochloramine/chlorination; water sampling; domestic/booster water pumps; and plumbing maintenance/service/repair as `VERIFY`.

Wastewater, stormwater, water mains, hydrants, pools, fire protection and bottled-water delivery remain excluded unless stronger supported TowerSignal service wording independently classifies the contract.

## Contract grouping

A contract identity is the deterministic combination of normalized vendor, source Department/Facility, and contract number. All descriptions across its source transactions participate in classification so later generic amendment descriptions do not orphan a relevant original water contract.

## Evidence boundaries

- Open Book vendor name is source-reported vendor evidence; no fuzzy TowerSignal company merge occurs here.
- Department/Facility is source contracting context, not an exact building/tower assignment unless another source establishes that link.
- Transaction amount is public contract evidence, not provider revenue.
- Source duplicates remain distinguishable through source-row transaction identity.
- The adapter does not populate spending-to-date because that field is not in the full transaction CSV export.

## Acceptance

Do not merge based on code alone. The workflow must download the current full OSC export, verify schema and realistic statewide volume, publish only water-relevant grouped contracts while preserving every relevant transaction, reconcile transaction counts and amounts, revalidate the downloaded artifact, and pass the complete existing Python/frontend/lint/typecheck/build gate.

Only after live verification should this source be joined to TowerSignal company identities and facility/property relationships.
