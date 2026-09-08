from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.oath import normalize_ticket_number  # noqa: E402
from towersignal.oath_cache import build_cache_payload, validate_cache, write_cache  # noqa: E402

DEFAULT_BASE_URL = "https://jeremyhennessy.github.io/TowerSignal/data"


def _read_json_url(url: str, *, retries: int = 4, timeout: int = 30) -> Any:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "TowerSignal-OATH-cache-bootstrap/1.0"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(2 * attempt)
    raise RuntimeError(f"Failed to read verified hosted payload after {retries} attempts: {url}: {last_error}")


def _source(metadata: dict[str, Any], dataset_id: str) -> dict[str, Any]:
    for item in metadata.get("sources") or []:
        if item.get("dataset_id") == dataset_id:
            return item
    raise RuntimeError(f"Hosted metadata is missing required source {dataset_id}")


def _health_source(source_health: dict[str, Any], source_key: str) -> dict[str, Any]:
    for item in source_health.get("sources") or []:
        if item.get("source_key") == source_key:
            return item
    raise RuntimeError(f"Verified history source-health is missing {source_key}")


def _detail_url(base_url: str, system_id: str) -> str:
    safe = "".join(ch for ch in str(system_id) if ch.isalnum() or ch in ("-", "_"))
    prefix = (safe[:2] or "xx").lower()
    return f"{base_url.rstrip('/')}/details/{prefix}/{safe}.json"


def _verified_checkpoint(hosted_metadata: dict[str, Any], hosted_systems: dict[str, Any], source_health: dict[str, Any]) -> None:
    generated_at = hosted_metadata.get("generated_at")
    history_generated_at = source_health.get("generated_at")
    if not generated_at or not history_generated_at:
        raise RuntimeError("Hosted metadata or durable source-health is missing generated_at")
    generated = datetime.fromisoformat(str(generated_at).replace("Z", "+00:00")).astimezone(timezone.utc)
    history_generated = datetime.fromisoformat(str(history_generated_at).replace("Z", "+00:00")).astimezone(timezone.utc)
    lag_seconds = (history_generated - generated).total_seconds()
    if lag_seconds < 0 or lag_seconds > 1800:
        raise RuntimeError(
            "Hosted release is not tied closely enough to the persisted verified-history checkpoint: "
            f"hosted={generated_at} history={history_generated_at} lag={lag_seconds:.0f}s"
        )

    if hosted_systems.get("metadata", {}).get("generated_at") != generated_at:
        raise RuntimeError("Hosted systems.json and metadata.json are from different generations")

    system_count = len(hosted_systems.get("systems") or [])
    registration_health = _health_source(source_health, "registrations")
    inspection_health = _health_source(source_health, "inspections")
    oath_health = _health_source(source_health, "oath")
    if any(item.get("status") != "HEALTHY" for item in (registration_health, inspection_health, oath_health)):
        raise RuntimeError("Verified history checkpoint does not mark registrations, inspections and OATH HEALTHY")
    if system_count != int(registration_health.get("normalized_entity_count") or 0):
        raise RuntimeError("Hosted system count does not match verified-history registration count")

    inspection_source = _source(hosted_metadata, "f9wb-g8mb")
    oath_source = _source(hosted_metadata, "jz4z-kudi")
    checks = [
        (int(inspection_source.get("source_record_count") or 0), int(inspection_health.get("retrieved_record_count") or 0), "inspection rows"),
        (int(oath_source.get("source_record_count") or 0), int(oath_health.get("retrieved_record_count") or 0), "OATH rows"),
        (int(hosted_metadata.get("oath_requested_ticket_count") or 0), int(oath_health.get("requested_entity_count") or 0), "OATH requested tickets"),
        (int(hosted_metadata.get("oath_matched_ticket_count") or 0), int(oath_health.get("matched_entity_count") or 0), "OATH matched tickets"),
    ]
    for hosted_value, history_value, label in checks:
        if hosted_value != history_value:
            raise RuntimeError(f"Hosted {label} do not match verified history: {hosted_value} != {history_value}")


