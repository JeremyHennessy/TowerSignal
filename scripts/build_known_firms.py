from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.known_firms import build_known_firms, utc_now  # noqa: E402

PROCUREMENT_FILES = (
    "procurement-city-record.json",
    "procurement-checkbook.json",
    "procurement-nys-authorities.json",
    "procurement-openbook-water.json",
    "procurement-nycha-water.json",
)


def load_json(path: Path, *, required: bool = True) -> dict[str, Any] | None:
    if not path.exists():
        if required:
            raise RuntimeError(f"Required known-firms input is missing: {path}")
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Known-firms input must be a JSON object: {path}")
    return payload


def safe_detail_path(base: Path, system_id: str) -> Path:
    safe = "".join(ch for ch in str(system_id) if ch.isalnum() or ch in ("-", "_"))
    return base / "details" / (safe[:2] or "xx").lower() / f"{safe}.json"


def build(output_dir: Path) -> dict[str, Any]:
    systems_payload = load_json(output_dir / "systems.json")
    companies_payload = load_json(output_dir / "companies.json")
    domestic_payload = load_json(output_dir / "domestic-water-market.json")
    assert systems_payload is not None and companies_payload is not None and domestic_payload is not None

    procurement_payloads = [
        payload
        for name in PROCUREMENT_FILES
        if (payload := load_json(output_dir / name, required=False)) is not None
    ]
    if len(procurement_payloads) < 3:
        raise RuntimeError(
            f"Known-firms build requires at least three normalized procurement payloads; found {len(procurement_payloads)}"
        )

    details_by_system: dict[str, dict[str, Any]] = {}
    systems = systems_payload.get("systems") or []
    for row in systems:
        if not isinstance(row, dict) or not row.get("system_id"):
            continue
        system_id = str(row["system_id"])
        detail_path = safe_detail_path(output_dir, system_id)
        detail = load_json(detail_path)
        assert detail is not None
        details_by_system[system_id] = detail
    if len(details_by_system) != len(systems):
        raise RuntimeError(
            f"Known-firms detail coverage mismatch: loaded {len(details_by_system):,}/{len(systems):,} account details"
        )

    generated_at = utc_now()
    payload, details = build_known_firms(
        systems_payload=systems_payload,
        companies_payload=companies_payload,
        domestic_payload=domestic_payload,
        procurement_payloads=procurement_payloads,
        details_by_system=details_by_system,
        generated_at=generated_at,
    )

    detail_root = output_dir / "firm-details"
    if detail_root.exists():
        for old in detail_root.rglob("*.json"):
            old.unlink()
    for firm_id, detail in details.items():
        row = detail.get("firm") or {}
        relative_path = row.get("detail_path")
        if not relative_path:
            raise RuntimeError(f"Known-firm {firm_id} is missing detail_path")
        target = output_dir / str(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(detail, separators=(",", ":")), encoding="utf-8")

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "known-firms.json").write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build normalized TowerSignal known-firm and firm-site intelligence")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data")
    args = parser.parse_args()
    build(args.output)


if __name__ == "__main__":
    main()
