from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import re
import sys
import threading
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.fetch import SourceFetchError, fetch_count, fetch_metadata, fetch_where  # noqa: E402
from towersignal.pluto import normalize_bbl  # noqa: E402

DATASET_ID = "ic3t-wcy2"
SOURCE_URL = "https://data.cityofnewyork.us/Housing-Development/DOB-Job-Application-Filings/ic3t-wcy2"
DOMAIN = "NYC_LEGACY_DOB_PROJECT_CONTEXT"
SOURCE = "NYC_DOB_BIS_JOB_APPLICATION_FILINGS"
SCHEMA_VERSION = "1.0"
QUERY_CHUNK_SIZE = 30
FETCH_CAP = 50000
RECENT_RELEVANT_DAYS = 1095
MAX_CONCURRENT_REQUESTS = 3
REQUEST_START_INTERVAL_SECONDS = 5.0
REQUEST_ATTEMPTS = 4
RATE_LIMIT_BACKOFF_SECONDS = (30.0, 60.0, 120.0)
TRANSIENT_BACKOFF_SECONDS = (1.0, 2.0, 4.0)
COOLING_TOWER_RE = re.compile(r"\bcooling\s+towers?\b", re.IGNORECASE)
BOROUGH_NAMES = {
    "1": "MANHATTAN",
    "2": "BRONX",
    "3": "BROOKLYN",
    "4": "QUEENS",
    "5": "STATEN ISLAND",
}
BOROUGH_CODES = {name: code for code, name in BOROUGH_NAMES.items()}
SELECT = ",".join((
    "job_s1_no", "job__", "doc__", "borough", "block", "lot", "bin__",
    "job_type", "job_status", "job_status_descrp", "latest_action_date",
    "plumbing", "mechanical", "boiler", "equipment", "other", "other_description",
    "applicant_s_first_name", "applicant_s_last_name", "applicant_professional_title",
    "applicant_license__", "pre__filing_date", "approved", "fully_permitted",
    "signoff_date", "initial_cost", "owner_s_business_name", "job_description",
))


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _flag(value: Any) -> bool:
    return str(value or "").strip().upper() in {"X", "Y", "YES", "TRUE", "1"}


