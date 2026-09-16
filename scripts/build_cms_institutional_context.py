from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from towersignal.cms_institutional import GEOSEARCH_URL, build_cms_institutional_context, normalize_bbl

ROOT = Path(__file__).resolve().parents[1]
TRANSIENT_GEOSEARCH_MARKERS = (
    "HTTP Error 429",
    "HTTP Error 500",
    "HTTP Error 502",
    "HTTP Error 503",
    "HTTP Error 504",
    "RemoteDisconnected",
    "Connection reset",
    "timed out",
    "Temporary failure",
    "Service Unavailable",
)


def load_tower_bbls(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    systems = payload.get("systems")
    if not isinstance(systems, list):
        raise RuntimeError("TowerSignal systems payload is malformed")
    return sorted({bbl for row in systems if isinstance(row, dict) and (bbl := normalize_bbl(row.get("bbl")))})


def _is_transient_geosearch_failure(exc: RuntimeError) -> bool:
    message = str(exc)
    return GEOSEARCH_URL in message and any(marker in message for marker in TRANSIENT_GEOSEARCH_MARKERS)


def build_with_geosearch_recovery(bbls: list[str], *, geosearch_workers: int) -> dict:
    try:
        return build_cms_institutional_context(bbls, geosearch_workers=geosearch_workers)
    except RuntimeError as exc:
        if geosearch_workers <= 1 or not _is_transient_geosearch_failure(exc):
            raise
        print(
            "[cms] NYC GeoSearch exhausted concurrent retries; pausing 10 seconds and retrying the complete exact-address reconciliation serially",
            flush=True,
        )
        time.sleep(10)
        return build_cms_institutional_context(bbls, geosearch_workers=1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build exact-BBL CMS institutional context for current TowerSignal accounts")
    parser.add_argument("--systems", type=Path, default=ROOT / "public/data/systems.json")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data/cms-institutional-context.json")
    parser.add_argument("--geosearch-workers", type=int, default=4)
    args = parser.parse_args()
    bbls = load_tower_bbls(args.systems)
    if len(bbls) < 3000:
        raise RuntimeError(f"Refusing CMS build for implausibly small TowerSignal BBL universe: {len(bbls):,}")
    payload = build_with_geosearch_recovery(bbls, geosearch_workers=args.geosearch_workers)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
