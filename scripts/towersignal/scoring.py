from __future__ import annotations

from typing import Any

from . import PRIORITY_MODEL_VERSION


def priority_score(system: dict[str, Any], signal_state: dict[str, Any]) -> dict[str, Any]:
    components: list[dict[str, Any]] = []

    if signal_state["recent_confirmed_violation"]:
        components.append({"points": 40, "reason": "confirmed recent violation"})
        recent_violation_types = {
            item.lower()
            for signal in signal_state["signals"]
            if signal["type"] == "CONFIRMED_RECENT_VIOLATION"
            for item in signal.get("violation_types", [])
        }
        if any("public health hazard" in item or "critical" in item for item in recent_violation_types):
            components.append({"points": 10, "reason": "recent critical/public-health-hazard violation"})

    days_since = signal_state["days_since_latest_sample"]
    if system.get("latest_sample_date") is None:
        components.append({"points": 18, "reason": "no usable public sample date"})
    elif days_since is not None and any(signal['type'] == 'POTENTIAL_SAMPLING_GAP' for signal in signal_state['signals']):
        if days_since > 60:
            points = 30
        elif days_since > 45:
            points = 25
        else:
            points = 20
        components.append({"points": points, "reason": f"potential sampling gap ({days_since} days since latest public sample)"})

    active_equipment = int(system.get("active_equipment") or 0)
    equipment_points = min(18, max(0, active_equipment - 1) * 6)
    if equipment_points:
        components.append({"points": equipment_points, "reason": f"{active_equipment} active tower units"})

    if any(signal['type'] == 'RECENT_NYC_HEALTH_INSPECTION' for signal in signal_state['signals']):
        components.append({"points": 10, "reason": "recent NYC Health regulatory activity"})

    score = min(100, sum(int(component["points"]) for component in components))
    return {"score": score, "components": components, "priority_model_version": PRIORITY_MODEL_VERSION}
