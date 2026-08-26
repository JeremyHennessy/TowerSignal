from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping, Sequence

PROCUREMENT_SCHEMA_VERSION = "1.0"
COMPANY_SCHEMA_VERSION = "1.0"
PROCUREMENT_HISTORY_SCHEMA_VERSION = "1.0"

SERVICE_CATEGORIES = (
    "COOLING_TOWER_MAINTENANCE",
    "COOLING_TOWER_CLEANING",
    "COOLING_TOWER_REPAIR",
    "COOLING_TOWER_REPLACEMENT",
    "WATER_TREATMENT",
    "COOLING_WATER_TREATMENT",
    "BOILER_WATER_TREATMENT",
    "LEGIONELLA_TESTING",
    "LEGIONELLA_REMEDIATION",
    "WATER_MANAGEMENT_PLAN",
    "DISINFECTION",
    "WATER_TREATMENT_CHEMICALS",
    "LABORATORY_TESTING",
    "HVAC_MECHANICAL",
    "CHILLER",
    "CONDENSER_WATER",
    "PIPING",
    "CONTROLS",
    "OTHER_RELEVANT_WATER_SERVICE",
    "UNRELATED",
)

MATCH_CONFIDENCE = ("CONFIRMED", "STRONG", "VERIFY", "UNRESOLVED")
FACILITY_LINK_CONFIDENCE = ("CONFIRMED", "STRONG", "CONTEXT", "UNLINKED")
EVIDENCE_CONFIDENCE = ("CONFIRMED", "STRONG", "VERIFY")

LEGAL_SUFFIXES = {
    "CORP", "CORPORATION", "INC", "INCORPORATED", "LLC", "LTD", "LIMITED",
    "LP", "LLP", "CO", "COMPANY", "PC", "PLLC",
}

GENERIC_COMPANY_WORDS = {
    "WATER", "ENVIRONMENTAL", "SERVICES", "SERVICE", "SOLUTIONS", "SYSTEMS",
    "GROUP", "TECHNOLOGIES", "TECHNOLOGY", "INDUSTRIAL", "MECHANICAL", "CHEMICAL",
}

# Rules are ordered from highly specific to broad. A broad rule never overrides a
# more specific match. Every emitted classification carries the exact matched terms.
CLASSIFICATION_RULES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("COOLING_TOWER_CLEANING", ("cooling tower cleaning", "clean cooling tower", "tower cleaning"), "Explicit cooling-tower cleaning language"),
    ("COOLING_TOWER_REPLACEMENT", ("cooling tower replacement", "replace cooling tower", "new cooling tower"), "Explicit cooling-tower replacement language"),
    ("COOLING_TOWER_REPAIR", ("cooling tower repair", "repair cooling tower", "cooling tower rehabilitation", "cooling tower rebuild"), "Explicit cooling-tower repair language"),
    ("COOLING_TOWER_MAINTENANCE", ("cooling tower maintenance", "cooling tower service", "cooling towers maintenance", "cooling tower preventive maintenance"), "Explicit cooling-tower maintenance language"),
    ("LEGIONELLA_REMEDIATION", ("legionella remediation", "legionella disinfection", "legionella corrective action"), "Explicit Legionella remediation language"),
    ("LEGIONELLA_TESTING", ("legionella testing", "legionella sampling", "legionella analysis", "legionella laboratory"), "Explicit Legionella testing language"),
    ("WATER_MANAGEMENT_PLAN", ("water management plan", "water management program", "ashrae 188", "water safety plan"), "Explicit water-management program language"),
    ("COOLING_WATER_TREATMENT", ("cooling water treatment", "condenser water treatment", "cooling tower water treatment"), "Explicit cooling/condenser-water treatment language"),
    ("BOILER_WATER_TREATMENT", ("boiler water treatment", "boiler chemical treatment", "steam boiler water treatment"), "Explicit boiler-water treatment language"),
    ("WATER_TREATMENT_CHEMICALS", ("water treatment chemicals", "chemical water treatment", "water treatment chemical", "corrosion inhibitor", "biocide"), "Explicit water-treatment chemical language"),
    ("DISINFECTION", ("disinfection", "disinfecting", "hyperchlorination", "chlorination service"), "Explicit disinfection language"),
    ("LABORATORY_TESTING", ("laboratory testing", "lab testing", "microbiological testing", "water quality testing"), "Explicit laboratory/water-quality testing language"),
    ("CHILLER", ("chiller maintenance", "chiller service", "chiller repair", "chiller replacement", "chiller plant"), "Explicit chiller language"),
    ("CONDENSER_WATER", ("condenser water", "condenser loop"), "Explicit condenser-water language"),
    ("PIPING", ("piping replacement", "piping repair", "hydronic piping", "condenser piping"), "Explicit piping language"),
    ("CONTROLS", ("building automation", "hvac controls", "bms controls", "ddc controls"), "Explicit controls language"),
    ("HVAC_MECHANICAL", ("hvac maintenance", "hvac service", "mechanical maintenance", "mechanical services", "air conditioning service"), "Explicit HVAC/mechanical language"),
    ("WATER_TREATMENT", ("water treatment", "water conditioning", "water treatment service"), "Explicit water-treatment language"),
)

