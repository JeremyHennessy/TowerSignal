from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Sequence

from towersignal.company_intelligence import strict_vendor_key
from towersignal.procurement import normalize_company_name, normalize_space, stable_id

SCHEMA_VERSION = "1.0"
DOMAIN = "TOWERSIGNAL_KNOWN_FIRMS"

ROLE_ORDER = (
    "DWT_INSPECTION_PROVIDER",
    "DWT_LABORATORY",
    "PROCUREMENT_VENDOR",
    "DEC_7G_REGISTERED_BUSINESS",
    "DOB_NOW_APPLICANT_BUSINESS",
    "DOB_NOW_OWNER_BUSINESS",
    "LEGACY_DOB_OWNER_BUSINESS",
)

SERVICE_ROLES = {"DWT_INSPECTION_PROVIDER", "DWT_LABORATORY"}
PROJECT_ROLES = {"DOB_NOW_APPLICANT_BUSINESS", "DOB_NOW_OWNER_BUSINESS", "LEGACY_DOB_OWNER_BUSINESS"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _date_only(value: Any) -> str | None:
    text = normalize_space(str(value or ""))
    if not text:
        return None
    for candidate in (text, text[:10]):
        try:
            return date.fromisoformat(candidate).isoformat()
        except ValueError:
            continue
    return None


def _has_legal_suffix(value: str) -> bool:
    strict = strict_vendor_key(value)
    base = normalize_company_name(value)
    return bool(strict and base and strict != base)


def _identity_confidence_for_name(value: str) -> str:
    base = normalize_company_name(value)
    tokens = [token for token in base.split() if token]
    if len(tokens) <= 1:
        return "VERIFY"
    return "STRONG"


def _safe_firm_detail_path(firm_id: str) -> str:
    safe = "".join(ch for ch in firm_id if ch.isalnum() or ch in ("-", "_"))
    prefix = (safe[:2] or "xx").lower()
    return f"firm-details/{prefix}/{safe}.json"


def _system_site_key(row: Mapping[str, Any]) -> str:
    bin_value = normalize_space(str(row.get("bin") or ""))
    bbl = normalize_space(str(row.get("bbl") or ""))
    system_id = normalize_space(str(row.get("system_id") or ""))
    if bin_value:
        return f"NYC-BIN-{bin_value}"
    if bbl:
        return f"NYC-BBL-{bbl}"
    return f"NYC-SYSTEM-{system_id}"


def _coordinate_average(rows: Sequence[Mapping[str, Any]]) -> tuple[float | None, float | None]:
    coordinates: list[tuple[float, float]] = []
    for row in rows:
        lat, lon = row.get("latitude"), row.get("longitude")
        try:
            latitude = float(lat) if lat is not None else None
            longitude = float(lon) if lon is not None else None
        except (TypeError, ValueError):
            continue
        if latitude is None or longitude is None:
            continue
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            continue
        coordinates.append((latitude, longitude))
    if not coordinates:
        return None, None
    return (
        round(sum(item[0] for item in coordinates) / len(coordinates), 7),
        round(sum(item[1] for item in coordinates) / len(coordinates), 7),
    )


def _site_from_systems(
    systems: Sequence[Mapping[str, Any]],
    *,
    fallback_key: str | None = None,
    fallback_bin: Any = None,
    fallback_bbl: Any = None,
    fallback_address: Any = None,
    fallback_borough: Any = None,
    fallback_zip: Any = None,
) -> dict[str, Any]:
    rows = list(systems)
    first = rows[0] if rows else {}
    bin_value = normalize_space(str(fallback_bin or first.get("bin") or "")) or None
    bbl = normalize_space(str(fallback_bbl or first.get("bbl") or "")) or None
    address = normalize_space(str(fallback_address or first.get("address") or "")) or None
    borough = normalize_space(str(fallback_borough or first.get("borough") or "")) or None
    zip_value = normalize_space(str(fallback_zip or first.get("zip") or "")) or None
    if bin_value:
        site_id = f"NYC-BIN-{bin_value}"
    elif bbl:
        site_id = f"NYC-BBL-{bbl}"
    elif fallback_key:
        site_id = str(fallback_key)
    elif rows:
        site_id = _system_site_key(first)
    else:
        material = "|".join(value or "" for value in (address, borough, zip_value))
        site_id = stable_id("NYC-SITE", material)
    latitude, longitude = _coordinate_average(rows)
    return {
        "site_id": site_id,
        "bin": bin_value,
        "bbl": bbl,
        "address": address,
        "borough": borough,
        "zip": zip_value,
        "latitude": latitude,
        "longitude": longitude,
        "system_ids": sorted({str(row.get("system_id")) for row in rows if row.get("system_id")}),
    }


def _procurement_rows(payload: Mapping[str, Any] | None) -> Iterable[Mapping[str, Any]]:
    if not payload:
        return ()
    for key in ("notices", "contracts", "records"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return (row for row in rows if isinstance(row, Mapping))
    return ()


def _new_firm(
    firm_id: str,
    name: str,
    *,
    identity_confidence: str,
    resolution_method: str,
    procurement_company: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "firm_id": firm_id,
        "canonical_name": normalize_space(name) or firm_id,
        "strict_name": strict_vendor_key(name),
        "normalized_name": normalize_company_name(name),
        "identity_confidence": identity_confidence,
        "resolution_method": resolution_method,
        "procurement_company_id": procurement_company.get("company_id") if procurement_company else None,
        "candidate_related_company_ids": set(),
        "roles": set(),
        "role_counts": Counter(),
        "source_classes": set(),
        "alias_observations": Counter(),
        "observation_count": 0,
        "first_observed_date": None,
        "latest_observed_date": None,
        "site_relationships": {},
        "qualifications": [],
        "procurement": dict(procurement_company) if procurement_company else None,
    }


def _observe(
    firm: dict[str, Any],
    *,
    role: str,
    source_class: str,
    date_value: Any = None,
    count: int = 1,
    alias: str | None = None,
) -> None:
    firm["roles"].add(role)
    firm["role_counts"][role] += max(0, int(count))
    firm["source_classes"].add(source_class)
    firm["observation_count"] += max(0, int(count))
    if alias:
        cleaned = normalize_space(alias)
        if cleaned:
            firm["alias_observations"][(cleaned, source_class, role)] += max(1, int(count))
    observed = _date_only(date_value)
    if observed:
        if not firm["first_observed_date"] or observed < firm["first_observed_date"]:
            firm["first_observed_date"] = observed
        if not firm["latest_observed_date"] or observed > firm["latest_observed_date"]:
            firm["latest_observed_date"] = observed


def _upsert_site(
    firm: dict[str, Any],
    site: Mapping[str, Any],
    *,
    role: str,
    relationship_class: str,
    evidence_class: str,
    date_value: Any = None,
    source_record_id: str | None = None,
    serviced: bool = False,
    contracted: bool = False,
    project_role: bool = False,
) -> None:
    site_id = str(site["site_id"])
    existing = firm["site_relationships"].setdefault(
        site_id,
        {
            "site_id": site_id,
            "bin": site.get("bin"),
            "bbl": site.get("bbl"),
            "address": site.get("address"),
            "borough": site.get("borough"),
            "zip": site.get("zip"),
            "latitude": site.get("latitude"),
            "longitude": site.get("longitude"),
            "system_ids": set(site.get("system_ids") or []),
            "roles": set(),
            "relationship_classes": set(),
            "evidence_classes": set(),
            "source_record_ids": set(),
            "observation_count": 0,
            "first_observed_date": None,
            "last_observed_date": None,
            "serviced": False,
            "contracted": False,
            "project_role": False,
        },
    )
    existing["system_ids"].update(site.get("system_ids") or [])
    existing["roles"].add(role)
    existing["relationship_classes"].add(relationship_class)
    existing["evidence_classes"].add(evidence_class)
    if source_record_id:
        existing["source_record_ids"].add(str(source_record_id))
    existing["observation_count"] += 1
    existing["serviced"] = bool(existing["serviced"] or serviced)
    existing["contracted"] = bool(existing["contracted"] or contracted)
    existing["project_role"] = bool(existing["project_role"] or project_role)
    observed = _date_only(date_value)
    if observed:
        if not existing["first_observed_date"] or observed < existing["first_observed_date"]:
            existing["first_observed_date"] = observed
        if not existing["last_observed_date"] or observed > existing["last_observed_date"]:
            existing["last_observed_date"] = observed


def build_known_firms(
    *,
    systems_payload: Mapping[str, Any],
    companies_payload: Mapping[str, Any],
    domestic_payload: Mapping[str, Any],
    procurement_payloads: Sequence[Mapping[str, Any] | None] = (),
    details_by_system: Mapping[str, Mapping[str, Any]] | None = None,
    generated_at: str | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    systems = [row for row in (systems_payload.get("systems") or []) if isinstance(row, Mapping)]
    systems_by_id = {str(row.get("system_id")): row for row in systems if row.get("system_id")}
    systems_by_bin: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    systems_by_bbl: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in systems:
        if row.get("bin"):
            systems_by_bin[str(row["bin"])].append(row)
        if row.get("bbl"):
            systems_by_bbl[str(row["bbl"])].append(row)

    firms: dict[str, dict[str, Any]] = {}
    procurement_alias_index: dict[str, set[str]] = defaultdict(set)
    external_strict_index: dict[str, str] = {}

    companies = [row for row in (companies_payload.get("companies") or []) if isinstance(row, Mapping)]
    for company in companies:
        company_id = str(company.get("company_id") or "")
        name = normalize_space(str(company.get("canonical_name") or ""))
        if not company_id or not name:
            continue
        identity_confidence = str(company.get("identity_confidence") or "VERIFY")
        resolution_method = str(company.get("cross_source_resolution_method") or "PROCUREMENT_OBSERVED_VENDOR")
        firm = _new_firm(
            company_id,
            name,
            identity_confidence=identity_confidence,
            resolution_method=resolution_method,
            procurement_company=company,
        )
        metrics = company.get("metrics") if isinstance(company.get("metrics"), Mapping) else {}
        procurement_observations = int(metrics.get("procurement_observation_count") or metrics.get("observed_contract_count") or 0)
        _observe(
            firm,
            role="PROCUREMENT_VENDOR",
            source_class="PUBLIC_PROCUREMENT",
            date_value=metrics.get("last_seen"),
            count=procurement_observations,
            alias=name,
        )
        first_seen = _date_only(metrics.get("first_seen"))
        if first_seen:
            firm["first_observed_date"] = first_seen
        for source_name in company.get("observed_sources") or []:
            firm["source_classes"].add(str(source_name))
        alias_names = [name]
        for alias in company.get("aliases") or []:
            if isinstance(alias, Mapping) and alias.get("name"):
                alias_name = normalize_space(str(alias["name"]))
                alias_names.append(alias_name)
                firm["alias_observations"][(alias_name, "PUBLIC_PROCUREMENT", "PROCUREMENT_VENDOR")] += int(alias.get("observation_count") or 1)
        firms[company_id] = firm
        for alias_name in alias_names:
            strict = strict_vendor_key(alias_name)
            if strict:
                procurement_alias_index[strict].add(company_id)

    def resolve_named_firm(name: Any) -> dict[str, Any] | None:
        cleaned = normalize_space(str(name or ""))
        strict = strict_vendor_key(cleaned)
        if not cleaned or not strict:
            return None
        procurement_candidates = procurement_alias_index.get(strict, set())
        if len(procurement_candidates) == 1:
            return firms[next(iter(procurement_candidates))]
        if strict in external_strict_index:
            firm = firms[external_strict_index[strict]]
            if len(procurement_candidates) > 1:
                firm["candidate_related_company_ids"].update(procurement_candidates)
                firm["identity_confidence"] = "VERIFY"
            return firm
        firm_id = stable_id("known-firm", strict)
        if firm_id not in firms:
            confidence = "VERIFY" if len(procurement_candidates) > 1 else _identity_confidence_for_name(cleaned)
            method = "AMBIGUOUS_PROCUREMENT_ALIAS" if len(procurement_candidates) > 1 else "STRICT_OBSERVED_NAME_SUFFIX_PRESERVED"
            firms[firm_id] = _new_firm(
                firm_id,
                cleaned,
                identity_confidence=confidence,
                resolution_method=method,
            )
            firms[firm_id]["candidate_related_company_ids"].update(procurement_candidates)
        external_strict_index[strict] = firm_id
        return firms[firm_id]

    def site_for_identity(
        *,
        bin_value: Any = None,
        bbl: Any = None,
        fallback_key: str | None = None,
        address: Any = None,
        borough: Any = None,
        zip_value: Any = None,
        system_ids: Sequence[str] = (),
    ) -> dict[str, Any]:
        linked: list[Mapping[str, Any]] = []
        for system_id in system_ids:
            system = systems_by_id.get(str(system_id))
            if system and system not in linked:
                linked.append(system)
        normalized_bin = normalize_space(str(bin_value or ""))
        normalized_bbl = normalize_space(str(bbl or ""))
        if normalized_bin:
            for system in systems_by_bin.get(normalized_bin, []):
                if system not in linked:
                    linked.append(system)
        elif normalized_bbl:
            for system in systems_by_bbl.get(normalized_bbl, []):
                if system not in linked:
                    linked.append(system)
        return _site_from_systems(
            linked,
            fallback_key=fallback_key,
            fallback_bin=normalized_bin,
            fallback_bbl=normalized_bbl,
            fallback_address=address,
            fallback_borough=borough,
            fallback_zip=zip_value,
        )

    for inspection in domestic_payload.get("tank_inspections") or []:
        if not isinstance(inspection, Mapping):
            continue
        site = site_for_identity(
            bin_value=inspection.get("bin"),
            bbl=inspection.get("bbl"),
            fallback_key=str(inspection.get("building_key") or "") or None,
            address=inspection.get("address"),
            borough=inspection.get("borough"),
            zip_value=inspection.get("zip"),
        )
        observation_date = inspection.get("inspection_date") or inspection.get("reporting_year")
        if inspection.get("provider_data_quality") == "VALID_NAME" and inspection.get("provider_raw"):
            firm = resolve_named_firm(inspection.get("provider_raw"))
            if firm:
                _observe(
                    firm,
                    role="DWT_INSPECTION_PROVIDER",
                    source_class="NYC_DWT_TANK_INSPECTIONS",
                    date_value=observation_date,
                    alias=str(inspection.get("provider_raw")),
                )
                _upsert_site(
                    firm,
                    site,
                    role="DWT_INSPECTION_PROVIDER",
                    relationship_class="OBSERVED_SERVICE",
                    evidence_class="DWT_INSPECTION_BY_FIRM_OBSERVED_SERVICE",
                    date_value=observation_date,
                    source_record_id=str(inspection.get("inspection_id") or "") or None,
                    serviced=True,
                )
        if inspection.get("laboratory_data_quality") == "VALID_NAME" and inspection.get("lab_raw"):
            firm = resolve_named_firm(inspection.get("lab_raw"))
            if firm:
                _observe(
                    firm,
                    role="DWT_LABORATORY",
                    source_class="NYC_DWT_TANK_INSPECTIONS",
                    date_value=observation_date,
                    alias=str(inspection.get("lab_raw")),
                )
                _upsert_site(
                    firm,
                    site,
                    role="DWT_LABORATORY",
                    relationship_class="OBSERVED_SERVICE",
                    evidence_class="DWT_LAB_NAME_OBSERVED_SERVICE",
                    date_value=observation_date,
                    source_record_id=str(inspection.get("inspection_id") or "") or None,
                    serviced=True,
                )

    as_of_text = (generated_at or systems_payload.get("metadata", {}).get("generated_at") or utc_now())[:10]
    try:
        as_of = date.fromisoformat(as_of_text)
    except ValueError:
        as_of = date.today()
    for qualification in domestic_payload.get("dec_7g_businesses") or []:
        if not isinstance(qualification, Mapping) or not qualification.get("provider_name"):
            continue
        firm = resolve_named_firm(qualification.get("provider_name"))
        if not firm:
            continue
        effective = qualification.get("registration_effective_date")
        expiration = _date_only(qualification.get("registration_expiration_date"))
        _observe(
            firm,
            role="DEC_7G_REGISTERED_BUSINESS",
            source_class="NYS_DEC_7G_BUSINESS_REGISTRATION",
            date_value=effective,
            alias=str(qualification.get("provider_name")),
        )
        record = {
            "qualification_id": qualification.get("qualification_id"),
            "registration_number": qualification.get("registration_number"),
            "city": qualification.get("city"),
            "state": qualification.get("state"),
            "registration_effective_date": _date_only(effective),
            "registration_expiration_date": expiration,
            "qualification_scope": qualification.get("qualification_scope"),
            "relationship_evidence": qualification.get("relationship_evidence") or "QUALIFIED_PROVIDER",
            "active_as_of_generation": bool(expiration and expiration >= as_of.isoformat()),
        }
        firm["qualifications"].append(record)

    seen_procurement_records: set[tuple[str, str]] = set()
    for procurement_payload in procurement_payloads:
        for record in _procurement_rows(procurement_payload):
            procurement_id = str(record.get("procurement_id") or record.get("source_record_id") or "")
            source = str(record.get("source") or "PUBLIC_PROCUREMENT")
            identity = (source, procurement_id)
            if not procurement_id or identity in seen_procurement_records:
                continue
            seen_procurement_records.add(identity)
            vendor = record.get("vendor_raw")
            firm = resolve_named_firm(vendor)
            if not firm:
                continue
            if "PROCUREMENT_VENDOR" not in firm["roles"]:
                _observe(
                    firm,
                    role="PROCUREMENT_VENDOR",
                    source_class=source,
                    date_value=record.get("award_date") or record.get("start_date") or record.get("retrieved_at"),
                    alias=str(vendor),
                )
            system_ids = [str(value) for value in (record.get("tower_account_system_ids") or []) if value]
            if not system_ids:
                continue
            linked_sites: dict[str, dict[str, Any]] = {}
            for system_id in system_ids:
                system = systems_by_id.get(system_id)
                if not system:
                    continue
                site = site_for_identity(
                    bin_value=system.get("bin"),
                    bbl=system.get("bbl"),
                    address=system.get("address"),
                    borough=system.get("borough"),
                    zip_value=system.get("zip"),
                    system_ids=[system_id],
                )
                linked_sites[str(site["site_id"])] = site
            confidence = str(record.get("tower_link_confidence") or "UNLINKED")
            for site in linked_sites.values():
                _upsert_site(
                    firm,
                    site,
                    role="PROCUREMENT_VENDOR",
                    relationship_class="PUBLIC_PROCUREMENT_TOWER_RELATIONSHIP",
                    evidence_class=f"PROCUREMENT_TOWER_LINK_{confidence}",
                    date_value=record.get("award_date") or record.get("start_date") or record.get("retrieved_at"),
                    source_record_id=procurement_id,
                    contracted=confidence == "CONFIRMED",
                )

    seen_project_observations: set[tuple[str, str, str, str]] = set()
    for system_id, detail in (details_by_system or {}).items():
        system = systems_by_id.get(str(system_id))
        if not system:
            continue
        site = site_for_identity(
            bin_value=system.get("bin"),
            bbl=system.get("bbl"),
            address=system.get("address"),
            borough=system.get("borough"),
            zip_value=system.get("zip"),
            system_ids=[str(system_id)],
        )
        for activity in detail.get("dob_activity_history") or []:
            if not isinstance(activity, Mapping):
                continue
            source_id = str(activity.get("job_filing_number") or stable_id("dob-now", activity.get("bbl"), activity.get("activity_date"), activity.get("job_description")))
            activity_date = activity.get("activity_date") or activity.get("filing_date")
            for role, field in (
                ("DOB_NOW_APPLICANT_BUSINESS", "applicant_business_name"),
                ("DOB_NOW_OWNER_BUSINESS", "owner_business_name"),
            ):
                raw_name = activity.get(field)
                firm = resolve_named_firm(raw_name)
                if not firm:
                    continue
                dedupe = (firm["firm_id"], role, source_id, str(site["site_id"]))
                if dedupe in seen_project_observations:
                    continue
                seen_project_observations.add(dedupe)
                _observe(
                    firm,
                    role=role,
                    source_class="NYC_DOB_NOW_JOB_APPLICATION_FILINGS",
                    date_value=activity_date,
                    alias=str(raw_name),
                )
                _upsert_site(
                    firm,
                    site,
                    role=role,
                    relationship_class="PROJECT_ROLE",
                    evidence_class=f"{role}_BBL_EXACT",
                    date_value=activity_date,
                    source_record_id=source_id,
                    project_role=True,
                )

        legacy_context = detail.get("legacy_dob_project_context")
        if isinstance(legacy_context, Mapping):
            for activity in legacy_context.get("records") or []:
                if not isinstance(activity, Mapping) or not activity.get("owner_business_name"):
                    continue
                raw_name = activity.get("owner_business_name")
                firm = resolve_named_firm(raw_name)
                if not firm:
                    continue
                source_id = str(activity.get("source_row_id") or stable_id("dob-bis", activity.get("bbl"), activity.get("job_number"), activity.get("document_number")))
                dedupe = (firm["firm_id"], "LEGACY_DOB_OWNER_BUSINESS", source_id, str(site["site_id"]))
                if dedupe in seen_project_observations:
                    continue
                seen_project_observations.add(dedupe)
                _observe(
                    firm,
                    role="LEGACY_DOB_OWNER_BUSINESS",
                    source_class="NYC_DOB_BIS_JOB_APPLICATION_FILINGS",
                    date_value=activity.get("activity_date"),
                    alias=str(raw_name),
                )
                _upsert_site(
                    firm,
                    site,
                    role="LEGACY_DOB_OWNER_BUSINESS",
                    relationship_class="PROJECT_ROLE",
                    evidence_class="LEGACY_DOB_OWNER_BUSINESS_BBL_EXACT",
                    date_value=activity.get("activity_date"),
                    source_record_id=source_id,
                    project_role=True,
                )

    details: dict[str, dict[str, Any]] = {}
    firm_rows: list[dict[str, Any]] = []
    unique_related_sites: set[str] = set()
    unique_serviced_sites: set[str] = set()
    unique_contracted_sites: set[str] = set()
    role_firm_counts: Counter[str] = Counter()

    active_since = as_of - timedelta(days=365)
    for firm in firms.values():
        site_rows: list[dict[str, Any]] = []
        tower_system_ids: set[str] = set()
        for site in firm["site_relationships"].values():
            system_ids = sorted(site.pop("system_ids"))
            roles = sorted(site.pop("roles"), key=lambda role: ROLE_ORDER.index(role) if role in ROLE_ORDER else 999)
            relationship_classes = sorted(site.pop("relationship_classes"))
            evidence_classes = sorted(site.pop("evidence_classes"))
            source_record_ids = sorted(site.pop("source_record_ids"))[:25]
            site["system_ids"] = system_ids
            site["roles"] = roles
            site["relationship_classes"] = relationship_classes
            site["evidence_classes"] = evidence_classes
            site["source_record_ids"] = source_record_ids
            site["tower_account_count"] = len(system_ids)
            site["mapped"] = site.get("latitude") is not None and site.get("longitude") is not None
            tower_system_ids.update(system_ids)
            unique_related_sites.add(str(site["site_id"]))
            if site["serviced"]:
                unique_serviced_sites.add(str(site["site_id"]))
            if site["contracted"]:
                unique_contracted_sites.add(str(site["site_id"]))
            site_rows.append(site)
        site_rows.sort(
            key=lambda row: (
                not bool(row["serviced"]),
                not bool(row["contracted"]),
                str(row.get("last_observed_date") or ""),
                str(row.get("address") or row["site_id"]),
            ),
            reverse=False,
        )

        roles = sorted(firm["roles"], key=lambda role: ROLE_ORDER.index(role) if role in ROLE_ORDER else 999)
        for role in roles:
            role_firm_counts[role] += 1
        aliases = [
            {
                "name": name,
                "source_class": source_class,
                "role": role,
                "observation_count": count,
            }
            for (name, source_class, role), count in firm["alias_observations"].most_common()
        ]
        if not firm.get("procurement_company_id") and aliases:
            firm["canonical_name"] = aliases[0]["name"]
        latest = firm["latest_observed_date"]
        active_last_12m = False
        if latest:
            try:
                active_last_12m = date.fromisoformat(latest) >= active_since
            except ValueError:
                active_last_12m = False
        procurement = firm.get("procurement") or {}
        metrics = procurement.get("metrics") if isinstance(procurement.get("metrics"), Mapping) else {}
        serviced_site_count = sum(1 for site in site_rows if site["serviced"])
        contracted_site_count = sum(1 for site in site_rows if site["contracted"])
        project_site_count = sum(1 for site in site_rows if site["project_role"])
        mapped_site_count = sum(1 for site in site_rows if site["mapped"])
        active_qualification_count = sum(1 for item in firm["qualifications"] if item.get("active_as_of_generation"))
        primary_role = next((role for role in ROLE_ORDER if role in firm["roles"]), roles[0] if roles else "OBSERVED_FIRM")
        row = {
            "firm_id": firm["firm_id"],
            "canonical_name": firm["canonical_name"],
            "strict_name": firm["strict_name"],
            "normalized_name": firm["normalized_name"],
            "identity_confidence": firm["identity_confidence"],
            "resolution_method": firm["resolution_method"],
            "candidate_related_company_ids": sorted(firm["candidate_related_company_ids"]),
            "procurement_company_id": firm.get("procurement_company_id"),
            "roles": roles,
            "primary_role": primary_role,
            "role_counts": dict(sorted(firm["role_counts"].items())),
            "source_classes": sorted(firm["source_classes"]),
            "observation_count": int(firm["observation_count"]),
            "observed_site_count": len(site_rows),
            "serviced_site_count": serviced_site_count,
            "contracted_site_count": contracted_site_count,
            "project_site_count": project_site_count,
            "tower_account_count": len(tower_system_ids),
            "mapped_site_count": mapped_site_count,
            "first_observed_date": firm["first_observed_date"],
            "latest_observed_date": latest,
            "active_last_12m": active_last_12m,
            "qualification_count": len(firm["qualifications"]),
            "active_qualification_count": active_qualification_count,
            "observed_contract_count": int(metrics.get("observed_contract_count") or 0),
            "active_contract_count": int(metrics.get("active_contract_count") or 0),
            "observed_customer_count": int(metrics.get("observed_customer_count") or 0),
            "repeat_buyer_count": int(metrics.get("repeat_buyer_count") or 0),
            "observed_contract_value": float(metrics.get("observed_contract_value") or 0),
            "service_categories": list(procurement.get("service_categories") or []),
            "detail_path": _safe_firm_detail_path(str(firm["firm_id"])),
        }
        firm_rows.append(row)
        details[str(firm["firm_id"])] = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated_at or utc_now(),
            "domain": "TOWERSIGNAL_KNOWN_FIRM_DETAIL",
            "firm": row,
            "aliases": aliases,
            "site_relationships": site_rows,
            "qualifications": sorted(
                firm["qualifications"],
                key=lambda item: (str(item.get("registration_expiration_date") or ""), str(item.get("registration_number") or "")),
                reverse=True,
            ),
            "procurement": {
                "company_id": procurement.get("company_id"),
                "canonical_name": procurement.get("canonical_name"),
                "observed_sources": procurement.get("observed_sources") or [],
                "observed_buyers": procurement.get("observed_buyers") or [],
                "service_categories": procurement.get("service_categories") or [],
                "procurement_ids": procurement.get("procurement_ids") or [],
                "metrics": metrics,
                "value_semantics": procurement.get("value_semantics"),
            } if procurement else None,
            "evidence_boundaries": {
                "identity": "Firm identities normalize source-reported names conservatively. Legal suffixes are preserved. Exact procurement aliases may reuse an existing company ID; ambiguous aliases remain separate with review candidates.",
                "serviced_site": "Serviced-site counts include only DWT source rows that explicitly name an inspection firm or laboratory at a building/tank. Procurement and DOB role relationships do not increment serviced-site counts.",
                "contracted_site": "Contracted-site counts require a CONFIRMED procurement-to-TowerSignal account link. A public contract relationship is not represented as proof that work was completed.",
                "project_roles": "DOB applicant/owner business names are recorded project roles on exact property identities. They do not establish an incumbent service provider or maintenance relationship.",
                "qualification": "DEC Category 7G registration supports qualification only and does not establish a service relationship at any property.",
            },
        }

    firm_rows.sort(
        key=lambda row: (
            -int(row["serviced_site_count"]),
            -int(row["contracted_site_count"]),
            -int(row["observation_count"]),
            str(row["canonical_name"]),
        )
    )
    summary = {
        "known_firm_count": len(firm_rows),
        "firms_with_site_relationships": sum(1 for row in firm_rows if row["observed_site_count"] > 0),
        "firms_with_serviced_sites": sum(1 for row in firm_rows if row["serviced_site_count"] > 0),
        "firms_with_contracted_sites": sum(1 for row in firm_rows if row["contracted_site_count"] > 0),
        "firms_with_procurement_evidence": sum(1 for row in firm_rows if row["procurement_company_id"]),
        "firms_with_dwt_service_evidence": sum(1 for row in firm_rows if any(role in SERVICE_ROLES for role in row["roles"])),
        "unique_related_site_count": len(unique_related_sites),
        "unique_serviced_site_count": len(unique_serviced_sites),
        "unique_contracted_site_count": len(unique_contracted_sites),
        "firm_site_relationship_count": sum(int(row["observed_site_count"]) for row in firm_rows),
        "firm_serviced_site_relationship_count": sum(int(row["serviced_site_count"]) for row in firm_rows),
        "mapped_firm_site_relationship_count": sum(int(row["mapped_site_count"]) for row in firm_rows),
        "role_firm_counts": dict(sorted(role_firm_counts.items())),
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or utc_now(),
        "domain": DOMAIN,
        "summary": summary,
        "evidence_semantics": {
            "normalization": "Case, punctuation and spacing are normalized while legal entity suffixes are preserved. Existing procurement aliases are reused only on exact strict-name identity; ambiguous matches remain separate.",
            "serviced_sites": "A serviced site requires explicit source-reported DWT inspection-provider or laboratory evidence at that building/tank.",
            "related_sites": "Related sites may include observed DWT service, confirmed procurement tower relationships, or exact-property DOB business roles. Related does not mean serviced.",
            "last_active": "Latest observed date is the latest dated public-record observation attached to the firm; it is not a claim that the firm is currently under contract.",
            "procurement_value": "Observed public procurement value is not company revenue.",
        },
        "firms": firm_rows,
    }
    return payload, details
