from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from toronto_final_identity_cleanup import iter_records
from toronto_market_common import clean_text, read_json

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data/toronto/market/current"
WAREHOUSE = ROOT / "data/toronto/warehouse/current"

SOURCES = {
    "toronto_aic_applications": MARKET / "open_licensed/toronto_aic_applications.json",
    "development_pipeline": WAREHOUSE / "open_licensed/development_pipeline.json",
    "affordable_housing_pipeline": WAREHOUSE / "open_licensed/affordable_housing_pipeline.json",
    "capital_project_pipeline": WAREHOUSE / "open_licensed/capital_project_pipeline.json",
    "tobids_awarded_contracts": WAREHOUSE / "open_licensed/tobids_awarded_contracts.json",
    "ontario_environmental_compliance_reports": WAREHOUSE / "open_licensed/ontario_environmental_compliance_reports.json",
    "ontario_bps_energy_2024": WAREHOUSE / "open_licensed/ontario_bps_energy_2024.json",
    "business_licence_matches": WAREHOUSE / "business_licence_matches.json",
}

ROLE_TOKENS = (
    "OWNER", "APPLICANT", "ARCHITECT", "ENGINEER", "CONSULTANT", "CONTRACTOR",
    "MANAGER", "MANAGEMENT", "SUPPLIER", "ORGANIZATION", "OPERATOR", "CLIENT",
)


def is_role_like_field(field: str) -> bool:
    normalized = " ".join(str(field or "").upper().replace("_", " ").split())
    return any(token in normalized for token in ROLE_TOKENS)


def rows_for(source: str, path: Path) -> list[dict[str, Any]]:
    payload = read_json(path) or {}
    rows = [row for row in iter_records(payload) if isinstance(row, dict)]
    if source == "business_licence_matches":
        return [row.get("source_row") if isinstance(row.get("source_row"), dict) else row for row in rows]
    return rows


def summarize_source(source: str, path: Path) -> dict[str, Any]:
    rows = rows_for(source, path)
    field_counts: Counter[str] = Counter()
    samples: dict[str, list[str]] = defaultdict(list)
    unique_values: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        for field, value in row.items():
            if not is_role_like_field(str(field)):
                continue
            text = clean_text(value)
            if not text or text.upper() in {"N/A", "NA", "NONE", "UNKNOWN", "NOT AVAILABLE"}:
                continue
            name = str(field)
            field_counts[name] += 1
            unique_values[name].add(text)
            if len(samples[name]) < 8 and text not in samples[name]:
                samples[name].append(text)
    return {
        "path": str(path.relative_to(ROOT)),
        "rows": len(rows),
        "role_like_fields": [
            {
                "field": field,
                "nonempty_rows": field_counts[field],
                "unique_values": len(unique_values[field]),
                "samples": samples[field],
            }
            for field in sorted(field_counts)
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only inventory of explicit role-like fields in persisted Toronto sources")
    parser.add_argument("--output", type=Path, default=Path("toronto-role-field-diagnostic.json"))
    args = parser.parse_args()
    sources = {source: summarize_source(source, path) for source, path in SOURCES.items()}
    report = {
        "schema_version": "toronto-role-field-diagnostic-1.0",
        "status": "PASSED_DIAGNOSTIC",
        "scope": "Read-only persisted-source schema inventory. No organization role is inferred from descriptions or keywords.",
        "role_tokens": list(ROLE_TOKENS),
        "sources": sources,
    }
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "sources": {
            source: {
                "rows": info["rows"],
                "fields": [(field["field"], field["nonempty_rows"], field["unique_values"]) for field in info["role_like_fields"]],
            }
            for source, info in sources.items()
        },
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
