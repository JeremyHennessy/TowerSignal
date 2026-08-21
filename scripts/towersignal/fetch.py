from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_ROOT = "https://data.cityofnewyork.us"
USER_AGENT = "TowerSignal/1.0 (+https://github.com/JeremyHennessy/TowerSignal)"


class SourceFetchError(RuntimeError):
    pass


@dataclass(frozen=True)
class DatasetSnapshot:
    dataset_id: str
    name: str
    rows: list[dict[str, Any]]
    retrieved_at: str
    source_record_count: int
    source_last_updated_at: str | None


def _request_json(url: str, retries: int = 4, timeout: int = 90) -> Any:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(2**attempt)
    raise SourceFetchError(f"Failed to retrieve authoritative source after {retries} attempts: {url}: {last_error}")


def _iso_from_epoch(value: Any) -> str | None:
    try:
        epoch = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_metadata(dataset_id: str) -> dict[str, Any]:
    metadata = _request_json(f"{API_ROOT}/api/views/{dataset_id}")
    return {
        "name": metadata.get("name") or dataset_id,
        "source_last_updated_at": _iso_from_epoch(metadata.get("rowsUpdatedAt") or metadata.get("dataUpdatedAt")),
    }


def fetch_count(dataset_id: str) -> int:
    query = urlencode({"$select": "count(*) as count"})
    payload = _request_json(f"{API_ROOT}/resource/{dataset_id}.json?{query}")
    if not payload or "count" not in payload[0]:
        raise SourceFetchError(f"Count query for {dataset_id} returned an unexpected payload")
    return int(payload[0]["count"])


def fetch_dataset(dataset_id: str, order_by: str, page_size: int = 50000) -> DatasetSnapshot:
    expected_count = fetch_count(dataset_id)
    metadata = fetch_metadata(dataset_id)
    rows: list[dict[str, Any]] = []
    offset = 0

    while offset < expected_count:
        query = urlencode({"$limit": page_size, "$offset": offset, "$order": order_by})
        page = _request_json(f"{API_ROOT}/resource/{dataset_id}.json?{query}")
        if not isinstance(page, list):
            raise SourceFetchError(f"Dataset {dataset_id} returned a non-list page at offset {offset}")
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size

    if len(rows) != expected_count:
        raise SourceFetchError(
            f"Dataset {dataset_id} pagination was incomplete: expected {expected_count:,} rows, fetched {len(rows):,}. "
            "Refusing to publish a partial snapshot."
        )

    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return DatasetSnapshot(
        dataset_id=dataset_id,
        name=str(metadata["name"]),
        rows=rows,
        retrieved_at=retrieved_at,
        source_record_count=len(rows),
        source_last_updated_at=metadata.get("source_last_updated_at"),
    )


def fetch_where(dataset_id: str, where: str, order_by: str | None = None, select: str | None = None) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"$limit": 50000, "$where": where}
    if order_by:
        params["$order"] = order_by
    if select:
        params["$select"] = select
    payload = _request_json(f"{API_ROOT}/resource/{dataset_id}.json?{urlencode(params)}")
    if not isinstance(payload, list):
        raise SourceFetchError(f"Filtered query for {dataset_id} returned a non-list payload")
    return payload
