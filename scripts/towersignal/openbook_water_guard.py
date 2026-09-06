from __future__ import annotations

from typing import Any

from towersignal import openbook_water
from towersignal.procurement import normalize_space

_BASE_CLASSIFY = openbook_water.classify_water_contract

PROTECTED_EXPLICIT_MARKERS = (
    "cooling tower",
    "legionella",
    "condenser water",
    "boiler water",
    "water management plan",
    "water management program",
    "ashrae 188",
)


def classify_water_contract(text: str) -> dict[str, Any]:
    source_text = normalize_space(text)
    lowered = source_text.lower()
    negative_matches = [
        term for term in openbook_water.SUPPLEMENTAL_NEGATIVES if term in lowered
    ]
    protected_matches = [
        marker for marker in PROTECTED_EXPLICIT_MARKERS if marker in lowered
    ]
    if negative_matches and not protected_matches:
        return {
            "service_category": "UNRELATED",
            "confidence": "STRONG",
            "matched_terms": negative_matches,
            "reason": (
                "Explicit non-building-water context excluded before generic "
                "water-service classification"
            ),
            "classification_layer": "OPENBOOK_CONTEXT_GUARD",
        }
    return _BASE_CLASSIFY(source_text)
