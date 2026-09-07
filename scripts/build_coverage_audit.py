from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "1.0"

# These are generated production artifacts, not new source ingestions. The audit
# reads them only after their existing build/validation gates have succeeded.
ARTIFACT_CONTRACTS = [
    ("domestic_water_market", "domestic-water-market.json", "BIN/source asset for observed service; source-native provider/lab identities", ["WHO_TO_PURSUE", "WHY_ACCOUNT_MATTERS"]),
    ("provider_resolution_review", "provider-resolution-review.json", "Review-only deterministic provider-name candidates; no automatic fuzzy merge", ["WHO_TO_PURSUE"]),
    ("nyc_building_water_signals", "nyc-water-signals.json", "Exact source BBL/BIN where published; context-only records remain unlinked", ["WHEN_TO_ACT", "WHY_ACCOUNT_MATTERS"]),
    ("nyc_historical_311_context", "historical-311-context.json", "2010-2024 DEP building-water requests aggregated by current exact TowerSignal BBL; raw events omitted", ["WHY_ACCOUNT_MATTERS"]),
    ("nyc_distribution_water", "nyc-distribution-water.json", "Source sample-site identity; no building crosswalk inferred", ["WHY_ACCOUNT_MATTERS"]),
    ("elap_source_probe", "elap-source-probe.json", "Official ELAP public-search contract probe only; no guessed laboratory IDs", ["WHO_TO_PURSUE"]),
    ("city_record_procurement", "procurement-city-record.json", "Source procurement identity; no property assignment without an exact source link", ["WHO_TO_PURSUE", "WHEN_TO_ACT"]),
    ("checkbook_procurement", "procurement-checkbook.json", "Source contract/vendor identity; no building assignment inferred", ["WHO_TO_PURSUE", "WHEN_TO_ACT"]),
    ("nys_authority_procurement", "procurement-nys-authorities.json", "Source authority/vendor identity; no building assignment inferred", ["WHO_TO_PURSUE", "WHEN_TO_ACT"]),
    ("openbook_water_procurement", "procurement-openbook-water.json", "Source contract/vendor identity with water-context guard", ["WHO_TO_PURSUE", "WHEN_TO_ACT"]),
    ("nycha_water_procurement", "procurement-nycha-water.json", "Source contract/release/line identity; NYCHA location remains context", ["WHO_TO_PURSUE", "WHEN_TO_ACT"]),
    ("companies", "companies.json", "Conservative cross-source observed-vendor aggregation; explicit evidence only", ["WHO_TO_PURSUE"]),
    ("deal_validation", "deal-validation.json", "Empirical validation artifact; does not authorize Priority Score changes", ["WHY_ACCOUNT_MATTERS"]),
    ("nys_public_water", "nys-public-water.json", "PWSID source spine; contacts/operators remain source-specific roles", ["WHO_TO_PURSUE", "WHY_ACCOUNT_MATTERS"]),
    ("nys_lsli_details", "nys-lsli-details.json", "Exact PWSID detail URL and internal PWSID validation", ["WHY_ACCOUNT_MATTERS", "WHEN_TO_ACT"]),
    ("nys_service_line_inventory", "nys-service-line-inventory-summary.json", "Source-native address/locality records; no PWSID inferred when absent", ["WHY_ACCOUNT_MATTERS"]),
]

