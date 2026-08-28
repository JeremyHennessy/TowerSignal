from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from typing import Any, Iterable, Mapping

from .company_identity import explicit_dba_aliases
from .procurement import (
    GENERIC_COMPANY_WORDS,
    company_alias_record,
    company_record,
    derive_company_metrics,
    normalize_company_name,
    normalize_space,
    stable_id,
)

COMPANY_INTELLIGENCE_SCHEMA_VERSION = "1.0"


def strict_vendor_key(value: str | None) -> str:
    """Normalize punctuation/case while preserving legal suffixes.

    A source label ending in LLC is not silently merged with a source label ending in
    INC. Broader corporate resolution remains a reviewable candidate relationship.
    """
    return normalize_company_name(value, strip_legal_suffixes=False)


def _ambiguous_base_name(value: str) -> bool:
    """Return True when an observed vendor label is too weak to treat as a strong identity.

    Single-token labels/acronyms such as RMC and labels made only from generic service
    words remain review candidates even when no competing source label is currently
    observed. This prevents absence of a collision from being misread as identity proof.
    """
    tokens = normalize_company_name(value).split()
    return len(tokens) < 2 or all(token in GENERIC_COMPANY_WORDS for token in tokens)


def _observation_date(row: Mapping[str, Any]) -> str | None:
    for field in (
        "award_date",
        "registration_date",
        "start_date",
        "notice_start_date",
        "due_date",
        "source_updated_at",
        "retrieved_at",
    ):
        value = normalize_space(str(row.get(field) or ""))
        if value:
            return value[:10]
    return None


def _canonical_label(rows: Iterable[Mapping[str, Any]]) -> str:
    labels = Counter(normalize_space(str(row.get("vendor_raw") or "")) for row in rows)
    labels.pop("", None)
    if not labels:
        return "Unknown observed vendor"
    return sorted(labels, key=lambda value: (-labels[value], -len(value), value))[0]


