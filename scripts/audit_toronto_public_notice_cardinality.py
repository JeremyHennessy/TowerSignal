from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from toronto_app_sources import _record_for_link, load_source_rows
from toronto_market_common import canonical_street_address

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data/toronto/market/current"
REPORT = MARKET / "public_notice_cardinality_audit.json"
NOTICE_SOURCE = "toronto_public_notices_exact_prior_poc"
AIC_SOURCE = "toronto_aic_applications"


def load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def normalize_application(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", clean(value).upper())


def notice_addresses(row: dict[str, Any]) -> set[str]:
    output: set[str] = set()
    for item in row.get("addressList") or []:
        if isinstance(item, dict):
            for key in ("fullAddress", "streetAddress"):
                value = canonical_street_address(item.get(key))
                if value:
                    output.add(value)
        elif isinstance(item, str):
            value = canonical_street_address(item)
            if value:
                output.add(value)
    return output


def main() -> None:
    link_payload = load(MARKET / "property_source_links.json")
    links = [link for link in link_payload.get("links", []) if isinstance(link, dict)]
    source_rows = load_source_rows(ROOT, load)

    # Build application number -> exact property IDs from already validated AIC links.
    aic_properties: dict[str, set[str]] = defaultdict(set)
    for link in links:
        if clean(link.get("source_key")) != AIC_SOURCE:
            continue
        row = _record_for_link(link, source_rows)
        app = normalize_application(row.get("APPLICATION_NUMBER"))
        pid = clean(link.get("property_id"))
        if app and pid:
            aic_properties[app].add(pid)

    notice_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for link in links:
        if clean(link.get("source_key")) == NOTICE_SOURCE:
            notice_groups[clean(link.get("source_record_id"))].append(link)

    reviewed = 0
    multi_property = 0
    validated_direct_address = 0
    validated_application = 0
    invalid: list[dict[str, Any]] = []
    ambiguous_contract: list[dict[str, Any]] = []
    max_properties = 0

    for record_id, group in sorted(notice_groups.items()):
        if not group:
            continue
        reviewed += 1
        pids = {clean(link.get("property_id")) for link in group if clean(link.get("property_id"))}
        max_properties = max(max_properties, len(pids))
        if len(pids) > 1:
            multi_property += 1
        row = _record_for_link(group[0], source_rows)
        if not row:
            invalid.append({"source_record_id": record_id, "reason": "NOTICE_ROW_NOT_RESOLVED", "property_ids": sorted(pids)})
            continue
        addresses = notice_addresses(row)
        apps = {normalize_application(value) for value in (row.get("planningApplicationNumbers") or []) if normalize_application(value)}
        allowed_by_app: set[str] = set()
        for app in apps:
            allowed_by_app.update(aic_properties.get(app, set()))

        for link in group:
            pid = clean(link.get("property_id"))
            basis = clean(link.get("match_basis"))
            source_address = canonical_street_address(link.get("source_address"))
            if "PUBLIC_NOTICE_APPLICATION_NUMBER_TO_DETERMINISTIC_AIC_PROPERTY_LINK" in basis:
                if pid and pid in allowed_by_app:
                    validated_application += 1
                else:
                    invalid.append({
                        "source_record_id": record_id,
                        "property_id": pid,
                        "reason": "APPLICATION_LINK_NOT_SUPPORTED_BY_NOTICE_AIC_MEMBERSHIP",
                        "match_basis": basis,
                        "notice_applications": sorted(apps),
                        "allowed_property_ids": sorted(allowed_by_app),
                    })
            elif "ADDRESS" in basis:
                if source_address and source_address in addresses:
                    validated_direct_address += 1
                else:
                    invalid.append({
                        "source_record_id": record_id,
                        "property_id": pid,
                        "reason": "ADDRESS_LINK_NOT_LISTED_ON_NOTICE",
                        "match_basis": basis,
                        "source_address": source_address,
                        "notice_addresses": sorted(addresses),
                    })
            else:
                ambiguous_contract.append({
                    "source_record_id": record_id,
                    "property_id": pid,
                    "match_basis": basis,
                    "source_address": source_address,
                })

    report = {
        "schema_version": "toronto-public-notice-cardinality-audit-1.0",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "PASSED" if not invalid and not ambiguous_contract else "FAILED",
        "counts": {
            "unique_notice_records": reviewed,
            "multi_property_notice_records": multi_property,
            "max_properties_per_notice": max_properties,
            "validated_direct_address_links": validated_direct_address,
            "validated_application_membership_links": validated_application,
            "invalid_links": len(invalid),
            "unknown_match_contract_links": len(ambiguous_contract),
        },
        "contract": {
            "direct_address": "Property link is valid only when the normalized link source_address is explicitly present in the notice addressList.",
            "application_membership": "Property link is valid only when the notice planningApplicationNumbers contains an application number whose deterministic AIC source link resolves to that same property.",
        },
        "invalid": invalid[:500],
        "unknown_match_contract": ambiguous_contract[:500],
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "counts": report["counts"]}, indent=2))
    if report["status"] != "PASSED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
