# Stage 4 resolution — current hosted data vs current official sources

Audit basis: hosted TowerSignal release data served during run 35885600439; complete current HPD registration snapshot `tesw-yqqr`; exact registration-ID contact scope `feu5-w2e2`; exact canonical-BBL PLUTO scope `64uk-42ks`; complete NYS cooling-tower registry `24a4-muw7`. No production code or data was changed.

## Hosted population stability

- 4,893 NYC systems and all 4,893 detail payloads were retrieved.
- The hosted systems response was byte-stable before/after the census.
- HPD registration snapshot was complete/stable.
- Scoped HPD contact retrieval was stable and below query caps.
- PLUTO exact-BBL scope was stable.
- NYS source snapshot was complete/stable.

## HPD contact reconciliation correction

The independent stage-4 reconstruction initially reported two product-status discrepancies because it allowed HPD lookup through every source-backed BBL alias. That is too broad for a building-specific HPD contact claim.

### 2000015727 — 45 Rivington St

- Current assigned BIN: `1005601`.
- Canonical property BBL: `1004207502`.
- Registry/base alias: `1004200047`.
- Alias evidence: Building Footprints exact-BIN bridge; `confirmed_footprint_base_alias=1004200047`; reconciliation basis `REGISTRY_BASE_BBL_TO_MAPPLUTO_BBL_EXACT_BIN`.
- HPD registration on base alias: registration `119842`, building `804847`, source BIN `1000000`, registration date 1993-04-01.
- HPD contact rows for registration 119842: 0.
- Product status: `NO_REGISTRATION_ON_CHECKED_KEYS`.

Disposition: **PRODUCT CORRECT / AUDIT-METHOD FALSE POSITIVE.** The HPD record belongs to the independently supported base parcel but does not identify the current building BIN. It is historical/parcel context, not a defensible building-specific HPD registration/contact attachment.

### 2000015832 — 125 W 57th St

- Current assigned BIN: `1091067`.
- Canonical property BBL: `1010107509`.
- Registry/base alias: `1010100015`.
- Alias evidence: Building Footprints exact-BIN bridge; `confirmed_footprint_base_alias=1010100015`; reconciliation basis `REGISTRY_BASE_BBL_TO_MAPPLUTO_BBL_EXACT_BIN`.
- HPD registration on base alias: registration `110313`, building `34302`, source BIN `1023724`, registration date 2020-10-23.
- Six source contacts exist on registration 110313, including Calvary Baptist Church and a SiteManager.
- Product status: `NO_REGISTRATION_ON_CHECKED_KEYS`.

Disposition: **PRODUCT CORRECT / AUDIT-METHOD FALSE POSITIVE.** The source registration's BIN differs from current TowerSignal building BIN `1091067`. The source contacts are attached to the base-parcel HPD building/registration, not independently proven to be current building-specific contacts for 125 W 57th. They may be retained as separately labelled historical/parcel-level evidence, but must not be promoted as confirmed building contacts.

Correct independent HPD rule: assigned BIN exact first; canonical parcel exact only when no assigned-BIN registration exists and the registration can safely represent the current building. A corroborated base-lot alias alone is insufficient to convert a different HPD building into a building-specific contact match.

## PLUTO owner census

- Canonical BBLs requested: 3,804.
- Source BBLs matched: 3,775.
- Product/source owner value discrepancies: 0.
- 705 matched source rows have blank/unavailable owner.
- 80 accounts have no matching PLUTO row in the exact canonical-BBL scope.

The last two populations are source/no-row gaps, not normalization discrepancies. They remain separately classifiable from HPD contacts.

## NYS complete current source census

Official source: NYS Cooling Tower Registry Weekly Extract `24a4-muw7`.

- Raw source rows: 6,244.
- Unique normalized equipment: 6,244.
- Hosted equipment: 6,244.
- Fresh-only equipment IDs: 0.
- Hosted-only equipment IDs: 0.
- Independently compared normalized field mismatches: 0.
- Duplicate equipment source rows: 0.
- Missing equipment-ID rows: 0.

### Missing sample date/result census

Exactly 363 source rows lack a usable date or result:

- 99 have no usable date. **Every one is the literal publisher sentinel `NA`**, and every one also has blank `Last_Sampled_Days`.
- 332 have a blank official `Equipment Last Legionella Test Result`.
- 68 have both `NA` sample date and blank result.
- No current source row has an actually blank date field in this 99-row set; the source explicitly publishes `NA`.
- Of the 332 blank-result rows, 315 have source `CT_Status = Missing Legionella Result`; 17 have source `CT_Status = Legionella Sampled`.
- Of the 99 `NA` date rows, 68 have `CT_Status = Missing Legionella Result` and 31 are `Decommissioned`.

Disposition:
- Date field: `NA` must be treated as a source sentinel / no usable published sample date, not as an ISO-date parse defect.
- Result field: 332 are **BLANK_IN_SOURCE** for the current complete source snapshot.
- The 363 cases are now source-verified gaps for this source snapshot, not unqueried/unverified cases.
- Source status values remain distinct from independent claims about operating status or whether a sample was physically collected.

## Evidence files

The exact machine evidence is in the stage-4 artifact from run 35885600439 (artifact 10761938674; SHA256 `34869a7b542cafb10f4913e01cf78b8ad755c1749b4bd85eb1f5cb65f34e59bd`) and compact persisted stage-4 files on this audit branch.

