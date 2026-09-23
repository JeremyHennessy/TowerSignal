# DOB job work-type classification finding

## Confirmed mechanism

The NYC building-water collector queries DOB job filings only when at least one of `plumbing_work_type`, `mechanical_systems_work_type_`, or `boiler_equipment_work_type_` is `YES`.

The current job normalizer retains those three source fields, but `classify_dob_work(row)` classifies from `job_description` plus a generic `work_type` field. The job-filings query does not select a generic `work_type` field.

## Population measured against served cache

Cache SHA256: `33ce3b43acddc920820cb1611b4c2b0f82d725e1bbc0bc05eb63eb2d8a5a6bd8`.

- 75,019 DOB water-job rows.
- 71,242 source-flagged Plumbing.
- 3,777 source-flagged Mechanical.
- 0 rows lacked all required work-type flags.
- 1,377 rows are currently categorized `OTHER_WATER_MECHANICAL`.
  - 1,099 of those are source-flagged Plumbing.
  - 278 are source-flagged Mechanical.

## Diagnosis

**NORMALIZATION / PRESENTATION CONTEXT LOSS.** TowerSignal retains authoritative source work-type flags but does not use them to qualify the displayed/derived category. The current broad category is not necessarily false, but it discards a source-native distinction that is available for every row in this population.

Do not rewrite categories until a precedence rule is reviewed. Multi-signal descriptions such as backflow, cooling tower, domestic-water storage, hot water, fire-water and pump terms can legitimately be more specific than the broad Plumbing/Mechanical source flag.

## Minimal integration opportunity

Use the explicit source work-type as a secondary qualifier or fallback:
- preserve the existing more-specific semantic categories when description terms support them;
- for otherwise generic rows, expose/derive the source work type rather than `OTHER_WATER_MECHANICAL`;
- retain both source flag and derived category as separate provenance;
- regression-test all 1,377 generic cases and the full 75,019-row population.

No production change was made by this audit.