def _collect_detail(detail: dict[str, Any], expected_generated_at: str) -> tuple[str, list[str], list[dict[str, Any]]]:
    metadata = detail.get("metadata") or {}
    if metadata.get("generated_at") != expected_generated_at:
        raise RuntimeError("Hosted detail belongs to a different generation")
    system_id = str((detail.get("identity") or {}).get("system_id") or "")
    if not system_id:
        raise RuntimeError("Hosted detail is missing system_id")
    requested: list[str] = []
    for inspection in detail.get("inspection_history") or []:
        for violation in inspection.get("violations") or []:
            ticket = normalize_ticket_number(violation.get("summons_number"))
            if ticket:
                requested.append(ticket)
    cases = [dict(item) for item in (detail.get("oath_case_history") or []) if item.get("ticket_number")]
    return system_id, requested, cases


def build(base_url: str, source_health_path: Path, output: Path, *, workers: int = 16) -> dict[str, Any]:
    source_health = json.loads(source_health_path.read_text(encoding="utf-8"))
    hosted_metadata = _read_json_url(f"{base_url.rstrip('/')}/metadata.json")
    hosted_systems = _read_json_url(f"{base_url.rstrip('/')}/systems.json")
    _verified_checkpoint(hosted_metadata, hosted_systems, source_health)

    expected_generated_at = str(hosted_metadata["generated_at"])
    system_ids = [str(item.get("system_id") or "") for item in hosted_systems.get("systems") or []]
    if not system_ids or any(not value for value in system_ids):
        raise RuntimeError("Hosted systems.json contains missing system IDs")

    requested_tickets: set[str] = set()
    cases_by_ticket: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {
            executor.submit(_read_json_url, _detail_url(base_url, system_id), retries=4, timeout=30): system_id
            for system_id in system_ids
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            expected_system_id = futures[future]
            system_id, detail_tickets, detail_cases = _collect_detail(future.result(), expected_generated_at)
            if system_id != expected_system_id:
                raise RuntimeError(f"Hosted detail identity mismatch: {expected_system_id} != {system_id}")
            requested_tickets.update(detail_tickets)
            for case in detail_cases:
                ticket = normalize_ticket_number(case.get("ticket_number"))
                if not ticket:
                    continue
                existing = cases_by_ticket.get(ticket)
                if existing is not None and existing != case:
                    raise RuntimeError(f"Conflicting hosted OATH case payload for exact ticket {ticket}")
                cases_by_ticket[ticket] = case
            if completed % 500 == 0 or completed == len(system_ids):
                print(
                    f"[oath-bootstrap] downloaded {completed:,}/{len(system_ids):,} verified hosted details; "
                    f"tickets={len(requested_tickets):,} cases={len(cases_by_ticket):,}",
                    flush=True,
                )

    inspection_source = _source(hosted_metadata, "f9wb-g8mb")
    oath_source = _source(hosted_metadata, "jz4z-kudi")
    inspection_snapshot = SimpleNamespace(
        dataset_id="f9wb-g8mb",
        name=inspection_source.get("name"),
        retrieved_at=inspection_source.get("retrieved_at"),
        source_record_count=inspection_source.get("source_record_count"),
        source_last_updated_at=inspection_source.get("source_last_updated_at"),
    )
    scoped_requested_count = len(requested_tickets)
    scoped_matched_count = len(cases_by_ticket)
    oath_metadata = {
        **oath_source,
        "source_query_scope": (
            str(oath_source.get("source_query_scope") or "OATH exact summons lifecycle")
            + "; bootstrap restricted to summons attached to the verified current TowerSignal registry systems"
        ),
        "requested_ticket_count": scoped_requested_count,
        "matched_ticket_count": scoped_matched_count,
        "unmatched_ticket_count": scoped_requested_count - scoped_matched_count,
        "matched_case_count": scoped_matched_count,
    }
    payload = build_cache_payload(
        inspection_snapshot=inspection_snapshot,
        requested_tickets=requested_tickets,
        cases_by_ticket=cases_by_ticket,
        oath_metadata=oath_metadata,
        generated_at=expected_generated_at,
    )
    write_cache(output, payload)
    result = validate_cache(output, max_age_days=2.0, require_production_volume=True, current_tickets=requested_tickets)
    print(json.dumps({
        "status": result["status"],
        "generated_at": payload["generated_at"],
        "system_count": len(system_ids),
        "requested_ticket_count": payload["summary"]["requested_ticket_count"],
        "matched_ticket_count": payload["summary"]["matched_ticket_count"],
        "match_ratio": payload["summary"]["match_ratio"],
        "cache_size_bytes": result["size_bytes"],
    }, indent=2))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap a full-fidelity OATH cache from the already-hosted verified TowerSignal release")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--source-health", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    build(args.base_url, args.source_health, args.output, workers=args.workers)


if __name__ == "__main__":
    main()