SOURCE_RULES: dict[str, dict[str, Any]] = {
    "registrations": {"identity_key": "system_id", "scope": "AUTHORITATIVE_CURRENT_UNIVERSE", "decisions": ["WHO_TO_PURSUE"]},
    "inspections": {"identity_key": "system_id", "scope": "OBSERVED_PREVALENCE_NOT_COMPLETENESS", "decisions": ["WHEN_TO_ACT", "WHY_ACCOUNT_MATTERS"]},
    "oath": {"identity_key": "summons_number -> ticket_number exact", "scope": "EXACT_IDENTIFIER_MATCH", "decisions": ["WHEN_TO_ACT", "WHY_ACCOUNT_MATTERS"]},
    "pluto": {"identity_key": "BBL_EXACT", "scope": "EXPECTED_BBL_SOURCE_WITH_ACTIONABLE_UNMATCHED_REVIEW", "decisions": ["WHO_TO_PURSUE", "WHY_ACCOUNT_MATTERS"]},
    "dob_now_jobs": {"identity_key": "BBL_EXACT", "scope": "DOB_NOW_SCOPE_NOT_ALL_HISTORICAL_CONSTRUCTION", "decisions": ["WHEN_TO_ACT", "WHY_ACCOUNT_MATTERS"]},
    "hpd_registrations": {"identity_key": "BBL_EXACT", "scope": "QUALIFYING_MULTIPLE_DWELLING_SCOPE", "decisions": ["WHO_TO_PURSUE"]},
    "hpd_contacts": {"identity_key": "registration_id exact after BBL match", "scope": "QUALIFYING_MULTIPLE_DWELLING_SCOPE", "decisions": ["WHO_TO_PURSUE"]},
    "planimetric_cooling_towers": {"identity_key": "BIN_EXACT / source GlobalID", "scope": "2022_PHYSICAL_OBSERVATION_NOT_CURRENT_REGISTRY_EQUIVALENCE", "decisions": ["WHY_ACCOUNT_MATTERS"]},
    "building_footprints": {"identity_key": "BIN_EXACT", "scope": "BUILDING_CONTEXT", "decisions": ["WHY_ACCOUNT_MATTERS"]},
    "dwt_planimetric": {"identity_key": "BIN_EXACT", "scope": "2022_PHYSICAL_OBSERVATION", "decisions": ["WHO_TO_PURSUE", "WHY_ACCOUNT_MATTERS"]},
    "dwt_compliance": {"identity_key": "BIN_EXACT", "scope": "OBSERVED_REGULATORY_PREVALENCE", "decisions": ["WHO_TO_PURSUE", "WHEN_TO_ACT"]},
    "dwt_self_reports": {"identity_key": "BIN_EXACT", "scope": "OBSERVED_SERVICE_AND_INSPECTION_PREVALENCE", "decisions": ["WHO_TO_PURSUE", "WHEN_TO_ACT"]},
    "acris_recent": {"identity_key": "borough/block/lot exact", "scope": "365_DAY_ACTIVITY_PREVALENCE_NOT_COMPLETENESS", "decisions": ["WHEN_TO_ACT", "WHY_ACCOUNT_MATTERS"]},
    "nys_registry": {"identity_key": "Equipment_ID", "scope": "NYS_SOURCE_NATIVE_IDENTITY_SEPARATE_FROM_NYC", "decisions": ["WHO_TO_PURSUE"]},
}

ROW_PREDICATES: dict[str, Callable[[dict[str, Any]], bool]] = {
    "registrations": lambda row: True,
    "inspections": lambda row: int(row.get("inspection_count") or 0) > 0,
    "pluto": lambda row: bool(row.get("pluto_match")),
    "dob_now_jobs": lambda row: int(row.get("dob_activity_count") or 0) > 0,
    "hpd_contacts": lambda row: int(row.get("hpd_contact_count") or 0) > 0,
    "planimetric_cooling_towers": lambda row: bool(row.get("planimetric_bin_match")),
    "building_footprints": lambda row: bool(row.get("building_footprint_bin_match")),
    "dwt_planimetric": lambda row: bool(row.get("dwt_planimetric_bin_match")),
    "dwt_compliance": lambda row: int(row.get("dwt_compliance_record_count") or 0) > 0,
    "dwt_self_reports": lambda row: int(row.get("dwt_self_report_record_count") or 0) > 0,
    "acris_recent": lambda row: int(row.get("acris_recent_document_count") or 0) > 0,
}


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _scalar_snapshot(value: Any, *, max_items: int = 120) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if not isinstance(value, dict):
        return result
    for key, item in value.items():
        if len(result) >= max_items:
            break
        if item is None or isinstance(item, (str, int, float, bool)):
            result[str(key)] = item
        elif isinstance(item, dict):
            for child_key, child in item.items():
                if len(result) >= max_items:
                    break
                if child is None or isinstance(child, (str, int, float, bool)):
                    result[f"{key}.{child_key}"] = child
    return result


