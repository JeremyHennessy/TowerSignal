# Parent mapping and recurring enrichment

## Verified production baseline

Read-only audit run [36137384972](https://github.com/JeremyHennessy/TowerSignal/actions/runs/36137384972), 2026-09-25 12:51 UTC:

- 89 active master accounts; 340 membership mappings; zero unmapped profiles, invalid primary mappings, memberships on merged accounts, or duplicate primary contacts.
- 47 active sourced contacts across 24 accounts; 19 primary contacts; 17 buying-role contacts.
- 10 accounts with sourced parent names, zero account/profile parent conflicts.
- 26 accounts with websites and HQ addresses; 27 with company type/identity source; 3 with revenue.
- 61 accounts never enrichment-checked. Zero older than 90 days among those with a recorded check.
- Roll-ups: 12 accepted, 2 pending, 5 superseded. Research queue: 95 unreviewed, 5 researching.

## Preservation

Migration 013 is additive and reserves 012 for the separate external-activity branch. It creates stable parent entities, dated evidence-backed ownership relationships, approved enrichment sources, run history, and candidate observations. It does not infer, backfill, or replace any existing parent or source-to-account mapping. Legacy recorded parents remain visible while explicit normalized relationships are reviewed.

Company enrichment observations are proposals, not verified company facts. Only approved HTTPS source pages are checked. Structured Organization data must match the approved exact company name. Missing/ambiguous data and failed retrievals stay distinct. Revenue, ownership absence and contact identities are never guessed. Marking a candidate reviewed does not publish it; the existing Research editor is the explicit publication path. Parent changes use the separate relationship review.

The initial collector supports published legal names, organization addresses, parentOrganization statements and explicit mailto/tel contact routes. Contact routes are not identified people or decision makers. Organization addresses require review before treating them as headquarters. This is bounded approved-source enrichment, not unrestricted web research; accounts without an approved source remain in the research backlog.

## Release order

1. Complete read-only audit and candidate CI/migration tests.
2. Review the isolated candidate UI and migration.
3. Obtain production authorization before migration, merge, deployment or enabling the scheduled worker.
4. Apply 013, verify admin/non-admin access and unchanged mappings, then release the tested application.
5. Register approved official source pages per account. Enable the repository variable `COMPANY_ENRICHMENT_ENABLED=true` only after database/UI acceptance.
6. Verify the first source-check run and its pending observations in Admin. Review evidence before publishing changes through the Research editor.

No private enrichment payload is committed to Git or uploaded as an Actions artifact. Logs contain aggregate counts and error categories only. A successful source check is not full account verification and does not update `enrichment_checked_at`.

An account with active parent links, approved enabled sources or pending observations cannot be merged until those records are explicitly reviewed, paused or archived. This prevents a roll-up from silently stranding or reassigning ownership evidence. Historical evidence remains attached to its original account.

## Read-only website smoke checks

On September 25 the collector retrieved three previously recorded official websites without writing to the database:

- Tower Water: exact organization matched; two explicitly published contact-route candidates.
- Atlas Environmental Lab: no supported structured organization data; left unresolved with no candidates.
- Certified Laboratories: organization matched; no supported proposed fields found on the checked page.

These results demonstrate the collector's boundaries, not complete research or current ownership verification. Broader coverage requires additional approved pages or separately reviewed research adapters.

## Candidate verification

- Existing frontend suite plus four evidence-control tests; eight collector tests.
- Disposable PostgreSQL 17: all existing migrations plus 013, repeat application of 013, RLS admin/non-admin checks, existing-parent/membership preservation, conflicting-parent rejection, merge guard, repeat-run deduplication, rejection preservation and retrieval-failure handling.
- Local browser preview with synthetic data: desktop and 390-pixel mobile, expanded evidence sections, pending-review action and no page errors. This does not replace authenticated hosted acceptance after release.
- Exact release allowlist: 74 changed paths from the accepted product baseline, with no unexpected/missing paths. Public data hash verification remains mandatory during release.
- Production remains at the previously accepted main until separately authorized. The scheduled worker is disabled by default.


## September 25 continuation: parent review and usable navigation

The production directory now retains 13,779 source identities in 13,528 rows, including 89 CRM masters covering 340 reviewed memberships. Four additional current group relationships were recorded with observed date September 25, taking the confirmed relationship total from three to seven:

- Nalco Water → Ecolab: https://www.ecolab.com/en-us/about/our-businesses/nalco-water-and-process-services
- Barclay Water Management → Ecolab: https://investor.ecolab.com/news/news-details/2024/Ecolab-Acquires-Barclay-Water-Management/default.aspx ; current barclaywater.com redirect corroborates the group connection.
- Environmental Building Solutions → Pinchin Ltd.: https://www.pinchin.com/about
- Rochester Midland Corp. → Peak Rock Capital: https://www.rochestermidland.com/team/jim-white/

The records describe sourced group/portfolio relationships, not ownership percentages or intermediate legal holding entities. The guarded transaction preserved all 89 active masters and 340 membership mappings. Cascade, Culligan and York legacy parent labels were not promoted merely from old or incomplete evidence.

Tower Water and Certified Laboratories official home pages were approved with exact matching published structured organization names. A read-only collector smoke check matched both organizations; Tower Water exposed two contact-route observations, while Certified Laboratories exposed no supported proposed fields. These are collection results, not complete company enrichment.

The enrichment workflow now offers an explicit `run_once` manual input on main. It permits checking the approved sources once while the weekly `COMPANY_ENRICHMENT_ENABLED` gate remains off. Existing candidate review and publication boundaries remain unchanged. Verify the first production run and pending observations before considering recurring activation.

Admin workspace, table and company-detail navigation now uses visible bordered links, dark selected states and keyboard focus indicators. Hash URLs preserve sections, directory filters, pagination and the selected research source identity. Copy page link copies the current view; recipients still require existing administrator access. The parent evidence date field accepts validated YYYY-MM-DD text and a Use today shortcut, avoiding the embedded browser native calendar crash.
