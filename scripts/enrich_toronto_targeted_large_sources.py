from __future__ import annotations

import argparse
import csv
import io
import json
import re
import time
import zipfile
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "TowerSignal-Toronto-Warehouse/0.1 (+https://github.com/JeremyHennessy/TowerSignal)"

STREET_SUFFIXES = {
    "STREET": "ST", "ST": "ST", "AVENUE": "AVE", "AVE": "AVE", "ROAD": "RD", "RD": "RD",
    "BOULEVARD": "BLVD", "BLVD": "BLVD", "DRIVE": "DR", "DR": "DR", "COURT": "CT", "CT": "CT",
    "CRESCENT": "CRES", "CRES": "CRES", "PARKWAY": "PKWY", "PKWY": "PKWY", "TRAIL": "TRL", "TRL": "TRL",
    "PLACE": "PL", "PL": "PL", "TERRACE": "TER", "TER": "TER", "HIGHWAY": "HWY", "HWY": "HWY",
}
DIRECTIONS = {"EAST": "E", "WEST": "W", "NORTH": "N", "SOUTH": "S", "E": "E", "W": "W", "N": "N", "S": "S"}


def request_bytes(url: str, *, timeout: int = 120, retries: int = 4) -> bytes:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
            with urlopen(request, timeout=timeout) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed to retrieve {url}: {last_error}")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def write_json(path: Path, payload: Any, *, pretty: bool = False) -> None:
    path.write_text(
        json.dumps(payload, indent=2 if pretty else None, separators=None if pretty else (",", ":"), ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def canonical_address(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).upper()
    text = re.sub(r"\b[A-Z]\d[A-Z]\s*\d[A-Z]\d\b.*$", "", text)
    text = text.split(",", 1)[0]
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    tokens = [STREET_SUFFIXES.get(token, DIRECTIONS.get(token, token)) for token in text.split()]
    value = " ".join(tokens).strip()
    return value or None


def poc_address_map(poc_dir: Path) -> dict[str, list[dict[str, Any]]]:
    properties = read_json(poc_dir / "properties.json").get("properties") or []
    mapping: dict[str, list[dict[str, Any]]] = {}
    for item in properties:
        if not isinstance(item, dict):
            continue
        address = canonical_address(item.get("address"))
        if address:
            mapping.setdefault(address, []).append(item)
    return mapping


def candidate_address_fields(fieldnames: Iterable[str], *, allow_location: bool = False) -> list[str]:
    fields = []
    for field in fieldnames:
        normalized = re.sub(r"[^a-z0-9]", "", str(field).lower())
        if "address" in normalized and "email" not in normalized:
            fields.append(field)
        elif allow_location and any(term in normalized for term in ("location", "intersection")):
            fields.append(field)
    return fields


def exact_row_address_matches(row: dict[str, Any], fields: list[str], known: set[str]) -> set[str]:
    matches: set[str] = set()
    for field in fields:
        value = canonical_address(row.get(field))
        if value and value in known:
            matches.add(value)
    return matches


def metadata_resource(metadata: dict[str, Any], preferred_name: str, preferred_format: str) -> dict[str, Any]:
    resources = [item for item in (metadata.get("resources") or []) if isinstance(item, dict)]
    exact = [item for item in resources if str(item.get("name") or "").strip().lower() == preferred_name.lower()]
    if exact:
        return exact[0]
    same_format = [item for item in resources if str(item.get("format") or "").upper() == preferred_format.upper()]
    if same_format:
        same_format.sort(key=lambda item: str(item.get("last_modified") or ""), reverse=True)
        return same_format[0]
    raise RuntimeError(f"Could not find resource {preferred_name!r} / format {preferred_format!r}")


def parse_csv_bytes(data: bytes) -> tuple[list[str], Iterable[dict[str, str]]]:
    text = io.StringIO(data.decode("utf-8-sig", errors="replace"))
    reader = csv.DictReader(text)
    return list(reader.fieldnames or []), reader


def pull_business_matches(poc: dict[str, list[dict[str, Any]]], warehouse_dir: Path) -> dict[str, Any]:
    metadata = read_json(warehouse_dir / "open_licensed" / "mls_business_licences_permits_metadata.json")
    resource = metadata_resource(metadata, "Business licences data.csv", "CSV")
    data = request_bytes(str(resource["url"]))
    fields, reader = parse_csv_bytes(data)
    address_fields = candidate_address_fields(fields)
    if not address_fields:
        raise RuntimeError(f"Business licence source has no address-like fields: {fields}")
    known = set(poc)
    matches = []
    source_rows = 0
    matched_addresses: set[str] = set()
    confirmed_addresses: set[str] = set()
    for row in reader:
        source_rows += 1
        for address in exact_row_address_matches(row, address_fields, known):
            matched_addresses.add(address)
            properties = poc[address]
            if any(item.get("tower_status") == "CONFIRMED" for item in properties):
                confirmed_addresses.add(address)
            matches.append({
                "canonical_address": address,
                "property_keys": [item.get("property_key") for item in properties],
                "tower_statuses": sorted({str(item.get("tower_status")) for item in properties}),
                "source_row": row,
            })
    payload = {
        "metadata": {
            "source_key": "mls_business_licences_permits",
            "source_url": metadata.get("portal_url"),
            "resource": resource,
            "download_bytes": len(data),
            "source_row_count": source_rows,
            "field_names": fields,
            "address_fields_used": address_fields,
            "join_basis": "EXACT_CANONICAL_ADDRESS_FIELD_EQUALITY",
            "matched_poc_address_count": len(matched_addresses),
            "matched_confirmed_tower_address_count": len(confirmed_addresses),
            "matched_source_row_count": len(matches),
            "semantics": "Business licence rows are occupant/operator context only; they never establish cooling-tower service responsibility.",
        },
        "matches": matches,
    }
    write_json(warehouse_dir / "business_licence_matches.json", payload)
    return payload["metadata"]


def csv_members(zip_bytes: bytes) -> list[tuple[str, bytes]]:
    members = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        for name in archive.namelist():
            if name.lower().endswith(".csv"):
                members.append((name, archive.read(name)))
    return members


def pull_311_matches(poc: dict[str, list[dict[str, Any]]], warehouse_dir: Path) -> dict[str, Any]:
    metadata = read_json(warehouse_dir / "open_licensed" / "311_service_requests_metadata.json")
    resource = metadata_resource(metadata, "311 Service Requests 2026", "ZIP")
    data = request_bytes(str(resource["url"]))
    members = csv_members(data)
    if not members:
        raise RuntimeError("2026 311 ZIP contained no CSV members")
    known = set(poc)
    matches = []
    diagnostics = []
    total_rows = 0
    matched_addresses: set[str] = set()
    confirmed_addresses: set[str] = set()

    for name, member_bytes in members:
        fields, reader = parse_csv_bytes(member_bytes)
        address_fields = candidate_address_fields(fields, allow_location=True)
        member_rows = 0
        member_matches = 0
        for row in reader:
            member_rows += 1
            total_rows += 1
            row_addresses = exact_row_address_matches(row, address_fields, known)
            for address in row_addresses:
                matched_addresses.add(address)
                properties = poc[address]
                if any(item.get("tower_status") == "CONFIRMED" for item in properties):
                    confirmed_addresses.add(address)
                matches.append({
                    "canonical_address": address,
                    "property_keys": [item.get("property_key") for item in properties],
                    "tower_statuses": sorted({str(item.get("tower_status")) for item in properties}),
                    "source_member": name,
                    "source_row": row,
                })
                member_matches += 1
        diagnostics.append({
            "member": name,
            "field_names": fields,
            "address_location_fields_used": address_fields,
            "row_count": member_rows,
            "matched_row_count": member_matches,
        })

    payload = {
        "metadata": {
            "source_key": "311_service_requests",
            "source_url": metadata.get("portal_url"),
            "resource": resource,
            "download_bytes": len(data),
            "source_row_count": total_rows,
            "join_basis": "EXACT_CANONICAL_ADDRESS_OR_LOCATION_FIELD_EQUALITY",
            "matched_poc_address_count": len(matched_addresses),
            "matched_confirmed_tower_address_count": len(confirmed_addresses),
            "matched_source_row_count": len(matches),
            "coverage_caveat": metadata.get("reason"),
            "semantics": "311 rows are complaint/service context only. A row does not establish a cooling-tower issue, and absence is not evidence of no complaint.",
            "member_diagnostics": diagnostics,
        },
        "matches": matches,
    }
    write_json(warehouse_dir / "311_matches.json", payload)
    return payload["metadata"]


def update_inventory(warehouse_dir: Path, business: dict[str, Any], service311: dict[str, Any]) -> None:
    path = warehouse_dir / "source_inventory.json"
    inventory = read_json(path)
    inventory["targeted_large_source_extraction"] = {
        "business_licences": business,
        "service_311_2026": service311,
    }
    write_json(path, inventory, pretty=True)


def build(poc_dir: Path, warehouse_dir: Path) -> dict[str, Any]:
    poc = poc_address_map(poc_dir)
    business = pull_business_matches(poc, warehouse_dir)
    service311 = pull_311_matches(poc, warehouse_dir)
    update_inventory(warehouse_dir, business, service311)
    result = {"business_licences": business, "service_311_2026": service311}
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Target large Toronto source families to the TowerSignal property spine")
    parser.add_argument("--poc", type=Path, default=ROOT / "data/toronto/poc/current")
    parser.add_argument("--warehouse", type=Path, default=ROOT / "data/toronto/warehouse/current")
    args = parser.parse_args()
    build(args.poc, args.warehouse)


if __name__ == "__main__":
    main()
