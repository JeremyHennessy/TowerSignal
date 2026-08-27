from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Sequence

from .checkbook import (
    API_URL,
    CONTRACT_API_URL,
    CITYWIDE_PRIME_MATERIAL_FIELDS,
    CITYWIDE_SCOPE,
    CITYWIDE_SOURCE,
    CITYWIDE_SUBVENDOR_SCOPE,
    EDC_MATERIAL_FIELDS,
    EDC_SCOPE,
    EDC_SOURCE,
    MIN_REQUEST_INTERVAL_SECONDS,
    PAGE_SIZE,
    CheckbookSourceError,
    RequestXml,
    ScopeResult,
    _collapse_rows,
    _dedupe_contracts,
    _default_request_xml,
    _material_key,
    _normalize_citywide_prime,
    _normalize_citywide_subcontract,
    _normalize_edc_contract,
    _source_health_for_scope,
    fetch_scope,
)
from .procurement import normalize_space, parse_money, utc_now

DEFAULT_FISCAL_YEAR_COUNT = 5

PRIME_MONEY_FIELDS = (
    "prime_contract_original_amount",
    "prime_contract_current_amount",
    "prime_vendor_spent_to_date",
)


def nyc_fiscal_year(as_of: date) -> int:
    """Return the NYC fiscal year containing ``as_of`` (July 1 through June 30)."""
    return as_of.year + 1 if as_of.month >= 7 else as_of.year


def recent_nyc_fiscal_years(as_of: date, count: int = DEFAULT_FISCAL_YEAR_COUNT) -> tuple[int, ...]:
    if count <= 0:
        raise ValueError("fiscal_year_count must be positive")
    current = nyc_fiscal_year(as_of)
    return tuple(range(current - count + 1, current + 1))


def _fetch_fiscal_year_partitions(
    spec,
    fiscal_years: Sequence[int],
    *,
    request_xml: RequestXml,
    page_size: int,
) -> tuple[tuple[int, ScopeResult], ...]:
    return tuple(
        (
            fiscal_year,
            fetch_scope(
                spec,
                request_xml=request_xml,
                page_size=page_size,
                extra_criteria=(("fiscal_year", "value", str(fiscal_year)),),
            ),
        )
        for fiscal_year in fiscal_years
    )


def _version_key(value: str | None) -> tuple[int, int | str]:
    text = normalize_space(value)
    if text.isdigit():
        return (1, int(text))
    return (0, text)


def _money_signature(row: Mapping[str, str]) -> tuple[float | None, ...]:
    return tuple(parse_money(row.get(field)) for field in PRIME_MONEY_FIELDS)


def _choose_prime_version_candidate(
    candidates: Sequence[Mapping[str, str]],
    *,
    identity: str,
    fiscal_year: int,
    material_fields: Sequence[str],
) -> dict[str, str]:
    """Collapse source duplicates without inventing contract values.

    Live Checkbook evidence shows that one registered contract/version can be returned
    multiple times with identical non-monetary fields: one row contains the reported
    contract amounts/spend and companion rows contain zero in all three monetary fields.
    Those all-zero companions are source placeholders, not independent contract values.

    We select the unique non-zero monetary row only when every non-monetary field is
    identical and every alternate monetary signature is exactly all-zero. Any other
    disagreement remains a hard failure.
    """
    structural_fields = tuple(
        field
        for field in material_fields
        if field not in {"prime_contract_version", *PRIME_MONEY_FIELDS}
    )
    structural_signatures = {_material_key(row, structural_fields) for row in candidates}
    selected_version = normalize_space(candidates[0].get("prime_contract_version")) or "(blank)"
    if len(structural_signatures) > 1:
        raise CheckbookSourceError(
            f"Checkbook NYC returned conflicting non-monetary fields for prime_contract_id={identity} "
            f"in FY{fiscal_year} version {selected_version}"
        )

    money_by_signature: dict[tuple[float | None, ...], Mapping[str, str]] = {}
    for row in candidates:
        money_by_signature.setdefault(_money_signature(row), row)
    if len(money_by_signature) == 1:
        chosen = dict(next(iter(money_by_signature.values())))
        chosen["_source_duplicate_row_count"] = str(len(candidates))
        if len(candidates) > 1:
            chosen["_source_duplicate_resolution"] = "IDENTICAL_DUPLICATES"
        return chosen

    zero_signature = (0.0, 0.0, 0.0)
    nonzero_signatures = [signature for signature in money_by_signature if signature != zero_signature]
    if zero_signature in money_by_signature and len(nonzero_signatures) == 1 and len(money_by_signature) == 2:
        chosen = dict(money_by_signature[nonzero_signatures[0]])
        chosen["_source_duplicate_row_count"] = str(len(candidates))
        chosen["_source_duplicate_resolution"] = "NONZERO_OVER_ZERO_PLACEHOLDER"
        return chosen

    raise CheckbookSourceError(
        f"Checkbook NYC returned conflicting monetary fields for prime_contract_id={identity} "
        f"in FY{fiscal_year} version {selected_version}"
    )


