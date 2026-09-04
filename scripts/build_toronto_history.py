from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "toronto-history-1.0"
PERMIT_SOURCES = {
    "toronto_building_permits_active_targeted",
    "toronto_building_permits_cleared_targeted_since_2017",
}


def clean(value: Any) -> str:
    return str(value or "").strip()


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def link_key(link: dict[str, Any]) -> tuple[str, str]:
    return clean(link.get("source_key")), clean(link.get("source_record_id"))


def relationship_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        clean(item.get("relationship")),
        " ".join(clean(item.get("organization")).upper().split()),
        clean(item.get("source_key")),
    )


def source_event_type(source_key: str, removed: bool = False) -> str:
    suffix = "REMOVED" if removed else "ADDED"
    if source_key in PERMIT_SOURCES:
        return f"PERMIT_RECORD_{suffix}"
    if source_key == "tdsb_facility_condition_renewal":
        return f"TDSB_RENEWAL_RECORD_{suffix}"
    if source_key.startswith("tobids_"):
        return f"PROCUREMENT_RECORD_{suffix}"
    if source_key == "toronto_aic_applications":
        return f"AIC_APPLICATION_{suffix}"
    if source_key in {"chemtrac_history", "chemtrac_2024"}:
        return f"CHEMTRAC_RECORD_{suffix}"
    return f"SOURCE_RECORD_{suffix}"


def event(
    *,
    event_type: str,
    property: dict[str, Any],
    detected_at: str,
    source_key: str | None,
    evidence_basis: str,
    previous_value: Any,
    new_value: Any,
    source_record_id: str | None = None,
    source_observation_date: str | None = None,
    record_title: str | None = None,
    record_status: str | None = None,
) -> dict[str, Any]:
    identity = {
        "event_type": event_type,
        "property_id": property.get("property_id"),
        "source_key": source_key,
        "source_record_id": source_record_id,
        "previous_value": previous_value,
        "new_value": new_value,
    }
    event_id = "toronto-event:" + hashlib.sha1(canonical(identity).encode("utf-8")).hexdigest()[:20]
    return {
        "event_id": event_id,
        "event_type": event_type,
        "property_id": property.get("property_id"),
        "address_point_id": property.get("address_point_id"),
        "address": property.get("display_address"),
        "detected_at": detected_at,
        "source_observation_date": source_observation_date,
        "source_key": source_key,
        "source_record_id": source_record_id,
        "record_title": record_title,
        "record_status": record_status,
        "evidence_basis": evidence_basis,
        "previous_value": previous_value,
        "new_value": new_value,
        "tower_evidence_status": property.get("tower_evidence_status"),
    }


def source_link_summary(link: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_key": link.get("source_key"),
        "source_record_id": link.get("source_record_id"),
        "record_title": link.get("record_title"),
        "record_status": link.get("record_status"),
        "record_date": link.get("record_date"),
    }


def relationship_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "relationship": item.get("relationship"),
        "organization": item.get("organization"),
        "source_key": item.get("source_key"),
    }


