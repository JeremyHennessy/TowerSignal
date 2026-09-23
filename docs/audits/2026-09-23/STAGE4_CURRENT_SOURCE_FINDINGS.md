# Stage 4 current-release independent source census — 2026-09-23

## Evidence boundary

Read-only audit run **35885600439** executed against the served TowerSignal release and current official publisher data from 2026-09-23T15:59:50Z through 16:02:31Z. It did not import the production HPD, PLUTO or NYS normalizers for the independent comparison and made no production writes.

Evidence artifact: **10761938674** (`lineage-stage4-current-source-census`), SHA-256 `34869a7b542cafb10f4913e01cf78b8ad755c1749b4bd85eb1f5cb65f34e59bd`, 13,048,397 bytes, expires 2026-10-07T16:02:34Z.

Hosted NYC systems response remained byte-identical throughout collection: 4,893 systems, SHA-256 `e90ad86b1e0ec033ffff1064a0152f3d619e65acef7eab3828489e5abfc26ad8`.

## NYS registry: source gap uncertainty resolved

The complete current NYS weekly extract (`24a4-muw7`) was retrieved with stable metadata and count-before/count-after checks:

- Raw rows: **6,244**
- Unique source row IDs: **6,244**
- Normalized Equipment_ID rows independently reconstructed: **6,244**
- Hosted Equipment_ID rows: **6,244**
- Fresh-only IDs: **0**
- Hosted-only IDs: **0**
- Compared normalized field-value mismatches: **0**
- Source duplicate Equipment_ID rows: **0**
- Missing Equipment_ID rows: **0**

The prior 363 unresolved missing-date/result records are now classified against the complete current publisher snapshot:

- **363** equipment records lack a normalized latest sample date or latest result.
- **99** have source sample date value `NA`; these are **MALFORMED/SENTINEL SOURCE VALUES**, not collector loss and not blank dates.
- **332** have a **BLANK_IN_SOURCE** latest sample-result field.
- **68** have both source date `NA` and blank result.
- The remaining missing-result cases have a valid published date but no published latest result.

This proves those 363 gaps are source-native in the checked weekly extract as of the audit query. It does not establish anything about unpublished/private sampling.

## PLUTO owner census: all 785 blank product owners explained

The current canonical TowerSignal BBL universe contains 3,804 distinct requested PLUTO BBLs. Exact current source queries returned 3,775 BBL records with stable source metadata.

Across all 4,893 accounts:

- Product/source owner value mismatches where a PLUTO row exists: **0**
- Accounts whose matched PLUTO row publishes owner blank/unavailable: **705**
- Accounts whose canonical BBL has no matching PLUTO row: **80**
- Total explained blank product owners: **785**

Therefore the 785 blank owner values in the current release are not demonstrated TowerSignal owner drops. They are either blank/unavailable in the checked PLUTO record or have no matching current PLUTO row on the canonical BBL.

## HPD registrations and contacts: two parcel-level evidence cases, not safe building-contact joins

The complete HPD Multiple Dwelling Registrations dataset (`tesw-yqqr`) was independently retrieved:

- **203,887 / 203,887** source rows
- **203,887** unique row IDs
- Stable source revision throughout retrieval

Contacts (`feu5-w2e2`) were queried by the full independently selected registration-ID universe:

- **8,860** unique scoped contact rows
- Every batch remained below the API cap
- Stable source revision throughout the query

Current product HPD status counts are:
- MATCHED: 2,129
- VERIFIED_EMPTY_CONTACTS: 24
- NO_REGISTRATION_ON_CHECKED_KEYS: 2,720
- AMBIGUOUS_HPD_BUILDING_PROPERTY: 7
- IDENTITY_UNRESOLVED: 10
- UNUSABLE_SOURCE_REGISTRATION_ID: 1
- COLLIDING_SOURCE_REGISTRATION_ID: 2

The independent alias-aware source scan found two additional HPD registrations reachable only through a corroborated base-lot alias. They are **not safe to promote as building-specific contacts** because the source registration BIN differs from the TowerSignal building BIN:

### 2000015727 — 45 Rivington Street
- TowerSignal current BIN: `1005601`
- Canonical BBL: `1004207502`
- Corroborated base-lot/registry alias: `1004200047`
- HPD registration BBL: `1004200047`
- HPD source BIN: `1000000` (borough-only placeholder)
- Registration ID: `119842`
- Last registration date: 1993-04-01
- Scoped contact rows: **0**

Disposition: **PARCEL_LEVEL/HISTORICAL SOURCE REGISTRATION; no building-specific contact attachment.** Product status currently says `NO_REGISTRATION_ON_CHECKED_KEYS`, which is stricter than the total source-evidence picture.

### 2000015832 — 125 West 57th Street
- TowerSignal current BIN: `1091067`
- Canonical BBL: `1010107509`
- Corroborated base-lot/registry alias: `1010100015`
- HPD registration BBL: `1010100015`
- HPD source BIN: `1023724`
- HPD published address range: 123–141 West 57th Street
- Registration ID: `110313`
- Last registration date: 2020-10-23
- Scoped contact rows: **6**

Disposition: **PARCEL_LEVEL SOURCE REGISTRATION WITH CONTACTS FOR A DIFFERENT SOURCE BUILDING ID/BIN.** Do not attach these six contacts as contacts for TowerSignal BIN `1091067`. A future UI/model improvement may expose the existence of parcel-level registration evidence separately instead of the narrower `NO_REGISTRATION_ON_CHECKED_KEYS` label.

These two cases are therefore not counted as wrong-building contact omissions. They are a **source-evidence classification/presentation opportunity**.

## Hosted #242 acceptance update

Canonical Pages run **35866906472** completed build, deploy, hosted desktop Chromium and iPhone/WebKit verification successfully.

Hosted verification:
- **92 passed**
- **12 test-defined skips**
- **0 failed**
- browser report artifact **10762656492**
- report artifact SHA-256 `baab998bdc1d7dee6cd4623938d97bdf378b135ceab1b479dd404d3223f1f6a8`

This establishes the canonical #242 served/hosted-verified state for the workflow's tested surfaces. It does not eliminate the separately reproduced firm-site identity, DOB provenance-label, or bounded-preview defects, because those mechanisms were not acceptance assertions in the hosted suite.

## Remaining actions from this stage

1. Keep the two HPD alias-only cases quarantined as parcel-level context; do not attach them as building-specific contacts.
2. Add a distinct parcel-level HPD evidence state only if a repair is separately reviewed; preserve current safe contact attachment policy.
3. Use the fresh NYS census to reclassify all 363 missing date/result cases in the source-field/missing-data ledgers.
4. Use the PLUTO census to reclassify all 785 blank owner cases.
5. Continue full-population proofs for the three isolated repair candidates before any merge consideration.