def _latest_partition_rows(
    partitions: Sequence[tuple[int, ScopeResult]],
    *,
    identity_field: str,
    material_fields: Sequence[str],
) -> tuple[dict[str, str], ...]:
    """Choose the latest fiscal-year/latest-version observation for each prime contract."""
    grouped: dict[str, dict[int, list[Mapping[str, str]]]] = {}
    for fiscal_year, scope in partitions:
        for row in scope.rows:
            identity = normalize_space(row.get(identity_field))
            if not identity:
                raise CheckbookSourceError(f"Source row missing identity {identity_field}")
            grouped.setdefault(identity, {}).setdefault(fiscal_year, []).append(row)

    selected: list[dict[str, str]] = []
    for identity in sorted(grouped):
        by_year = grouped[identity]
        latest_year = max(by_year)
        fiscal_year_candidates = by_year[latest_year]
        latest_version_key = max(_version_key(row.get("prime_contract_version")) for row in fiscal_year_candidates)
        candidates = [
            row for row in fiscal_year_candidates
            if _version_key(row.get("prime_contract_version")) == latest_version_key
        ]
        row = _choose_prime_version_candidate(
            candidates,
            identity=identity,
            fiscal_year=latest_year,
            material_fields=material_fields,
        )
        row["_fiscal_year_scope"] = str(latest_year)
        selected.append(row)
    return tuple(selected)


SUBCONTRACT_MATERIAL_FIELDS = (
    "sub_vendor",
    "sub_contract_purpose",
    "sub_contract_status",
    "sub_contract_original_amount",
    "sub_contract_current_amount",
    "sub_vendor_paid_to_date",
    "sub_contract_start_date",
    "sub_contract_end_date",
)


def _subcontract_key(row: Mapping[str, str]) -> tuple[str, ...]:
    prime_id = normalize_space(row.get("prime_contract_id"))
    reference = normalize_space(row.get("sub_contract_reference_id"))
    if reference:
        return (prime_id, "REF", reference)
    return (
        prime_id,
        "COMPOSITE",
        normalize_space(row.get("sub_vendor")),
        normalize_space(row.get("sub_contract_purpose")),
        normalize_space(row.get("sub_contract_start_date")),
        normalize_space(row.get("sub_contract_end_date")),
    )


def _latest_subcontract_rows(
    partitions: Sequence[tuple[int, ScopeResult]],
) -> tuple[dict[str, str], ...]:
    grouped: dict[tuple[str, ...], dict[int, list[Mapping[str, str]]]] = {}
    for fiscal_year, scope in partitions:
        for row in scope.rows:
            grouped.setdefault(_subcontract_key(row), {}).setdefault(fiscal_year, []).append(row)

    selected: list[dict[str, str]] = []
    for key in sorted(grouped):
        by_year = grouped[key]
        latest_year = max(by_year)
        candidates = by_year[latest_year]
        signatures = {_material_key(row, SUBCONTRACT_MATERIAL_FIELDS) for row in candidates}
        if len(signatures) > 1:
            raise CheckbookSourceError(
                f"Checkbook NYC returned conflicting subcontract fields for {key!r} in FY{latest_year}"
            )
        row = dict(candidates[0])
        row["_fiscal_year_scope"] = str(latest_year)
        row["_source_duplicate_row_count"] = str(len(candidates))
        if len(candidates) > 1:
            row["_source_duplicate_resolution"] = "IDENTICAL_DUPLICATES"
        selected.append(row)
    return tuple(selected)


