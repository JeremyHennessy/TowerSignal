from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PWS_ID_RE = re.compile(r"^NY\d{7}$")


def _timestamp(value: Any) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise RuntimeError("Missing generated_at timestamp")
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def validate(path: Path, *, max_age_days: int, require_production_volume: bool) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0" or payload.get("domain") != "NYS_PUBLIC_WATER_SYSTEMS":
        raise RuntimeError("Unexpected NYS public-water cache schema/domain")
    age = (datetime.now(timezone.utc) - _timestamp(payload.get("generated_at"))).total_seconds() / 86400
    if age < -0.05 or age > max_age_days:
        raise RuntimeError(f"NYS public-water cache generated_at age is {age:.2f} days")

    summary = payload.get("summary")
    sources = payload.get("source_health")
    if not isinstance(summary, dict) or not isinstance(sources, list) or len(sources) != 4:
        raise RuntimeError("NYS public-water cache must contain summary and four source-health records")
    for source in sources:
        if source.get("status") != "HEALTHY" or source.get("pagination_complete") is not True or source.get("schema_valid") is not True:
            raise RuntimeError(f"Unhealthy NYSDOH source: {source.get('source')}")

    collections = {
        "pws_system_count": "pws_systems",
        "pws_contact_record_count": "pws_contacts",
        "certified_operator_count": "certified_operators",
        "lsli_required_system_count": "lsli_index",
        "violation_count_2025": "violations_2025",
    }
    for count_key, collection_key in collections.items():
        rows = payload.get(collection_key)
        if not isinstance(rows, list):
            raise RuntimeError(f"Missing collection {collection_key}")
        if len(rows) != int(summary.get(count_key) or 0):
            raise RuntimeError(f"Summary mismatch for {count_key}")

    pws_ids: set[str] = set()
    for row in payload["pws_systems"]:
        pws_id = str(row.get("pws_id") or "")
        if not PWS_ID_RE.fullmatch(pws_id):
            raise RuntimeError(f"Invalid PWS ID in system spine: {pws_id!r}")
        if pws_id in pws_ids:
            raise RuntimeError(f"Duplicate PWS profile: {pws_id}")
        pws_ids.add(pws_id)
        contacts = row.get("contacts")
        if not isinstance(contacts, list):
            raise RuntimeError(f"PWS {pws_id} contacts are not a list")
        if len(contacts) != int(row.get("contact_count") or 0):
            raise RuntimeError(f"PWS {pws_id} contact-count mismatch")
        for contact in contacts:
            if contact.get("relationship_role") != "CONTACT_FOR_PWS" or contact.get("operator_assignment_confidence") != "NOT_PROOF_OF_OPERATOR_ROLE":
                raise RuntimeError(f"PWS directory contact was promoted beyond source evidence: {pws_id}")

    for row in payload["certified_operators"]:
        certification = str(row.get("certification_number") or "")
        if not PWS_ID_RE.fullmatch(certification):
            raise RuntimeError(f"Invalid operator certification number: {certification!r}")
        if row.get("relationship_evidence") != "QUALIFIED_OPERATOR" or row.get("pws_assignment_confidence") != "UNLINKED_TO_PWS":
            raise RuntimeError(f"Certified operator was incorrectly assigned to a PWS: {certification}")

    for row in payload["lsli_index"]:
        pws_id = str(row.get("pws_id") or "")
        if not PWS_ID_RE.fullmatch(pws_id) or row.get("lead_service_line_inventory_required") is not True:
            raise RuntimeError(f"Invalid LSLI row: {pws_id!r}")
        if not str(row.get("detail_url") or "").endswith(f"/{pws_id}.htm"):
            raise RuntimeError(f"Invalid LSLI detail URL for {pws_id}")

    violation_ids: set[str] = set()
    for row in payload["violations_2025"]:
        pws_id = str(row.get("pws_id") or "")
        violation_id = str(row.get("violation_id") or "")
        if not PWS_ID_RE.fullmatch(pws_id):
            raise RuntimeError(f"Invalid violation PWS ID: {pws_id!r}")
        if not violation_id or violation_id in violation_ids:
            raise RuntimeError(f"Missing/duplicate violation ID: {violation_id!r}")
        violation_ids.add(violation_id)
        if int(row.get("calendar_year") or 0) != 2025:
            raise RuntimeError("Violation cache contains a non-2025 record")

    if int(summary.get("pws_contact_page_count") or 0) < 50 or int(summary.get("violation_page_count") or 0) < 50:
        raise RuntimeError("NYSDOH county/page discovery was incomplete")

    if require_production_volume:
        floors = {
            "pws_system_count": 8000,
            "pws_contact_record_count": 8000,
            "certified_operator_count": 1000,
            # Current authoritative NYSDOH LSLI index contains 2,927 systems.
            # Keep a meaningful fail-closed floor while allowing the live source count.
            "lsli_required_system_count": 2500,
            "violation_count_2025": 8000,
        }
        for key, minimum in floors.items():
            value = int(summary.get(key) or 0)
            if value < minimum:
                raise RuntimeError(f"Implausibly small production {key}: {value:,} < {minimum:,}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate TowerSignal NYS public-water-system cache")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--max-age-days", type=int, default=1)
    parser.add_argument("--require-production-volume", action="store_true")
    args = parser.parse_args()
    payload = validate(args.cache, max_age_days=args.max_age_days, require_production_volume=args.require_production_volume)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
