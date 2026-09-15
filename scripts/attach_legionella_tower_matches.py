from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
TOPIC_URL = "https://www.nyc.gov/site/doh/health/health-topics/legionnaires-disease.page"
USER_AGENT = "Mozilla/5.0 TowerSignal/1.0"
ZIP_RE = re.compile(r"\b(10\d{3})\b")
STREET_RE = re.compile(r"^\s*(\d+[A-Z]?)\s+(.+?)\s*$", re.I)
SUFFIX = {
    "STREET": "ST", "ST": "ST", "ST.": "ST", "AVENUE": "AVE", "AVE": "AVE", "AVE.": "AVE",
    "ROAD": "RD", "RD": "RD", "BOULEVARD": "BLVD", "BLVD": "BLVD", "PLACE": "PL", "PL": "PL",
    "DRIVE": "DR", "DR": "DR", "LANE": "LN", "LN": "LN", "PARKWAY": "PKWY", "PKWY": "PKWY",
    "WEST": "W", "EAST": "E", "NORTH": "N", "SOUTH": "S",
}


class TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if value:
            self.parts.append(value)


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8"})
    with urlopen(request, timeout=60) as response:
        content_type = str(response.headers.get("Content-Type") or "")
        if "html" not in content_type.lower():
            return ""
        parser = TextParser()
        parser.feed(response.read().decode("utf-8", errors="replace"))
        return "\n".join(parser.parts)


def normalize_address(value: str | None) -> str:
    text = re.sub(r"[^A-Z0-9 ]+", " ", (value or "").upper())
    tokens = [SUFFIX.get(token, token) for token in text.split()]
    return " ".join(tokens)


