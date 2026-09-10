from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

MIN_PRODUCTION_FIRMS = 300
MIN_PRODUCTION_DWT_SERVICE_FIRMS = 100
MIN_PRODUCTION_PROCUREMENT_FIRMS = 100
MIN_PRODUCTION_SERVICED_SITES = 1000
MAX_SUMMARY_BYTES = 32 * 1024 * 1024


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"Required known-firms payload is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Known-firms payload must be a JSON object: {path}")
    return payload


def _generated_age_days(value: Any) -> float:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError("Known-firms generated_at is missing")
    generated = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    return (datetime.now(timezone.utc) - generated).total_seconds() / 86400


def validate(path: Path, *, max_age_days: float, require_production_volume: bool = False) -> dict[str, Any]:
    if path.stat().st_size > MAX_SUMMARY_BYTES:
        raise RuntimeError(f"Known-firms summary exceeds size ceiling: {path.stat().st_size:,} bytes")
    payload = load_json(path)
    if payload.get("schema_version") != "1.0" or payload.get("domain") != "TOWERSIGNAL_KNOWN_FIRMS":
        raise RuntimeError("Known-firms schema/domain contract is invalid")
    age_days = _generated_age_days(payload.get("generated_at"))
    if age_days < -0.25:
        raise RuntimeError(f"Known-firms generated_at is implausibly in the future: {age_days:.2f} days")
    if age_days > max_age_days:
        raise RuntimeError(f"Known-firms payload is stale: {age_days:.2f} days > {max_age_days}")

    firms = payload.get("firms")
    summary = payload.get("summary")
    if not isinstance(firms, list) or not firms or not isinstance(summary, dict):
        raise RuntimeError("Known-firms payload is missing firms or summary")

    firm_ids: set[str] = set()
    unique_related_sites: set[str] = set()
    unique_serviced_sites: set[str] = set()
    unique_contracted_sites: set[str] = set()
    firms_with_sites = 0
    firms_with_service = 0
    firms_with_contracts = 0
    firms_with_procurement = 0
    firms_with_dwt = 0
    firm_site_relationship_count = 0
    firm_service_relationship_count = 0
    mapped_relationship_count = 0

    for row in firms:
        if not isinstance(row, dict):
            raise RuntimeError("Known-firms row is not an object")
        firm_id = str(row.get("firm_id") or "")
        if not firm_id or firm_id in firm_ids:
            raise RuntimeError(f"Known-firms contains missing or duplicate firm_id: {firm_id!r}")
        firm_ids.add(firm_id)
        if not row.get("canonical_name") or not row.get("roles"):
            raise RuntimeError(f"Known-firm {firm_id} is missing canonical name or roles")
        observed_sites = int(row.get("observed_site_count") or 0)
        serviced_sites = int(row.get("serviced_site_count") or 0)
        contracted_sites = int(row.get("contracted_site_count") or 0)
        mapped_sites = int(row.get("mapped_site_count") or 0)
        if min(observed_sites, serviced_sites, contracted_sites, mapped_sites, int(row.get("observation_count") or 0)) < 0:
            raise RuntimeError(f"Known-firm {firm_id} has negative metrics")
        if serviced_sites > observed_sites or contracted_sites > observed_sites or mapped_sites > observed_sites:
            raise RuntimeError(f"Known-firm {firm_id} site metrics do not reconcile")
        if firm_id in set(row.get("candidate_related_company_ids") or []):
            raise RuntimeError(f"Known-firm {firm_id} lists itself as a resolution candidate")

        detail_path = row.get("detail_path")
        if not isinstance(detail_path, str) or not detail_path.startswith("firm-details/"):
            raise RuntimeError(f"Known-firm {firm_id} has invalid detail_path")
        detail = load_json(path.parent / detail_path)
        detail_firm = detail.get("firm") or {}
        if detail_firm.get("firm_id") != firm_id:
            raise RuntimeError(f"Known-firm detail identity mismatch for {firm_id}")
        sites = detail.get("site_relationships")
        if not isinstance(sites, list) or len(sites) != observed_sites:
            raise RuntimeError(f"Known-firm {firm_id} detail site count does not match summary")
        site_ids: set[str] = set()
        service_count = 0
        contract_count = 0
        mapped_count = 0
        tower_accounts: set[str] = set()
        for site in sites:
            if not isinstance(site, dict):
                raise RuntimeError(f"Known-firm {firm_id} contains malformed site relationship")
            site_id = str(site.get("site_id") or "")
            if not site_id or site_id in site_ids:
                raise RuntimeError(f"Known-firm {firm_id} contains missing or duplicate site_id {site_id!r}")
            site_ids.add(site_id)
            unique_related_sites.add(site_id)
            system_ids = [str(value) for value in (site.get("system_ids") or []) if value]
            tower_accounts.update(system_ids)
            latitude, longitude = site.get("latitude"), site.get("longitude")
            if (latitude is None) != (longitude is None):
                raise RuntimeError(f"Known-firm {firm_id} site {site_id} has partial coordinates")
            if latitude is not None:
                try:
                    lat, lon = float(latitude), float(longitude)
                except (TypeError, ValueError) as exc:
                    raise RuntimeError(f"Known-firm {firm_id} site {site_id} has invalid coordinates") from exc
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    raise RuntimeError(f"Known-firm {firm_id} site {site_id} coordinates are out of range")
                mapped_count += 1
            if site.get("serviced"):
                service_count += 1
                unique_serviced_sites.add(site_id)
                evidence = set(site.get("evidence_classes") or [])
                roles = set(site.get("roles") or [])
                if not evidence.intersection({"DWT_INSPECTION_BY_FIRM_OBSERVED_SERVICE", "DWT_LAB_NAME_OBSERVED_SERVICE"}):
                    raise RuntimeError(f"Known-firm {firm_id} site {site_id} is marked serviced without explicit DWT service evidence")
                if not roles.intersection({"DWT_INSPECTION_PROVIDER", "DWT_LABORATORY"}):
                    raise RuntimeError(f"Known-firm {firm_id} site {site_id} is marked serviced without a service role")
            if site.get("contracted"):
                contract_count += 1
                unique_contracted_sites.add(site_id)
                if "PROCUREMENT_TOWER_LINK_CONFIRMED" not in set(site.get("evidence_classes") or []):
                    raise RuntimeError(f"Known-firm {firm_id} site {site_id} is marked contracted without confirmed tower-link evidence")

        if service_count != serviced_sites or contract_count != contracted_sites or mapped_count != mapped_sites:
            raise RuntimeError(f"Known-firm {firm_id} detail metrics do not reconcile")
        if len(tower_accounts) != int(row.get("tower_account_count") or 0):
            raise RuntimeError(f"Known-firm {firm_id} tower-account count does not reconcile")

        firm_site_relationship_count += observed_sites
        firm_service_relationship_count += serviced_sites
        mapped_relationship_count += mapped_sites
        firms_with_sites += int(observed_sites > 0)
        firms_with_service += int(serviced_sites > 0)
        firms_with_contracts += int(contracted_sites > 0)
        firms_with_procurement += int(bool(row.get("procurement_company_id")))
        firms_with_dwt += int(bool(set(row.get("roles") or []).intersection({"DWT_INSPECTION_PROVIDER", "DWT_LABORATORY"})))

    reconciliations = {
        "known_firm_count": len(firms),
        "firms_with_site_relationships": firms_with_sites,
        "firms_with_serviced_sites": firms_with_service,
        "firms_with_contracted_sites": firms_with_contracts,
        "firms_with_procurement_evidence": firms_with_procurement,
        "firms_with_dwt_service_evidence": firms_with_dwt,
        "unique_related_site_count": len(unique_related_sites),
        "unique_serviced_site_count": len(unique_serviced_sites),
        "unique_contracted_site_count": len(unique_contracted_sites),
        "firm_site_relationship_count": firm_site_relationship_count,
        "firm_serviced_site_relationship_count": firm_service_relationship_count,
        "mapped_firm_site_relationship_count": mapped_relationship_count,
    }
    for key, expected in reconciliations.items():
        if int(summary.get(key) or 0) != expected:
            raise RuntimeError(f"Known-firms summary {key} does not reconcile: {summary.get(key)} != {expected}")

    if require_production_volume:
        if len(firms) < MIN_PRODUCTION_FIRMS:
            raise RuntimeError(f"Known-firms production firm count is too low: {len(firms)}")
        if firms_with_dwt < MIN_PRODUCTION_DWT_SERVICE_FIRMS:
            raise RuntimeError(f"Known-firms DWT service-firm count is too low: {firms_with_dwt}")
        if firms_with_procurement < MIN_PRODUCTION_PROCUREMENT_FIRMS:
            raise RuntimeError(f"Known-firms procurement-firm count is too low: {firms_with_procurement}")
        if len(unique_serviced_sites) < MIN_PRODUCTION_SERVICED_SITES:
            raise RuntimeError(f"Known-firms serviced-site count is too low: {len(unique_serviced_sites)}")

    report = {
        "status": "PASS",
        "age_days": round(age_days, 4),
        "size_bytes": path.stat().st_size,
        **reconciliations,
    }
    print(json.dumps(report, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate TowerSignal normalized known-firm intelligence")
    parser.add_argument("--input", type=Path, default=ROOT / "public/data/known-firms.json")
    parser.add_argument("--max-age-days", type=float, default=1.0)
    parser.add_argument("--require-production-volume", action="store_true")
    args = parser.parse_args()
    validate(args.input, max_age_days=args.max_age_days, require_production_volume=args.require_production_volume)


if __name__ == "__main__":
    main()
