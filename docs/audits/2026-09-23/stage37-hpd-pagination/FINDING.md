# HPD current-source lifecycle and pagination adjudication

## Result

The served NYC building-water cache and a later same-day current source replay do not have identical HPD open-water violation identity sets:

- served snapshot: 184,546 open-water violation IDs
- current replay: 184,645 open-water violation IDs
- current-only: 126
- served-only: 27

The publisher metadata `rowsUpdatedAt` is identical for both observations: `1790175419` / `2026-09-23T14:56:59Z`.

## Pagination test

A fresh parity replay under that same stable source metadata compared:

- independent offset pagination, and
- the production seek-pagination rule using `violationid > cursor`.

All five borough identity sets are exactly equal:

- Manhattan: 28,514 = 28,514
- Bronx: 43,735 = 43,735
- Brooklyn: 71,181 = 71,181
- Queens: 34,594 = 34,594
- Staten Island: 6,621 = 6,621
- total: 184,645 = 184,645

Therefore the current production seek-pagination algorithm is **not dropping HPD rows**.

## Lifecycle evidence

All 27 served-only IDs still exist in the publisher but are now `violationstatus != Open`; they are current lifecycle closures.

The 126 current-only IDs are overwhelmingly recently updated records (primarily September 21–22) and are returned consistently by both current pagination methods even though the publisher's dataset-level `rowsUpdatedAt` did not advance from the value captured by the served release.

## Diagnosis

**SOURCE QUERY-STATE / METADATA FRESHNESS LIMITATION, not TowerSignal pagination loss.**

The official API's query-visible open/closed state can change without a corresponding change in the dataset-level `rowsUpdatedAt` value TowerSignal records. Consequently:

- an older served release is a valid point-in-time source observation, not a live current-state mirror;
- `rowsUpdatedAt` alone is insufficient proof that two filtered query populations are identical;
- source-health wording must not imply that an unchanged dataset metadata timestamp proves unchanged HPD open-violation population.

A stronger future proof can record filtered population counts/identity digests alongside publisher metadata. No production change was made by this audit.