def _artifact_snapshot(output_dir: Path, key: str, filename: str, identity: str, decisions: list[str]) -> dict[str, Any]:
    path = output_dir / filename
    payload = load_json(path)
    snapshot: dict[str, Any] = {
        "source_key": key,
        "artifact": filename,
        "integration_status": "INTEGRATED" if path.exists() else "MISSING_EXPECTED_ARTIFACT",
        "authoritative_contract": identity,
        "decisions_supported": decisions,
        "exists": path.exists(),
        "artifact_bytes": path.stat().st_size if path.exists() else 0,
    }
    if isinstance(payload, dict):
        snapshot["schema_version"] = payload.get("schema_version")
        snapshot["generated_at"] = payload.get("generated_at") or (payload.get("metadata") or {}).get("generated_at") or (payload.get("source") or {}).get("generated_at")
        snapshot["summary_metrics"] = _scalar_snapshot(payload.get("summary") or {})
        snapshot["metadata_metrics"] = _scalar_snapshot(payload.get("metadata") or payload.get("source") or {})
    return snapshot


def _borough_counts(systems: list[dict[str, Any]], predicate: Callable[[dict[str, Any]], bool]) -> dict[str, int]:
    counts = Counter(str(row.get("borough") or "UNKNOWN") for row in systems if predicate(row))
    return dict(sorted(counts.items()))


