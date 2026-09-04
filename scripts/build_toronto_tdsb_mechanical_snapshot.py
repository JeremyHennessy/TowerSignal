from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from toronto_final_identity_cleanup import address_point_root, canonical_address, load_address_points
from toronto_market_common import clean_text, utc_now, write_json

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data/toronto/warehouse/current/open_licensed/tdsb_facility_condition_renewal.json"
SOURCE_KEY = "tdsb_facility_condition_renewal"
STRICT_TDSB_BASELINE_SHA = "101c6808b22bb5ce69a16697f97df95424ad0e2c"
EXPECTED_SCHOOLS = 352
EXPECTED_SOURCE_ROWS = 826
EXPECTED_RESOLVED_SCHOOLS = 334
EXPECTED_RESOLVED_ROWS = 782
EXPECTED_RESOLVED_ROOTS = 330
EXPECTED_AMBIGUOUS_SCHOOLS = 4
EXPECTED_UNRESOLVED_SCHOOLS = 14
EXPECTED_EXPLICIT_TOWER_SCHOOLS = 13


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return value


def stable_row_key(school_id: str, renewal_text: str) -> str:
    digest = hashlib.sha256(renewal_text.strip().encode("utf-8")).hexdigest()[:20]
    return f"school:{school_id}:sha256:{digest}"


