from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from towersignal import nys_public_water  # noqa: E402

_ORIGINAL_PARSE_VIOLATION_PAGE = nys_public_water.parse_violation_page


def parse_violation_page_allow_explicit_empty(html: str, *, source_url: str) -> list[dict]:
    try:
        return _ORIGINAL_PARSE_VIOLATION_PAGE(html, source_url=source_url)
    except nys_public_water.NysPublicWaterSourceError:
        parser = nys_public_water.parse_html(html)
        heading_text = nys_public_water.normalize_space(" ".join(parser.headings)).lower()
        if "there are no violations entered in sdwis/state for 2025" in heading_text:
            return []
        raise


def build(output: Path) -> dict:
    # County pages with an explicit NYSDOH "no violations" heading legitimately
    # omit the violation table. Tolerate only that exact source state; every other
    # missing/changed table remains fail-closed in the source parser.
    nys_public_water.parse_violation_page = parse_violation_page_allow_explicit_empty
    payload = nys_public_water.build_payload()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build TowerSignal NYS public-water-system cache")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build(args.output)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
