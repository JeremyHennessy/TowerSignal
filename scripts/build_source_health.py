from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.source_health import health_entry, validate_source_health  # noqa: E402


def load_json(path: Path | None, default: Any) -> Any:
    if path is None or not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def safe_detail_path(base: Path, system_id: str) -> Path:
    safe = "".join(ch for ch in system_id if ch.isalnum() or ch in ("-", "_"))
    return base / "details" / (safe[:2] or "xx").lower() / f"{safe}.json"


def build(output_dir: Path, previous_snapshot_path: Path | None = None) -> list[dict[str, Any]]:
    systems_path = output_dir / "systems.json"
    metadata_path = output_dir / "metadata.json"
    payload = load_json(systems_path, None)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Missing or malformed generated systems payload: {systems_path}")
    metadata = payload.get("metadata") or {}
    summary = payload.get("summary") or {}
    systems = payload.get("systems") or []
    sources = {source.get("dataset_id"): source for source in metadata.get("sources", [])}

    previous = load_json(previous_snapshot_path, {})
    previous_health = {entry.get("source_key"): entry for entry in previous.get("source_health", []) if isinstance(entry, dict)}
    previous_coverage = lambda key: previous_health.get(key, {}).get("coverage_percentage")

    normalized_system_count = int(metadata.get("normalized_system_count") or len(systems))
    inspection_systems = sum(1 for row in systems if int(row.get("inspection_count") or 0) > 0)
    inspection_count = sum(int(row.get("inspection_count") or 0) for row in systems)
    oath_systems = sum(1 for row in systems if int(row.get("oath_case_count") or 0) > 0)
    pluto_systems = sum(1 for row in systems if bool(row.get("pluto_match")))
    hpd_contact_systems = sum(1 for row in systems if int(row.get("hpd_contact_count") or 0) > 0)
    hpd_registration_systems = int(summary.get("systems_with_hpd_registration") or 0)

    reg = sources.get("y4fw-iqfr", {})
    insp = sources.get("f9wb-g8mb", {})
    oath = sources.get("jz4z-kudi", {})
    pluto = next((value for key, value in sources.items() if key not in {"y4fw-iqfr", "f9wb-g8mb", "jz4z-kudi", "tesw-yqqr", "feu5-w2e2"} and "PLUTO" in str(value.get("name", "")).upper()), {})
    hpd_reg = sources.get("tesw-yqqr", {})
    hpd_contacts = sources.get("feu5-w2e2", {})

    entries = [
        health_entry(source_key="registrations", dataset_id=str(reg.get("dataset_id") or "y4fw-iqfr"), name=str(reg.get("name") or "NYC Cooling Tower Registrations"), entity_unit="cooling tower systems", retrieved_record_count=int(reg.get("source_record_count") or 0), requested_entity_count=normalized_system_count, normalized_entity_count=normalized_system_count, matched_entity_count=normalized_system_count, attached_entity_count=normalized_system_count, displayed_entity_count=len(systems), previous_coverage_percentage=previous_coverage("registrations"), coverage_note="Coverage is normalized current systems represented in the generated product."),
        health_entry(source_key="inspections", dataset_id=str(insp.get("dataset_id") or "f9wb-g8mb"), name=str(insp.get("name") or "NYC Cooling Tower System Inspection Results"), entity_unit="current cooling tower systems with published inspection history", retrieved_record_count=int(insp.get("source_record_count") or 0), requested_entity_count=normalized_system_count, normalized_entity_count=inspection_count, matched_entity_count=inspection_systems, attached_entity_count=inspection_systems, displayed_entity_count=inspection_systems, previous_coverage_percentage=previous_coverage("inspections"), coverage_note="Coverage is the share of current systems with at least one exact system_id inspection history; it is not an expected-completeness percentage."),
        health_entry(source_key="oath", dataset_id=str(oath.get("dataset_id") or "jz4z-kudi"), name=str(oath.get("name") or "OATH Hearings Division Case Status"), entity_unit="summons/ticket identifiers", retrieved_record_count=int(oath.get("source_record_count") or 0), requested_entity_count=int(metadata.get("oath_requested_ticket_count") or 0), normalized_entity_count=int(metadata.get("oath_matched_ticket_count") or 0), matched_entity_count=int(metadata.get("oath_matched_ticket_count") or 0), attached_entity_count=oath_systems, displayed_entity_count=oath_systems, previous_coverage_percentage=previous_coverage("oath"), coverage_note="Coverage is exact NYC Health summons_number to OATH ticket_number match coverage."),
        health_entry(source_key="pluto", dataset_id=str(pluto.get("dataset_id") or "PLUTO"), name=str(pluto.get("name") or "NYC DCP PLUTO"), entity_unit="BBLs", retrieved_record_count=int(pluto.get("source_record_count") or 0), requested_entity_count=int(metadata.get("pluto_requested_bbl_count") or 0), normalized_entity_count=int(metadata.get("pluto_matched_bbl_count") or 0), matched_entity_count=int(metadata.get("pluto_matched_bbl_count") or 0), attached_entity_count=pluto_systems, displayed_entity_count=pluto_systems, previous_coverage_percentage=previous_coverage("pluto"), coverage_note="Coverage is exact BBL match coverage; one BBL can attach to more than one cooling-tower system."),
        health_entry(source_key="hpd_registrations", dataset_id=str(hpd_reg.get("dataset_id") or "tesw-yqqr"), name=str(hpd_reg.get("name") or "NYC HPD Multiple Dwelling Registrations"), entity_unit="BBLs", retrieved_record_count=int(hpd_reg.get("source_record_count") or 0), requested_entity_count=int(metadata.get("hpd_requested_bbl_count") or 0), normalized_entity_count=int(metadata.get("hpd_matched_registration_bbl_count") or 0), matched_entity_count=int(metadata.get("hpd_matched_registration_bbl_count") or 0), attached_entity_count=hpd_registration_systems, displayed_entity_count=hpd_registration_systems, previous_coverage_percentage=previous_coverage("hpd_registrations"), coverage_note="Coverage is exact BBL registration match coverage. HPD registration applies only to qualifying properties, so low absolute coverage is not itself a failure."),
        health_entry(source_key="hpd_contacts", dataset_id=str(hpd_contacts.get("dataset_id") or "feu5-w2e2"), name=str(hpd_contacts.get("name") or "NYC HPD Registration Contacts"), entity_unit="matched HPD registration BBLs", retrieved_record_count=int(hpd_contacts.get("source_record_count") or 0), requested_entity_count=int(metadata.get("hpd_matched_registration_bbl_count") or 0), normalized_entity_count=int(metadata.get("hpd_matched_contact_bbl_count") or 0), matched_entity_count=int(metadata.get("hpd_matched_contact_bbl_count") or 0), attached_entity_count=hpd_contact_systems, displayed_entity_count=hpd_contact_systems, previous_coverage_percentage=previous_coverage("hpd_contacts"), coverage_note="Coverage is the share of exact-matched HPD registration BBLs with public contact rows."),
    ]

    validate_source_health(entries)
    metadata["source_health"] = entries
    payload["metadata"] = metadata
    systems_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (output_dir / "source-health.json").write_text(json.dumps({"generated_at": metadata.get("generated_at"), "sources": entries}, indent=2), encoding="utf-8")

    for row in systems:
        detail_path = safe_detail_path(output_dir, row["system_id"])
        detail = load_json(detail_path, None)
        if not isinstance(detail, dict):
            raise RuntimeError(f"Missing generated detail payload for source-health attachment verification: {row['system_id']}")
        detail_metadata = detail.get("metadata") or {}
        detail_metadata["source_health"] = entries
        detail["metadata"] = detail_metadata
        detail_path.write_text(json.dumps(detail, separators=(",", ":")), encoding="utf-8")

    print(json.dumps({entry["source_key"]: {"status": entry["status"], "coverage_percentage": entry["coverage_percentage"], "attached": entry["attached_entity_count"], "displayed": entry["displayed_entity_count"]} for entry in entries}, indent=2))
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and validate TowerSignal source-health coverage")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data")
    parser.add_argument("--previous-snapshot", type=Path)
    args = parser.parse_args()
    build(args.output, args.previous_snapshot)


if __name__ == "__main__":
    main()
