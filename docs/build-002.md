# Build 002 — OATH adjudication lifecycle

Build 002 enriches NYC Health cooling-tower violation records with NYC OATH Hearings Division case-status data.

## Join semantics

TowerSignal uses only an exact identifier join:

`NYC Health inspection violation.summons_number` → `OATH ticket_number`

The canonical match basis is `SUMMONS_NUMBER_EXACT`. TowerSignal does not infer OATH cases from respondent identity, address similarity, BBL, or other fuzzy matching when the summons/ticket identity is absent.

## Source

NYC OATH Hearings Division Case Status — `jz4z-kudi`.

The source is queried only for summons numbers already present in the cooling-tower inspection dataset. The approximately 22-million-row OATH dataset is not downloaded into the Pages artifact or browser.

## Product semantics

OATH hearing status, hearing result, decision date, penalty/payment/balance data, compliance-status field, and charge details are displayed as source-backed case-lifecycle facts. They do not change TowerSignal Priority Score model 1.0 in this build.
