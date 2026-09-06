from __future__ import annotations

import argparse
import json
from pathlib import Path

ALLOWED_DETAIL_STATUSES = {
    "LAB_ID_LINK_PROVEN",
    "CAPTCHA_OR_INTERACTIVE_GATE",
    "NO_LAB_ID_LINK_RETURNED",
}


def validate(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    search_url = str(payload.get("search_url") or "")
    if not search_url.startswith("https://apps.health.ny.gov/pubdoh/applinks/wc/elappublicweb/"):
        raise RuntimeError("Unexpected ELAP public search URL")

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
    payload = validate(parser.parse_args().probe)
    print(json.dumps({
        "populated_lab_options": payload["lab_selector"]["populated_option_count"],
        "exact_name_value_options": payload["lab_selector"]["exact_name_value_option_count"],
        "detail_resolution_status": payload["detail_resolution_probe"]["detail_resolution_status"],
        "scope_claims_created": 0,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
