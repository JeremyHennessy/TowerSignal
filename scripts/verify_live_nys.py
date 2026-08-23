from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.fetch import fetch_where  # noqa: E402
from towersignal.nys_registry import (  # noqa: E402
    NYS_API_ROOT,
    NYS_COOLING_TOWER_DATASET_ID,
    normalize_nys_registry,
)


def deterministic_sample(rows: list[dict], sample_size: int) -> list[dict]:
    if sample_size <= 0 or not rows:
        return []
    if len(rows) <= sample_size:
        return rows
    indexes = sorted({round(index * (len(rows) - 1) / (sample_size - 1)) for index in range(sample_size)}) if sample_size > 1 else [0]
    return [rows[index] for index in indexes]


def verify(payload_path: Path, sample_size: int = 5) -> dict:
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    systems = payload.get("systems") or []
    sampled = deterministic_sample(systems, sample_size)
    equipment_ids = [str(row["source_equipment_id"]) for row in sampled]
    where = "equipment_id in (" + ",".join(f"'{value}'" for value in equipment_ids) + ")"
    live_rows = fetch_where(
        NYS_COOLING_TOWER_DATASET_ID,
        where=where,
        order_by="equipment_id",
        api_root=NYS_API_ROOT,
    )
    normalized_live, _ = normalize_nys_registry(live_rows)
    live_by_id = {row["source_equipment_id"]: row for row in normalized_live}

    fields = (
        "source_equipment_id",
        "address",
        "city",
        "zip",
        "source_county",
        "regulation_compliance",
        "ct_status",
        "latest_sample_date",
        "latest_sample_result",
        "operation_duration",
        "coordinate_status",
        "latitude",
        "longitude",
    )
    verified = []
    for generated in sampled:
        equipment_id = str(generated["source_equipment_id"])
        live = live_by_id.get(equipment_id)
        if live is None:
            raise RuntimeError(f"Live NYS source did not return sampled Equipment_ID {equipment_id}")
        mismatches = {
            field: {"generated": generated.get(field), "live": live.get(field)}
            for field in fields
            if generated.get(field) != live.get(field)
        }
        if mismatches:
            raise RuntimeError(f"NYS live verification mismatch for Equipment_ID {equipment_id}: {mismatches}")
        verified.append(equipment_id)

    result = {"sample_size": len(sampled), "verified_equipment_ids": verified}
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Independently verify generated NYS equipment against the live source")
    parser.add_argument("--payload", type=Path, default=ROOT / "public/data/nys-systems.json")
    parser.add_argument("--sample-size", type=int, default=5)
    args = parser.parse_args()
    verify(args.payload, args.sample_size)


if __name__ == "__main__":
    main()