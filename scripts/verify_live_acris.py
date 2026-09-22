from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import defaultdict
from http.client import IncompleteRead
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal.acris import (  # noqa: E402
    ALIAS_BBL_MATCH_BASIS,
    CONDO_ROLLUP_MATCH_BASIS,
    EXACT_BBL_MATCH_BASIS,
    LEGALS_DATASET_ID,
    MASTER_DATASET_ID,
    PARTIES_DATASET_ID,
    bbl_from_legal,
    load_cache,
    normalize_address_number,
    normalize_street_name,
)

API_ROOT = "https://data.cityofnewyork.us"
USER_AGENT = "TowerSignal-ACRIS-Verifier/1.0"


def request_rows(dataset_id: str, where: str, select: str, attempts: int = 4) -> list[dict[str, Any]]:
    params = {"$limit": 50000, "$where": where, "$select": select}
    url = f"{API_ROOT}/resource/{dataset_id}.json?{urlencode(params)}"
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urlopen(request, timeout=90) as response:
                payload = json.load(response)
            if not isinstance(payload, list):
                raise RuntimeError(f"Verifier received non-list payload from {dataset_id}")
            return payload
        except HTTPError as exc:
            last_error = exc
            if exc.code not in {429, 500, 502, 503, 504}:
                raise
        except (URLError, TimeoutError, IncompleteRead, json.JSONDecodeError, ConnectionError) as exc:
            last_error = exc
        if attempt + 1 < attempts:
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Verifier failed {dataset_id} after {attempts} attempts: {last_error}")


def quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def normalize_date(value: Any) -> str | None:
    text = str(value or "").strip()
    return text[:10] if len(text) >= 10 else None


def verify(cache_path: Path, sample_size: int) -> None:
    cache = load_cache(cache_path)
    candidates: list[tuple[str, str, dict[str, Any]]] = []
    for bbl, context in cache["properties"].items():
        for document in context.get("documents") or []:
            document_id = str(document.get("document_id") or "")
            digest = hashlib.sha256(f"{bbl}:{document_id}".encode("utf-8")).hexdigest()
            candidates.append((digest, bbl, document))
    selected = sorted(candidates, key=lambda item: item[0])[:sample_size]
    if len(selected) < sample_size:
        raise RuntimeError(f"ACRIS verifier could only select {len(selected)} documents")

    document_ids = [str(cached["document_id"]) for _, _, cached in selected]
    where = "document_id in (" + ",".join(quote(document_id) for document_id in document_ids) + ")"

    master_rows = request_rows(
        MASTER_DATASET_ID,
        where,
        "document_id,doc_type,recorded_datetime,document_amt,percent_trans",
    )
    legal_rows = request_rows(
        LEGALS_DATASET_ID,
        where,
        "document_id,borough,block,lot,street_number,street_name",
    )
    party_rows = request_rows(
        PARTIES_DATASET_ID,
        where,
        "document_id,party_type,name",
    )

    master_by_document: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in master_rows:
        master_by_document[str(row.get("document_id") or "")].append(row)

    legal_bbls_by_document: dict[str, set[str]] = defaultdict(set)
    legal_rows_by_document: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in legal_rows:
        document_id = str(row.get("document_id") or "")
        legal_rows_by_document[document_id].append(row)
        if bbl := bbl_from_legal(row):
            legal_bbls_by_document[document_id].add(bbl)

    party_pairs_by_document: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in party_rows:
        document_id = str(row.get("document_id") or "")
        party_pairs_by_document[document_id].add(
            (str(row.get("party_type") or ""), str(row.get("name") or "").strip())
        )

    verified = []
    for _, bbl, cached in selected:
        document_id = str(cached["document_id"])
        document_master_rows = master_by_document.get(document_id, [])
        if not document_master_rows:
            raise RuntimeError(f"ACRIS Master no longer returns cached document {document_id}")
        cached_type = str(cached.get("doc_type") or "")
        cached_recorded = cached.get("recorded_date")
        if not any(
            str(row.get("doc_type") or "") == cached_type
            and normalize_date(row.get("recorded_datetime")) == cached_recorded
            for row in document_master_rows
        ):
            raise RuntimeError(f"ACRIS Master values no longer reproduce cached document {document_id}")

        match_basis = str(cached.get("match_basis") or EXACT_BBL_MATCH_BASIS)
        live_legals = legal_rows_by_document.get(document_id, [])
        live_bbls = legal_bbls_by_document.get(document_id, set())
        cached_legals = [row for row in (cached.get("legal_context") or []) if isinstance(row, dict)]

        if match_basis == EXACT_BBL_MATCH_BASIS:
            if bbl not in live_bbls:
                raise RuntimeError(f"ACRIS Legals no longer reproduces exact BBL {bbl} for document {document_id}")
        elif match_basis == ALIAS_BBL_MATCH_BASIS:
            source_bbls = {
                str(row.get("source_bbl") or "")
                for row in cached_legals
                if row.get("source_bbl") and str(row.get("source_bbl")) != bbl
            }
            if not source_bbls or not (source_bbls & live_bbls):
                raise RuntimeError(
                    f"ACRIS Legals no longer reproduces exact preserved BBL alias for {bbl} document {document_id}"
                )
        elif match_basis == CONDO_ROLLUP_MATCH_BASIS:
            reproduced = False
            for cached_legal in cached_legals:
                source_bbl = str(cached_legal.get("source_bbl") or "")
                cached_number = normalize_address_number(cached_legal.get("street_number"))
                cached_street = normalize_street_name(cached_legal.get("street_name"))
                if not source_bbl or source_bbl == bbl or not cached_number or not cached_street:
                    continue
                for live_legal in live_legals:
                    if bbl_from_legal(live_legal) != source_bbl:
                        continue
                    if normalize_address_number(live_legal.get("street_number")) != cached_number:
                        continue
                    if normalize_street_name(live_legal.get("street_name")) != cached_street:
                        continue
                    reproduced = True
                    break
                if reproduced:
                    break
            if not reproduced:
                raise RuntimeError(
                    f"ACRIS Legals no longer reproduces condo source-BBL + exact-address evidence for {bbl} document {document_id}"
                )
        else:
            raise RuntimeError(f"ACRIS verifier encountered unsupported match basis {match_basis!r}")

        cached_parties = cached.get("parties") or []
        cached_party_pairs = {
            (str(row.get("party_type") or ""), str(row.get("name") or "").strip())
            for row in cached_parties
        }
        live_party_pairs = party_pairs_by_document.get(document_id, set())
        if cached_party_pairs and not live_party_pairs:
            raise RuntimeError(f"ACRIS Parties no longer returns cached party evidence for document {document_id}")
        if cached_party_pairs and not (cached_party_pairs & live_party_pairs):
            raise RuntimeError(f"ACRIS Parties no longer reproduces cached party evidence for document {document_id}")
        verified.append({"bbl": bbl, "document_id": document_id, "doc_type": cached_type, "recorded_date": cached_recorded, "match_basis": match_basis})

    print(json.dumps({"status": "PASS", "sample_size": len(verified), "verified": verified}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Independently verify sampled ACRIS cache records against live sources")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=5)
    args = parser.parse_args()
    verify(args.cache, args.sample_size)


if __name__ == "__main__":
    main()
