from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CKAN = "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action"
USER_AGENT = "TowerSignal-Toronto-Warehouse/0.1 (+https://github.com/JeremyHennessy/TowerSignal)"
LICENSE = "Open Government Licence - Toronto"

FULL_SOURCES = [
    {
        "key": "renewable_energy_installations",
        "slug": "renewable-energy-installations",
        "title": "Renewable Energy Installations",
        "quality_note": "Historical City-owned-facility context; source coverage is not a cooling-tower inventory and is not treated as current equipment status.",
    },
]

METADATA_SOURCES = [
    {
        "key": "311_service_requests",
        "slug": "311-service-requests-customer-initiated",
        "title": "311 Service Requests - Customer Initiated",
        "reason": "Large service-request feed. Register resources now; use bounded/property-relevant extraction later. City-published analysis notes the open feed covers only a subset of total 311 requests/divisions, so absence cannot be interpreted as no complaint.",
    },
    {
        "key": "mls_business_licences_permits",
        "slug": "municipal-licensing-and-standards-business-licences-and-permits",
        "title": "Municipal Licensing and Standards Business Licences and Permits",
        "reason": "Potential occupant/operator enrichment source. Register metadata first because the full citywide licence universe is broader than TowerSignal and should be queried against the property spine rather than indiscriminately replicated.",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def request_bytes(url: str, *, timeout: int = 60, retries: int = 4) -> bytes:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,*/*;q=0.8"})
            with urlopen(request, timeout=timeout) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(1.25 * (attempt + 1))
    raise RuntimeError(f"Failed to retrieve {url}: {last_error}")


def request_json(url: str) -> dict[str, Any]:
    payload = json.loads(request_bytes(url).decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object from {url}")
    return payload


def ckan(action: str, params: dict[str, Any]) -> dict[str, Any]:
    payload = request_json(f"{CKAN}/{action}?{urlencode(params)}")
    if payload.get("success") is not True or not isinstance(payload.get("result"), dict):
        raise RuntimeError(f"Toronto CKAN {action} failed: {payload!r}")
    return payload["result"]


def package(slug: str, title: str) -> dict[str, Any]:
    try:
        return ckan("package_show", {"id": slug})
    except Exception:
        result = ckan("package_search", {"q": f'title:"{title}"', "rows": 20})
        matches = [
            item for item in (result.get("results") or [])
            if str(item.get("title") or "").strip().lower() == title.lower()
        ]
        if not matches:
            raise RuntimeError(f"Could not resolve Toronto package {title!r}")
        return matches[0]


def resources(package_payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in (package_payload.get("resources") or []) if isinstance(item, dict)]


def resource_metadata(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "format": item.get("format"),
        "last_modified": item.get("last_modified"),
        "url": item.get("url"),
        "datastore_active": bool(item.get("datastore_active")),
    }


def choose_datastore(package_payload: dict[str, Any]) -> dict[str, Any]:
    candidates = resources(package_payload)
    datastore = [item for item in candidates if item.get("datastore_active")]
    if datastore:
        return datastore[0]
    raise RuntimeError(f"Package {package_payload.get('title')} has no datastore-backed resource")


def fetch_datastore(resource_id: str, max_rows: int = 20_000) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    offset = 0
    limit = 5000
    total: int | None = None
    while total is None or offset < total:
        result = ckan("datastore_search", {"resource_id": resource_id, "limit": limit, "offset": offset})
        if total is None:
            total = int(result.get("total") or 0)
            if total > max_rows:
                raise RuntimeError(f"Resource {resource_id} has {total:,} rows over cap {max_rows:,}")
        batch = result.get("records") or []
        if not isinstance(batch, list):
            raise RuntimeError("CKAN datastore records were not a list")
        rows.extend(item for item in batch if isinstance(item, dict))
        if not batch:
            break
        offset += len(batch)
    return rows, int(total or 0)


def write_json(path: Path, payload: Any, *, pretty: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2 if pretty else None, separators=None if pretty else (",", ":"), ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def replace_inventory_source(inventory: dict[str, Any], entry: dict[str, Any]) -> None:
    sources = inventory.setdefault("open_licensed_sources", [])
    sources[:] = [source for source in sources if source.get("key") != entry.get("key")]
    sources.append(entry)


def build(output_dir: Path) -> dict[str, Any]:
    inventory_path = output_dir / "source_inventory.json"
    if not inventory_path.exists():
        raise RuntimeError("Base Toronto warehouse must be pulled before additional sources")
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    open_dir = output_dir / "open_licensed"
    retrieved_at = utc_now()
    results: dict[str, Any] = {"full": {}, "metadata": {}}

    for spec in FULL_SOURCES:
        package_payload = package(spec["slug"], spec["title"])
        resource = choose_datastore(package_payload)
        rows, total = fetch_datastore(str(resource["id"]))
        metadata = {
            "key": spec["key"],
            "title": package_payload.get("title"),
            "package_name": package_payload.get("name"),
            "package_id": package_payload.get("id"),
            "portal_url": f"https://open.toronto.ca/dataset/{package_payload.get('name')}/",
            "license": LICENSE,
            "license_basis": "Toronto Open Data portal-wide licence.",
            "retrieved_at": retrieved_at,
            "resource": resource_metadata(resource),
            "row_count": len(rows),
            "reported_total": total,
            "quality_note": spec.get("quality_note"),
        }
        write_json(open_dir / f"{spec['key']}.json", {"metadata": metadata, "rows": rows})
        replace_inventory_source(inventory, metadata)
        results["full"][spec["key"]] = {"rows": len(rows)}

    for spec in METADATA_SOURCES:
        package_payload = package(spec["slug"], spec["title"])
        metadata = {
            "key": spec["key"],
            "title": package_payload.get("title"),
            "package_name": package_payload.get("name"),
            "package_id": package_payload.get("id"),
            "portal_url": f"https://open.toronto.ca/dataset/{package_payload.get('name')}/",
            "license": LICENSE,
            "license_basis": "Toronto Open Data portal-wide licence.",
            "retrieved_at": retrieved_at,
            "mode": "METADATA_ONLY_PENDING_TARGETED_EXTRACTION",
            "reason": spec["reason"],
            "resources": [resource_metadata(item) for item in resources(package_payload)],
        }
        write_json(open_dir / f"{spec['key']}_metadata.json", metadata, pretty=True)
        replace_inventory_source(inventory, metadata)
        results["metadata"][spec["key"]] = {"resources": len(metadata["resources"])}

    inventory["generated_at"] = retrieved_at
    inventory["additional_source_pull"] = results
    write_json(inventory_path, inventory, pretty=True)
    print(json.dumps(results, indent=2))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull additional Toronto warehouse source families")
    parser.add_argument("--output", type=Path, default=ROOT / "data/toronto/warehouse/current")
    args = parser.parse_args()
    build(args.output)


if __name__ == "__main__":
    main()
