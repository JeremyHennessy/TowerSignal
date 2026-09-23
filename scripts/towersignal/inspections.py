from __future__ import annotations

from collections import defaultdict
from typing import Any

from .normalize import _clean, _int, parse_date

VIOLATION_FIELDS = (
    "violation_code",
    "law_section",
    "violation_text",
    "violation_type",
    "citation_text",
    "summons_number",
)


def _inspection_key(row: dict[str, Any]) -> tuple[str, str, str]:
    system_id = _clean(row.get("system_id")) or ""
    date_value = parse_date(row.get("inspection_date"))
    inspection_date = date_value.isoformat() if date_value else (_clean(row.get("inspection_date")) or "")
    inspection_type = _clean(row.get("inspection_type")) or "UNKNOWN"
    return system_id, inspection_date, inspection_type


def _violation(row: dict[str, Any]) -> dict[str, Any] | None:
    if not any(_clean(row.get(field)) for field in VIOLATION_FIELDS):
        return None
    return {field: _clean(row.get(field)) for field in VIOLATION_FIELDS}


def aggregate_inspections(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    observed_statuses: dict = defaultdict(set)
    observed_equipment: dict = defaultdict(set)
    seen_violations: dict[tuple[str, str, str], set[tuple[Any, ...]]] = defaultdict(set)

    for row in rows:
        system_id = _clean(row.get("system_id"))
        if not system_id:
            continue
        key = _inspection_key(row)
        observed_statuses[key].add(_clean(row.get("status")))
        observed_equipment[key].add(_int(row.get("active_equip"), 0))
        if key not in grouped:
            grouped[key] = {
                "system_id": system_id,
                "inspection_date": key[1] or None,
                "inspection_type": key[2],
                "status": _clean(row.get("status")),
                "active_equipment_at_publication": _int(row.get("active_equip"), 0),
                "violations": [],
            }
        violation = _violation(row)
        if violation is not None:
            identity = tuple(violation.get(field) for field in VIOLATION_FIELDS)
            if identity not in seen_violations[key]:
                grouped[key]["violations"].append(violation)
                seen_violations[key].add(identity)

    by_system: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for key, inspection in grouped.items():
        statuses = sorted(observed_statuses[key], key=lambda v: v or "")
        equipment = sorted(observed_equipment[key])
        inspection["status"] = statuses[0] if len(statuses) == 1 else "SOURCE_CONFLICT"
        inspection["active_equipment_at_publication"] = equipment[0] if len(equipment) == 1 else None
        if len(statuses) > 1 or len(equipment) > 1:
            inspection["source_metadata_conflicts"] = {"statuses": statuses, "active_equipment": equipment}
        inspection["violations"].sort(key=lambda r: tuple(str(r.get(f) or "") for f in VIOLATION_FIELDS))
        inspection["violation_count"] = len(inspection["violations"])
        by_system[inspection["system_id"]].append(inspection)

    for inspections in by_system.values():
        inspections.sort(key=lambda item: (item.get("inspection_date") or "", item.get("inspection_type") or ""), reverse=True)
    return dict(by_system)
