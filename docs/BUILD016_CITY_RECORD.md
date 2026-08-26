# TowerSignal Build 016B — NYC City Record Procurement

Build 016B connects the official NYC City Record Online dataset (`dg92-zbpx`) as the first production procurement source.

## Source

- Dataset: NYC City Record Online
- Publisher: NYC Department of Citywide Administrative Services (DCAS)
- NYC Open Data dataset ID: `dg92-zbpx`
- Update frequency: daily
- Source page: `https://data.cityofnewyork.us/d/dg92-zbpx`

The source contains solicitations, awards and other official City Record notices. TowerSignal queries the authoritative dataset directly rather than relying on community-created filtered views.

## Bounded production scope

Production does not download the full ~1.1M-row City Record on every Pages build.

It deterministically retrieves and validates:

1. every `Solicitation` record whose `due_date` is on or after the build date;
2. every `Award` record whose `start_date` falls within the previous 730 days.

For each scope TowerSignal first performs an exact source-side count, then paginates in `request_id ASC` order and fails closed if the retrieved count differs, a page ends early, rows are malformed, IDs are missing or duplicate IDs appear.

The full dataset row count is also queried separately for source reporting. The bounded scope and its exact SoQL predicates are stored in the output metadata.

## Classification

All rows in the bounded source scope are retrieved before service classification. TowerSignal then applies the Build 016A service taxonomy and emits only records classified as relevant or `VERIFY`-level adjacent service evidence.

Each emitted record preserves:

- raw/source text;
- matching classification terms;
- classification reason;
- confidence;
- full raw source row;
- source notice/document link when supplied;
- source record ID, PIN, agency, notice type/category and selection method;
- due/start/end dates;
- contact data;
- award vendor where present.

Broad phrases such as `water services` remain `VERIFY`. Negative-context tests ensure bottled water, water meters, stormwater and swimming-pool procurement are not promoted as cooling-tower intelligence solely because they contain water-related terms.

## Contract amounts

City Record `contract_amount` is preserved when present, but TowerSignal labels it `SOURCE_REPORTED_UNVALIDATED`. It is not used as total company revenue, a complete contract-book value, or a production deal score. Historical contract-value intelligence is expected to rely primarily on the later Checkbook NYC/Open Book normalized contract sources.

## Company and facility linkage

Build 016B does not silently resolve vendors or attach procurement records to cooling-tower properties.

- award vendor names are retained as raw evidence;
- unresolved award vendors are counted in source health;
- company identity resolution is Build 016E work;
- facility/tower linkage remains `UNLINKED` until a conservative evidence-backed linkage stage is implemented.

## Production payload

The Pages build writes:

`public/data/procurement-city-record.json`

The payload contains source metadata, exact scoped counts, relevant counts, service-category counts, procurement source health and source-backed normalized notices.

No mock procurement records are emitted.
