from __future__ import annotations

import argparse
import json
from pathlib import Path

ALLOWED_DETAIL_STATUSES = {
    "LAB_ID_LINK_PROVEN",
    "CAPTCHA_OR_INTERACTIVE_GATE",
    "NO_LAB_ID_LINK_RETURNED",
}


def validate(path: Path, *, allow_source_unavailable: bool = False) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    search_url = str(payload.get("search_url") or "")
    if not search_url.startswith("https://apps.health.ny.gov/pubdoh/applinks/wc/elappublicweb/"):
        raise RuntimeError("Unexpected ELAP public search URL")

    probe_status = str(payload.get("probe_status") or "SOURCE_CONTRACT_PROVEN")
    if probe_status == "SOURCE_UNAVAILABLE":
        if not allow_source_unavailable:
            raise RuntimeError("ELAP source is unavailable")
        if not str(payload.get("source_error") or ""):
            raise RuntimeError("ELAP unavailable probe is missing source_error")
        return payload
    if probe_status != "SOURCE_CONTRACT_PROVEN":
        raise RuntimeError(f"Unexpected ELAP probe status: {probe_status}")

    lab_selector = payload.get("lab_selector")
    detail_probe = payload.get("detail_resolution_probe")
    if not isinstance(lab_selector, dict) or not isinstance(detail_probe, dict):
        raise RuntimeError("ELAP probe is missing lab_selector/detail_resolution_probe")
    populated = int(lab_selector.get("populated_option_count") or 0)
    exact_name = int(lab_selector.get("exact_name_value_option_count") or 0)
    if populated < 250 or exact_name < 250:
        raise RuntimeError(f"Implausibly small ELAP lab selector proof: populated={populated}, exact_name={exact_name}")
    if exact_name < populated - 10:
        raise RuntimeError("ELAP lab selector is not predominantly exact name-valued")
    if detail_probe.get("detail_resolution_status") not in ALLOWED_DETAIL_STATUSES:
        raise RuntimeError("Unexpected ELAP detail-resolution probe status")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate TowerSignal ELAP public source-contract probe")
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--allow-source-unavailable", action="store_true")
    args = parser.parse_args()
    payload = validate(args.probe, allow_source_unavailable=args.allow_source_unavailable)
    if payload.get("probe_status") == "SOURCE_UNAVAILABLE":
        summary = {
            "detail_resolution_status": "SOURCE_UNAVAILABLE",
            "scope_claims_created": 0,
            "source_available": False,
            "source_error": payload.get("source_error"),
        }
    else:
        summary = {
            "populated_lab_options": payload["lab_selector"]["populated_option_count"],
            "exact_name_value_options": payload["lab_selector"]["exact_name_value_option_count"],
            "detail_resolution_status": payload["detail_resolution_probe"]["detail_resolution_status"],
            "scope_claims_created": 0,
            "source_available": True,
        }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
