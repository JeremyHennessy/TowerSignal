from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

RETIRE_PATTERNS = [
    re.compile(r"\breplac(?:e|ement|ing)\b.*\bcooling\s+towers?\b.*\bwith\b.*\bair[ -]?cooled\b", re.I),
    re.compile(r"\bcooling\s+towers?\b.*\breplac(?:e|ement|ing)\b.*\bwith\b.*\bair[ -]?cooled\b", re.I),
    re.compile(r"\bremove|removal|decommission|eliminate\b.*\bcooling\s+towers?\b", re.I),
]
REPLACE_PATTERNS = [
    re.compile(r"\breplacement\b.*\bcooling\s+towers?\b", re.I),
    re.compile(r"\bcooling\s+towers?\b.*\breplacement\b", re.I),
    re.compile(r"\breplace\b.*\bcooling\s+towers?\b", re.I),
    re.compile(r"\bcooling\s+towers?\b.*\breplace\b", re.I),
]
INSTALL_PATTERNS = [
    re.compile(r"\binstallation\b.*\bcooling\s+towers?\b", re.I),
    re.compile(r"\binstall(?:ed|ing)?\b.*\bcooling\s+towers?\b", re.I),
    re.compile(r"\bnew\b.*\bcooling\s+towers?\b", re.I),
    re.compile(r"\baddition\b.*\bcooling\s+towers?\b", re.I),
]
REPAIR_PATTERNS = [
    re.compile(r"\bupgrade|upgrades|refurbish|refurbishment|repair|winterization\b.*\bcooling\s+towers?\b", re.I),
    re.compile(r"\bcooling\s+towers?\b.*\bupgrade|upgrades|refurbish|refurbishment|repair|winterization\b", re.I),
]


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def permit_number(item: dict[str, Any]) -> str | None:
    value = clean((item.get("source_fields") or {}).get("permit_number"))
    return value or None


def description_core(text: str) -> str:
    value = text.split(" | ", 1)[0]
    value = re.sub(r"^Rev\s*\d+\s*", "", value, flags=re.I)
    value = re.sub(r"\s+", " ", value).strip().lower()
    return value


def description_fingerprint(text: str) -> str | None:
    core = description_core(text)
    if not core:
        return None
    return hashlib.sha1(core.encode("utf-8")).hexdigest()[:16]


def lifecycle_for(text: str) -> str:
    core = description_core(text)
    if any(pattern.search(core) for pattern in RETIRE_PATTERNS):
        return "RETIRE_OR_CONVERT_AWAY_FROM_TOWER"
    if any(pattern.search(core) for pattern in REPLACE_PATTERNS):
        return "REPLACE_OR_RENEW_TOWER"
    if any(pattern.search(core) for pattern in INSTALL_PATTERNS):
        return "INSTALL_OR_ADD_TOWER"
    if any(pattern.search(core) for pattern in REPAIR_PATTERNS):
        return "ALTER_REPAIR_OR_UPGRADE_TOWER"
    return "EXPLICIT_TOWER_UNSPECIFIED"


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            serialized = dict(row)
            for key, value in list(serialized.items()):
                if isinstance(value, (list, dict)):
                    serialized[key] = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
            writer.writerow(serialized)


