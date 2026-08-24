from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from http.client import IncompleteRead
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_ROOT = "https://data.cityofnewyork.us"
USER_AGENT = "TowerSignal/1.0 (+https://github.com/JeremyHennessy/TowerSignal)"
ACRIS_CACHE_SCHEMA_VERSION = "1.0"
ACRIS_LOOKBACK_DAYS = 365
ACRIS_MAX_CACHE_BYTES = 12 * 1024 * 1024
ACRIS_BROWSER_DOCUMENT_LIMIT = 25

MASTER_DATASET_ID = "bnx9-e6tj"
LEGALS_DATASET_ID = "8h5j-fqxa"
PARTIES_DATASET_ID = "636b-3b5g"
MASTER_URL = "https://data.cityofnewyork.us/City-Government/ACRIS-Real-Property-Master/bnx9-e6tj"
LEGALS_URL = "https://data.cityofnewyork.us/City-Government/ACRIS-Real-Property-Legals/8h5j-fqxa"
PARTIES_URL = "https://data.cityofnewyork.us/City-Government/ACRIS-Real-Property-Parties/636b-3b5g"

RELEVANT_DOC_TYPES = (
    "DEED",
    "DEED COR",
    "MTGE",
    "ASST",
    "ASSTO",
    "SAT",
    "SAGE",
    "AALR",
    "AL&R",
    "LEAS",
    "MLEA",
    "REL",
)
DEED_DOC_TYPES = {"DEED", "DEED COR"}
MORTGAGE_DOC_TYPES = {"MTGE"}
LEASE_DOC_TYPES = {"LEAS", "MLEA"}
ASSIGNMENT_DOC_TYPES = {"ASST", "ASSTO"}
SATISFACTION_DOC_TYPES = {"SAT", "SAGE"}

MASTER_SELECT = ",".join((
    "document_id",
    "record_type",
    "crfn",
    "recorded_borough",
    "doc_type",
    "document_date",
    "document_amt",
    "recorded_datetime",
    "modified_date",
    "percent_trans",
    "good_through_date",
))
LEGAL_SELECT = ",".join((
    "document_id",
    "borough",
    "block",
    "lot",
    "property_type",
    "street_number",
    "street_name",
    "unit",
    "good_through_date",
))
PARTY_SELECT = ",".join((
    "document_id",
    "record_type",
    "party_type",
    "name",
    "address_1",
    "address_2",
    "country",
    "city",
    "state",
    "zip",
    "good_through_date",
))


class AcrisError(RuntimeError):
    pass


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _date(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    if len(text) >= 10:
        try:
            return date.fromisoformat(text[:10]).isoformat()
        except ValueError:
            pass
    for pattern in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _number(value: Any) -> float | None:
    text = _text(value)
    if text is None:
        return None
    cleaned = text.replace("$", "").replace(",", "").replace("%", "")
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    if negative:
        cleaned = cleaned[1:-1]
    try:
        parsed = Decimal(cleaned)
    except InvalidOperation:
        return None
    if not parsed.is_finite():
        return None
    result = float(parsed)
    return -result if negative else result


def normalize_bbl(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    if text.endswith(".0"):
        text = text[:-2]
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) != 10 or digits[0] not in "12345":
        return None
    return digits


def bbl_from_legal(row: dict[str, Any]) -> str | None:
    try:
        borough = int(float(str(row.get("borough"))))
        block = int(float(str(row.get("block"))))
        lot = int(float(str(row.get("lot"))))
    except (TypeError, ValueError):
        return None
    if borough not in range(1, 6) or block < 0 or lot < 0:
        return None
    return f"{borough}{block:05d}{lot:04d}"


def tower_bbl_hash(values: Iterable[str]) -> str:
    normalized = sorted({bbl for value in values if (bbl := normalize_bbl(value)) is not None})
    return hashlib.sha256("\n".join(normalized).encode("utf-8")).hexdigest()


def _quote(value: Any) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index:index + size]


def _request_json(url: str, attempts: int = 5, timeout: int = 90) -> Any:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except HTTPError as exc:
            last_error = exc
            if exc.code not in {429, 500, 502, 503, 504}:
                raise AcrisError(f"ACRIS request failed with HTTP {exc.code}: {url}") from exc
        except (URLError, TimeoutError, IncompleteRead, json.JSONDecodeError, ConnectionError) as exc:
            last_error = exc
        if attempt + 1 < attempts:
            time.sleep(min(8.0, 1.5 ** attempt))
    raise AcrisError(f"ACRIS request failed after {attempts} attempts: {url}: {last_error}")