def flattened_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group, resolution in (
        (snapshot.get("resolved") or [], "EXACT_LITERAL_TDSB_CIVIC_ADDRESS_TO_UNIQUE_CURRENT_ROOT"),
        (snapshot.get("ambiguous") or [], "AMBIGUOUS_CURRENT_ROOTS_NOT_FORCED"),
        (snapshot.get("unresolved") or [], "NO_EXACT_CURRENT_ADDRESS_POINT_ROOT"),
    ):
        for school in group:
            if not isinstance(school, dict):
                continue
            school_id = clean_text(school.get("school_id"))
            school_name = clean_text(school.get("school_name"))
            published_address = clean_text(school.get("published_address"))
            if not school_id or not school_name or not published_address:
                raise RuntimeError(f"TDSB school identity is incomplete: {school!r}")
            for renewal in school.get("rows") or []:
                if not isinstance(renewal, dict):
                    continue
                renewal_text = clean_text(renewal.get("text"))
                if not renewal_text or "renewal" not in renewal_text.lower():
                    raise RuntimeError(f"TDSB source row is not an actual renewal row: {school_id}: {renewal_text!r}")
                signals = sorted({clean_text(value) for value in (renewal.get("signals") or []) if clean_text(value)})
                if not signals:
                    raise RuntimeError(f"TDSB renewal row has no retained mechanical signal: {school_id}: {renewal_text!r}")
                row = {
                    "_id": stable_row_key(school_id, renewal_text),
                    "school_id": school_id,
                    "school_name": school_name,
                    "published_address": published_address,
                    "canonical_published_address": canonical_address(published_address),
                    "priority": clean_text(renewal.get("priority")) or None,
                    "signals": signals,
                    "renewal_text": renewal_text,
                    "resolution_status": resolution,
                    "property_id": clean_text(school.get("property_id")) or None,
                    "address_point_id": clean_text(school.get("address_point_id")) or None,
                    "current_address": clean_text(school.get("current_address")) or None,
                    "candidate_root_address_point_ids": [clean_text(value) for value in (school.get("candidate_root_address_point_ids") or []) if clean_text(value)],
                    "school_page_url": f"https://www.tdsb.on.ca/Find-your/Schools/School-FCI/schno/{school_id}",
                }
                rows.append(row)
    rows.sort(key=lambda row: (int(row["school_id"]), row["_id"]))
    identities = [row["_id"] for row in rows]
    if len(identities) != len(set(identities)):
        raise RuntimeError("TDSB flattened source snapshot has duplicate stable row identities")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a persisted TDSB mechanical-renewal source snapshot from the verified strict-SHA diagnostic artifact")
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    snapshot = load(args.artifact)
    if clean_text(snapshot.get("strict_baseline_sha")) != STRICT_TDSB_BASELINE_SHA:
        raise RuntimeError("TDSB artifact baseline SHA does not match the verified strict permit checkpoint")
    if int(snapshot.get("renewal_schools") or 0) != EXPECTED_SCHOOLS:
        raise RuntimeError("TDSB artifact renewal-school count drift")
    if int(snapshot.get("resolved_schools") or 0) != EXPECTED_RESOLVED_SCHOOLS:
        raise RuntimeError("TDSB artifact resolved-school count drift")
    if len(snapshot.get("ambiguous") or []) != EXPECTED_AMBIGUOUS_SCHOOLS:
        raise RuntimeError("TDSB artifact ambiguous-school count drift")
    if len(snapshot.get("unresolved") or []) != EXPECTED_UNRESOLVED_SCHOOLS:
        raise RuntimeError("TDSB artifact unresolved-school count drift")

    rows = flattened_rows(snapshot)
    if len(rows) != EXPECTED_SOURCE_ROWS:
        raise RuntimeError(f"Expected {EXPECTED_SOURCE_ROWS} actual TDSB renewal rows, found {len(rows)}")
    resolved_rows = [row for row in rows if row["resolution_status"] == "EXACT_LITERAL_TDSB_CIVIC_ADDRESS_TO_UNIQUE_CURRENT_ROOT"]
    if len(resolved_rows) != EXPECTED_RESOLVED_ROWS:
        raise RuntimeError(f"Expected {EXPECTED_RESOLVED_ROWS} resolved TDSB renewal rows, found {len(resolved_rows)}")
    resolved_apids = {clean_text(row.get("address_point_id")) for row in resolved_rows if clean_text(row.get("address_point_id"))}
    if len(resolved_apids) != EXPECTED_RESOLVED_ROOTS:
        raise RuntimeError(f"Expected {EXPECTED_RESOLVED_ROOTS} resolved TDSB roots, found {len(resolved_apids)}")
    tower_school_ids = {row["school_id"] for row in resolved_rows if "cooling_tower" in row["signals"]}
    if len(tower_school_ids) != EXPECTED_EXPLICIT_TOWER_SCHOOLS:
        raise RuntimeError(f"Expected {EXPECTED_EXPLICIT_TOWER_SCHOOLS} explicit TDSB cooling-tower schools, found {len(tower_school_ids)}")

    by_id, _, scanned = load_address_points()
    roots: dict[str, dict[str, Any]] = {}
    for apid in sorted(resolved_apids, key=int):
        candidate = by_id.get(apid)
        if not candidate:
            raise RuntimeError(f"Verified TDSB Address Point ID is no longer present: {apid}")
        root = address_point_root(candidate, by_id)
        root_id = clean_text(root.get("address_point_id"))
        if root_id != apid:
            raise RuntimeError(f"Verified TDSB root changed: {apid} -> {root_id}")
        expected_addresses = {clean_text(row.get("current_address")) for row in resolved_rows if clean_text(row.get("address_point_id")) == apid}
        current_address = clean_text(root.get("address"))
        if expected_addresses != {current_address}:
            raise RuntimeError(f"Verified TDSB root address drift for {apid}: artifact={sorted(expected_addresses)!r}, current={current_address!r}")
        if not isinstance(root.get("longitude"), (int, float)) or not isinstance(root.get("latitude"), (int, float)):
            raise RuntimeError(f"Verified TDSB root lacks current City coordinates: {apid}")
        roots[apid] = root

    for row in resolved_rows:
        apid = clean_text(row.get("address_point_id"))
        row["property_id"] = f"toronto-address-point:{apid}"
        row["current_address"] = roots[apid].get("address")
        row["_towersignal_source_address"] = roots[apid].get("address")
    for row in rows:
        if row["resolution_status"] != "EXACT_LITERAL_TDSB_CIVIC_ADDRESS_TO_UNIQUE_CURRENT_ROOT":
            row["property_id"] = None
            row["address_point_id"] = None
            row["current_address"] = None
            row["_towersignal_source_address"] = None

    output = {
        "schema_version": "toronto-tdsb-facility-condition-renewal-1.0",
        "generated_at": utc_now(),
        "source_key": SOURCE_KEY,
        "source_name": "Toronto District School Board facility condition renewal evidence",
        "source_page": "https://www.tdsb.on.ca/Community/Planning/School-Facilities/Facility-Condition-Index",
        "source_artifact_baseline_sha": STRICT_TDSB_BASELINE_SHA,
        "source_contract": "Only actual official TDSB facility-condition rows containing Renewal and a retained mechanical signal are persisted. Literal official school Address fields resolve only by exact civic address to one current City Address Point root. Ambiguous and unmatched schools remain unlinked. Non-cooling-tower rows are supporting renewal intelligence only.",
        "metadata": {
            "school_ids_discovered": int(snapshot.get("school_ids_discovered") or 0),
            "renewal_schools": EXPECTED_SCHOOLS,
            "source_records": EXPECTED_SOURCE_ROWS,
            "resolved_schools": EXPECTED_RESOLVED_SCHOOLS,
            "resolved_records": EXPECTED_RESOLVED_ROWS,
            "resolved_property_roots": EXPECTED_RESOLVED_ROOTS,
            "ambiguous_schools_not_forced": EXPECTED_AMBIGUOUS_SCHOOLS,
            "unresolved_schools_not_forced": EXPECTED_UNRESOLVED_SCHOOLS,
            "unmatched_source_records": EXPECTED_SOURCE_ROWS - EXPECTED_RESOLVED_ROWS,
            "explicit_cooling_tower_schools": EXPECTED_EXPLICIT_TOWER_SCHOOLS,
            "address_point_rows_scanned": scanned,
            "resolution_counts": snapshot.get("resolution_counts") or {},
            "signal_resolved_school_counts": snapshot.get("signal_resolved_school_counts") or {},
        },
        "property_roots": roots,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, output)
    print(json.dumps({"status": "PASSED", "metadata": output["metadata"], "property_roots": len(roots)}, indent=2))


if __name__ == "__main__":
    main()
