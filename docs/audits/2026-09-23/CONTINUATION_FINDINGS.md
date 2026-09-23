# TowerSignal lineage audit — continuation, 23 September 2026

## Status and evidence boundaries

This is a diagnostic checkpoint, not completion of the all-source audit, a repair, or hosted-release acceptance. No production file, production data, score, UI, deployment configuration, authenticated workflow state or workflow concurrency was changed by this continuation. All repository writes are on `audit/full-lineage-20260923-1350`.

Inspected code: `f1cbdb925b704a8b7a34aaccd169be6649b80a92`. Earlier served snapshot: Pages #241, source `567afc00df97da06486b55b7749ca101ed069ec4`, run `35848062959`, captured 2026-09-23 14:06:21–14:08:22 UTC. The captured systems response SHA256 is `8c5b04ab588cfae774703c7e7d6fe67a9f6e84852a85ab36d1c21b88c803c141`.

During the continuation the canonical Pages #242 build completed independently. Its exact downloadable artifact was inspected, not assumed to be served: run `35866906472`, artifact `10759814013`, source `f1cbdb925b704a8b7a34aaccd169be6649b80a92`, archive SHA256 `b989f5da4a4f37320a5ab026cb518391fb7556ddb8a324e928947c9e1826d66a`. Archive bytes were hashed and matched this digest before inspection. Source build timestamp in its NYC payload is `2026-09-23T13:32:14.925138Z`. Build/deployment/served/hosted-verified remain separate states; consult the current workflow for deployment status.

## 1. Confirmed correct behavior and newly tested scope

Against the Pages241 captured population, 34,251 independent record/value MULTISET comparisons passed: 4,893 accounts times five NYC building-water families, legacy DOB and CMS. There were zero dropped, extra or changed compact rows against their captured caches. Full values and multiplicity were compared, not merely counts or normalized IDs. This proves the checked attachment layer, not safe identity or full publisher retrieval.

Across 609,067 retained source-cache rows, 68 direct field contracts passed 7,930,905 independently implemented raw-to-normalized comparisons with zero mismatches. The families contained 190,233 311 rows, 184,528 HPD water-violation rows, 75,019 DOB job rows, 56,028 permit rows and 103,259 LL84 rows. The independent checker did not import the production normalizers. It checked retained `raw` values; it was not a new complete official-source download. LL84 water quantities remain kgal rather than gallons or concentration units.

Another 4,893 historical-311 aggregate counts and 14,679 domestic-water summary/detail counts agreed. Historical event identities cannot be proved from that aggregate cache because complete source event IDs are not retained there.

Actual pinned account firm-role selectors were mechanically type-stripped with Node and executed against every captured account. They emitted 157,210 role rows for Pages241. Independently reconstructed unsafe-key observations agreed exactly with the actual selector results. This is actual client-selector execution, not authenticated browser rendering. No app source or production dependency was modified.

The new Pages242 artifact has exactly the same 4,893 system IDs as the earlier capture. All 4,893 HPD summary/detail contact counts agree, and no `BIN_EXACT` HPD registration in the artifact disagrees with its account BIN or uses a borough-only placeholder.

## 2. Genuine source gaps versus unresolved gaps

The earlier full NYC registry/duplicate census remains the evidence for 511 blank public sample-date cases. This continuation does not turn inspection dates, domestic-water results or outbreak information into cooling-tower samples.

In Pages242, 400 West 61st (`2000014227`) still has no published registry sample dates, but has five inspection events, four HPD contacts, owner `RCB1 NOMINEE LLC`, and 12 recent ACRIS documents in summary and detail. Its canonical BBL is `1011717513`, with source-supported alias `1011710154`; HPD BIN is `1089723`. This is artifact evidence, not a fresh screenshot assertion.

For NYS, 6,244 stored equipment IDs/property-group projections and 18 stored summary metrics were independently recomputed without discrepancy. There are 363 stored records lacking a sample date or result: 99 missing dates and 332 missing results, including 68 missing both. These remain UNRESOLVED as source gaps because current official NYS raw rows were not recollected. They are not labelled verified missing in the publisher dataset.

The canonical NYS verifier checks five equipment rows (`pages.yml:284`) and imports `normalize_nys_registry`, the same normalizer used by the builder. It is a sampled freshness comparison, not independent full-population source validation. The previous audit ledger's `nys-details` consumer entry was corrected: the inspected builder emits `nys-systems.json` and `nys-metadata.json`, not per-equipment detail shards.

## 3. Incorrect attribution: earlier release and new artifact must not be conflated

### Pages241 confirmed failure population

The expanded bad-BIN account attachment census totals 488 rows across disjoint evidence families:

