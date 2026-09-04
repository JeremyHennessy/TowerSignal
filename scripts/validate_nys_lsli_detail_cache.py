from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

PWS_RE = re.compile(r"^NY\d{7}$")
EXPECTED_METHODS = {
    "Historical Records",
    "Field Inspection",
    "Customer Identification with Photo or other Verification",
    "Excavation",
    "Sequential Sampling",
    "Statistical Analysis/Predictive Model",
}


def validate(path: Path, *, max_age_days: int, require_production_volume: bool) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0" or payload.get("domain") != "NYS_LEAD_SERVICE_LINE_INVENTORY_DETAILS":
        raise RuntimeError("Unexpected LSLI detail cache schema/domain")
    generated = datetime.fromisoformat(str(payload.get("generated_at") or "").replace("Z", "+00:00"))
    age_days = (datetime.now(timezone.utc) - generated).total_seconds() / 86400
    if age_days < -0.05 or age_days > max_age_days:
        raise RuntimeError(f"LSLI detail cache age is {age_days:.2f} days")

    source = payload.get("source")
    summary = payload.get("summary")
    details = payload.get("details")
    if not isinstance(source, dict) or not isinstance(summary, dict) or not isinstance(details, list):
        raise RuntimeError("LSLI detail cache missing source/summary/details")
    index_count = int(source.get("index_record_count") or 0)
    detail_count = int(source.get("detail_record_count") or 0)
    if source.get("retrieval_complete") is not True or index_count != detail_count or detail_count != len(details):
        raise RuntimeError("LSLI detail retrieval is incomplete")
    if int(summary.get("detail_count") or -1) != len(details):
        raise RuntimeError("LSLI detail summary count mismatch")

    pws_ids: set[str] = set()
    total_service_lines = 0
    with_contact = 0
    for row in details:
        pws_id = str(row.get("pws_id") or "")
        if not PWS_RE.fullmatch(pws_id) or pws_id in pws_ids:
            raise RuntimeError(f"Invalid/duplicate LSLI PWS ID: {pws_id!r}")
        pws_ids.add(pws_id)
        if not str(row.get("source_url") or "").endswith(f"/{pws_id}.htm"):
            raise RuntimeError(f"LSLI detail URL mismatch: {pws_id}")
        source_hash = str(row.get("source_sha256") or "")
        if len(source_hash) != 64:
            raise RuntimeError(f"LSLI detail source hash missing: {pws_id}")

        inventory = row.get("inventory")
        if not isinstance(inventory, dict):
            raise RuntimeError(f"LSLI inventory missing: {pws_id}")
        values = {
            key: int(inventory[key])
            for key in (
                "total_service_lines",
                "identified_service_lines",
                "lead_service_lines",
                "gslrr_service_lines",
                "non_lead_service_lines",
                "unknown_service_lines",
            )
        }
        if any(value < 0 for value in values.values()):
            raise RuntimeError(f"Negative LSLI inventory count: {pws_id}")
        if values["identified_service_lines"] != (
            values["lead_service_lines"]
            + values["gslrr_service_lines"]
            + values["non_lead_service_lines"]
        ):
            raise RuntimeError(f"LSLI identified-line reconciliation failed: {pws_id}")
        if values["total_service_lines"] != values["identified_service_lines"] + values["unknown_service_lines"]:
            raise RuntimeError(f"LSLI total-line reconciliation failed: {pws_id}")
        total_service_lines += values["total_service_lines"]

        contact = row.get("owner_or_operator_form_contact")
        if not isinstance(contact, dict):
            raise RuntimeError(f"LSLI contact object missing: {pws_id}")
        if contact.get("name"):
            with_contact += 1
            if contact.get("relationship_role") != "OWNER_OR_LICENSED_OPERATOR_OF_RECORD_FORM_CONTACT":
                raise RuntimeError(f"LSLI form contact role misrepresented: {pws_id}")

        methods = row.get("identification_methods")
        if not isinstance(methods, list):
            raise RuntimeError(f"LSLI methods missing: {pws_id}")
        names = {str(item.get("method") or "") for item in methods if isinstance(item, dict)}
        if not EXPECTED_METHODS.issubset(names):
            raise RuntimeError(f"LSLI methods incomplete: {pws_id}")

    if int(summary.get("details_with_form_contact") or 0) != with_contact:
        raise RuntimeError("LSLI contact summary mismatch")
    if int(summary.get("source_reported_total_service_lines_sum") or -1) != total_service_lines:
        raise RuntimeError("LSLI service-line total summary mismatch")

    if require_production_volume:
        if index_count < 2500:
            raise RuntimeError(f"Implausibly small LSLI detail universe: {index_count:,}")
        if with_contact < 1500:
            raise RuntimeError(f"Implausibly few LSLI form contacts: {with_contact:,}")
        if total_service_lines < 1_000_000:
            raise RuntimeError(f"Implausibly small source-reported service-line total: {total_service_lines:,}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate complete NYSDOH LSLI detail cache")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--max-age-days", type=int, default=1)
    parser.add_argument("--require-production-volume", action="store_true")
    args = parser.parse_args()
    payload = validate(args.cache, max_age_days=args.max_age_days, require_production_volume=args.require_production_volume)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