def _date(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        try:
            return date.fromisoformat(text[:10]).isoformat()
        except ValueError:
            return None
    return None


def _source_bbl(row: dict[str, Any]) -> str | None:
    borough_raw = str(row.get("borough") or "").strip().upper()
    borough = BOROUGH_CODES.get(borough_raw)
    if borough is None and borough_raw in BOROUGH_NAMES:
        borough = borough_raw
    block_digits = "".join(ch for ch in str(row.get("block") or "") if ch.isdigit())
    lot_digits = "".join(ch for ch in str(row.get("lot") or "") if ch.isdigit())
    if borough not in BOROUGH_NAMES or not block_digits or not lot_digits:
        return None
    block_number, lot_number = int(block_digits), int(lot_digits)
    if block_number <= 0 or lot_number <= 0 or block_number > 99999 or lot_number > 9999:
        return None
    return normalize_bbl(f"{borough}{str(block_number).zfill(5)}{str(lot_number).zfill(4)}")


def _bbl_components(value: Any) -> tuple[str, str, str] | None:
    bbl = normalize_bbl(value)
    if not bbl:
        return None
    padded = bbl.zfill(10)
    if len(padded) != 10 or padded[0] not in BOROUGH_NAMES:
        return None
    return BOROUGH_NAMES[padded[0]], padded[1:6], padded[6:10]


def _exact_where(chunk: list[str]) -> str:
    clauses: list[str] = []
    for bbl in chunk:
        components = _bbl_components(bbl)
        if not components:
            continue
        borough, block, lot = components
        clauses.append(f"(borough='{borough}' AND block='{block}' AND lot='{str(int(lot)).zfill(5)}')")
    if not clauses:
        raise ValueError("No valid BBLs for legacy DOB query")
    return " OR ".join(clauses)


def _applicant(row: dict[str, Any]) -> str | None:
    parts = [_text(row.get("applicant_s_first_name")), _text(row.get("applicant_s_last_name"))]
    name = " ".join(part for part in parts if part)
    return name or None


def _is_recent(value: str | None, as_of: date, days: int = RECENT_RELEVANT_DAYS) -> bool:
    if not value:
        return False
    try:
        age = (as_of - date.fromisoformat(value)).days
    except ValueError:
        return False
    return 0 <= age <= days


def normalize_job(row: dict[str, Any], *, as_of: date) -> dict[str, Any] | None:
    bbl = _source_bbl(row)
    if not bbl:
        return None
    description = _text(row.get("job_description"))
    other_description = _text(row.get("other_description"))
    explicit_text = " ".join(value for value in (description, other_description) if value)
    explicit_ct = bool(explicit_text and COOLING_TOWER_RE.search(explicit_text))
    mechanical = _flag(row.get("mechanical"))
    boiler = _flag(row.get("boiler"))
    plumbing = _flag(row.get("plumbing"))
    equipment = _flag(row.get("equipment"))
    lifecycle = [
        value for value in (
            _date(row.get("pre__filing_date")), _date(row.get("approved")),
            _date(row.get("fully_permitted")), _date(row.get("signoff_date")),
            _date(row.get("latest_action_date")),
        ) if value
    ]
    activity_date = max(lifecycle) if lifecycle else None
    recent_relevant = _is_recent(activity_date, as_of) and (mechanical or boiler or plumbing or equipment)
    if not explicit_ct and not recent_relevant:
        return None
    relevance = "COOLING_TOWER_EXPLICIT" if explicit_ct else "RECENT_MECHANICAL_BOILER_PLUMBING_OR_EQUIPMENT"
    return {
        "source_row_id": _text(row.get("job_s1_no")),
        "job_number": _text(row.get("job__")),
        "document_number": _text(row.get("doc__")),
        "bbl": bbl,
        "bin": _text(row.get("bin__")),
        "job_type": _text(row.get("job_type")),
        "job_status": _text(row.get("job_status")),
        "job_status_description": _text(row.get("job_status_descrp")),
        "activity_date": activity_date,
        "latest_action_date": _date(row.get("latest_action_date")),
        "prefiling_date": _date(row.get("pre__filing_date")),
        "approved_date": _date(row.get("approved")),
        "fully_permitted_date": _date(row.get("fully_permitted")),
        "signoff_date": _date(row.get("signoff_date")),
        "plumbing": plumbing,
        "mechanical": mechanical,
        "boiler": boiler,
        "equipment": equipment,
        "other_work": _flag(row.get("other")),
        "job_description": description,
        "other_description": other_description,
        "explicit_cooling_tower_mention": explicit_ct,
        "recent_relevant_project": recent_relevant,
        "commercial_relevance": relevance,
        "applicant_name": _applicant(row),
        "applicant_professional_title": _text(row.get("applicant_professional_title")),
        "applicant_license_number": _text(row.get("applicant_license__")),
        "owner_business_name": _text(row.get("owner_s_business_name")),
        "initial_cost_raw": _text(row.get("initial_cost")),
        "source": SOURCE,
        "match_basis": "BOROUGH_BLOCK_LOT_TO_BBL_EXACT",
        "relationship_boundary": "RECORDED_DOB_APPLICANT_NOT_PROOF_OF_SERVICE_CONTRACT",
    }


def build(output_dir: Path, output_file: Path | None = None) -> dict[str, Any]:
    systems_path = output_dir / "systems.json"
    payload = json.loads(systems_path.read_text(encoding="utf-8"))
    systems = payload.get("systems") or []
    snapshot_date = date.fromisoformat(str((payload.get("metadata") or {}).get("snapshot_date") or date.today().isoformat()))
    requested = sorted({bbl for row in systems if (bbl := normalize_bbl(row.get("bbl"))) and _bbl_components(bbl)}, key=int)
    requested_set = set(requested)

    retained_by_bbl: dict[str, dict[str, dict[str, Any]]] = {}
    source_matched_bbls: set[str] = set()
    fetched_job_count = 0
    started = time.monotonic()
    batches = [requested[start:start + QUERY_CHUNK_SIZE] for start in range(0, len(requested), QUERY_CHUNK_SIZE)]
    total_batches = len(batches)
    print(
        f"[legacy_dob] Fetching {len(requested):,} canonical BBLs in {total_batches} batches "
        f"with at most {MAX_CONCURRENT_REQUESTS} concurrent requests and "
        f"{REQUEST_START_INTERVAL_SECONDS:.0f}s minimum request-start spacing",
        file=sys.stderr,
        flush=True,
    )

    throttle_lock = threading.Lock()
    next_request_start = 0.0

    def reserve_request_start() -> None:
        nonlocal next_request_start
        while True:
            with throttle_lock:
                now = time.monotonic()
                delay = next_request_start - now
                if delay <= 0:
                    next_request_start = now + REQUEST_START_INTERVAL_SECONDS
                    return
            time.sleep(min(delay, 1.0))

    def extend_global_cooldown(seconds: float) -> None:
        nonlocal next_request_start
        with throttle_lock:
            next_request_start = max(next_request_start, time.monotonic() + seconds)

    def fetch_batch(batch_index: int, chunk: list[str]) -> tuple[int, list[dict[str, Any]], float]:
        query_started = time.monotonic()
        where = _exact_where(chunk)
        last_error: SourceFetchError | None = None
        for attempt in range(1, REQUEST_ATTEMPTS + 1):
            reserve_request_start()
            print(
                f"[legacy_dob] Batch {batch_index}/{total_batches}: querying {len(chunk)} BBLs "
                f"(attempt {attempt}/{REQUEST_ATTEMPTS})",
                file=sys.stderr,
                flush=True,
            )
            try:
                rows = fetch_where(
                    DATASET_ID,
                    where=where,
                    order_by="borough,block,lot,job_s1_no",
                    select=SELECT,
                    limit=FETCH_CAP,
                    request_retries=1,
                    request_timeout=120,
                )
            except SourceFetchError as error:
                last_error = error
                message = str(error)
                retryable_transport = message.startswith("Failed to retrieve authoritative source after")
                if not retryable_transport or attempt >= REQUEST_ATTEMPTS:
                    raise
                rate_limited = "429" in message or "Too Many Requests" in message
                delays = RATE_LIMIT_BACKOFF_SECONDS if rate_limited else TRANSIENT_BACKOFF_SECONDS
                delay = delays[attempt - 1]
                if rate_limited:
                    extend_global_cooldown(delay)
                else:
                    time.sleep(delay)
                print(
                    f"[legacy_dob] Batch {batch_index}/{total_batches}: "
                    f"{'rate limited' if rate_limited else 'transient source failure'}; "
                    f"retrying after {delay:.0f}s",
                    file=sys.stderr,
                    flush=True,
                )
                continue
            if len(rows) >= FETCH_CAP:
                raise SourceFetchError(
                    f"Legacy DOB exact-property query reached the {FETCH_CAP:,}-row cap for {len(chunk)} BBLs; refusing possibly truncated evidence"
                )
            elapsed = time.monotonic() - query_started
            print(f"[legacy_dob] Batch {batch_index}/{total_batches}: {len(rows):,} rows in {elapsed:.1f}s", file=sys.stderr, flush=True)
            return batch_index, rows, elapsed
        raise last_error or SourceFetchError(f"Legacy DOB batch {batch_index} exhausted retries")

    rows_by_batch: dict[int, list[dict[str, Any]]] = {}
    executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS)
    futures = [executor.submit(fetch_batch, index, chunk) for index, chunk in enumerate(batches, 1)]
    try:
        for future in as_completed(futures):
            batch_index, rows, _ = future.result()
            rows_by_batch[batch_index] = rows
    except BaseException:
        for future in futures:
            future.cancel()
        executor.shutdown(wait=True, cancel_futures=True)
        raise
    else:
        executor.shutdown(wait=True)

    if set(rows_by_batch) != set(range(1, total_batches + 1)):
        raise SourceFetchError("Legacy DOB batch collection completed with an incomplete batch inventory")

    for batch_index, chunk in enumerate(batches, 1):
        rows = rows_by_batch[batch_index]
        fetched_job_count += len(rows)
        print(
            f"[legacy_dob] Batch {batch_index}/{total_batches}: merging {len(rows):,} rows; "
            f"{fetched_job_count:,} rows total; elapsed {time.monotonic() - started:.1f}s",
            file=sys.stderr,
            flush=True,
        )
        for source_row in rows:
            source_bbl = _source_bbl(source_row)
            if source_bbl not in requested_set:
                continue
            source_matched_bbls.add(str(source_bbl))
            record = normalize_job(source_row, as_of=snapshot_date)
            if not record:
                continue
            identity = record.get("source_row_id") or f"{record.get('job_number')}:{record.get('document_number')}"
            if not identity or identity == "None:None":
                raise SourceFetchError(f"Retained legacy DOB row on BBL {source_bbl} lacks stable identity")
            retained_by_bbl.setdefault(str(source_bbl), {})[str(identity)] = record

    by_bbl: dict[str, Any] = {}
    explicit_count = 0
    recent_relevant_count = 0
    for bbl, record_map in retained_by_bbl.items():
        records = sorted(
            record_map.values(),
            key=lambda row: (bool(row.get("explicit_cooling_tower_mention")), row.get("activity_date") or "", row.get("source_row_id") or ""),
            reverse=True,
        )
        explicit = sum(1 for row in records if row.get("explicit_cooling_tower_mention"))
        recent = sum(1 for row in records if row.get("recent_relevant_project"))
        explicit_count += explicit
        recent_relevant_count += recent
        by_bbl[bbl] = {
            "summary": {
                "record_count": len(records),
                "explicit_cooling_tower_count": explicit,
                "recent_relevant_project_count": recent,
                "latest_activity_date": max((row.get("activity_date") or "" for row in records), default="") or None,
            },
            "records": records,
        }

    print("[legacy_dob] All exact-property batches completed; fetching source metadata", file=sys.stderr, flush=True)
    metadata = fetch_metadata(DATASET_ID)
    print("[legacy_dob] Source metadata received; fetching total source count", file=sys.stderr, flush=True)
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "domain": DOMAIN,
        "as_of": snapshot_date.isoformat(),
        "source": {
            "dataset_id": DATASET_ID,
            "name": metadata.get("name") or "DOB Job Application Filings",
            "url": SOURCE_URL,
            "source_record_count": fetch_count(DATASET_ID),
            "source_last_updated_at": metadata.get("source_last_updated_at"),
            "requested_bbl_count": len(requested),
            "source_matched_bbl_count": len(source_matched_bbls),
            "exact_bbl_job_count": fetched_job_count,
            "source_scope": "Legacy BIS/eFiling/HUB jobs; DOB NOW is excluded by the source contract",
        },
        "summary": {
            "requested_bbl_count": len(requested),
            "source_matched_bbl_count": len(source_matched_bbls),
            "exact_bbl_job_count": fetched_job_count,
            "retained_bbl_count": len(by_bbl),
            "retained_record_count": sum(item["summary"]["record_count"] for item in by_bbl.values()),
            "explicit_cooling_tower_record_count": explicit_count,
            "recent_relevant_project_record_count": recent_relevant_count,
        },
        "evidence_semantics": {
            "property_link": "Exact borough + block + lot reconstruction to canonical 10-digit BBL only; no address or fuzzy property matching.",
            "retention": "Retain all explicit published cooling-tower mentions plus mechanical/boiler/plumbing/equipment jobs with lifecycle activity within 1,095 days of the build snapshot.",
            "roles": "Applicant and owner names are recorded DOB project roles only; they do not establish a service contract, incumbent provider, current ownership or maintenance responsibility.",
            "history": "This cache is historical/project context and is not written into TowerSignal Monitor history as newly occurring events.",
            "scoring": "Legacy DOB project context does not alter Priority Score 1.0.",
        },
        "by_bbl": by_bbl,
    }
    target = output_file or output_dir / "legacy-dob-projects.json"
    target.write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    print(f"[legacy_dob] Complete: {total_batches} batches in {time.monotonic() - started:.1f}s", file=sys.stderr, flush=True)
    print(json.dumps(result["summary"], indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Build compact exact-BBL legacy DOB/BIS project context")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data")
    parser.add_argument("--cache", type=Path)
    args = parser.parse_args()
    build(args.output, args.cache)


if __name__ == "__main__":
    main()