def _identifier_gap(systems: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(systems)

    def registry_bbl(row: dict[str, Any]) -> str | None:
        value = row.get("registry_bbl") if "registry_bbl" in row else row.get("bbl")
        return str(value) if value else None

    registry_bbls = [value for row in systems if (value := registry_bbl(row))]
    canonical_bbls = [str(row.get("bbl")) for row in systems if row.get("bbl")]
    usable_bin = [str(row.get("bin")) for row in systems if row.get("bin")]
    recovered = [row for row in systems if row.get("bbl_identity_status") == "RECOVERED_EXACT_BIN_MAPPLUTO_BBL"]

    by_borough: dict[str, dict[str, int]] = {}
    for row in systems:
        borough = str(row.get("borough") or "UNKNOWN")
        bucket = by_borough.setdefault(
            borough,
            {
                "systems": 0,
                "with_bbl": 0,
                "with_registry_source_bbl": 0,
                "with_canonical_bbl": 0,
                "recovered_bbl": 0,
                "with_bin": 0,
            },
        )
        source_bbl = registry_bbl(row)
        bucket["systems"] += 1
        bucket["with_bbl"] += int(bool(source_bbl))
        bucket["with_registry_source_bbl"] += int(bool(source_bbl))
        bucket["with_canonical_bbl"] += int(bool(row.get("bbl")))
        bucket["recovered_bbl"] += int(row.get("bbl_identity_status") == "RECOVERED_EXACT_BIN_MAPPLUTO_BBL")
        bucket["with_bin"] += int(bool(row.get("bin")))

    return {
        "systems": total,
        "with_bbl": len(registry_bbls),
        "missing_bbl": total - len(registry_bbls),
        "unique_bbl": len(set(registry_bbls)),
        "with_registry_source_bbl": len(registry_bbls),
        "missing_registry_source_bbl": total - len(registry_bbls),
        "with_canonical_bbl": len(canonical_bbls),
        "missing_canonical_bbl": total - len(canonical_bbls),
        "unique_canonical_bbl": len(set(canonical_bbls)),
        "recovered_bbl_count": len(recovered),
        "with_bin": len(usable_bin),
        "missing_bin": total - len(usable_bin),
        "unique_bin": len(set(usable_bin)),
        "bbl_semantics": {
            "with_bbl": "Registry-source BBL coverage; recovered identifiers do not inflate source completeness.",
            "with_canonical_bbl": "Canonical BBL available for exact downstream joins after conservative identity recovery.",
            "recovery": "Exact BIN to one unique published MapPLUTO BBL with borough-prefix reconciliation; no address or fuzzy matching.",
        },
        "by_borough": dict(sorted(by_borough.items())),
    }


def _storage(output_dir: Path) -> dict[str, Any]:
    all_files = [path for path in output_dir.rglob("*") if path.is_file()]
    details = [path for path in all_files if "details" in path.parts]
    history = [path for path in all_files if "history" in path.parts]
    top_level = [path for path in all_files if path.parent == output_dir]
    return {
        "public_data_total_bytes": sum(path.stat().st_size for path in all_files),
        "top_level_artifact_bytes": sum(path.stat().st_size for path in top_level),
        "detail_artifact_bytes": sum(path.stat().st_size for path in details),
        "history_artifact_bytes": sum(path.stat().st_size for path in history),
        "systems_json_bytes": (output_dir / "systems.json").stat().st_size if (output_dir / "systems.json").exists() else 0,
        "source_health_json_bytes": (output_dir / "source-health.json").stat().st_size if (output_dir / "source-health.json").exists() else 0,
        "file_count": len(all_files),
        "detail_file_count": len(details),
    }


def _history_depth(output_dir: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for label, filename in (("nyc", "history/events.json"), ("nys", "history/nys/events.json")):
        path = output_dir / filename
        payload = load_json(path, {})
        events = payload.get("events") if isinstance(payload, dict) else None
        result[label] = {
            "artifact": filename,
            "exists": path.exists(),
            "bytes": path.stat().st_size if path.exists() else 0,
            "event_count": len(events) if isinstance(events, list) else None,
            "history_started_at": payload.get("history_started_at") if isinstance(payload, dict) else None,
            "generated_at": payload.get("generated_at") if isinstance(payload, dict) else None,
        }
    return result


def _gap_analysis(metadata: dict[str, Any], source_health_by_key: dict[str, dict[str, Any]], elap_probe: dict[str, Any] | None) -> list[dict[str, Any]]:
    def entry(key: str) -> dict[str, Any]:
        return source_health_by_key.get(key, {})

    dob = entry("dob_now_jobs")
    pluto = entry("pluto")
    hpd = entry("hpd_registrations")
    acris = entry("acris_recent")
    elap_status = None
    if isinstance(elap_probe, dict):
        elap_status = elap_probe.get("status") or elap_probe.get("source_status") or elap_probe.get("result")

    return [
        {
            "gap_key": "DOB_NOW",
            "classification": "MIXED_EXPECTED_SCOPE_AND_ACTIONABLE_DIAGNOSTIC",
            "observed": {"requested_bbl": dob.get("requested_entity_count"), "matched_bbl": dob.get("matched_entity_count"), "coverage_percentage": dob.get("coverage_percentage")},
            "interpretation": "DOB NOW is not a complete historical construction archive. Unmatched exact BBLs must be separated into no usable identifier, DOB NOW source scope, legacy-only history, and genuine retrieval/join misses before any new source is added.",
            "next_action": "Evaluate legacy DOB/BIS only after this audit and the physical-inventory diagnostic; do not fuzzy-match BBLs.",
        },
        {
            "gap_key": "PLUTO",
            "classification": "ACTIONABLE_EXACT_IDENTIFIER_REVIEW",
            "observed": {"requested_bbl": pluto.get("requested_entity_count"), "matched_bbl": pluto.get("matched_entity_count"), "coverage_percentage": pluto.get("coverage_percentage")},
            "interpretation": "PLUTO is expected to cover tax lots, but missing/invalid source BBLs and atypical records can be legitimate. Review exact-BBL misses before treating the percentage as a defect.",
            "next_action": "Classify missing-BBL versus usable-BBL-unmatched records; preserve exact joins only.",
        },
        {
            "gap_key": "HPD",
            "classification": "EXPECTED_SOURCE_SCOPE_LIMITATION",
            "observed": {"requested_bbl": hpd.get("requested_entity_count"), "matched_registration_bbl": hpd.get("matched_entity_count"), "coverage_percentage": hpd.get("coverage_percentage")},
            "interpretation": "HPD registration/contact data applies to qualifying multiple dwellings. Non-match is not missing owner/manager evidence and cannot be filled by invented contacts.",
            "next_action": "Measure contactability outside HPD separately; evaluate authoritative owner/manager sources only where they add exact evidence.",
        },
        {
            "gap_key": "ACRIS",
            "classification": "PREVALENCE_NOT_COMPLETENESS",
            "observed": {"requested_bbl": acris.get("requested_entity_count"), "recent_activity_bbl": acris.get("matched_entity_count"), "coverage_percentage": acris.get("coverage_percentage"), "status": acris.get("status")},
            "interpretation": "The ACRIS metric is bounded recent relevant-document activity prevalence, not a completeness percentage. A non-match does not mean the property lacks recorded history.",
            "next_action": "Use ACRIS as a timing signal only; do not inflate coverage by expanding unrelated document classes.",
        },
        {
            "gap_key": "NYS",
            "classification": "SEPARATE_IDENTITY_REGIME",
            "observed": {"normalized_equipment_count": metadata.get("normalized_equipment_count")},
            "interpretation": "NYS uses source-native Equipment_ID and statewide source semantics. NYC BBL/BIN coverage percentages are not a valid denominator for NYS equipment.",
            "next_action": "Keep NYS coverage and history separate from NYC identity semantics.",
        },
        {
            "gap_key": "CMS",
            "classification": "NOT_INTEGRATED_SOURCE_CONTRACT_REQUIRED",
            "observed": {"integrated": False},
            "interpretation": "No authoritative CMS dataset and exact TowerSignal join contract is currently integrated in the repository.",
            "next_action": "Before ingestion, identify the exact CMS dataset, authoritative entity key, incremental matched population, freshness/runtime footprint, and a concrete who/when/why decision it improves. No fuzzy name/address attachment.",
        },
        {
            "gap_key": "NYC_311_HISTORICAL",
            "classification": "BOUNDED_HISTORICAL_CONTEXT_INTEGRATED",
            "observed": {"integrated": True, "current_signal_window": "2025+", "historical_context_window": "2010-2024", "commercial_lift_run": 34158852047, "historical_only_tower_bbl_count": 1908},
            "interpretation": "Measured exact-BBL lift justified compact 2010-2024 building-water context for why an account matters. Historical requests remain explicitly separate from current signals and are not current-condition or timing evidence.",
            "next_action": "Retain compact per-BBL counts/categories/years/dates only; no raw historical events, score changes, current trigger, fuzzy matching, or provider inference.",
        },
        {
            "gap_key": "ELAP",
            "classification": "SOURCE_CONTRACT_LIMITATION_OR_PROBE",
            "observed": {"probe_status": elap_status},
            "interpretation": "ELAP scope ingestion remains gated on a deterministic authoritative way to enumerate current laboratories. IDs must not be brute-forced or derived from names.",
            "next_action": "Advance only if the official public source exposes stable lab keys; otherwise retain SOURCE_UNAVAILABLE/source-limitation semantics.",
        },
    ]


def build(output_dir: Path, output_file: Path | None = None, markdown_file: Path | None = None) -> dict[str, Any]:
    systems_payload = load_json(output_dir / "systems.json")
    nys_payload = load_json(output_dir / "nys-systems.json")
    source_health_payload = load_json(output_dir / "source-health.json")
    if not isinstance(systems_payload, dict) or not isinstance(nys_payload, dict) or not isinstance(source_health_payload, dict):
        raise RuntimeError("Coverage audit requires generated systems.json, nys-systems.json and source-health.json")

    metadata = systems_payload.get("metadata") or {}
    systems = systems_payload.get("systems") or []
    nys_metadata = nys_payload.get("metadata") or {}
    health_entries = source_health_payload.get("sources") or metadata.get("source_health") or []
    if not isinstance(systems, list) or not isinstance(health_entries, list):
        raise RuntimeError("Coverage audit received malformed systems/source-health arrays")

    source_health_by_key = {str(item.get("source_key")): item for item in health_entries if isinstance(item, dict)}
    standardized_sources: list[dict[str, Any]] = []
    for item in health_entries:
        if not isinstance(item, dict):
            continue
        key = str(item.get("source_key") or "")
        rule = SOURCE_RULES.get(key, {})
        enriched = dict(item)
        enriched["integration_status"] = "INTEGRATED"
        enriched["identity_key"] = rule.get("identity_key", "SOURCE_NATIVE_OR_DOCUMENTED_IN_SOURCE_ADAPTER")
        enriched["scope_classification"] = rule.get("scope", "SOURCE_NATIVE_METRIC_REVIEW_REQUIRED")
        enriched["decisions_supported"] = rule.get("decisions", [])
        predicate = ROW_PREDICATES.get(key)
        enriched["borough_breakdown"] = _borough_counts(systems, predicate) if predicate else None
        standardized_sources.append(enriched)

    artifact_sources = [
        _artifact_snapshot(output_dir, key, filename, identity, decisions)
        for key, filename, identity, decisions in ARTIFACT_CONTRACTS
    ]
    missing_required = [item["artifact"] for item in artifact_sources if not item["exists"]]
    if missing_required:
        raise RuntimeError("Coverage audit missing expected generated artifact(s): " + ", ".join(missing_required))

    elap_probe = load_json(output_dir / "elap-source-probe.json")
    generated_at = metadata.get("generated_at") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "audit_scope": "Existing generated TowerSignal production artifacts only; no new source ingestion or fuzzy matching.",
        "nyc": {
            "system_count": len(systems),
            "identifier_coverage": _identifier_gap(systems),
            "metadata_metrics": _scalar_snapshot(metadata),
        },
        "nys": {
            "system_count": len(nys_payload.get("systems") or []),
            "identity_regime": "Equipment_ID source-native; separate from NYC BBL/BIN semantics",
            "metadata_metrics": _scalar_snapshot(nys_metadata),
        },
        "standardized_coverage_sources": standardized_sources,
        "source_artifacts": artifact_sources,
        "gap_analysis": _gap_analysis({**metadata, **nys_metadata}, source_health_by_key, elap_probe if isinstance(elap_probe, dict) else None),
        "history_depth": _history_depth(output_dir),
        "storage_footprint": _storage(output_dir),
        "governance": {
            "priority_score_1_0_changed": False,
            "opportunity_score_authorized": False,
            "fuzzy_matching_used": False,
            "new_source_ingestion_performed": False,
            "ui_redesign_performed": False,
            "follow_on_rule": "New source, Prospect-column, or Opportunity Score work must cite this audit and state the exact coverage/commercial decision improved.",
        },
    }

    output_path = output_file or output_dir / "coverage-audit.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    markdown_path = markdown_file or output_dir / "coverage-audit.md"
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# TowerSignal data completeness audit",
        "",
        f"Generated: {report.get('generated_at')}",
        "",
        "This report measures existing generated production artifacts only. It does not add sources, change Priority Score 1.0, or use fuzzy matching.",
        "",
        "## Standardized coverage matrix",
        "",
        "| Source | Identity | Requested | Retrieved | Matched | Attached | Coverage | Scope | Decision |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for source in report.get("standardized_coverage_sources", []):
        coverage = source.get("coverage_percentage")
        coverage_text = "—" if coverage is None else f"{coverage:.2f}%"
        lines.append(
            f"| {source.get('name')} | {source.get('identity_key')} | {source.get('requested_entity_count', 0):,} | "
            f"{source.get('retrieved_record_count', 0):,} | {source.get('matched_entity_count', 0):,} | "
            f"{source.get('attached_entity_count', 0):,} | {coverage_text} | {source.get('scope_classification')} | "
            f"{', '.join(source.get('decisions_supported') or []) or 'context'} |"
        )
    lines.extend(["", "## Explicit gap classifications", ""])
    for gap in report.get("gap_analysis", []):
        lines.extend([
            f"### {gap.get('gap_key')} — {gap.get('classification')}",
            "",
            str(gap.get("interpretation") or ""),
            "",
            f"Next: {gap.get('next_action')}",
            "",
        ])
    storage = report.get("storage_footprint") or {}
    lines.extend([
        "## Storage footprint",
        "",
        f"- public/data total: {int(storage.get('public_data_total_bytes') or 0):,} bytes",
        f"- systems.json: {int(storage.get('systems_json_bytes') or 0):,} bytes",
        f"- detail artifacts: {int(storage.get('detail_artifact_bytes') or 0):,} bytes across {int(storage.get('detail_file_count') or 0):,} files",
        f"- durable history artifacts in deployed output: {int(storage.get('history_artifact_bytes') or 0):,} bytes",
        "",
        "## Governance",
        "",
        "Priority Score 1.0 is unchanged. This audit does not authorize Opportunity Score 2.0. No fuzzy joins were used.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build TowerSignal data completeness audit from generated production artifacts")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data", help="Generated TowerSignal public/data directory")
    parser.add_argument("--report", type=Path, help="JSON report path; defaults to <output>/coverage-audit.json")
    parser.add_argument("--markdown", type=Path, help="Markdown report path; defaults to <output>/coverage-audit.md")
    args = parser.parse_args()
    report = build(args.output, args.report, args.markdown)
    print(json.dumps({
        "standardized_source_count": len(report["standardized_coverage_sources"]),
        "artifact_source_count": len(report["source_artifacts"]),
        "gap_count": len(report["gap_analysis"]),
        "storage_footprint": report["storage_footprint"],
    }, indent=2))


if __name__ == "__main__":
    main()