def detect_property_changes(previous: dict[str, Any], current: dict[str, Any], detected_at: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    if clean(previous.get("display_address")) != clean(current.get("display_address")):
        events.append(event(
            event_type="PROPERTY_ADDRESS_CHANGED",
            property=current,
            detected_at=detected_at,
            source_key="toronto_address_points",
            evidence_basis="PROPERTY_ID_EXACT_CURRENT_ADDRESS_POINT",
            previous_value=previous.get("display_address"),
            new_value=current.get("display_address"),
        ))

    if clean(previous.get("tower_evidence_status")) != clean(current.get("tower_evidence_status")):
        events.append(event(
            event_type="TOWER_EVIDENCE_CHANGED",
            property=current,
            detected_at=detected_at,
            source_key=None,
            evidence_basis="PROPERTY_ID_EXACT_TOWERSIGNAL_EVIDENCE_CONTRACT",
            previous_value=previous.get("tower_evidence_status"),
            new_value=current.get("tower_evidence_status"),
        ))

    previous_links = {link_key(item): item for item in previous.get("source_links") or [] if isinstance(item, dict) and all(link_key(item))}
    current_links = {link_key(item): item for item in current.get("source_links") or [] if isinstance(item, dict) and all(link_key(item))}
    for key in sorted(current_links.keys() - previous_links.keys()):
        source_key, source_record_id = key
        link = current_links[key]
        events.append(event(
            event_type=source_event_type(source_key),
            property=current,
            detected_at=detected_at,
            source_key=source_key,
            source_record_id=source_record_id,
            source_observation_date=clean(link.get("record_date")) or None,
            record_title=clean(link.get("record_title")) or None,
            record_status=clean(link.get("record_status")) or None,
            evidence_basis="PROPERTY_ID_EXACT_AND_STABLE_SOURCE_RECORD_ID",
            previous_value=None,
            new_value=source_link_summary(link),
        ))
    for key in sorted(previous_links.keys() - current_links.keys()):
        source_key, source_record_id = key
        link = previous_links[key]
        events.append(event(
            event_type=source_event_type(source_key, removed=True),
            property=current,
            detected_at=detected_at,
            source_key=source_key,
            source_record_id=source_record_id,
            source_observation_date=clean(link.get("record_date")) or None,
            record_title=clean(link.get("record_title")) or None,
            record_status=clean(link.get("record_status")) or None,
            evidence_basis="PROPERTY_ID_EXACT_AND_STABLE_SOURCE_RECORD_ID",
            previous_value=source_link_summary(link),
            new_value=None,
        ))

    previous_relationships = {relationship_key(item): item for item in previous.get("relationships") or [] if isinstance(item, dict) and all(relationship_key(item))}
    current_relationships = {relationship_key(item): item for item in current.get("relationships") or [] if isinstance(item, dict) and all(relationship_key(item))}
    for key in sorted(current_relationships.keys() - previous_relationships.keys()):
        rel = current_relationships[key]
        events.append(event(
            event_type="RELATIONSHIP_ADDED",
            property=current,
            detected_at=detected_at,
            source_key=clean(rel.get("source_key")) or None,
            evidence_basis="PROPERTY_ID_EXACT_AND_SOURCE_ROLE_PRESERVED",
            previous_value=None,
            new_value=relationship_summary(rel),
        ))
    for key in sorted(previous_relationships.keys() - current_relationships.keys()):
        rel = previous_relationships[key]
        events.append(event(
            event_type="RELATIONSHIP_REMOVED",
            property=current,
            detected_at=detected_at,
            source_key=clean(rel.get("source_key")) or None,
            evidence_basis="PROPERTY_ID_EXACT_AND_SOURCE_ROLE_PRESERVED",
            previous_value=relationship_summary(rel),
            new_value=None,
        ))

    return events


def build_changes(previous_payload: dict[str, Any], current_payload: dict[str, Any], detected_at: str, previous_sha: str, current_sha: str) -> dict[str, Any]:
    previous_properties = {item["property_id"]: item for item in previous_payload.get("properties") or [] if isinstance(item, dict) and item.get("property_id")}
    current_properties = {item["property_id"]: item for item in current_payload.get("properties") or [] if isinstance(item, dict) and item.get("property_id")}
    events: list[dict[str, Any]] = []

    for property_id in sorted(current_properties.keys() - previous_properties.keys()):
        current = current_properties[property_id]
        events.append(event(
            event_type="PROPERTY_FIRST_SEEN",
            property=current,
            detected_at=detected_at,
            source_key="toronto_address_points",
            evidence_basis="CURRENT_CANONICAL_ADDRESS_POINT_PROPERTY_NOT_PRESENT_IN_PREVIOUS_VERIFIED_RELEASE",
            previous_value=None,
            new_value={"present_in_release": True},
        ))
    for property_id in sorted(previous_properties.keys() - current_properties.keys()):
        previous = previous_properties[property_id]
        events.append(event(
            event_type="PROPERTY_NO_LONGER_PRESENT",
            property=previous,
            detected_at=detected_at,
            source_key="toronto_address_points",
            evidence_basis="PREVIOUS_CANONICAL_PROPERTY_NOT_PRESENT_IN_CURRENT_VERIFIED_RELEASE",
            previous_value={"present_in_release": True},
            new_value={"present_in_release": False},
        ))
    for property_id in sorted(current_properties.keys() & previous_properties.keys()):
        events.extend(detect_property_changes(previous_properties[property_id], current_properties[property_id], detected_at))

    deduped = {item["event_id"]: item for item in events}
    events = list(deduped.values())
    events.sort(key=lambda item: (
        clean(item.get("source_observation_date")) or clean(item.get("detected_at")),
        clean(item.get("address")),
        clean(item.get("event_type")),
        clean(item.get("event_id")),
    ), reverse=True)
    event_type_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    property_ids: set[str] = set()
    for item in events:
        event_type_counts[item["event_type"]] = event_type_counts.get(item["event_type"], 0) + 1
        if item.get("source_key"):
            source_counts[item["source_key"]] = source_counts.get(item["source_key"], 0) + 1
        if item.get("property_id"):
            property_ids.add(item["property_id"])

    return {
        "schema_version": SCHEMA_VERSION,
        "history_started_at": previous_payload.get("generated_at") or previous_payload.get("observed_at") or detected_at,
        "observed_at": detected_at,
        "previous_release_sha": previous_sha,
        "current_release_sha": current_sha,
        "previous_generated_at": previous_payload.get("generated_at"),
        "current_generated_at": current_payload.get("generated_at"),
        "event_count": len(events),
        "properties_with_changes": len(property_ids),
        "event_type_counts": dict(sorted(event_type_counts.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "contract": {
            "identity": "Events compare the same canonical property_id across two verified Toronto release payloads. Source-record changes additionally require stable source_key + source_record_id identity.",
            "semantics": "Events report observed dataset/release changes only. They do not infer compliance, equipment condition, ownership, contractor specialty, or procurement intent beyond the source role.",
            "baseline": "The first Toronto Monitor baseline is the last verified deployed Toronto preview source checkpoint before the parity expansion.",
        },
        "events": events,
    }


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Toronto release-to-release change events")
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--detected-at", required=True)
    parser.add_argument("--previous-sha", required=True)
    parser.add_argument("--current-sha", required=True)
    args = parser.parse_args()
    result = build_changes(read_json(args.previous), read_json(args.current), args.detected_at, args.previous_sha, args.current_sha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("event_count", "properties_with_changes", "event_type_counts", "source_counts")}, indent=2))


if __name__ == "__main__":
    main()
