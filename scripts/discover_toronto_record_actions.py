from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from toronto_app_sources import load_source_rows

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "data/toronto/market/current"
REPORT = MARKET / "record_action_discovery.json"

IDENTIFIER_HINTS = (
    "id", "rsn", "licence", "license", "application", "reference", "folder", "notice",
    "document", "project", "case", "facility", "request", "status", "address", "url",
)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected object: {path}")
    return value


def compact(row: dict[str, Any]) -> dict[str, Any]:
    selected: dict[str, Any] = {}
    for key, value in row.items():
        name = str(key)
        lowered = name.lower()
        if any(hint in lowered for hint in IDENTIFIER_HINTS):
            selected[name] = value
    return selected


def main() -> None:
    links = [x for x in (load(MARKET / "property_source_links.json").get("links") or []) if isinstance(x, dict)]
    rows = load_source_rows(ROOT, load)
    first_link: dict[str, dict[str, Any]] = {}
    for link in links:
        first_link.setdefault(str(link.get("source_key") or ""), link)
    report: dict[str, Any] = {"sources": {}}
    for source, source_rows in sorted(rows.items()):
        representative = source_rows[0] if source_rows else {}
        link = first_link.get(source) or {}
        idx = link.get("source_row_index")
        if isinstance(idx, int) and 0 <= idx < len(source_rows):
            representative = source_rows[idx]
        report["sources"][source] = {
            "row_count_loaded": len(source_rows),
            "representative_link": link,
            "representative_identifier_fields": compact(representative),
            "all_fields": sorted(str(key) for key in representative),
        }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    for source, info in report["sources"].items():
        print(f"=== {source} ===")
        print("LINK=" + json.dumps(info["representative_link"], sort_keys=True, default=str))
        print("IDENTIFIERS=" + json.dumps(info["representative_identifier_fields"], sort_keys=True, default=str))
        print("FIELDS=" + json.dumps(info["all_fields"]))


if __name__ == "__main__":
    main()