# Phrases that frequently appear in unrelated procurement and must not be promoted
# solely because one generic word matches a service rule.
NEGATIVE_CONTEXT_PATTERNS = (
    "drinking water delivery",
    "bottled water",
    "water meter",
    "water main",
    "wastewater treatment plant construction",
    "stormwater",
    "fire sprinkler",
    "fire suppression",
    "pool maintenance",
    "swimming pool",
    "janitorial",
    "landscaping",
)


@dataclass(frozen=True)
class ClassificationResult:
    service_category: str
    confidence: str
    matched_terms: tuple[str, ...]
    reason: str
    source_text: str


@dataclass(frozen=True)
class CompanyResolution:
    company_id: str | None
    canonical_name: str | None
    confidence: str
    resolution_method: str
    normalized_vendor_name: str
    candidate_company_ids: tuple[str, ...] = ()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def stable_id(prefix: str, *parts: Any) -> str:
    material = "|".join(normalize_space(str(part or "")) for part in parts)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}-{digest}"


def normalize_space(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def normalize_company_name(value: str | None, *, strip_legal_suffixes: bool = True) -> str:
    text = normalize_space(value).upper()
    text = text.replace("&", " AND ")
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    tokens = [token for token in text.split() if token]
    if strip_legal_suffixes:
        while tokens and tokens[-1] in LEGAL_SUFFIXES:
            tokens.pop()
    return " ".join(tokens)


def normalize_address(value: str | None) -> str:
    text = normalize_space(value).upper()
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    substitutions = {
        " STREET ": " ST ",
        " AVENUE ": " AVE ",
        " ROAD ": " RD ",
        " BOULEVARD ": " BLVD ",
        " DRIVE ": " DR ",
        " SUITE ": " STE ",
    }
    padded = f" {text} "
    for source, target in substitutions.items():
        padded = padded.replace(source, target)
    return normalize_space(padded)


def parse_money(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return None
    text = str(value).strip().replace("$", "").replace(",", "")
    if not text:
        return None
    if text.startswith("(") and text.endswith(")"):
        text = f"-{text[1:-1]}"
    try:
        amount = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    return float(amount.quantize(Decimal("0.01")))


def parse_iso_date(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    candidates = (text, text[:10])
    for candidate in candidates:
        try:
            return date.fromisoformat(candidate).isoformat()
        except ValueError:
            pass
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y%m%d", "%d-%b-%Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _classification_text(*values: Any) -> str:
    return normalize_space(" ".join(str(value or "") for value in values)).lower()


def classify_procurement(*values: Any) -> ClassificationResult:
    source_text = normalize_space(" ".join(str(value or "") for value in values))
    text = source_text.lower()
    if not text:
        return ClassificationResult("UNRELATED", "CONFIRMED", (), "No service description text", source_text)

    matched_negative = tuple(pattern for pattern in NEGATIVE_CONTEXT_PATTERNS if pattern in text)

    for category, terms, reason in CLASSIFICATION_RULES:
        matched = tuple(term for term in terms if term in text)
        if not matched:
            continue

        # Highly specific cooling tower / Legionella / condenser / boiler wording can
        # stand even when a generic negative phrase is elsewhere in a long notice.
        explicit = any(
            marker in " ".join(matched)
            for marker in ("cooling tower", "legionella", "condenser water", "boiler water", "water management")
        )
        if matched_negative and not explicit:
            return ClassificationResult(
                "UNRELATED",
                "STRONG",
                tuple(sorted(set(matched + matched_negative))),
                "Generic service wording occurs in an unrelated procurement context",
                source_text,
            )

        confidence = "CONFIRMED" if explicit or category in {
            "WATER_TREATMENT_CHEMICALS", "CHILLER", "LABORATORY_TESTING", "DISINFECTION"
        } else "STRONG"
        return ClassificationResult(category, confidence, matched, reason, source_text)

    # Context-only clues are useful for review, but must not become definitive service proof.
    context_terms = tuple(term for term in ("water services", "chemical services", "mechanical", "hvac") if term in text)
    if context_terms and not matched_negative:
        return ClassificationResult(
            "OTHER_RELEVANT_WATER_SERVICE" if "water services" in context_terms or "chemical services" in context_terms else "HVAC_MECHANICAL",
            "VERIFY",
            context_terms,
            "Broad service wording requires manual/source-specific verification",
            source_text,
        )

    return ClassificationResult("UNRELATED", "CONFIRMED", matched_negative, "No supported service-taxonomy evidence", source_text)


def company_record(
    canonical_name: str,
    *,
    company_id: str | None = None,
    company_type: str = "SERVICE_COMPANY",
    website: str | None = None,
    headquarters: str | None = None,
    status: str = "UNKNOWN",
    current_parent_company_id: str | None = None,
    current_sponsor_company_id: str | None = None,
    identity_confidence: str = "VERIFY",
    first_seen: str | None = None,
    last_seen: str | None = None,
) -> dict[str, Any]:
    canonical = normalize_space(canonical_name)
    return {
        "schema_version": COMPANY_SCHEMA_VERSION,
        "company_id": company_id or stable_id("company", normalize_company_name(canonical)),
        "canonical_name": canonical,
        "company_type": company_type,
        "website": website,
        "headquarters": headquarters,
        "status": status,
        "current_parent_company_id": current_parent_company_id,
        "current_sponsor_company_id": current_sponsor_company_id,
        "identity_confidence": identity_confidence,
        "first_seen": first_seen,
        "last_seen": last_seen,
    }


def company_alias_record(
    company_id: str,
    alias: str,
    *,
    source: str,
    source_vendor_id: str | None = None,
    address: str | None = None,
    confidence: str = "VERIFY",
    resolution_method: str = "MANUAL_REVIEW",
) -> dict[str, Any]:
    return {
        "company_id": company_id,
        "alias": normalize_space(alias),
        "normalized_alias": normalize_company_name(alias),
        "source": source,
        "source_vendor_id": normalize_space(source_vendor_id) or None,
        "address": normalize_space(address) or None,
        "normalized_address": normalize_address(address) or None,
        "confidence": confidence,
        "resolution_method": resolution_method,
    }


def resolve_company(
    vendor_name: str | None,
    *,
    source: str,
    source_vendor_id: str | None,
    address: str | None,
    companies: Sequence[Mapping[str, Any]],
    aliases: Sequence[Mapping[str, Any]],
) -> CompanyResolution:
    normalized = normalize_company_name(vendor_name)
    if not normalized:
        return CompanyResolution(None, None, "UNRESOLVED", "EMPTY_VENDOR_NAME", normalized)

    company_by_id = {str(company["company_id"]): company for company in companies}
    normalized_address = normalize_address(address)
    vendor_id = normalize_space(source_vendor_id)

    # Authoritative source vendor ID takes precedence, but only within the same source.
    if vendor_id:
        id_matches = [
            alias for alias in aliases
            if normalize_space(str(alias.get("source") or "")) == normalize_space(source)
            and normalize_space(str(alias.get("source_vendor_id") or "")) == vendor_id
        ]
        company_ids = sorted({str(alias.get("company_id")) for alias in id_matches if alias.get("company_id") in company_by_id})
        if len(company_ids) == 1:
            company = company_by_id[company_ids[0]]
            return CompanyResolution(company_ids[0], str(company.get("canonical_name")), "CONFIRMED", "AUTHORITATIVE_VENDOR_ID", normalized)
        if len(company_ids) > 1:
            return CompanyResolution(None, None, "VERIFY", "CONFLICTING_AUTHORITATIVE_VENDOR_ID", normalized, tuple(company_ids))

    name_matches = [alias for alias in aliases if normalize_company_name(str(alias.get("alias") or alias.get("normalized_alias") or "")) == normalized]
    company_ids = sorted({str(alias.get("company_id")) for alias in name_matches if alias.get("company_id") in company_by_id})

    if len(company_ids) == 1:
        company_id = company_ids[0]
        company = company_by_id[company_id]
        alias_addresses = {
            normalize_address(str(alias.get("address") or alias.get("normalized_address") or ""))
            for alias in name_matches if str(alias.get("company_id")) == company_id
        }
        alias_addresses.discard("")
        if normalized_address and alias_addresses and normalized_address in alias_addresses:
            return CompanyResolution(company_id, str(company.get("canonical_name")), "STRONG", "NORMALIZED_NAME_AND_ADDRESS", normalized)
        # Distinctive multi-token legal names can be strong without an address. Generic
        # one/two-token aliases remain VERIFY to avoid silent merges such as "RMC".
        tokens = normalized.split()
        if len(tokens) >= 2 and not all(token in GENERIC_COMPANY_WORDS for token in tokens):
            alias_confidences = {str(alias.get("confidence") or "") for alias in name_matches if str(alias.get("company_id")) == company_id}
            if "CONFIRMED" in alias_confidences:
                return CompanyResolution(company_id, str(company.get("canonical_name")), "CONFIRMED", "AUTHORITATIVE_ALIAS", normalized)
            return CompanyResolution(company_id, str(company.get("canonical_name")), "STRONG", "NORMALIZED_DISTINCTIVE_NAME", normalized)
        return CompanyResolution(company_id, str(company.get("canonical_name")), "VERIFY", "AMBIGUOUS_NORMALIZED_NAME", normalized)

    if len(company_ids) > 1:
        return CompanyResolution(None, None, "VERIFY", "MULTIPLE_ALIAS_CANDIDATES", normalized, tuple(company_ids))

    # Canonical-name exact normalization is allowed only as a candidate. It is STRONG
    # for a distinctive name; acronyms/single generic tokens are VERIFY.
    canonical_matches = [company for company in companies if normalize_company_name(str(company.get("canonical_name") or "")) == normalized]
    if len(canonical_matches) == 1:
        company = canonical_matches[0]
        tokens = normalized.split()
        confidence = "STRONG" if len(tokens) >= 2 and not all(token in GENERIC_COMPANY_WORDS for token in tokens) else "VERIFY"
        return CompanyResolution(str(company["company_id"]), str(company.get("canonical_name")), confidence, "CANONICAL_NAME_EXACT_NORMALIZED", normalized)
    if len(canonical_matches) > 1:
        ids = tuple(sorted(str(company["company_id"]) for company in canonical_matches))
        return CompanyResolution(None, None, "VERIFY", "MULTIPLE_CANONICAL_CANDIDATES", normalized, ids)

    return CompanyResolution(None, None, "UNRESOLVED", "NO_SAFE_MATCH", normalized)


def normalize_contract(
    *,
    source: str,
    source_record_id: str,
    source_contract_id: str | None,
    vendor_raw: str | None,
    buyer_name: str | None,
    title: str | None,
    description: str | None,
    retrieved_at: str,
    raw: Mapping[str, Any],
    company_resolution: CompanyResolution | None = None,
    agency: str | None = None,
    department: str | None = None,
    facility_raw: str | None = None,
    original_amount: Any = None,
    current_amount: Any = None,
    spend_to_date: Any = None,
    start_date: Any = None,
    end_date: Any = None,
    amended_end_date: Any = None,
    award_date: Any = None,
    registration_date: Any = None,
    award_method: str | None = None,
    contract_type: str | None = None,
    status: str | None = None,
    city: str | None = None,
    state: str | None = None,
    zip_code: str | None = None,
    facility_id: str | None = None,
    facility_match_confidence: str = "UNLINKED",
    tower_account_system_ids: Sequence[str] = (),
    tower_link_confidence: str = "UNLINKED",
    source_url: str | None = None,
    source_updated_at: str | None = None,
) -> dict[str, Any]:
    if facility_match_confidence not in FACILITY_LINK_CONFIDENCE:
        raise ValueError(f"Unsupported facility_match_confidence: {facility_match_confidence}")
    if tower_link_confidence not in FACILITY_LINK_CONFIDENCE:
        raise ValueError(f"Unsupported tower_link_confidence: {tower_link_confidence}")

    classification = classify_procurement(title, description)
    resolution = company_resolution or CompanyResolution(None, None, "UNRESOLVED", "NOT_RESOLVED", normalize_company_name(vendor_raw))
    procurement_id = stable_id("contract", source, source_record_id, source_contract_id or "")

    return {
        "schema_version": PROCUREMENT_SCHEMA_VERSION,
        "procurement_id": procurement_id,
        "source": source,
        "source_record_id": normalize_space(source_record_id),
        "source_contract_id": normalize_space(source_contract_id) or None,
        "vendor_raw": normalize_space(vendor_raw) or None,
        "company_id": resolution.company_id,
        "company_match_confidence": resolution.confidence,
        "company_resolution_method": resolution.resolution_method,
        "buyer_name": normalize_space(buyer_name) or None,
        "agency": normalize_space(agency) or None,
        "department": normalize_space(department) or None,
        "facility_raw": normalize_space(facility_raw) or None,
        "facility_id": facility_id,
        "facility_match_confidence": facility_match_confidence,
        "title": normalize_space(title) or None,
        "description": normalize_space(description) or None,
        "service_category": classification.service_category,
        "service_confidence": classification.confidence,
        "classification_terms": list(classification.matched_terms),
        "classification_reason": classification.reason,
        "original_amount": parse_money(original_amount),
        "current_amount": parse_money(current_amount),
        "spend_to_date": parse_money(spend_to_date),
        "start_date": parse_iso_date(start_date),
        "end_date": parse_iso_date(end_date),
        "amended_end_date": parse_iso_date(amended_end_date),
        "award_date": parse_iso_date(award_date),
        "registration_date": parse_iso_date(registration_date),
        "award_method": normalize_space(award_method) or None,
        "contract_type": normalize_space(contract_type) or None,
        "status": normalize_space(status) or None,
        "city": normalize_space(city) or None,
        "state": normalize_space(state) or None,
        "zip": normalize_space(zip_code) or None,
        "tower_account_system_ids": sorted(set(str(value) for value in tower_account_system_ids if value)),
        "tower_link_confidence": tower_link_confidence,
        "source_url": source_url,
        "retrieved_at": retrieved_at,
        "source_updated_at": source_updated_at,
        "raw": dict(raw),
    }


def normalize_notice(
    *,
    source: str,
    source_record_id: str,
    title: str | None,
    procurement_text: str | None,
    retrieved_at: str,
    raw: Mapping[str, Any],
    notice_id: str | None = None,
    agency: str | None = None,
    notice_type: str | None = None,
    procurement_category: str | None = None,
    selection_method: str | None = None,
    pin: str | None = None,
    due_date: Any = None,
    notice_start_date: Any = None,
    notice_end_date: Any = None,
    contact_name: str | None = None,
    contact_phone: str | None = None,
    amount: Any = None,
    status: str | None = None,
    source_url: str | None = None,
    source_updated_at: str | None = None,
) -> dict[str, Any]:
    classification = classify_procurement(title, procurement_text, procurement_category)
    procurement_id = stable_id("notice", source, source_record_id, notice_id or pin or "")
    return {
        "schema_version": PROCUREMENT_SCHEMA_VERSION,
        "procurement_id": procurement_id,
        "source": source,
        "source_record_id": normalize_space(source_record_id),
        "notice_id": normalize_space(notice_id) or None,
        "agency": normalize_space(agency) or None,
        "notice_type": normalize_space(notice_type) or None,
        "procurement_category": normalize_space(procurement_category) or None,
        "title": normalize_space(title) or None,
        "selection_method": normalize_space(selection_method) or None,
        "pin": normalize_space(pin) or None,
        "due_date": parse_iso_date(due_date),
        "notice_start_date": parse_iso_date(notice_start_date),
        "notice_end_date": parse_iso_date(notice_end_date),
        "contact_name": normalize_space(contact_name) or None,
        "contact_phone": normalize_space(contact_phone) or None,
        "procurement_text": normalize_space(procurement_text) or None,
        "amount": parse_money(amount),
        "status": normalize_space(status) or None,
        "service_category": classification.service_category,
        "service_confidence": classification.confidence,
        "classification_terms": list(classification.matched_terms),
        "classification_reason": classification.reason,
        "source_url": source_url,
        "retrieved_at": retrieved_at,
        "source_updated_at": source_updated_at,
        "raw": dict(raw),
    }


def procurement_source_health(
    *,
    source: str,
    last_success: str | None,
    last_attempt: str,
    record_count: int,
    relevant_record_count: int,
    normalized_contract_count: int,
    normalized_notice_count: int,
    resolved_company_count: int,
    unresolved_vendor_count: int,
    facility_link_count: int,
    exact_tower_link_count: int,
    pagination_complete: bool,
    schema_valid: bool,
    freshness: str,
    error: str | None = None,
    unsupported_geographic_scope: bool = False,
) -> dict[str, Any]:
    reasons: list[str] = []
    if error:
        reasons.append("RETRIEVAL_FAILURE")
    if not pagination_complete:
        reasons.append("PAGINATION_INCOMPLETE")
    if not schema_valid:
        reasons.append("SCHEMA_INVALID")
    if unsupported_geographic_scope:
        reasons.append("UNSUPPORTED_GEOGRAPHIC_SCOPE")
    if record_count > 0 and relevant_record_count == 0:
        reasons.append("EXPECTED_OR_OBSERVED_ZERO_RELEVANT_RECORDS")
    if unresolved_vendor_count > 0:
        reasons.append("ENTITY_RESOLUTION_UNCERTAINTY")

    hard_failure = bool(error) or not pagination_complete or not schema_valid
    status = "FAILED" if hard_failure else ("WARNING" if unsupported_geographic_scope or unresolved_vendor_count > 0 else "HEALTHY")
    return {
        "schema_version": PROCUREMENT_SCHEMA_VERSION,
        "source": source,
        "status": status,
        "last_success": last_success,
        "last_attempt": last_attempt,
        "record_count": int(record_count),
        "relevant_record_count": int(relevant_record_count),
        "normalized_contract_count": int(normalized_contract_count),
        "normalized_notice_count": int(normalized_notice_count),
        "resolved_company_count": int(resolved_company_count),
        "unresolved_vendor_count": int(unresolved_vendor_count),
        "facility_link_count": int(facility_link_count),
        "exact_tower_link_count": int(exact_tower_link_count),
        "pagination_complete": bool(pagination_complete),
        "schema_valid": bool(schema_valid),
        "freshness": freshness,
        "error": error,
        "status_reasons": reasons,
    }


def _effective_value(contract: Mapping[str, Any]) -> float:
    for key in ("current_amount", "original_amount", "spend_to_date"):
        value = contract.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return 0.0


def _effective_end_date(contract: Mapping[str, Any]) -> date | None:
    raw = contract.get("amended_end_date") or contract.get("end_date")
    parsed = parse_iso_date(raw)
    return date.fromisoformat(parsed) if parsed else None


def derive_company_metrics(contracts: Iterable[Mapping[str, Any]], *, as_of: date | None = None) -> dict[str, Any]:
    as_of = as_of or date.today()
    rows = list(contracts)
    active = []
    for row in rows:
        end = _effective_end_date(row)
        start = parse_iso_date(row.get("start_date"))
        start_date = date.fromisoformat(start) if start else None
        if (start_date is None or start_date <= as_of) and (end is None or end >= as_of):
            active.append(row)

    customers: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        customer = normalize_space(str(row.get("buyer_name") or row.get("agency") or "UNKNOWN"))
        customers[customer].append(row)

    customer_values = {
        customer: sum(_effective_value(row) for row in customer_rows)
        for customer, customer_rows in customers.items()
        if customer != "UNKNOWN"
    }
    total_value = sum(_effective_value(row) for row in rows)
    top_values = sorted(customer_values.values(), reverse=True)
    largest = top_values[0] if top_values else 0.0
    top_5 = sum(top_values[:5])

    category_counts = Counter(str(row.get("service_category") or "UNRELATED") for row in rows)
    states = {normalize_space(str(row.get("state") or "")) for row in rows if normalize_space(str(row.get("state") or ""))}

    durations: list[int] = []
    for row in rows:
        start = parse_iso_date(row.get("start_date"))
        end = parse_iso_date(row.get("amended_end_date") or row.get("end_date"))
        if start and end:
            delta = (date.fromisoformat(end) - date.fromisoformat(start)).days
            if delta >= 0:
                durations.append(delta)

    repeat_customers = sum(1 for customer_rows in customers.values() if len(customer_rows) > 1)
    expiring = {12: 0, 24: 0, 36: 0}
    for row in active:
        end = _effective_end_date(row)
        if not end:
            continue
        days = (end - as_of).days
        for months in (12, 24, 36):
            if 0 <= days <= round(months * 30.4375):
                expiring[months] += 1

    average_duration = round(sum(durations) / len(durations), 1) if durations else None
    median_duration = None
    if durations:
        ordered = sorted(durations)
        mid = len(ordered) // 2
        median_duration = float(ordered[mid]) if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2

    return {
        "observed_contract_count": len(rows),
        "active_contract_count": len(active),
        "historical_contract_count": max(len(rows) - len(active), 0),
        "observed_contract_value": round(total_value, 2),
        "active_observed_contract_value": round(sum(_effective_value(row) for row in active), 2),
        "observed_spend_to_date": round(sum(float(row.get("spend_to_date") or 0) for row in rows), 2),
        "observed_customer_count": len(customer_values),
        "active_customer_count": len({normalize_space(str(row.get("buyer_name") or row.get("agency") or "")) for row in active if normalize_space(str(row.get("buyer_name") or row.get("agency") or ""))}),
        "cooling_tower_related_contract_count": sum(category_counts[key] for key in category_counts if key.startswith("COOLING_TOWER") or key in {"COOLING_WATER_TREATMENT", "CONDENSER_WATER"}),
        "water_treatment_contract_count": sum(category_counts[key] for key in category_counts if "WATER_TREATMENT" in key),
        "legionella_contract_count": category_counts["LEGIONELLA_TESTING"] + category_counts["LEGIONELLA_REMEDIATION"],
        "mechanical_contract_count": category_counts["HVAC_MECHANICAL"] + category_counts["CHILLER"] + category_counts["PIPING"] + category_counts["CONTROLS"],
        "median_contract_duration": median_duration,
        "average_contract_duration": average_duration,
        "contracts_expiring_12m": expiring[12],
        "contracts_expiring_24m": expiring[24],
        "contracts_expiring_36m": expiring[36],
        "geographic_state_count": len(states),
        "geographic_market_count": len(states),
        "largest_observed_customer_value": round(largest, 2),
        "top_5_customer_value": round(top_5, 2),
        "observed_customer_concentration": round(largest / total_value, 4) if total_value > 0 else None,
        "repeat_customer_count": repeat_customers,
        "observable_customer_retention": round(repeat_customers / len(customer_values), 4) if customer_values else None,
    }


def procurement_history_events(
    previous: Mapping[str, Mapping[str, Any]] | None,
    current: Mapping[str, Mapping[str, Any]],
    *,
    observed_at: str,
) -> list[dict[str, Any]]:
    """Generate deterministic procurement changes.

    The first observed baseline intentionally emits no events. This mirrors TowerSignal's
    existing history invariant and prevents an initial procurement import from appearing
    as thousands of new contracts/notices.
    """
    if previous is None:
        return []

    events: list[dict[str, Any]] = []
    for procurement_id in sorted(current):
        now = current[procurement_id]
        before = previous.get(procurement_id)
        if before is None:
            record_kind = "NOTICE" if now.get("notice_id") is not None else "CONTRACT"
            event_type = "PROCUREMENT_NOTICE_ADDED" if record_kind == "NOTICE" else "CONTRACT_ADDED"
            events.append(_procurement_event(event_type, procurement_id, observed_at, before, now, {}))
            continue

        comparisons = (
            ("current_amount", "CONTRACT_VALUE_CHANGED"),
            ("spend_to_date", "CONTRACT_SPEND_CHANGED"),
            ("end_date", "CONTRACT_END_DATE_CHANGED"),
            ("amended_end_date", "CONTRACT_END_DATE_CHANGED"),
            ("due_date", "PROCUREMENT_DUE_DATE_CHANGED"),
            ("company_id", "VENDOR_CHANGED"),
        )
        emitted: set[str] = set()
        for field, event_type in comparisons:
            if event_type in emitted:
                continue
            if before.get(field) != now.get(field):
                events.append(_procurement_event(event_type, procurement_id, observed_at, before, now, {"field": field, "before": before.get(field), "after": now.get(field)}))
                emitted.add(event_type)
    return events


def _procurement_event(
    event_type: str,
    procurement_id: str,
    observed_at: str,
    before: Mapping[str, Any] | None,
    now: Mapping[str, Any],
    detail: Mapping[str, Any],
) -> dict[str, Any]:
    event_id = stable_id("proc-event", event_type, procurement_id, observed_at, detail)
    return {
        "schema_version": PROCUREMENT_HISTORY_SCHEMA_VERSION,
        "event_id": event_id,
        "event_type": event_type,
        "procurement_id": procurement_id,
        "observed_at": observed_at,
        "source": now.get("source"),
        "company_id": now.get("company_id"),
        "buyer_name": now.get("buyer_name") or now.get("agency"),
        "detail": dict(detail),
        "previous_present": before is not None,
    }