| Family | Unsupported account attachment rows |
|---|---:|
| Facade compliance | 71 |
| Building footprints | 36 |
| Planimetric cooling-tower geometry | 17 |
| Drinking-water self-report history | 307 |
| Drinking-water compliance history | 11 |
| LL84 water benchmarks | 22 |
| HPD building-water violations | 21 |
| DOB water permits | 3 |

These are account-to-record attachment rows, not 488 distinct publisher events. Thirteen accounts use placeholder BINs. Keep the separately identified registration-ID-zero contacts and firm relationship edges at their own grains; do not add those counts to this table.

Example: Wollman Rink (`2000001474`) received a drinking-water inspection for 4 Times Square, BBL `1009950005`, through BIN `1000000`. The record names Nalco and EMSL and inspection date `12/20/2025`; it is not a Wollman cooling-tower inspection.

Actual client selectors promoted these bad attachments to 548 `CONFIRMED` drinking-water service-role rows across 12 accounts and 98 account/firm pairs. The earlier release's 13,638 firm detail shards contained 154 unsafe firm-site rows across 139 firms, with 340 tower-account relationship edges. These are separate downstream manifestations, not additional unique source records.

First incorrect stage: treating a borough-only placeholder as a unique building identifier. Later attachment, company projection and confidence labeling preserve/amplify that mistake.

### Pages242 artifact result

All 13 former placeholder system BINs are now null/unused as join keys. The previously identified 488 unsafe account attachments are absent from the inspected affected families; their geometry/facade rows and bad-BIN domestic/building-water rows are zero. The associated erroneous drinking-water service-role rows are zero. Placeholder firm sites have zero tower-account links. This is artifact-level evidence of PR306's effect, not blanket acceptance of the entire product or a fresh hosted response.

545 West 112th (`2000001046`) now has zero attached contacts for source registration ID `0`, with explicit `UNUSABLE_SOURCE_REGISTRATION_ID`, rather than the earlier 42 unrelated contact rows. Its owner remains separately sourced, not inferred from those removed contacts.

## 4. Defects still reproduced in the Pages242 artifact / pinned client

### F1 — Firm market sites still collapse distinct parcels

The new artifact has 13,777 firm detail shards. Although tower-account links through placeholder keys are gone, 34 firm sites still use placeholder BIN identities. Resolving their retained normalized inspection IDs into the new 62,972-row domestic-water inspection cache proves that 14 sites across 10 firms combine observations from multiple distinct BBLs and addresses. This is a confirmed lower bound because each firm's source-reference list is capped at 25 IDs.

Example: `EMSL Analytical`, site `NYC-BIN-1000000`, combines source BBLs `1005977503`, `1007290060`, `1008150026`, with addresses 110 Charlton Street, 395 9th Avenue and 1045 Avenue of the Americas. These are not one building merely because the publisher used the same placeholder BIN.

First failing stage: `scripts/towersignal/known_firms.py`, `_system_site_key`, `_site_from_systems` and `site_for_identity` accept a nonempty BIN and construct/merge a site around it. Minimal repair candidate: validate assigned BINs at site identity creation, then use independently supported parcel/property identity or retain separate unresolved source observations. Do not merge by address alone and do not remove valid observations. No such repair was applied by this audit.

### F2 — DOB provenance claims exact BBL when the actual link is BIN

Pages241 had 39 affected input records, producing 36 role rows across five accounts. In Pages242, the three placeholder-linked roles are removed, but 33 emitted role rows remain across accounts `2000004045` and `2000015696`. Their records are linked through assigned BINs; the pinned `addDobWaterRole` still emits literal `BBL_EXACT` and source-reference text `exact BBL`.

First failing stage: client provenance mapping in `src/domain/accountEvidence.ts`, not the existence of the source record. Minimal repair: carry the actual validated match basis into the role row and text. Do not change score weights or invent a BBL relationship to match the existing label.

### F3 — Building-water preview hides records and newer permits

`BuildingWaterSignalsSection.tsx` uses unconditional `.slice(0, 8)` for four groups. DOB jobs are concatenated before permits and the combined sequence is then truncated; the component has no show-more control. The records remain present in detail JSON, so this is not a collector drop.

In Pages241, 1,488 capped account/group instances affected 1,360 accounts and left 31,320 attachment rows outside this component's preview. All permit cards were outside the preview for 785 accounts; 398 had a hidden permit newer than every preview card.

The defect remains with the Pages242 data: 786 accounts have no permit in the preview because at least eight job filings precede the permits; 399 have a newer hidden permit. These counts come from exact pinned component expressions applied to the artifact, not authenticated screenshots. Other routes/raw JSON are not claimed to omit those records.