def classify(output_dir: Path) -> dict[str, Any]:
    summary_path = output_dir / "summary.json"
    evidence_path = output_dir / "evidence.json"
    properties_path = output_dir / "properties.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    evidence_payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    properties_payload = json.loads(properties_path.read_text(encoding="utf-8"))
    evidence = evidence_payload.get("evidence") or []
    properties = properties_payload.get("properties") or []

    tower_lifecycle_by_source_record: dict[tuple[str, str], str] = {}
    recent_fingerprints: dict[str, dict[str, Any]] = defaultdict(lambda: {"addresses": set(), "records": []})

    for item in evidence:
        if not str(item.get("source_key") or "").startswith("toronto_building_permits_"):
            continue
        pnum = permit_number(item)
        if pnum:
            item["permit_project_key"] = f"toronto-permit:{pnum}"
        fingerprint = description_fingerprint(clean(item.get("description")))
        item["description_fingerprint"] = fingerprint
        if item.get("equipment_type") == "cooling_tower":
            lifecycle = lifecycle_for(clean(item.get("description")))
            item["tower_lifecycle_event"] = lifecycle
            tower_lifecycle_by_source_record[(str(item.get("source_key")), str(item.get("source_record_id")))] = lifecycle
            if item.get("recent_activity_365d") and fingerprint:
                recent_fingerprints[fingerprint]["addresses"].add(clean(item.get("address")))
                recent_fingerprints[fingerprint]["records"].append(item.get("evidence_id"))

    # Give supporting equipment rows the lifecycle semantics of the same permit record,
    # without changing their evidence confidence or equipment identity.
    for item in evidence:
        key = (str(item.get("source_key")), str(item.get("source_record_id")))
        if key in tower_lifecycle_by_source_record and item.get("equipment_type") != "cooling_tower":
            item["tower_lifecycle_event_context"] = tower_lifecycle_by_source_record[key]

    evidence_by_id = {item["evidence_id"]: item for item in evidence}
    lifecycle_counts: dict[str, int] = defaultdict(int)
    recent_lifecycle_properties: dict[str, set[str]] = defaultdict(set)
    recent_project_keys: set[str] = set()

    for property_item in properties:
        explicit = [
            evidence_by_id[evidence_id]
            for evidence_id in property_item.get("explicit_tower_evidence_ids") or []
            if evidence_id in evidence_by_id
        ]
        events = sorted({item.get("tower_lifecycle_event") for item in explicit if item.get("tower_lifecycle_event")})
        recent_events = sorted(
            {
                item.get("tower_lifecycle_event")
                for item in explicit
                if item.get("tower_lifecycle_event") and item.get("recent_activity_365d")
            }
        )
        project_keys = sorted({item.get("permit_project_key") for item in explicit if item.get("permit_project_key")})
        recent_keys = sorted(
            {
                item.get("permit_project_key")
                for item in explicit
                if item.get("permit_project_key") and item.get("recent_activity_365d")
            }
        )
        property_item["tower_lifecycle_events"] = events
        property_item["recent_tower_lifecycle_events_365d"] = recent_events
        property_item["permit_project_keys"] = project_keys
        property_item["recent_permit_project_keys_365d"] = recent_keys

        for event in events:
            lifecycle_counts[event] += 1
        for event in recent_events:
            recent_lifecycle_properties[event].add(property_item["property_key"])
        recent_project_keys.update(recent_keys)

        if "RETIRE_OR_CONVERT_AWAY_FROM_TOWER" in recent_events:
            property_item["commercial_disposition"] = "VERIFY_RETIREMENT_OR_CONVERSION_NOT_NEW_TOWER_LEAD"
        elif "INSTALL_OR_ADD_TOWER" in recent_events:
            property_item["commercial_disposition"] = "NEW_OR_EXPANDED_TOWER_SIGNAL"
        elif "REPLACE_OR_RENEW_TOWER" in recent_events:
            property_item["commercial_disposition"] = "TOWER_REPLACEMENT_OR_RENEWAL_SIGNAL"
        elif property_item.get("organization") == "Toronto District School Board" and "HIGH" in (
            property_item.get("renewal_priorities") or []
        ):
            property_item["commercial_disposition"] = "OWNER_REPORTED_HIGH_RENEWAL_NEED"
        elif property_item.get("tower_status") == "CONFIRMED":
            property_item["commercial_disposition"] = "CONFIRMED_TOWER_HISTORY_OR_UNDATED_NEED"
        else:
            property_item["commercial_disposition"] = "NO_TOWER_ASSERTION"

    shared_recent_descriptions: list[dict[str, Any]] = []
    for fingerprint, group in sorted(recent_fingerprints.items()):
        addresses = sorted(address for address in group["addresses"] if address)
        if len(addresses) > 1:
            shared_recent_descriptions.append(
                {
                    "description_fingerprint": fingerprint,
                    "addresses": addresses,
                    "evidence_ids": sorted(str(value) for value in group["records"] if value),
                    "interpretation": "Identical recent permit description appears at multiple addresses; do not assume independent commercial opportunities without project-level reconciliation.",
                }
            )

    summary["tower_lifecycle_contract"] = {
        "classification_basis": "Deterministic phrases in explicit public permit descriptions; no model inference.",
        "precedence": [
            "RETIRE_OR_CONVERT_AWAY_FROM_TOWER",
            "REPLACE_OR_RENEW_TOWER",
            "INSTALL_OR_ADD_TOWER",
            "ALTER_REPAIR_OR_UPGRADE_TOWER",
            "EXPLICIT_TOWER_UNSPECIFIED",
        ],
        "current_presence_caveat": "A permit can describe existing, proposed, replaced, or removed equipment. CONFIRMED means explicit documentary tower evidence, not guaranteed current post-project tower presence.",
    }
    counts = summary.setdefault("counts", {})
    counts["confirmed_properties_by_lifecycle_event"] = dict(sorted(lifecycle_counts.items()))
    counts["recent_365d_confirmed_properties_by_lifecycle_event"] = {
        key: len(value) for key, value in sorted(recent_lifecycle_properties.items())
    }
    counts["recent_365d_permit_project_keys"] = len(recent_project_keys)
    counts["shared_recent_description_groups_across_addresses"] = len(shared_recent_descriptions)
    summary["potential_project_aliases"] = shared_recent_descriptions

    evidence_payload["metadata"] = summary
    properties_payload["metadata"] = summary
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    evidence_path.write_text(json.dumps(evidence_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    properties_path.write_text(json.dumps(properties_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    write_csv(
        output_dir / "properties.csv",
        properties,
        [
            "property_key",
            "tower_status",
            "address",
            "property_name",
            "organization",
            "geo_id",
            "equipment_types",
            "commercial_signals",
            "tower_lifecycle_events",
            "recent_tower_lifecycle_events_365d",
            "commercial_disposition",
            "permit_project_keys",
            "recent_permit_project_keys_365d",
            "renewal_priorities",
            "latest_source_event_date",
            "source_active_permit_record",
            "recent_source_active_permit_activity_365d",
            "latest_recent_permit_activity_date",
            "rentsafe",
            "source_keys",
            "evidence_count",
        ],
    )
    write_csv(
        output_dir / "evidence.csv",
        evidence,
        [
            "evidence_id",
            "source_key",
            "source_record_id",
            "source_status",
            "source_url",
            "property_key",
            "geo_id",
            "address",
            "property_name",
            "organization",
            "equipment_type",
            "evidence_confidence",
            "signal_type",
            "tower_lifecycle_event",
            "tower_lifecycle_event_context",
            "permit_project_key",
            "description_fingerprint",
            "event_date",
            "event_age_days",
            "recent_activity_365d",
            "priority",
            "description",
        ],
    )
    print(json.dumps(counts["recent_365d_confirmed_properties_by_lifecycle_event"], indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify Toronto POC cooling-tower lifecycle events")
    parser.add_argument("--output", type=Path, default=ROOT / "data/toronto/poc/current")
    args = parser.parse_args()
    classify(args.output)


if __name__ == "__main__":
    main()
