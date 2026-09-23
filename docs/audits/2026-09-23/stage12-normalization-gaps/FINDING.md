# Stage 12 confirmed normalization defects

## DEC Category 7G applicator region

Source: NYS certified pesticide applicators `c7db-kwpj`, filtered to Category 7G.

Independent current-source/served-cache census:
- 1,681 official 7G rows.
- 1,681 exact cert-number + normalized-person-name matches to served `dec_7g_applicators`.
- 1,681 source rows have nonblank official `region`.
- 0 served applicators have nonblank `dec_region`.
- 1,681 mismatches.

First failing stage: `scripts/towersignal/domestic_water_market.py::normalize_dec_applicator`.

Root cause: the official field is `region`; the normalizer reads `row.get("dec_region")`.

Diagnosis: **CONFIRMED NORMALIZATION DEFECT**. This drops source-published DEC region for the entire served 7G applicator population. Region remains qualification/geographic context only; it does not prove employment, incumbent service, or a tower relationship.

## NYS State Authority procurement spend and source transaction identity

Source: `ehig-g5x3` Procurement Report for State Authorities.

The audit reproduced TowerSignal's source-row fingerprint independently and joined every served State Authority contract by exact `source_record_id`.

Population:
- 566 served State Authority contracts.
- 566/566 exact source fingerprint matches.
- 566 source rows publish `amount_expended_for_fiscal_year`.
- 481 publish `amount_expended_to_date`.
- 481 publish `current_or_outstanding_balance`.
- 489 publish `transaction_number`.
- 0/566 served contracts have nonblank `spend_to_date`.
- 481 source spend-to-date values are present while served spend is missing.
- 566 source fiscal-year spend values are present while served spend is missing.
- 489 source transaction numbers are present while served `source_contract_id` is missing.

First failing stage: `scripts/towersignal/nys_authority_procurement.py::normalize_row`.

Root cause:
- spend aliases currently check `amount_expended`, `amount_spent`, `expenditures`, `spend_to_date`, but the State Authority schema publishes `amount_expended_to_date` and `amount_expended_for_fiscal_year`;
- source contract ID aliases do not include `transaction_number`.

Diagnosis: **CONFIRMED NORMALIZATION GAP**. Source-reported procurement spend/identity is dropped after retrieval. These values are public procurement-report observations and must never be presented as vendor/company revenue.

Exact evidence: `stage12-normalization-gaps/dec-applicator-region-audit.json` and `stage12-normalization-gaps/abo-state-spend-audit.json`.

No production repair was performed by the audit.
