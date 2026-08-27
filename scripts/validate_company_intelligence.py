#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Required input is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Malformed JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"Input must be an object: {path}")
    return payload


def normalized_tokens(value: Any) -> list[str]:
    return re.findall(r"[A-Z0-9]+", str(value or "").upper())


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate TowerSignal company intelligence against City Record + Checkbook inputs.")
    parser.add_argument("--companies", default="public/data/companies.json")
    parser.add_argument("--city-record", default="public/data/procurement-city-record.json")
    parser.add_argument("--checkbook", default="public/data/procurement-checkbook.json")
    args = parser.parse_args()

    company_payload = load_json(Path(args.companies))
    city_record = load_json(Path(args.city_record))
    checkbook = load_json(Path(args.checkbook))
    companies = company_payload.get("companies")
    notices = city_record.get("notices")
    contracts = checkbook.get("contracts")
    unresolved = company_payload.get("unresolved_vendor_observations")
    if not isinstance(companies, list) or not isinstance(unresolved, list):
        raise SystemExit("Company payload is missing companies[] or unresolved_vendor_observations[]")
    if not isinstance(notices, list) or not isinstance(contracts, list):
        raise SystemExit("Procurement inputs are missing notices[] or contracts[]")

    source_vendor_rows = [
        row for row in [*notices, *contracts]
        if isinstance(row, dict) and str(row.get("vendor_raw") or "").strip()
    ]
    source_by_id: dict[str, dict[str, Any]] = {}
    for row in source_vendor_rows:
        procurement_id = str(row.get("procurement_id") or "").strip()
        if not procurement_id:
            raise SystemExit("Source vendor observation is missing procurement_id")
        if procurement_id in source_by_id:
            raise SystemExit(f"Duplicate procurement_id across company source inputs: {procurement_id}")
        source_by_id[procurement_id] = row

    company_ids: set[str] = set()
    strict_keys: set[str] = set()
    assigned_ids: list[str] = []
    for company in companies:
        if not isinstance(company, dict):
            raise SystemExit("Company payload contains a non-object company")
        company_id = str(company.get("company_id") or "").strip()
        strict_key = str(company.get("strict_vendor_key") or "").strip()
        if not company_id or company_id in company_ids:
            raise SystemExit(f"Missing or duplicate company_id: {company_id!r}")
        if not strict_key or strict_key in strict_keys:
            raise SystemExit(f"Missing or duplicate strict_vendor_key: {strict_key!r}")
        company_ids.add(company_id)
        strict_keys.add(strict_key)

        if company.get("current_parent_company_id") is not None or company.get("current_sponsor_company_id") is not None:
            raise SystemExit(f"Observed procurement company {company_id} contains unsupported parent/sponsor assignment")

        procurement_ids = company.get("procurement_ids")
        if not isinstance(procurement_ids, list):
            raise SystemExit(f"Company {company_id} is missing procurement_ids[]")
        if int(company.get("procurement_observation_count") or 0) != len(procurement_ids):
            raise SystemExit(f"Company {company_id} procurement_observation_count does not match procurement_ids[]")
        for procurement_id in procurement_ids:
            value = str(procurement_id)
            if value not in source_by_id:
                raise SystemExit(f"Company {company_id} references procurement_id absent from source inputs: {value}")
            assigned_ids.append(value)

        base_tokens = normalized_tokens(company.get("normalized_base_name"))
        if len(base_tokens) < 2:
            if company.get("identity_confidence") != "VERIFY" or company.get("cross_source_resolution_confidence") != "VERIFY":
                raise SystemExit(f"Ambiguous short company label promoted above VERIFY: {company.get('canonical_name')}")

        semantics = str(company.get("value_semantics") or "").lower()
        if "not company revenue" not in semantics:
            raise SystemExit(f"Company {company_id} is missing observed-value semantics")

    if len(assigned_ids) != len(set(assigned_ids)):
        raise SystemExit("One procurement observation is assigned to more than one observed company")
    if set(assigned_ids) != set(source_by_id):
        missing = sorted(set(source_by_id) - set(assigned_ids))[:10]
        extra = sorted(set(assigned_ids) - set(source_by_id))[:10]
        raise SystemExit(f"Company aggregation does not exactly cover source vendor observations; missing={missing}, extra={extra}")

    summary = company_payload.get("summary") or {}
    if int(summary.get("procurement_observation_count") or -1) != len(source_vendor_rows):
        raise SystemExit("Company summary procurement_observation_count does not match source vendor observation count")
    if int(summary.get("observed_vendor_company_count") or -1) != len(companies):
        raise SystemExit("Company summary observed_vendor_company_count does not match companies[]")

    unresolved_ids = {str(row.get("procurement_id") or "") for row in unresolved if isinstance(row, dict)}
    for company in companies:
        if company.get("cross_source_resolution_confidence") == "VERIFY":
            for procurement_id in company.get("procurement_ids") or []:
                if str(procurement_id) not in unresolved_ids:
                    raise SystemExit(f"VERIFY company observation is missing from unresolved review queue: {procurement_id}")

    print(json.dumps({
        "company_count": len(companies),
        "source_vendor_observation_count": len(source_vendor_rows),
        "unresolved_review_count": len(unresolved),
        "exact_coverage": True,
        "unsupported_parent_or_sponsor_assignments": 0,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
