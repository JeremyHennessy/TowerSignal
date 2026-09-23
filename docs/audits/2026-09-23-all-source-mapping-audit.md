# TowerSignal — independent source mapping audit, 23 September 2026

## Scope and provenance

This is an audit, not a production fix or deployment acceptance. No production data or application code was changed by this audit. Diagnostic collection ran on the isolated `audit/source-mapping-20260923` branch.

- Inspected application source baseline: `567afc00df97da06486b55b7749ca101ed069ec4` (merged PR #305).
- Published identity-release artifact: run `35803035405`, artifact `10727730698`, SHA-256 `309a0c972dc0641aced39e58b726644740b5f39af2af8b3789b03d4f739e651b`.
- Live systems.json independently captured during the audit equals that artifact's systems.json. All 4,893 NYC account detail files from the deployed artifact were examined. The target 400 West 61st detail was also retrieved directly from the live host.
- Independent primary-source capture: run `35851364952`, artifact `10746095517`, SHA-256 `dd99fc1bf5ffe6e6413c0be12068a27396f22a9c21635d944f3a3c76e6720811`.
- Supplementary primary-source capture: run `35852331731`, artifact `10746047041`, SHA-256 `54811b6e306cdcdc2d7118e6a5135e990f48b6b4d30d1c5855e4efb2a305689e`.
- 86 timestamped request records, with URLs and response hashes, span 10:53:36–11:07:18 UTC on 23 September. Both collection runs completed successfully; recorded collection errors are empty.
- Canonical production rebuild `35848062959` is separate. At the last audit status check it was still building NYS LSLI details, after core NYC enrichment and the 400 West 61st build-time acceptance passed. Deployment and hosted acceptance had not occurred. Do not label the defects below fixed in production.

## What was freshly checked

Independent collectors used direct public APIs, not the production collectors, with explicit paging, source counts, and before/after source-update checks for the full captures.

| Source | Independently fetched rows | Scope |
|---|---:|---|
| NYC cooling-tower registry, y4fw-iqfr | 5,944 | Complete source; 4,893 unique systems; all duplicate rows examined for sample-date loss |
| NYC cooling-tower inspections, f9wb-g8mb | 125,065 | Complete source; 32,778 normalized events for current systems |
| HPD registrations, tesw-yqqr | 203,887 | Complete source; search current BBLs, preserved aliases, and exact BINs |
| HPD contacts, feu5-w2e2 | 11,204 | All returned contacts for 2,532 relevant registration IDs, representing 2,533 registration rows |
| Drinking-water tank self-reports, gjm4-k24g | 62,972 | Complete source; all-account exact-BIN count comparisons |
| Drinking-water compliance, rytv-g5ui | 26,842 | Complete source; all-account exact-BIN count comparisons |
| NYS cooling-tower registry, 24a4-muw7 | 6,244 | Complete current extract; source-native equipment ID comparisons |
| Building footprints, 5zhs-2jue | 2,074 | Targeted non-placeholder BIN retrieval; returned identity pairs compared with retained footprints |

The published-cache audit also replayed exact identity attachment for current 311 water requests, HPD water violations, DOB water jobs and permits, LL84, property enforcement, legacy DOB, CMS, and historical 311. Other families received retained-artifact, source-coverage, and identity-contract review. This is NOT a claim that every upstream procurement, court, laboratory, CMS, ACRIS, or PWS record was freshly re-downloaded. The companion inventory explicitly labels each verification level. Its 42 rows comprise 21 base-source entries, 20 overlapping auxiliary artifacts, and the NYS registry—not 42 independent feeds.

## 1. Missing NYC sampling: source blanks, not lost dates

All 511 NYC systems without a published sample date have a blank sampledates field in EVERY matching row of the fresh registry. There were zero dates lost in parsing, zero duplicate-row sample-date losses, and zero published-vs-fresh normalized date differences across all 4,893 systems. All 511 have the NO_PUBLIC_SAMPLE_DATE warning; 472 also have public inspection events. All 511 show positive active-equipment counts in the registry.

Interpretation: no usable public date in this registry. This does not establish that no sampling occurred, a Legionella-positive result, or an outbreak. Drinking-water tank tests, distribution-water samples, and ZIP-level results must not be substituted for system-specific cooling-tower sampling.

Primary source: https://data.cityofnewyork.us/Health/NYC-Cooling-Tower-Registrations/y4fw-iqfr

## 2. Missing HPD contacts: 57 confirmed false zeros and 19 follow-up cases

The published systems summary lists 2,828 systems with zero HPD contacts. Mutually exclusive audit classifications are:

| Classification | Systems |
|---|---:|
| Summary says zero, but account detail already contains contacts | 57 |
| Exact non-placeholder BIN leads to contact-bearing HPD registration; property reconciliation needed | 15 |
| Omitted footprint base BBL leads to contacts; controlled alias review needed | 3 |
| Other historical/same-parcel registration contains contacts; not a safe automatic building match | 1 |
| Canonical HPD registration found without usable contact rows | 20 |
| No HPD contact match on the checked valid keys | 2,732 |
| Total | 2,828 |

The last group is NOT proof that no owner, manager, or contact information exists anywhere. Among the 2,828 HPD-zero accounts, 2,577 have a substantive PLUTO owner value in their detail data; another 170 contain the placeholder UNAVAILABLE OWNER and 81 have no owner value. An owner entity name is useful context but is not a verified phone/email contact.

HPD's published contact schema provides names, roles, organizations, and business addresses; it has no phone or email columns. Preserve the distinction between absent HPD contacts and absent outreach channels.

Concrete independently checked candidates:

- 15 East 26th Street, system 2000003056: current BBL 1008567503; exact-BIN footprint base lot 1008560011; HPD registration 144936 has five contacts on that base lot. The base lot is absent from account aliases.
- 1185 Broadway, system 2000015473: retained registry BBL 1008290030 conflicts with exact-BIN footprint/HPD property 1008307503. HPD registration 145397 has four contacts and the same address and BIN 1090462.
- 626 First Avenue, system 2000011125: registry BBL 1009610001 conflicts with footprint/HPD BBL 1009670001. HPD registration 144338 has four contacts with matching BIN 1089237 and address.
- 1 Boerum Place, system 2000014447: no current account BBL or footprint match; HPD registration 390137 supplies BBL 3001530003 and four contacts for the same BIN 3000417. HPD's address range is 1–17 Boerum Place. This is a strong additional identity route, not an address-only fuzzy match.

The dated HPD rows are source observations, not a fresh guarantee that each named party remains appointed. One other candidate, 180 East 88th Street, only has contacts on an older registration for a different BIN on the same parcel and must not be automatically imported.

Primary sources: https://data.cityofnewyork.us/Housing-Development/Multiple-Dwelling-Registrations/tesw-yqqr and https://data.cityofnewyork.us/Housing-Development/Registration-Contacts/feu5-w2e2

## 3. Confirmed unsafe matches: unknown BINs and registration ID zero

Thirteen published accounts use borough-only BINs 1000000, 2000000, 3000000, 4000000, or 5000000. NYC's source documentation explicitly describes these as unassigned/unknown identifiers. Current normalizers accept them, enabling unrelated records to join as BIN_EXACT.

Example: Wollman Rink, system 2000001474, BIN 1000000, receives 91 drinking-water self-report records. The fresh source rows contain 26 distinct address strings and 23 BBLs, including 15 West 65th Street, 50 Hudson Yards, and 945 West End Avenue. Its attached compliance addresses include 102 Charlton Street and 320 West 13th Street. This is an identity collision, not legitimate shared-building evidence. The 13-account list includes the affected source addresses and counts. Normalized address-string counts are not asserted to equal distinct buildings.

A separate contact collision affects 545 West 112th Street, system 2000001046: the app attaches 42 contacts through registration_id 0. The complete registration table contains three different registration rows using ID 0, and the fresh contacts query returns 42 rows sharing it. That key cannot establish which contact belongs to this building. Quarantine these attributions; do not choose one arbitrarily.

Primary BIN definition: https://dev.socrata.com/foundry/data.cityofnewyork.us/5zhs-2jue

## 4. Published records already present but missing from accounts

Replaying current exact aliases/BINs against published caches found 3,381 missing record attachments across 389 distinct accounts. These are account-record attachment counts; one source record can correctly attach to more than one system. There are 879 account/source-layer discrepancy rows, not 879 distinct accounts.

| Source layer | Accounts affected | Missing attachments |
|---|---:|---:|
| LL84 water benchmarks | 228 | 432 |
| Current building-water 311 requests | 45 | 237 |
| DOB water job filings | 57 | 228 |
| DOB water permits | 55 | 196 |
| HPD open water violations | 7 | 22 |
| DOB stop-work complaint/disposition history | 228 | 1,002 |
| Dated official SWO snapshot | 41 | 85 |
| Façade compliance filings | 218 | 1,179 |

The source-level and account-level data are incoherent. This cannot be explained by a public source not having those records: the records are already in the published caches. However, this audit does not claim every missing attachment is a current adverse condition. Historical SWO events include rescissions, and the separate official snapshot is dated February 2024.

Other all-account discrepancies: 114 PLUTO-match flags, 120 owner values, 121 building-area values, and 63 HPD contact counts differ between summary and details. The 57 zero-contact cases are a subset of those 63 contact-count discrepancies.

Published data examples: https://jeremyhennessy.github.io/TowerSignal/data/property-enforcement.json and https://jeremyhennessy.github.io/TowerSignal/data/nyc-water-signals.json

## 5. Additional identity coverage beyond the prior 121 bridges

The current account alias universe contains 3,900 BBLs versus 3,801 canonical BBLs. Several retained downstream caches were generated for the old 3,801-BBL scope. Zero results from those caches are not complete negative evidence for the expanded universe.

Separately, 1,231 accounts have a non-placeholder exact-BIN footprint with one base BBL and one MapPLUTO BBL agreeing with the current canonical property, yet omit the distinct base BBL from aliases. This includes 209 accounts whose BBL was recovered from footprints and 1,022 already-confirmed canonical properties. On 21 such accounts, the existing water cache alone contains 105 additional candidate record attachments under the omitted base lot. This is a lower bound; most missing base-lot universes were not fully queried upstream. Treat these as controlled alias candidates, not permission to indiscriminately combine condominium units, neighboring buildings, or multiple-candidate parcels.

The retained identity ledger still explicitly flags 44 conflicts/multiple-candidate registry identities and 40 unresolved identities. Those must remain visible as unresolved rather than masquerading as no-source-record results.

Also, 188 accounts with contacts are linked to HPD registrations whose BIN does not equal the account BIN. These may be valid parcel-level contacts on multi-building lots, not necessarily erroneous contacts. Keep property-level and building-level relationship confidence distinct.

## 6. 400 West 61st Street, system 2000014227

- Current property BBL 1011717513; preserved registry/base BBL 1011710154; BIN 1089723.
- Cooling-tower sample dates: genuinely blank in the current NYC registry.
- HPD contacts: four already present in detail and in fresh HPD registration 144666, but zero in summary.
- PLUTO owner: RCB1 NOMINEE LLC already present in detail, absent in summary.
- Eight additional building-water records exist in the cache but are absent from the account: three 311 requests, one DOB water job, and four LL84 observations.
- Thirteen historical SWO complaint/disposition records and two façade filings are in the exact-BIN cache but absent from detail. The SWO records do not mean 13 active orders. The retained façade cache includes a filing dated 27 July 2026 with source status UNSAFE; this is a source observation, not an independent current engineering assessment.
- Twelve ACRIS documents are already present in its retained account activity. Those are bounded recent recorded-document context, not a universal current-owner directory.

## 7. Freshness and inspection aggregation findings

NYS uses its own equipment IDs, not NYC BBL/BIN identity. Its fresh extract contains 6,244 records versus 6,696 on the captured live baseline: 460 previously published IDs are absent from the current extract and eight are new. Source absence is not proof of decommissioning. Twenty previously blank sample results are now populated in the source. All 99 previously missing sample dates remain blank. Refresh the feed with explicit source-membership changes and appropriate acceptance checks; do not manufacture dates or retirement status.

The drinking-water self-report source has 36 more rows than the retained market cache, producing fresh count differences at ten accounts. This is separate from the unknown-BIN contamination.

For NYC inspections, all normalized event keys and all violation sets match the fresh source. Twenty-five events across 15 accounts have conflicting status/equipment metadata depending on which duplicate source row the aggregator encounters first. The aggregator currently keeps first-row metadata. This is nondeterministic reduction of inconsistent source rows, not lost inspection or violation records. All attached OATH cases have a matching inspection summons ticket; upstream adjudication content was not independently refreshed in this audit.

## Repair order and acceptance requirements

1. Block placeholder BINs and registration ID zero as relationship keys, preserve their raw source values, and quarantine previously attributed records. Never suppress valid system-native sampling merely because a property key is unknown.
2. Establish and hosted-verify the canonical PR #305 data baseline, then rerun summary/detail and cached-record reconciliation. Do not equate successful build steps with deployment.
3. Resolve the 18 additional contact/identity candidates conservatively; keep the one historical same-parcel case separate. Expand confirmed footprint base-lot aliases with provenance and source-specific scope.
4. Replace count-only mapping acceptance with exact queried-key sets/hashes and per-account source outcomes: matched, verified empty, not queried, source unavailable, unresolved identity, stale snapshot, or out of scope. The existing validator checks selected summary fields and alias counts, not every attached record's identity.
5. Label HPD parcel contacts versus building contacts, preserve registration dates, reject UNAVAILABLE OWNER as a usable owner, and expose alternative verified owner/company context without inventing phone/email details.
6. Refresh NYS and DWT sources with explicit additions/removals, and make inspection metadata conflict handling deterministic and visible.

The companion CSV bundle contains every audited NYC sampling gap, every HPD-zero account, the 76 contact follow-ups, all 879 attachment discrepancies, the 13 unsafe BIN cases, registration-zero evidence, 1,231 base-alias candidates, 188 parcel-contact reviews, 84 unresolved/conflicting identities, all 99 NYS date gaps, 20 newly populated NYS results, source changes, and the 86-request provenance manifest.
