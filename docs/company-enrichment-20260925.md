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

## Release order

1. Complete read-only audit and candidate CI/migration tests.
2. Review the isolated candidate UI and migration.
3. Obtain production authorization before migration, merge, deployment or enabling the scheduled worker.
4. Apply 013, verify admin/non-admin access and unchanged mappings, then release the tested application.
5. Register approved official source pages per account. Enable the repository variable `COMPANY_ENRICHMENT_ENABLED=true` only after database/UI acceptance.
6. Verify the first source-check run and its pending observations in Admin. Review evidence before publishing changes through the Research editor.

No private enrichment payload is committed to Git or uploaded as an Actions artifact. Logs contain aggregate counts and error categories only. A successful source check is not full account verification and does not update `enrichment_checked_at`.

An account with active parent links, approved enabled sources or pending observations cannot be merged until those records are explicitly reviewed, paused or archived. This prevents a roll-up from silently stranding or reassigning ownership evidence. Historical evidence remains attached to its original account.