def build_company_intelligence(
    procurement_rows: Iterable[Mapping[str, Any]],
    *,
    generated_at: str,
    as_of: date | None = None,
) -> dict[str, Any]:
    rows = [dict(row) for row in procurement_rows if normalize_space(str(row.get("vendor_raw") or ""))]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = strict_vendor_key(str(row.get("vendor_raw") or ""))
        if key:
            groups[key].append(row)

    base_name_to_company_ids: dict[str, list[str]] = defaultdict(list)
    company_id_by_strict_key: dict[str, str] = {}
    for strict_key in groups:
        company_id = stable_id("observed-company", strict_key)
        company_id_by_strict_key[strict_key] = company_id
        base_name = normalize_company_name(strict_key)
        if base_name:
            base_name_to_company_ids[base_name].append(company_id)

    companies: list[dict[str, Any]] = []
    unresolved_observations: list[dict[str, Any]] = []

    for strict_key in sorted(groups):
        company_rows = groups[strict_key]
        company_id = company_id_by_strict_key[strict_key]
        canonical_name = _canonical_label(company_rows)
        dates = sorted(date_value for row in company_rows if (date_value := _observation_date(row)))
        sources = sorted({normalize_space(str(row.get("source") or "")) for row in company_rows if row.get("source")})
        buyers = sorted({normalize_space(str(row.get("buyer_name") or row.get("agency") or "")) for row in company_rows if normalize_space(str(row.get("buyer_name") or row.get("agency") or ""))})
        categories = sorted({normalize_space(str(row.get("service_category") or "")) for row in company_rows if normalize_space(str(row.get("service_category") or ""))})
        base_name = normalize_company_name(strict_key)
        ambiguous_identity = _ambiguous_base_name(base_name)

        aliases = []
        alias_seen: set[tuple[str, str]] = set()
        for row in company_rows:
            alias = normalize_space(str(row.get("vendor_raw") or ""))
            source = normalize_space(str(row.get("source") or ""))
            address = normalize_space(str(row.get("vendor_address") or "")) or None
            marker = (alias, source)
            if alias and marker not in alias_seen:
                alias_seen.add(marker)
                aliases.append(company_alias_record(
                    company_id,
                    alias,
                    source=source,
                    address=address,
                    confidence="VERIFY" if ambiguous_identity else "STRONG",
                    resolution_method=(
                        "AMBIGUOUS_SHORT_OR_GENERIC_VENDOR_LABEL"
                        if ambiguous_identity
                        else "EXACT_SOURCE_LABEL_SUFFIX_PRESERVED"
                    ),
                ))

            for dba_alias in explicit_dba_aliases(alias):
                dba_marker = (dba_alias, source)
                if dba_marker in alias_seen:
                    continue
                alias_seen.add(dba_marker)
                aliases.append(company_alias_record(
                    company_id,
                    dba_alias,
                    source=source,
                    address=address,
                    confidence="CONFIRMED",
                    resolution_method="EXPLICIT_SOURCE_DBA_ALIAS",
                ))

        checkbook_contracts = [row for row in company_rows if str(row.get("source") or "") != "NYC_CITY_RECORD"]
        metrics = derive_company_metrics(checkbook_contracts, as_of=as_of)
        city_record_rows = [row for row in company_rows if str(row.get("source") or "") == "NYC_CITY_RECORD"]
        recent_awards = sum(1 for row in city_record_rows if str(row.get("scope") or "") == "RECENT_AWARDS")

        candidate_ids = sorted(set(base_name_to_company_ids.get(base_name, ())) - {company_id})
        if candidate_ids:
            resolution_confidence = "VERIFY"
            resolution_method = "LEGAL_SUFFIX_OR_SOURCE_VARIANT_REQUIRES_REVIEW"
        elif ambiguous_identity:
            resolution_confidence = "VERIFY"
            resolution_method = "AMBIGUOUS_SHORT_OR_GENERIC_VENDOR_LABEL"
        else:
            resolution_confidence = "STRONG"
            resolution_method = "EXACT_SOURCE_LABEL_SUFFIX_PRESERVED"

        record = company_record(
            canonical_name,
            company_id=company_id,
            company_type="OBSERVED_PROCUREMENT_VENDOR",
            identity_confidence="VERIFY" if ambiguous_identity else "STRONG",
            first_seen=dates[0] if dates else None,
            last_seen=dates[-1] if dates else None,
        )
        record.update({
            "identity_scope": "OBSERVED_PUBLIC_PROCUREMENT_VENDOR_LABEL",
            "identity_basis": "CASE_AND_PUNCTUATION_NORMALIZED_LEGAL_SUFFIX_PRESERVED",
            "strict_vendor_key": strict_key,
            "normalized_base_name": base_name,
            "cross_source_resolution_confidence": resolution_confidence,
            "cross_source_resolution_method": resolution_method,
            "candidate_related_company_ids": candidate_ids,
            "aliases": sorted(aliases, key=lambda row: (str(row.get("source") or ""), str(row.get("alias") or ""))),
            "explicit_dba_alias_count": sum(
                1 for alias_row in aliases
                if alias_row.get("resolution_method") == "EXPLICIT_SOURCE_DBA_ALIAS"
            ),
            "observed_sources": sources,
            "observed_buyers": buyers,
            "service_categories": categories,
            "procurement_ids": sorted(str(row.get("procurement_id")) for row in company_rows if row.get("procurement_id")),
            "procurement_observation_count": len(company_rows),
            "city_record_observation_count": len(city_record_rows),
            "city_record_recent_award_count": recent_awards,
            "metrics": metrics,
            "value_semantics": "Observed source-reported public contract values and spend-to-date; not company revenue, enterprise value, or a complete customer book.",
        })
        companies.append(record)

        if candidate_ids or ambiguous_identity:
            for row in company_rows:
                unresolved_observations.append({
                    "procurement_id": row.get("procurement_id"),
                    "source": row.get("source"),
                    "vendor_raw": row.get("vendor_raw"),
                    "observed_company_id": company_id,
                    "normalized_base_name": base_name,
                    "resolution_confidence": "VERIFY",
                    "resolution_method": resolution_method,
                    "candidate_company_ids": candidate_ids,
                })

    companies.sort(key=lambda row: (
        -int((row.get("metrics") or {}).get("observed_contract_count") or 0),
        -float((row.get("metrics") or {}).get("observed_contract_value") or 0),
        str(row.get("canonical_name") or ""),
    ))

    return {
        "schema_version": COMPANY_INTELLIGENCE_SCHEMA_VERSION,
        "generated_at": generated_at,
        "summary": {
            "observed_vendor_company_count": len(companies),
            "procurement_observation_count": len(rows),
            "cross_source_exact_label_company_count": sum(1 for company in companies if len(company.get("observed_sources") or []) > 1),
            "companies_requiring_resolution_review": sum(1 for company in companies if company.get("cross_source_resolution_confidence") == "VERIFY"),
            "unresolved_observation_count": len(unresolved_observations),
            "explicit_dba_alias_count": sum(int(company.get("explicit_dba_alias_count") or 0) for company in companies),
            "value_semantics": "Observed source-reported public contract values; not company revenue, enterprise value, or a complete customer book.",
        },
        "companies": companies,
        "unresolved_vendor_observations": sorted(unresolved_observations, key=lambda row: (str(row.get("vendor_raw") or ""), str(row.get("procurement_id") or ""))),
    }