def _resource(dataset_id: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _request_json(f"{API_ROOT}/resource/{dataset_id}.json?{urlencode(params)}")
    if not isinstance(payload, list):
        raise AcrisError(f"ACRIS dataset {dataset_id} returned a non-list payload")
    return payload


def _metadata(dataset_id: str) -> dict[str, Any]:
    url = f"{API_ROOT}/api/views/{dataset_id}"
    try:
        payload = _request_json(url, attempts=2, timeout=15)
    except AcrisError as exc:
        return {
            "name": dataset_id,
            "source_last_updated_at": None,
            "metadata_status": "UNAVAILABLE",
            "metadata_error": str(exc),
        }
    if not isinstance(payload, dict):
        return {
            "name": dataset_id,
            "source_last_updated_at": None,
            "metadata_status": "UNAVAILABLE",
            "metadata_error": f"ACRIS metadata {dataset_id} returned malformed payload",
        }
    updated = payload.get("rowsUpdatedAt") or payload.get("dataUpdatedAt")
    source_last_updated_at = None
    try:
        if updated is not None:
            source_last_updated_at = datetime.fromtimestamp(int(updated), tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError, OSError):
        pass
    return {
        "name": str(payload.get("name") or dataset_id),
        "source_last_updated_at": source_last_updated_at,
        "metadata_status": "AVAILABLE",
        "metadata_error": None,
    }


def canonical_master(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise AcrisError("Cannot canonicalize an empty ACRIS Master group")
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("recorded_datetime") or ""),
            str(row.get("modified_date") or ""),
            str(row.get("record_type") or ""),
            json.dumps(row, sort_keys=True),
        ),
        reverse=True,
    )[0]


def normalize_party(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "party_type": _text(row.get("party_type")),
        "name": _text(row.get("name")),
        "address_1": _text(row.get("address_1")),
        "address_2": _text(row.get("address_2")),
        "country": _text(row.get("country")),
        "city": _text(row.get("city")),
        "state": _text(row.get("state")),
        "zip": _text(row.get("zip")),
    }


def normalize_legal_context(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "property_type": _text(row.get("property_type")),
        "street_number": _text(row.get("street_number")),
        "street_name": _text(row.get("street_name")),
        "unit": _text(row.get("unit")),
    }


