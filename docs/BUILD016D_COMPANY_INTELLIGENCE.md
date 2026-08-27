# Build 016D — Company Intelligence

Base: `main@cba1806a9a661afdb5c943bf5e975594fcc9ae21`

## Objective

Create a source-backed Companies workspace and shareable Company Profile from the verified City Record + Checkbook procurement payloads without inferring corporate parentage, sponsor ownership, revenue, enterprise value or a complete customer book.

## Identity boundary

- Observed company entities are keyed from exact public procurement vendor labels after case/punctuation normalization.
- Legal suffixes are preserved.
- Similar base names with different suffix/source labels remain separate `VERIFY` candidates.
- Single-token/acronym/generic labels such as `RMC` remain identity `VERIFY` and cross-source `VERIFY` even if no collision is presently observed.
- No parent or sponsor relationship is created from procurement names.

## Product surfaces

- `#/companies`
- `#/company/:company_id`
- Company search/service/resolution filters
- Observed contracts, buyers, repeat-buyer evidence, service mix, active/expiring contracts and public observed values
- Exact linked procurement evidence with source links
- Share/reload-safe company profile URLs

## Production verification

`validate_company_intelligence.py` requires exact accounting from City Record + Checkbook vendor observations into `companies.json`, forbids duplicate assignments, verifies every procurement ID against the two inputs, requires all short identities to remain `VERIFY`, and rejects unsupported parent/sponsor assignments.

Hosted Playwright coverage verifies Companies and Company Profile on desktop Chromium and iPhone contexts, including deep link/reload behavior, copy-link control, observed-value semantics and resolution confidence.

## Preserved boundaries

- Priority Score 1.0 unchanged.
- No Opportunity Score 2.0 in this build.
- No acquisition/deal score in this build.
- No global Home redesign in this build.
- Existing Build 015 account UI remains unchanged except navigation required to expose Companies.
