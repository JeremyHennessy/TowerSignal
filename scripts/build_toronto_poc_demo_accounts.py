from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def evidence_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": item.get("evidence_id"),
        "source_key": item.get("source_key"),
        "source_record_id": item.get("source_record_id"),
        "source_url": item.get("source_url"),
        "equipment_type": item.get("equipment_type"),
        "evidence_confidence": item.get("evidence_confidence"),
        "signal_type": item.get("signal_type"),
        "event_date": item.get("event_date"),
        "priority": item.get("priority"),
        "description": item.get("description"),
    }


def account_record(
    property_item: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    explicit_ids = list(property_item.get("explicit_tower_evidence_ids") or [])
    supporting_ids = list(property_item.get("supporting_evidence_ids") or [])
    return {
        "property_key": property_item.get("property_key"),
        "address": property_item.get("address"),
        "property_name": property_item.get("property_name"),
        "organization": property_item.get("organization"),
        "tower_status": property_item.get("tower_status"),
        "commercial_signals": property_item.get("commercial_signals") or [],
        "renewal_priorities": property_item.get("renewal_priorities") or [],
        "latest_source_event_date": property_item.get("latest_source_event_date"),
        "recent_source_active_permit_activity_365d": bool(
            property_item.get("recent_source_active_permit_activity_365d")
        ),
        "latest_recent_permit_activity_date": property_item.get("latest_recent_permit_activity_date"),
        "rentsafe": property_item.get("rentsafe"),
        "explicit_tower_evidence": [
            evidence_summary(evidence_by_id[evidence_id])
            for evidence_id in explicit_ids
            if evidence_id in evidence_by_id
        ],
        "supporting_evidence": [
            evidence_summary(evidence_by_id[evidence_id])
            for evidence_id in supporting_ids
            if evidence_id in evidence_by_id
        ],
    }


def write_flat_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "segment",
        "property_key",
        "address",
        "property_name",
        "organization",
        "tower_status",
        "latest_source_event_date",
        "latest_recent_permit_activity_date",
        "renewal_priorities",
        "property_management_company",
        "property_type",
        "confirmed_storeys",
        "confirmed_units",
        "year_built",
        "air_conditioning_type",
        "explicit_tower_evidence_descriptions",
        "explicit_tower_source_urls",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            rentsafe = row.get("rentsafe") or {}
            writer.writerow(
                {
                    "segment": row.get("segment"),
                    "property_key": row.get("property_key"),
                    "address": row.get("address"),
                    "property_name": row.get("property_name"),
                    "organization": row.get("organization"),
                    "tower_status": row.get("tower_status"),
                    "latest_source_event_date": row.get("latest_source_event_date"),
                    "latest_recent_permit_activity_date": row.get("latest_recent_permit_activity_date"),
                    "renewal_priorities": " | ".join(row.get("renewal_priorities") or []),
                    "property_management_company": rentsafe.get("property_management_company"),
                    "property_type": rentsafe.get("property_type"),
                    "confirmed_storeys": rentsafe.get("confirmed_storeys"),
                    "confirmed_units": rentsafe.get("confirmed_units"),
                    "year_built": rentsafe.get("year_built"),
                    "air_conditioning_type": rentsafe.get("air_conditioning_type"),
                    "explicit_tower_evidence_descriptions": " || ".join(
                        str(item.get("description") or "") for item in row.get("explicit_tower_evidence") or []
                    ),
                    "explicit_tower_source_urls": " || ".join(
                        str(item.get("source_url") or "") for item in row.get("explicit_tower_evidence") or []
                    ),
                }
            )


def build(output_dir: Path) -> dict[str, Any]:
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    properties_payload = json.loads((output_dir / "properties.json").read_text(encoding="utf-8"))
    evidence_payload = json.loads((output_dir / "evidence.json").read_text(encoding="utf-8"))
    properties = properties_payload.get("properties") or []
    evidence = evidence_payload.get("evidence") or []
    evidence_by_id = {item["evidence_id"]: item for item in evidence}

    confirmed = [item for item in properties if item.get("tower_status") == "CONFIRMED"]
    recent_permit = [
        item for item in confirmed if item.get("recent_source_active_permit_activity_365d")
    ]
    recent_permit.sort(
        key=lambda item: str(item.get("latest_recent_permit_activity_date") or ""), reverse=True
    )

    rentsafe_accounts = [item for item in confirmed if item.get("rentsafe")]
    rentsafe_accounts.sort(
        key=lambda item: (
            0 if item.get("recent_source_active_permit_activity_365d") else 1,
            -(int((item.get("rentsafe") or {}).get("confirmed_units") or 0)),
            str(item.get("address") or ""),
        )
    )

    tdsb_high = [
        item
        for item in confirmed
        if item.get("organization") == "Toronto District School Board"
        and "HIGH" in (item.get("renewal_priorities") or [])
    ]
    tdsb_high.sort(key=lambda item: str(item.get("property_name") or item.get("address") or ""))

    def tagged(items: list[dict[str, Any]], segment: str) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for item in items:
            account = account_record(item, evidence_by_id)
            if not account["explicit_tower_evidence"]:
                raise RuntimeError(f"Demo account lacks explicit tower evidence: {item.get('property_key')}")
            account["segment"] = segment
            output.append(account)
        return output

    recent_records = tagged(recent_permit, "RECENT_CONFIRMED_TOWER_PERMIT_ACTIVITY")
    rentsafe_records = tagged(rentsafe_accounts, "CONFIRMED_TOWER_WITH_RENTSAFE_ACCOUNT_CONTEXT")
    tdsb_records = tagged(tdsb_high, "TDSB_HIGH_RENEWAL_CONFIRMED_TOWER")

    payload = {
        "metadata": {
            "generated_at": summary.get("generated_at"),
            "jurisdiction": "TORONTO_ON",
            "status": "EXPERIMENTAL_POC",
            "ranking_contract": "No Toronto priority score is applied. Segments are deterministic evidence filters only.",
            "counts": {
                "recent_confirmed_tower_permit_activity": len(recent_records),
                "confirmed_tower_with_rentsafe_account_context": len(rentsafe_records),
                "tdsb_high_renewal_confirmed_tower": len(tdsb_records),
            },
        },
        "recent_confirmed_tower_permit_activity": recent_records,
        "confirmed_tower_with_rentsafe_account_context": rentsafe_records,
        "tdsb_high_renewal_confirmed_tower": tdsb_records,
    }
    (output_dir / "demo_accounts.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    flat_rows = recent_records + rentsafe_records + tdsb_records
    write_flat_csv(output_dir / "demo_accounts.csv", flat_rows)
    print(json.dumps(payload["metadata"]["counts"], indent=2))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Assemble evidence-backed Toronto POC demo accounts")
    parser.add_argument("--output", type=Path, default=ROOT / "data/toronto/poc/current")
    args = parser.parse_args()
    build(args.output)


if __name__ == "__main__":
    main()
