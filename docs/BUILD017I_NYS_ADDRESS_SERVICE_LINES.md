# TowerSignal Build 017I — NYSDOH Address-Level Service-Line Inventory

Date: 2026-09-04

## Exact starting baseline

This source proof starts from exact `main@4bcc199f16a79c67f967c00fe5dcaf31d8ee4c59`.

It is independent of the statewide PWS/LSLI-summary branches. No production UI, Priority Score 1.0, cooling-tower behavior, procurement, auth/RLS or deployment behavior is modified.

## Authoritative source

NYSDOH publishes `New York State Lead Service Line Inventory` as Health Data NY dataset `j63k-4n92`.

The current published schema contains exactly 20 source fields:

1. Service Line Locality
2. Street Address
3. Zip Code
4. State
5. Lead Gooseneck, Pigtail or Connector Currently Present
6. Current Public Side SL Material
7. Was Public SL Material Ever Previously Lead
8. Public SL Material Verification Method
9. Public SL Installation or Replacement Date
10. Public SL Size
11. Customer SL Material
12. Customer SL Material Verification Method
13. Lead Solder Present
14. Building Type
15. POU or POE Treatment Present
16. Customer SL Installation or Replacement Date
17. Customer SL Size
18. SL Category
19. Note
20. Location

The line-level source does **not** publish PWSID. TowerSignal therefore does not infer a PWS relationship from locality, ZIP or address.

## Coherent snapshot strategy

The source has no authoritative row ID suitable for deterministic offset pagination and contains legitimate repeated addresses/source rows. Build 017I therefore uses one coherent bulk CSV export rather than pretending offset order gives durable source identity.

The workflow:

1. reads authoritative metadata, exact row count and update timestamps;
2. requires the exact ordered 20-field schema;
3. refuses this strategy if the live source grows above five million rows;
4. downloads one CSV export with a five-million-row limit to a temporary file;
5. records source-byte SHA-256 and byte count;
6. parses CSV with a standards-compliant parser so embedded newlines/commas remain valid;
7. preserves every source row and all 20 source fields;
8. writes a compressed normalized CSV;
9. re-reads source metadata/count after processing;
10. deletes/refuses the output if source row count or source update timestamps changed during the snapshot;
11. independently re-reads every compressed normalized row before acceptance.

A partial or mixed-version export therefore cannot pass merely because a summary file was produced.

## Source identity and duplicates

There is no durable line-level source record ID in this dataset.

TowerSignal preserves:

- `source_row_ordinal` — unique only within the exact coherent snapshot; never represented as a longitudinal source identifier;
- `service_address_id` — deterministic normalized locality + street address + ZIP grouping key.

`service_address_id` is deliberately **non-unique**. Multiple service-line rows at one address are legitimate and every source row is retained. Build 017I performs no exact-row or address deduplication.

## NYC source pattern

NYC rows commonly use locality codes `MN`, `BX`, `BK`, `QN`, and `SI`. TowerSignal adds a borough analysis label for those exact codes only.

This does not collapse or reinterpret the current NYC source-row pattern. If NYSDOH supplies multiple rows at the same NYC address, all rows remain separate until a stronger source defines their relationship.

## Conservative normalization

All source strings remain present. Additional normalized categories are comparison/analysis fields only.

### Materials
Recognized explicit/case/punctuation variants map to conservative categories such as:

- LEAD
- COPPER
- PLASTIC
- GALVANIZED
- KNOWN_OTHER
- UNKNOWN_COULD_BE_LEAD
- UNKNOWN_UNLIKELY_LEAD
- UNKNOWN
- NON_LEAD_OTHER

Any material text outside explicit supported variants remains `OTHER_RAW`.

### Verification methods
Recognized explicit variants map to:

- RECORDS
- NOT_VERIFIED
- FIELD_INSPECTION
- STATISTICAL_MODEL
- EXCAVATION
- CUSTOMER_IDENTIFICATION
- SEQUENTIAL_SAMPLING
- OTHER

Unrecognized free text remains `OTHER_RAW`.

### SL category
Explicit source categories such as Lead, Non-Lead, GSLRR and Unknown receive normalized labels. Source error strings such as `Err:508` remain `SOURCE_ERROR`; they are not silently treated as a material classification.

## Location

Valid source point geometry is normalized to latitude/longitude only when it falls within conservative New York geographic bounds. The raw source `Location` field is always retained.

## Additional domestic-water intelligence

The source also contains building type, lead solder, gooseneck/connector, installation/replacement dates and sizes, POU/POE treatment presence and free-text notes. These fields are retained without converting free-text claims into unsupported provider/property relationships.

## Acceptance

Do not advance this increment based on code alone. The live workflow must prove:

- current authoritative schema;
- exact multi-million-row source count;
- one coherent snapshot with stable before/after source state;
- parsed count exactly equal to source count;
- all raw fields preserved;
- no invented PWSID;
- every source row retained;
- compressed cache re-read row-for-row with no ordinal gaps;
- normalization summaries independently reconciled;
- realistic location/NYC volume;
- artifact revalidation after download;
- complete repository Python/frontend/lint/typecheck/build gate.