def extract_current_cluster(topic_text: str) -> dict[str, Any]:
    start = topic_text.find("Legionnaires' Disease Cluster in the South Bronx")
    if start < 0:
        start = topic_text.find("Legionnaires’ Disease Cluster in the South Bronx")
    end = topic_text.find("About Legionnaires' Disease", start + 1)
    if end < 0:
        end = topic_text.find("About Legionnaires’ Disease", start + 1)
    if start < 0 or end < 0:
        raise RuntimeError("Unable to isolate current South Bronx cluster section from NYC Health topic page")
    section = topic_text[start:end]
    zips = sorted(set(ZIP_RE.findall(section)))
    marker = "The following buildings have cooling towers that tested positive in a PCR test."
    marker_at = section.find(marker)
    if marker_at < 0:
        raise RuntimeError("NYC Health topic page no longer exposes the PCR-positive building list")
    tail = section[marker_at + len(marker):]
    stop = tail.find("In addition to the PCR screening tests")
    if stop >= 0:
        tail = tail[:stop]
    addresses: list[str] = []
    for line in tail.splitlines():
        line = line.strip()
        if STREET_RE.match(line) and len(line) <= 80:
            addresses.append(line)
    if not zips or not addresses:
        raise RuntimeError(f"Current cluster parse incomplete: zips={zips}, addresses={addresses}")
    return {
        "cluster_id": "NYC_DOH_2026_SOUTH_BRONX_MELROSE_MORRISANIA",
        "status": "ACTIVE_INVESTIGATION",
        "affected_zip_codes": zips,
        "pcr_positive_building_addresses": addresses,
        "source_url": TOPIC_URL,
        "match_semantics": {
            "EXPLICIT_PCR_POSITIVE_ADDRESS": "NYC Health explicitly lists the building address as having a cooling tower with a positive preliminary PCR result. PCR does not establish live bacteria or outbreak source attribution.",
            "AFFECTED_ZIP_CODE": "Tower is registered in a ZIP code NYC Health identifies as part of the community-cluster investigation area. This is geographic context only and is not evidence the tower tested positive or caused illness.",
        },
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected object: {path}")
    return value


def safe_detail_path(base: Path, system_id: str) -> Path:
    safe = "".join(ch for ch in system_id if ch.isalnum() or ch in ("-", "_"))
    return base / "details" / (safe[:2] or "xx").lower() / f"{safe}.json"


def attach(output_dir: Path, alerts_path: Path) -> dict[str, Any]:
    systems_path = output_dir / "systems.json"
    systems_payload = load(systems_path)
    alerts = load(alerts_path)
    if alerts.get("domain") != "LEGIONELLA_PUBLIC_HEALTH_ALERTS":
        raise RuntimeError("Unexpected Legionella alert domain")

    topic_text = fetch_text(TOPIC_URL)
    cluster = extract_current_cluster(topic_text)
    systems = systems_payload.get("systems") or []
    by_address: dict[str, list[dict[str, Any]]] = {}
    by_zip: dict[str, list[dict[str, Any]]] = {}
    for row in systems:
        by_address.setdefault(normalize_address(row.get("address")), []).append(row)
        if row.get("zip"):
            by_zip.setdefault(str(row["zip"]), []).append(row)

    explicit_ids: set[str] = set()
    unmatched_addresses: list[str] = []
    explicit_matches: list[dict[str, Any]] = []
    for address in cluster["pcr_positive_building_addresses"]:
        matches = by_address.get(normalize_address(address), [])
        if not matches:
            unmatched_addresses.append(address)
        for row in matches:
            explicit_ids.add(str(row["system_id"]))
            explicit_matches.append({"system_id": row["system_id"], "address": row.get("address"), "zip": row.get("zip"), "match_basis": "EXPLICIT_PCR_POSITIVE_ADDRESS"})

    area_ids = {str(row["system_id"]) for zip_code in cluster["affected_zip_codes"] for row in by_zip.get(zip_code, [])}
    cluster["tower_matches"] = {
        "explicit_pcr_positive": explicit_matches,
        "affected_area": [
            {"system_id": row["system_id"], "address": row.get("address"), "zip": row.get("zip"), "match_basis": "AFFECTED_ZIP_CODE"}
            for row in systems if str(row["system_id"]) in area_ids and str(row["system_id"]) not in explicit_ids
        ],
        "unmatched_published_addresses": unmatched_addresses,
    }

    for item in alerts.get("items") or []:
        item_text = ""
        try:
            item_text = fetch_text(str(item.get("url") or ""))
        except Exception:
            item_text = ""
        item_zips = sorted(set(ZIP_RE.findall(item_text)))
        title = str(item.get("title") or "").lower()
        current_cluster_item = bool(set(item_zips) & set(cluster["affected_zip_codes"])) or "south bronx" in title or "melrose" in title or "morrisania" in title or "bronx" in title
        if current_cluster_item:
            item["cluster_ids"] = sorted(set((item.get("cluster_ids") or []) + [cluster["cluster_id"]]))
            item["tower_match_summary"] = {
                "explicit_pcr_positive_system_count": len(explicit_ids),
                "affected_area_system_count": len(area_ids),
                "match_basis": ["EXPLICIT_PCR_POSITIVE_ADDRESS", "AFFECTED_ZIP_CODE"],
            }
            item["matched_system_ids"] = sorted(area_ids)

    for row in systems:
        sid = str(row["system_id"])
        row["legionella_cluster_match"] = sid in area_ids
        row["legionella_pcr_positive_match"] = sid in explicit_ids
        row["legionella_cluster_ids"] = [cluster["cluster_id"]] if sid in area_ids else []
        if sid not in area_ids:
            continue
        detail_path = safe_detail_path(output_dir, sid)
        detail = load(detail_path)
        detail["legionella_public_health_context"] = {
            "cluster_id": cluster["cluster_id"],
            "cluster_status": cluster["status"],
            "match_basis": "EXPLICIT_PCR_POSITIVE_ADDRESS" if sid in explicit_ids else "AFFECTED_ZIP_CODE",
            "source_url": cluster["source_url"],
            "evidence_boundary": cluster["match_semantics"]["EXPLICIT_PCR_POSITIVE_ADDRESS" if sid in explicit_ids else "AFFECTED_ZIP_CODE"],
        }
        detail_path.write_text(json.dumps(detail, separators=(",", ":")), encoding="utf-8")

    summary = systems_payload.get("summary") or {}
    summary["systems_in_active_legionella_cluster_area"] = len(area_ids)
    summary["systems_explicitly_pcr_positive_by_nyc_health_address"] = len(explicit_ids)
    systems_payload["summary"] = summary
    metadata = systems_payload.get("metadata") or {}
    metadata["legionella_tower_matching_available"] = True
    metadata["legionella_tower_match_source"] = TOPIC_URL
    metadata["legionella_tower_match_semantics"] = "Published address exact-normalized match for PCR-positive buildings; ZIP exact match for investigation-area context. No causal attribution."
    systems_payload["metadata"] = metadata
    systems_path.write_text(json.dumps(systems_payload, separators=(",", ":")), encoding="utf-8")
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    alerts["clusters"] = [cluster]
    alerts["tower_matching"] = {
        "generated_from": TOPIC_URL,
        "explicit_pcr_positive_system_count": len(explicit_ids),
        "affected_area_system_count": len(area_ids),
        "published_positive_address_count": len(cluster["pcr_positive_building_addresses"]),
        "unmatched_published_address_count": len(unmatched_addresses),
        "causation_boundary": "A tower/building match does not establish that the tower caused any Legionnaires disease case. PCR-positive means Legionella DNA was detected and may represent living or dead bacteria.",
    }
    alerts_path.write_text(json.dumps(alerts, separators=(",", ":")), encoding="utf-8")
    result = alerts["tower_matching"] | {"unmatched_addresses": unmatched_addresses}
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Match official Legionnaires cluster evidence to TowerSignal NYC cooling-tower systems")
    parser.add_argument("--output", type=Path, default=ROOT / "public/data")
    parser.add_argument("--alerts", type=Path, default=ROOT / "public/data/legionella-alerts.json")
    args = parser.parse_args()
    attach(args.output, args.alerts)


if __name__ == "__main__":
    main()
