from __future__ import annotations

from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from towersignal.oath import MATCH_BASIS, MIN_EXPECTED_MATCH_RATIO, normalize_ticket_number

OATH_CACHE_SCHEMA_VERSION = "1.0"
OATH_DATASET_ID = "jz4z-kudi"
INSPECTION_DATASET_ID = "f9wb-g8mb"
DEFAULT_MAX_AGE_DAYS = 2.0
MAX_COMPRESSED_CACHE_BYTES = 64 * 1024 * 1024
MIN_PRODUCTION_INSPECTION_ROWS = 100_000
MIN_PRODUCTION_REQUESTED_TICKETS = 40_000


def normalized_ticket_universe(values: Iterable[Any]) -> list[str]:
    return sorted({ticket for value in values if (ticket := normalize_ticket_number(value))})


def ticket_universe_fingerprint(values: Iterable[Any]) -> dict[str, Any]:
    tickets = normalized_ticket_universe(values)
    canonical = "\n".join(tickets).encode("utf-8")
    return {
        "count": len(tickets),
        "sha256": hashlib.sha256(canonical).hexdigest(),
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("OATH cache generated_at is missing")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def build_cache_payload(
    *,
    inspection_snapshot: Any,
    requested_tickets: Iterable[Any],
    cases_by_ticket: Mapping[str, Mapping[str, Any]],
    oath_metadata: Mapping[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    requested = normalized_ticket_universe(requested_tickets)
    requested_set = set(requested)
    normalized_cases: dict[str, dict[str, Any]] = {}
    for raw_ticket, raw_case in cases_by_ticket.items():
        ticket = normalize_ticket_number(raw_ticket)
        if not ticket:
            raise ValueError("OATH cache case map contains an empty ticket key")
        if ticket not in requested_set:
            raise ValueError(f"OATH cache contains case outside requested universe: {ticket}")
        case = dict(raw_case)
        case_ticket = normalize_ticket_number(case.get("ticket_number"))
        if case_ticket != ticket:
            raise ValueError(f"OATH cache case/key ticket mismatch: {ticket} != {case_ticket}")
        normalized_cases[ticket] = case

    requested_count = len(requested)
    matched_count = len(normalized_cases)
    ratio = matched_count / requested_count if requested_count else 1.0
    if requested_count >= 100 and ratio < MIN_EXPECTED_MATCH_RATIO:
        raise ValueError(
            f"OATH cache coverage below production floor: {matched_count:,}/{requested_count:,} ({ratio:.1%})"
        )

    metadata_requested = int(oath_metadata.get("requested_ticket_count") or 0)
    metadata_matched = int(oath_metadata.get("matched_ticket_count") or 0)
    if metadata_requested != requested_count:
        raise ValueError(
            f"OATH metadata requested count mismatch: {metadata_requested:,} != {requested_count:,}"
        )
    if metadata_matched != matched_count:
        raise ValueError(
            f"OATH metadata matched count mismatch: {metadata_matched:,} != {matched_count:,}"
        )

    return {
        "schema_version": OATH_CACHE_SCHEMA_VERSION,
        "generated_at": generated_at or _utc_now(),
        "inspection_source": {
            "dataset_id": getattr(inspection_snapshot, "dataset_id", INSPECTION_DATASET_ID),
            "name": getattr(inspection_snapshot, "name", None),
            "retrieved_at": getattr(inspection_snapshot, "retrieved_at", None),
            "source_record_count": getattr(inspection_snapshot, "source_record_count", None),
            "source_last_updated_at": getattr(inspection_snapshot, "source_last_updated_at", None),
        },
        "ticket_universe": ticket_universe_fingerprint(requested),
        "oath_source": dict(oath_metadata),
        "summary": {
            "requested_ticket_count": requested_count,
            "matched_ticket_count": matched_count,
            "unmatched_ticket_count": requested_count - matched_count,
            "match_ratio": ratio,
        },
        "cases": [normalized_cases[ticket] for ticket in sorted(normalized_cases)],
    }


def write_cache(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8", compresslevel=9) as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        return
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def read_cache(path: Path) -> dict[str, Any]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("OATH cache root is not an object")
    return payload


def validate_cache(
    path: Path,
    *,
    max_age_days: float = DEFAULT_MAX_AGE_DAYS,
    require_production_volume: bool = False,
    current_tickets: Iterable[Any] | None = None,
) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"Verified OATH cache is missing: {path}")
    size = path.stat().st_size
    if size <= 0:
        raise ValueError("OATH cache is empty")
    if size > MAX_COMPRESSED_CACHE_BYTES:
        raise ValueError(f"OATH cache exceeds hard size ceiling: {size} > {MAX_COMPRESSED_CACHE_BYTES}")

    payload = read_cache(path)
    if payload.get("schema_version") != OATH_CACHE_SCHEMA_VERSION:
        raise ValueError("Unsupported OATH cache schema_version")

    generated = _parse_timestamp(payload.get("generated_at"))
    age_days = (datetime.now(timezone.utc) - generated).total_seconds() / 86400
    if age_days < -0.25:
        raise ValueError(f"OATH cache timestamp is implausibly in the future: {age_days:.2f} days")
    if age_days > max_age_days:
        raise ValueError(f"OATH cache is stale: {age_days:.2f} days > {max_age_days}")

    inspection_source = payload.get("inspection_source")
    ticket_universe = payload.get("ticket_universe")
    oath_source = payload.get("oath_source")
    summary = payload.get("summary")
    cases = payload.get("cases")
    for name, value in (
        ("inspection_source", inspection_source),
        ("ticket_universe", ticket_universe),
        ("oath_source", oath_source),
        ("summary", summary),
    ):
        if not isinstance(value, Mapping):
            raise ValueError(f"OATH cache {name} is missing")
    if not isinstance(cases, list):
        raise ValueError("OATH cache cases is not a list")

    if inspection_source.get("dataset_id") != INSPECTION_DATASET_ID:
        raise ValueError("OATH cache inspection dataset identity is invalid")
    if oath_source.get("dataset_id") != OATH_DATASET_ID:
        raise ValueError("OATH cache source dataset identity is invalid")

    try:
        universe_count = int(ticket_universe.get("count"))
    except (TypeError, ValueError) as exc:
        raise ValueError("OATH cache ticket universe count is invalid") from exc
    universe_sha = str(ticket_universe.get("sha256") or "")
    if len(universe_sha) != 64 or any(char not in "0123456789abcdef" for char in universe_sha.lower()):
        raise ValueError("OATH cache ticket universe fingerprint is invalid")

    cases_by_ticket: dict[str, dict[str, Any]] = {}
    for index, raw_case in enumerate(cases):
        if not isinstance(raw_case, Mapping):
            raise ValueError(f"OATH cache case {index} is not an object")
        case = dict(raw_case)
        ticket = normalize_ticket_number(case.get("ticket_number"))
        if not ticket:
            raise ValueError(f"OATH cache case {index} is missing ticket_number")
        if ticket in cases_by_ticket:
            raise ValueError(f"Duplicate OATH cache ticket_number: {ticket}")
        if case.get("match_basis") != MATCH_BASIS:
            raise ValueError(f"OATH cache ticket {ticket} has non-exact match basis")
        cases_by_ticket[ticket] = case

    matched_count = len(cases_by_ticket)
    try:
        summary_requested = int(summary.get("requested_ticket_count"))
        summary_matched = int(summary.get("matched_ticket_count"))
        summary_unmatched = int(summary.get("unmatched_ticket_count"))
    except (TypeError, ValueError) as exc:
        raise ValueError("OATH cache summary counts are invalid") from exc
    if summary_requested != universe_count:
        raise ValueError("OATH cache requested count does not match ticket universe")
    if summary_matched != matched_count:
        raise ValueError("OATH cache matched count does not match cases")
    if summary_unmatched != universe_count - matched_count:
        raise ValueError("OATH cache unmatched count does not reconcile")

    source_requested = int(oath_source.get("requested_ticket_count") or -1)
    source_matched = int(oath_source.get("matched_ticket_count") or -1)
    if source_requested != universe_count or source_matched != matched_count:
        raise ValueError("OATH cache source metadata does not reconcile with cached cases")

    ratio = matched_count / universe_count if universe_count else 1.0
    if universe_count >= 100 and ratio < MIN_EXPECTED_MATCH_RATIO:
        raise ValueError(
            f"OATH cache match coverage collapsed to {matched_count:,}/{universe_count:,} ({ratio:.1%})"
        )

    current_fingerprint = None
    if current_tickets is not None:
        current_fingerprint = ticket_universe_fingerprint(current_tickets)
        if current_fingerprint != {"count": universe_count, "sha256": universe_sha}:
            raise ValueError(
                "OATH cache ticket universe is not aligned to the current NYC inspection summons universe: "
                f"cache={universe_count}:{universe_sha} current={current_fingerprint['count']}:{current_fingerprint['sha256']}"
            )

    if require_production_volume:
        inspection_rows = int(inspection_source.get("source_record_count") or 0)
        if inspection_rows < MIN_PRODUCTION_INSPECTION_ROWS:
            raise ValueError("OATH cache inspection source volume is below production threshold")
        if universe_count < MIN_PRODUCTION_REQUESTED_TICKETS:
            raise ValueError("OATH cache requested summons volume is below production threshold")
        if matched_count < int(MIN_PRODUCTION_REQUESTED_TICKETS * MIN_EXPECTED_MATCH_RATIO):
            raise ValueError("OATH cache matched summons volume is below production threshold")

    return {
        "status": "PASS",
        "cache": payload,
        "cases_by_ticket": cases_by_ticket,
        "size_bytes": size,
        "age_days": age_days,
        "match_ratio": ratio,
        "ticket_universe": {"count": universe_count, "sha256": universe_sha},
        "current_ticket_universe": current_fingerprint,
    }


def cases_and_metadata_from_verified_cache(
    path: Path,
    current_tickets: Iterable[Any],
    *,
    max_age_days: float = DEFAULT_MAX_AGE_DAYS,
    require_production_volume: bool = True,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any], dict[str, Any]]:
    result = validate_cache(
        path,
        max_age_days=max_age_days,
        require_production_volume=require_production_volume,
        current_tickets=current_tickets,
    )
    cache = result["cache"]
    metadata = dict(cache["oath_source"])
    scope = str(metadata.get("source_query_scope") or "OATH exact summons lifecycle")
    metadata["source_query_scope"] = scope + "; verified durable cache aligned to current inspection summons universe"
    metadata["cache_generated_at"] = cache.get("generated_at")
    metadata["cache_age_days"] = round(float(result["age_days"]), 4)
    metadata["cache_ticket_universe_sha256"] = result["ticket_universe"]["sha256"]
    return result["cases_by_ticket"], metadata, result