Minimal repair candidate: preserve approved layout while exposing a clearly labelled bounded preview with an explicit full-list path, and define a merged chronological DOB order. This requires separate repair authorization and visual/PDF regression acceptance; it was not changed in this audit.

## 5. Additional defensible opportunities and observation-grain risks

The frozen old cache with main's independently reviewed identity replay yields 175 added and 57 removed account-record edges across 40 accounts. These are different relationship edges, not 175 newly discovered publisher rows; validate against a newly accepted source release before promotion. The earlier 1,237 validated base-lot opportunities and 37 unpromoted candidates retain their original status.

A full cached-ID multiplicity census found 8,800 repeated normalized-ID groups. Of these, 8,225 contain nonidentical normalized rows: 14 DOB job groups, 8,012 permit groups and 199 LL84 groups. All rows are retained by the tested cache/detail multisets. This is a grain/collision risk for future deduplication/upserts, not evidence that those rows are already lost.

Example: permit `B00193739-I1-PL` uses one activity ID for sequence 1 issued 2024-03-22 and sequence 2 issued 2024-12-30. Distinguish a permit identity from its issue/renewal observations rather than discarding a valid version to make IDs unique.

Toronto is explicitly a separate implementation scope. The `TowerSignal-Toronto-Preview` README reports a Sept 3 preview pinned to source `a535195e32eb2be7397eafd709ec0eba013e6890`. That historical documentation is not current hosted verification or an audited Toronto source census. Main's NYC/NYS loader has only marketing references to Toronto; historical Toronto branches and the separate preview must not inflate NYC coverage.

## 6. Ledger and verification coverage

The combined source-field ledger retains 1,288 enumerated fields: 158 USED, seven UNUSED_POTENTIALLY_USEFUL, and 1,123 UNRESOLVED. Sixty-eight fields gained an independent retained-raw/value check. USED is not a claim of a complete official-source-to-authenticated-renderer trace.

The application register contains 2,218 entries: the prior 2,171 inventory candidates plus 47 explicit selector/component/aggregate traces. It is not a count of unique visible fields or a completed route-state denominator. The mapping register contains 95 entries after adding 11 continuation contracts. The source register has 55 entries including derived datasets and an explicit Toronto scope record; that scope row is not another independent feed.

Current authenticated visual coverage remains zero for this audit. Earlier read-only captures reached sign-in. No current export/PDF correctness, authenticated workflow-state behavior, full browser route matrix or current hosted data-origin equality is claimed.

Fresh complete official-source retrieval in this continuation: zero. Existing timestamped raw/schema captures and exact artifact bytes were reused. Direct external retrieval from the runtime failed; no failed or unqueried request was classified as a zero-row source.

## 7. Persistence, reproduction and next actions

The downloadable continuation checkpoint contains the merged four ledgers, prior censuses, expanded attribution records, full record/value reconciliation, actual selector outputs, source-field tests, NYS unresolved census, Pages242 manifests and comparisons, scripts, hashes, and continuation state. This document and compact continuation ledgers are persisted on the isolated audit branch. The entire combined machine ledger bundle is not claimed committed to GitHub; remote persistence remains itemized work.

Raw source evidence references: stage1 run `35870554694`, artifact `10755386489`; stage2 run `35871731541`, artifacts `10755697091` (identity/hosted) and `10755343139` (public browser); Pages241 artifact `10747891216`; Pages242 artifact `10759814013`. Audit output hashes and exact input archive hashes are retained in the downloadable manifest. No fonts, credentials, session state or production cache changes are part of the audit report package.

Nine local checkpoint-integrity tests pass. They validate accounting and proof boundaries; they are not additional source retrieval, a repair acceptance suite or browser verification.

Prioritized repair/acceptance sequence (not executed):
1. Validate identities at firm-market site creation and split the 14 demonstrated multi-parcel collapses; preserve observations and unresolved cases. Reconcile every affected firm, site, account link and map projection.
2. Correct the 33 actual match-basis labels by carrying verified provenance; test BIN-only, BBL-only, ambiguous and no-key cases.
3. Add reviewed access/chronology behavior for the building-water preview without altering approved unrelated UI or PDF appearance.
4. Formalize record-versus-observation identity before any deduplication or upsert; test permit sequences, amended filings, LL84 repeated submissions and full row multiplicity.
5. Complete independent official NYS and remaining source-population retrieval, remaining 1,123 field dispositions, per-consumer history/company/portfolio/workflow/export lineage, and the authenticated renderer matrix.
6. Independently establish current hosted application/data provenance and replay the negative/positive regression population against the accepted release. Canonical green CI or deployment alone is not completion.