def _aggregate_scope(spec, partitions: Sequence[tuple[int, ScopeResult]]) -> ScopeResult:
    return ScopeResult(
        spec=spec,
        expected_count=sum(scope.expected_count for _, scope in partitions),
        rows=(),
        pagination_complete=all(scope.pagination_complete for _, scope in partitions),
    )


def _partition_metadata(
    partitions: Sequence[tuple[int, ScopeResult]],
) -> list[dict[str, Any]]:
    return [
        {
            "name": f"{scope.spec.name}_FY{fiscal_year}",
            "source": scope.spec.source,
            "fiscal_year": fiscal_year,
            "record_count": scope.expected_count,
            "pagination_complete": scope.pagination_complete,
        }
        for fiscal_year, scope in partitions
    ]


def _attach_source_resolution(contract: dict[str, Any], row: Mapping[str, str]) -> None:
    contract["source_fiscal_year"] = int(row["_fiscal_year_scope"])
    duplicate_count = int(row.get("_source_duplicate_row_count") or 1)
    contract["source_duplicate_row_count"] = duplicate_count
    resolution = normalize_space(row.get("_source_duplicate_resolution"))
    if resolution:
        contract["source_duplicate_resolution"] = resolution


def build_recent_checkbook_cache(
    *,
    as_of: date | None = None,
    fiscal_year_count: int = DEFAULT_FISCAL_YEAR_COUNT,
    request_xml: RequestXml = _default_request_xml,
    retrieved_at: str | None = None,
    page_size: int = PAGE_SIZE,
) -> dict[str, Any]:
    as_of = as_of or date.today()
    retrieved_at = retrieved_at or utc_now()
    fiscal_years = recent_nyc_fiscal_years(as_of, fiscal_year_count)

    citywide_partitions = _fetch_fiscal_year_partitions(
        CITYWIDE_SCOPE,
        fiscal_years,
        request_xml=request_xml,
        page_size=page_size,
    )
    subvendor_partitions = _fetch_fiscal_year_partitions(
        CITYWIDE_SUBVENDOR_SCOPE,
        fiscal_years,
        request_xml=request_xml,
        page_size=page_size,
    )
    edc_scope = fetch_scope(EDC_SCOPE, request_xml=request_xml, page_size=page_size)

    citywide_primes = _latest_partition_rows(
        citywide_partitions,
        identity_field="prime_contract_id",
        material_fields=CITYWIDE_PRIME_MATERIAL_FIELDS,
    )
    citywide_subcontracts = _latest_subcontract_rows(subvendor_partitions)
    edc_primes = _collapse_rows(
        edc_scope.rows,
        identity_field="contract_id",
        material_fields=EDC_MATERIAL_FIELDS,
    )

    citywide_contracts: list[dict[str, Any]] = []
    for row in citywide_primes:
        contract = _normalize_citywide_prime(row, retrieved_at=retrieved_at)
        if contract["service_category"] != "UNRELATED":
            _attach_source_resolution(contract, row)
            citywide_contracts.append(contract)
    for row in citywide_subcontracts:
        subcontract = _normalize_citywide_subcontract(row, retrieved_at=retrieved_at)
        if subcontract is not None:
            _attach_source_resolution(subcontract, row)
            citywide_contracts.append(subcontract)
    citywide_contracts = _dedupe_contracts(citywide_contracts)

    edc_contracts = [
        contract
        for row in edc_primes
        if (contract := _normalize_edc_contract(row, retrieved_at=retrieved_at))["service_category"] != "UNRELATED"
    ]
    edc_contracts = _dedupe_contracts(edc_contracts)
    all_contracts = _dedupe_contracts([*citywide_contracts, *edc_contracts])

    citywide_aggregate = _aggregate_scope(CITYWIDE_SCOPE, citywide_partitions)
    subvendor_aggregate = _aggregate_scope(CITYWIDE_SUBVENDOR_SCOPE, subvendor_partitions)
    citywide_health = _source_health_for_scope(
        citywide_aggregate,
        citywide_contracts,
        retrieved_at=retrieved_at,
    )
    citywide_health.update(
        {
            "fiscal_years": list(fiscal_years),
            "subvendor_record_count": subvendor_aggregate.expected_count,
            "subvendor_pagination_complete": subvendor_aggregate.pagination_complete,
            "zero_placeholder_duplicate_resolution_count": sum(
                1
                for row in citywide_contracts
                if row.get("source_duplicate_resolution") == "NONZERO_OVER_ZERO_PLACEHOLDER"
            ),
        }
    )
    source_health = {
        CITYWIDE_SOURCE: citywide_health,
        EDC_SOURCE: _source_health_for_scope(edc_scope, edc_contracts, retrieved_at=retrieved_at),
    }

    classification_counts: dict[str, int] = {}
    for contract in all_contracts:
        category = str(contract.get("service_category") or "UNRELATED")
        classification_counts[category] = classification_counts.get(category, 0) + 1

    return {
        "schema_version": "1.0",
        "generated_at": retrieved_at,
        "source": {
            "name": "Checkbook NYC Contracts API",
            "api_url": API_URL,
            "documentation_url": CONTRACT_API_URL,
            "retrieved_at": retrieved_at,
            "page_size": page_size,
            "request_rate_floor_seconds": MIN_REQUEST_INTERVAL_SECONDS,
            "historical_coverage": {
                "mode": "RECENT_FISCAL_YEAR_WINDOW",
                "as_of_date": as_of.isoformat(),
                "fiscal_years": list(fiscal_years),
                "fiscal_year_count": len(fiscal_years),
                "older_years_status": "DEFERRED_DURABLE_BACKFILL",
                "reason": "The Checkbook all-years registered-expense query is not repeatably bounded enough for the verified daily/PR cache gate.",
            },
            "scopes": [
                *_partition_metadata(citywide_partitions),
                *_partition_metadata(subvendor_partitions),
                {
                    "name": edc_scope.spec.name,
                    "source": edc_scope.spec.source,
                    "record_count": edc_scope.expected_count,
                    "pagination_complete": edc_scope.pagination_complete,
                },
            ],
            "deferred_scopes": [
                {
                    "name": "NYCHA",
                    "type_of_data": "Contracts_NYCHA",
                    "status": "DEFERRED_SEPARATE_ADAPTER",
                    "reason": "NYCHA contract data uses release and line-item granularity and requires a separate normalization contract.",
                }
            ],
        },
        "summary": {
            "citywide_source_transaction_count": citywide_aggregate.expected_count,
            "citywide_subvendor_source_transaction_count": subvendor_aggregate.expected_count,
            "citywide_unique_prime_contract_count": len(citywide_primes),
            "citywide_relevant_contract_count": len(citywide_contracts),
            "edc_source_transaction_count": edc_scope.expected_count,
            "edc_unique_prime_contract_count": len(edc_primes),
            "edc_relevant_contract_count": len(edc_contracts),
            "relevant_contract_count": len(all_contracts),
            "unresolved_vendor_count": sum(1 for row in all_contracts if row.get("vendor_raw") and not row.get("company_id")),
            "classification_counts": dict(sorted(classification_counts.items())),
            "value_semantics": "Observed source-reported public contract/subcontract values and spend-to-date; not company revenue or a complete customer book.",
        },
        "source_health": source_health,
        "contracts": all_contracts,
    }
