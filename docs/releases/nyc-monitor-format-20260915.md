# NYC Monitor table review — 15 September 2026

Baseline: merged source `30422453fd832df2baec74ff5ab10f4ecd3bf959`, accepted NYC evidence release `35034217352`, exact source runtime from candidate `35032234529` / `62bf803ce92bd469757df63030bac66338572253`. This preserves Priority 1.1, named-building links, Home intelligence and Source Health. No Azure or Toronto changes.

## Observed presentation issues

The seven Monitor categories share one table. Existing desktop and iPhone screenshots show cramped separate account-link columns; dense repeated Job/Ticket metadata; raw ISO dates in sample and filing detail values; untranslated PLUTO/derived source labels; oversized provenance borders; and hidden mobile column-sort controls. The source chronology itself must not change.

## Scoped correction

Use five columns, retaining the existing account link beside account identity. Readable field/value rows separate prior and new statuses, owner/contact values and monetary amounts. Leading-zero ticket identifiers, false booleans, zero balances and missing fields remain distinct. Dates in detail fields are calendar-formatted without altering event-date selection, order, filters or source data. Undated OATH state/balance events are not assigned hearing dates or collection dates. Violation descriptions/codes/summons remain visible.

Restrict CSS to Monitor. Adjust table widths, labels, badges, tabs, filter controls and mobile row hierarchy. Provide an accessible sort select and synchronized top/bottom pagination using the existing state. Do not change pagination size, model, data ingestion, navigation, Home, Source Health, account packs or stored history.

## Proof

Local frontend tests: 76 passed, with seven new formatting/count/navigation/pagination tests. Typecheck, lint and production build passed. Actual source-payload rendering inspected locally at 1440, 1280, 1024, 768, 390 and 320 CSS pixels; local renders are not represented as hosted evidence.

Candidate gates require accepted immediate release, original hosted byte identity, every data file unchanged, complete frontend/Python checks, full desktop/iPhone acceptance, all-route inventory and all seven Monitor categories at six widths. Specific cases include OATH penalty/balance, DOB filings, sample changes, HPD contacts, pagination, expanded provenance and empty date filters. Source-file hashes pin the locally tested transfer. The exact tested artifact is promoted only after screenshot inspection and an exact-head merge. Separate actual hosted verification rechecks HTML/assets/data, all named-building account payloads, every Monitor tab and the full browser suite. Failed acceptance restores the immediate accepted NYC runtime, not an older Home-only release.

This is formatting only: all source records, scores, publication/inspection dates and history timestamps are byte-preserved. The previously documented ACRIS refresh error and SWO/Labor Law coverage gaps are not claimed resolved by this release.
