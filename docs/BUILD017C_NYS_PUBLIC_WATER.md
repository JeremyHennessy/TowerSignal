# TowerSignal Build 017C — New York State Public Water Systems

Date: 2026-09-04

## Verified baseline and isolation

Build 017C is intentionally isolated on `agent/nys-public-water-20260904` from verified Build 017A commit `400434201cf1992ac982ab11604401dafe01b252`.

It does not depend on the still-verifying NYC Build 017B increment. It does not change the TowerSignal UI, Priority Score 1.0, current cooling-tower payloads, procurement classification, ACRIS, authentication/RLS, or production deployment.

## Objective

Create a statewide public-water-system spine keyed by authoritative NYSDOH PWSID, then attach current system/contact context, operator qualification, lead-service-line-inventory applicability and 2025 drinking-water violations without overstating provider relationships.

## Current authoritative source scope

1. **NYSDOH Public Water Supply Contact Information (2026)** — current Community and Non-Community public water systems, arranged by county, with PWS name, PWSID, system type, population and one or more contact records. Revised May 2026.
2. **NYSDOH current certified water operators** — statewide water-treatment-plant and distribution-system operator certifications, including county, name, certification number, expiration and level description. Revised August 2026.
3. **NYSDOH Lead Service Line Inventory index** — PWSID, PWS name and principal county for systems subject to the inventory requirement. The index supplies deterministic detail-page URLs; Build 017C does not yet crawl every detail page.
4. **NYSDOH 2025 public-water violations** — county compliance pages listing PWSID, system type, violation type, contaminant, months covered and enforcement/status text. The statewide 2025 report records 9,199 violations across 4,134 systems and is retained as the report reference.

The adapter discovers county pages from the current NYSDOH index pages rather than hardcoding a county list. Every discovered page must be successfully retrieved and parsed before the cache is accepted.

## PWSID as the statewide identity spine

`PWSID` is the canonical key for this domain. Directory rows sharing the same PWSID are grouped into one system profile while preserving all observed name/type/population variants and all distinct contact blocks.

A PWS directory may contain multiple contacts for a single PWSID. Those contacts can include government staff, site contacts, consultants or laboratories. Therefore directory contacts are stored only as:

- `relationship_role = CONTACT_FOR_PWS`
- `relationship_evidence = NYSDOH_PWS_DIRECTORY`
- `operator_assignment_confidence = NOT_PROOF_OF_OPERATOR_ROLE`

No contact is silently promoted to owner, licensed operator, laboratory, water-treatment contractor or incumbent service provider.

## Certified-operator evidence boundary

The statewide certified-operator list proves qualification, not assignment. Each certification record is stored as:

- `relationship_evidence = QUALIFIED_OPERATOR`
- `pws_assignment_confidence = UNLINKED_TO_PWS`

The operator list is not name-matched to PWS directory contacts in this increment. A later source may establish an operator-of-record relationship explicitly.

## Lead service line inventory boundary

The current LSLI index establishes only that a PWS is subject to the lead-service-line inventory requirement and supplies a deterministic detail page such as `/service_line/NY7003493.htm`.

Build 017C records:

- PWSID;
- PWS name;
- principal county served;
- `lead_service_line_inventory_required = true`;
- authoritative detail URL.

The individual detail pages are reserved for a separate crawl because they contain stronger evidence: contact information for the **Owner / Licensed Operator of Record Completing the Form**, inventory counts, identification methods, public inventory availability and certification information. Keeping that crawl separate prevents thousands of detail requests from destabilizing the initial statewide spine.

## 2025 violation evidence

Each county violation row is retained as a separate PWSID-keyed compliance observation with:

- calendar year;
- PWSID/system name;
- system type;
- violation type;
- contaminant(s);
- months covered;
- status;
- source county page.

The source is NYSDOH's 2025 annual compliance reporting. These records do not identify a water-service contractor.

## Source retrieval contract

NYSDOH pages are HTML rather than Socrata APIs. The adapter therefore:

- uses only Python standard library HTTP/HTML parsing;
- sends the TowerSignal user agent;
- retries bounded network failures;
- tries the official `healthweb-back.health.ny.gov` mirror only when the canonical `www.health.ny.gov` page fails;
- discovers county-page links from the current index pages;
- requires at least 50 current PWS contact pages and 50 violation pages;
- requires every discovered page to fetch and contain the expected table schema;
- fails closed rather than publishing a partial statewide result.

## Production-volume gates

The initial proof refuses implausibly small live payloads. Current sanity floors are deliberately below the known statewide totals but high enough to catch broken discovery/parsing:

- at least 8,000 unique PWS systems;
- at least 8,000 PWS contact records;
- at least 1,000 certified operators;
- at least 3,000 systems in the LSLI index;
- at least 8,000 2025 violation rows.

The live workflow, not these floors, determines the actual current counts.

## Next statewide increments after 017C proof

1. Crawl all LSLI detail pages in a separate rate-limited cache to capture explicit owner/licensed-operator-of-record contacts, system-specific lead/GSLRR/non-lead/unknown counts, identification methods and certification dates.
2. Resolve explicit operator-of-record relationships against the certified-operator universe only when certification/name evidence supports the match.
3. Add annual water-quality reports where NYSDOH or suppliers expose durable public documents.
4. Add ELAP laboratory accreditation/analyte scope after its current search/form contract is independently proven.
5. Expand Open Book NY contracts and spending into PWS/facility/provider intelligence using the existing procurement evidence model.
6. Add EPA SDWIS/ECHO as a separate federal corroboration layer rather than silently merging federal and NYSDOH violation semantics.

## Acceptance

Build 017C is accepted only when the live source workflow proves current page discovery, source retrieval, schemas, evidence boundaries and production volumes, and the repository's existing Python/frontend/build gates remain green. A green data proof does not authorize a production merge or UI change.