def normalize_document(
    bbl: str,
    master: dict[str, Any],
    legal_rows: list[dict[str, Any]],
    party_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    document_id = _text(master.get("document_id"))
    if not document_id:
        raise AcrisError("ACRIS canonical Master row is missing document_id")

    legal_seen: set[tuple[Any, ...]] = set()
    legal_context: list[dict[str, Any]] = []
    for row in legal_rows:
        normalized = normalize_legal_context(row)
        identity = tuple(normalized.get(key) for key in ("property_type", "street_number", "street_name", "unit"))
        if identity in legal_seen:
            continue
        legal_seen.add(identity)
        legal_context.append(normalized)
    legal_context.sort(key=lambda item: tuple(str(item.get(key) or "") for key in ("street_number", "street_name", "unit", "property_type")))

    party_seen: set[tuple[Any, ...]] = set()
    parties: list[dict[str, Any]] = []
    for row in party_rows:
        normalized = normalize_party(row)
        identity = tuple(normalized.get(key) for key in ("party_type", "name", "address_1", "address_2", "city", "state", "zip", "country"))
        if identity in party_seen:
            continue
        party_seen.add(identity)
        parties.append(normalized)
    parties.sort(key=lambda item: (str(item.get("party_type") or ""), str(item.get("name") or ""), str(item.get("address_1") or "")))

    return {
        "document_id": document_id,
        "bbl": bbl,
        "record_type": _text(master.get("record_type")),
        "crfn": _text(master.get("crfn")),
        "recorded_borough": _text(master.get("recorded_borough")),
        "doc_type": _text(master.get("doc_type")),
        "document_date": _date(master.get("document_date")),
        "recorded_date": _date(master.get("recorded_datetime")),
        "modified_date": _date(master.get("modified_date")),
        "document_amount": _number(master.get("document_amt")),
        "percent_transferred": _number(master.get("percent_trans")),
        "legal_context": legal_context,
        "parties": parties,
        "source": "NYC_ACRIS_REAL_PROPERTY",
        "match_basis": "BBL_EXACT_DOCUMENT_ID_EXACT",
    }


def summarize_property(documents: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(
        documents,
        key=lambda item: (str(item.get("recorded_date") or ""), str(item.get("document_id") or "")),
        reverse=True,
    )
    doc_types = [str(item.get("doc_type") or "").strip().upper() for item in ordered]
    return {
        "recent_document_count": len(ordered),
        "latest_recorded_date": max((str(item.get("recorded_date")) for item in ordered if item.get("recorded_date")), default=None),
        "deed_count": sum(1 for value in doc_types if value in DEED_DOC_TYPES),
        "mortgage_count": sum(1 for value in doc_types if value in MORTGAGE_DOC_TYPES),
        "lease_count": sum(1 for value in doc_types if value in LEASE_DOC_TYPES),
        "assignment_count": sum(1 for value in doc_types if value in ASSIGNMENT_DOC_TYPES),
        "satisfaction_count": sum(1 for value in doc_types if value in SATISFACTION_DOC_TYPES),
        "recorded_party_count": sum(len(item.get("parties") or []) for item in ordered),
        "documents": ordered,
    }


def browser_property_context(property_context: dict[str, Any], document_limit: int = ACRIS_BROWSER_DOCUMENT_LIMIT) -> dict[str, Any]:
    result = {key: value for key, value in property_context.items() if key != "documents"}
    documents = list(property_context.get("documents") or [])
    result["documents"] = documents[:document_limit]
    result["displayed_document_count"] = min(len(documents), document_limit)
    return result


def build_recent_cache(
    tower_bbl_values: Iterable[str],
    *,
    as_of: date | None = None,
    lookback_days: int = ACRIS_LOOKBACK_DAYS,
    page_size: int = 50000,
    document_batch_size: int = 300,
    max_workers: int = 8,
) -> dict[str, Any]:
    started = time.monotonic()
    tower_bbls = sorted({bbl for value in tower_bbl_values if (bbl := normalize_bbl(value)) is not None})
    if not tower_bbls:
        raise AcrisError("No usable cooling-tower BBLs were supplied for ACRIS cache generation")
    tower_bbl_set = set(tower_bbls)
    cutoff = ((as_of or datetime.now(timezone.utc).date()) - timedelta(days=lookback_days)).isoformat()
    type_clause = ",".join(_quote(value) for value in RELEVANT_DOC_TYPES)
    master_where = f"recorded_datetime >= '{cutoff}T00:00:00.000' AND doc_type in ({type_clause})"

    count_rows = _resource(MASTER_DATASET_ID, {"$select": "count(*) as count", "$where": master_where})
    if not count_rows or "count" not in count_rows[0]:
        raise AcrisError("ACRIS Master count query returned an unexpected payload")
    expected_master_count = int(count_rows[0]["count"])
    if expected_master_count <= 0:
        raise AcrisError("ACRIS bounded Master slice unexpectedly returned zero rows")

    master_rows: list[dict[str, Any]] = []
    offset = 0
    while offset < expected_master_count:
        rows = _resource(MASTER_DATASET_ID, {
            "$select": MASTER_SELECT,
            "$where": master_where,
            "$limit": page_size,
            "$offset": offset,
            "$order": "document_id,recorded_datetime,modified_date",
        })
        master_rows.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size
    if len(master_rows) != expected_master_count:
        raise AcrisError(f"ACRIS Master pagination incomplete: expected {expected_master_count:,}, got {len(master_rows):,}")

    master_by_doc: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in master_rows:
        document_id = _text(row.get("document_id"))
        if document_id:
            master_by_doc[document_id].append(row)
    canonical_master_by_doc = {document_id: canonical_master(rows) for document_id, rows in master_by_doc.items()}
    document_ids = sorted(canonical_master_by_doc)
    master_elapsed = time.monotonic() - started

    def fetch_legal_batch(batch: list[str]) -> list[dict[str, Any]]:
        where = "document_id in (" + ",".join(_quote(value) for value in batch) + ")"
        rows = _resource(LEGALS_DATASET_ID, {
            "$select": LEGAL_SELECT,
            "$where": where,
            "$limit": 50000,
            "$order": "document_id,borough,block,lot",
        })
        if len(rows) >= 50000:
            raise AcrisError(f"ACRIS Legals batch reached the 50,000 row cap for {len(batch)} document IDs")
        return rows

    legal_batches = list(_chunks(document_ids, document_batch_size))
    legal_rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(fetch_legal_batch, batch) for batch in legal_batches]
        for future in as_completed(futures):
            legal_rows.extend(future.result())

    matched_docs_by_bbl: dict[str, set[str]] = defaultdict(set)
    legal_by_bbl_doc: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    matched_legal_row_count = 0
    for row in legal_rows:
        bbl = bbl_from_legal(row)
        document_id = _text(row.get("document_id"))
        if bbl in tower_bbl_set and document_id in canonical_master_by_doc:
            matched_docs_by_bbl[bbl].add(document_id)
            legal_by_bbl_doc[(bbl, document_id)].append(row)
            matched_legal_row_count += 1
    matched_document_ids = sorted({document_id for values in matched_docs_by_bbl.values() for document_id in values})
    legal_elapsed = time.monotonic() - started

    def fetch_party_batch(batch: list[str]) -> list[dict[str, Any]]:
        where = "document_id in (" + ",".join(_quote(value) for value in batch) + ")"
        rows = _resource(PARTIES_DATASET_ID, {
            "$select": PARTY_SELECT,
            "$where": where,
            "$limit": 50000,
            "$order": "document_id,party_type,name",
        })
        if len(rows) >= 50000:
            raise AcrisError(f"ACRIS Parties batch reached the 50,000 row cap for {len(batch)} document IDs")
        return rows

    party_batches = list(_chunks(matched_document_ids, document_batch_size))
    party_rows: list[dict[str, Any]] = []
    if party_batches:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(fetch_party_batch, batch) for batch in party_batches]
            for future in as_completed(futures):
                party_rows.extend(future.result())
    parties_by_doc: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in party_rows:
        document_id = _text(row.get("document_id"))
        if document_id:
            parties_by_doc[document_id].append(row)

    properties: dict[str, dict[str, Any]] = {}
    for bbl in sorted(matched_docs_by_bbl):
        documents = [
            normalize_document(
                bbl,
                canonical_master_by_doc[document_id],
                legal_by_bbl_doc[(bbl, document_id)],
                parties_by_doc.get(document_id, []),
            )
            for document_id in sorted(matched_docs_by_bbl[bbl])
        ]
        properties[bbl] = summarize_property(documents)

    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    master_meta = _metadata(MASTER_DATASET_ID)
    legal_meta = _metadata(LEGALS_DATASET_ID)
    party_meta = _metadata(PARTIES_DATASET_ID)
    party_doc_ids = set(parties_by_doc)
    matched_counts = [len(values) for values in matched_docs_by_bbl.values()]
    total_elapsed = time.monotonic() - started

    sources = [
        {
            "dataset_id": MASTER_DATASET_ID,
            **master_meta,
            "retrieved_at": generated_at,
            "source_record_count": len(master_rows),
            "url": MASTER_URL,
            "source_query_scope": f"{lookback_days}-day bounded Master slice for commercially relevant ACRIS document types",
        },
        {
            "dataset_id": LEGALS_DATASET_ID,
            **legal_meta,
            "retrieved_at": generated_at,
            "source_record_count": len(legal_rows),
            "url": LEGALS_URL,
            "source_query_scope": f"Exact document_id Legals rows for {len(document_ids):,} bounded recent Master documents; intersected to exact cooling-tower BBLs",
        },
        {
            "dataset_id": PARTIES_DATASET_ID,
            **party_meta,
            "retrieved_at": generated_at,
            "source_record_count": len(party_rows),
            "url": PARTIES_URL,
            "source_query_scope": f"Exact document_id Party rows for {len(matched_document_ids):,} ACRIS documents matched to cooling-tower BBLs",
        },
    ]
    metrics = {
        "requested_tower_bbl_count": len(tower_bbls),
        "master_source_row_count_for_slice": expected_master_count,
        "master_rows_retrieved": len(master_rows),
        "master_unique_document_count": len(document_ids),
        "master_documents_with_multiple_rows": sum(1 for rows in master_by_doc.values() if len(rows) > 1),
        "legal_batch_count": len(legal_batches),
        "legal_rows_retrieved_for_recent_documents": len(legal_rows),
        "tower_bbls_with_recent_relevant_acris": len(properties),
        "matched_recent_document_count": len(matched_document_ids),
        "matched_legal_row_count": matched_legal_row_count,
        "median_matched_documents_per_matched_bbl": sorted(matched_counts)[len(matched_counts) // 2] if matched_counts else 0,
        "max_matched_documents_per_bbl": max(matched_counts, default=0),
        "party_batch_count": len(party_batches),
        "party_row_count": len(party_rows),
        "matched_documents_with_parties": len(set(matched_document_ids) & party_doc_ids),
        "matched_documents_without_parties": len(set(matched_document_ids) - party_doc_ids),
        "master_fetch_seconds": round(master_elapsed, 2),
        "legal_fetch_cumulative_seconds": round(legal_elapsed, 2),
        "total_seconds": round(total_elapsed, 2),
    }
    cache = {
        "schema_version": ACRIS_CACHE_SCHEMA_VERSION,
        "generated_at": generated_at,
        "lookback_days": lookback_days,
        "cutoff": cutoff,
        "tower_bbl_universe": {"count": len(tower_bbls), "sha256": tower_bbl_hash(tower_bbls)},
        "sources": sources,
        "metrics": metrics,
        "properties": properties,
    }
    validate_cache(cache, require_production_volume=True)
    return cache


def validate_cache(cache: dict[str, Any], *, require_production_volume: bool = False) -> None:
    if cache.get("schema_version") != ACRIS_CACHE_SCHEMA_VERSION:
        raise AcrisError(f"Unsupported ACRIS cache schema: {cache.get('schema_version')!r}")
    generated_at = cache.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at:
        raise AcrisError("ACRIS cache is missing generated_at")
    if int(cache.get("lookback_days") or 0) <= 0:
        raise AcrisError("ACRIS cache has invalid lookback_days")
    sources = cache.get("sources")
    if not isinstance(sources, list) or {source.get("dataset_id") for source in sources if isinstance(source, dict)} != {MASTER_DATASET_ID, LEGALS_DATASET_ID, PARTIES_DATASET_ID}:
        raise AcrisError("ACRIS cache does not contain the three verified source contracts")
    metrics = cache.get("metrics")
    properties = cache.get("properties")
    if not isinstance(metrics, dict) or not isinstance(properties, dict):
        raise AcrisError("ACRIS cache is missing metrics or properties")
    if int(metrics.get("tower_bbls_with_recent_relevant_acris") or 0) != len(properties):
        raise AcrisError("ACRIS cache property count does not match metrics")

    unique_documents: set[str] = set()
    for bbl, context in properties.items():
        if normalize_bbl(bbl) != bbl:
            raise AcrisError(f"ACRIS cache contains invalid BBL key: {bbl!r}")
        if not isinstance(context, dict):
            raise AcrisError(f"ACRIS property context for {bbl} is malformed")
        documents = context.get("documents")
        if not isinstance(documents, list):
            raise AcrisError(f"ACRIS property context for {bbl} is missing documents")
        if int(context.get("recent_document_count") or 0) != len(documents):
            raise AcrisError(f"ACRIS property context document count mismatch for {bbl}")
        for document in documents:
            if not isinstance(document, dict):
                raise AcrisError(f"ACRIS document for {bbl} is malformed")
            if document.get("bbl") != bbl or document.get("match_basis") != "BBL_EXACT_DOCUMENT_ID_EXACT":
                raise AcrisError(f"ACRIS document join provenance mismatch for {bbl}")
            document_id = _text(document.get("document_id"))
            if not document_id:
                raise AcrisError(f"ACRIS document for {bbl} is missing document_id")
            unique_documents.add(document_id)
    if int(metrics.get("matched_recent_document_count") or 0) != len(unique_documents):
        raise AcrisError("ACRIS unique document count does not match metrics")
    if require_production_volume:
        if int(metrics.get("requested_tower_bbl_count") or 0) < 1000:
            raise AcrisError("ACRIS cache was not built against a production-scale cooling-tower BBL universe")
        if len(properties) < 100 or len(unique_documents) < 100:
            raise AcrisError("ACRIS cache recent-activity volume is unexpectedly small")


def load_cache(path: Path) -> dict[str, Any]:
    try:
        cache = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AcrisError(f"Unable to load verified ACRIS cache {path}: {exc}") from exc
    if not isinstance(cache, dict):
        raise AcrisError(f"ACRIS cache {path} is not a JSON object")
    validate_cache(cache)
    return cache


def cache_age_days(cache: dict[str, Any], *, now: datetime | None = None) -> float:
    text = str(cache.get("generated_at") or "")
    try:
        generated = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AcrisError(f"Invalid ACRIS cache generated_at: {text!r}") from exc
    reference = now or datetime.now(timezone.utc)
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)
    return max(0.0, (reference - generated.astimezone(timezone.utc)).total_seconds() / 86400.0)


def validate_cache_file(path: Path, *, max_bytes: int = ACRIS_MAX_CACHE_BYTES, max_age_days: float | None = None, require_production_volume: bool = False) -> dict[str, Any]:
    size = path.stat().st_size
    if size > max_bytes:
        raise AcrisError(f"ACRIS cache exceeds size ceiling: {size:,} bytes > {max_bytes:,}")
    cache = load_cache(path)
    validate_cache(cache, require_production_volume=require_production_volume)
    age = cache_age_days(cache)
    if max_age_days is not None and age > max_age_days:
        raise AcrisError(f"ACRIS cache is stale: {age:.1f} days > {max_age_days:.1f} day limit")
    return {"size_bytes": size, "age_days": round(age, 2), "cache": cache}
