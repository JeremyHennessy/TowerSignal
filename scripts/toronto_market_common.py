from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

USER_AGENT = "TowerSignal-Toronto-Market/0.1 (+https://github.com/JeremyHennessy/TowerSignal)"

STREET_TYPES = {
    "STREET": "ST", "ST": "ST", "ROAD": "RD", "RD": "RD", "AVENUE": "AVE", "AVE": "AVE",
    "BOULEVARD": "BLVD", "BLVD": "BLVD", "DRIVE": "DR", "DR": "DR", "COURT": "CRT", "CRT": "CRT", "CT": "CRT",
    "CRESCENT": "CRES", "CRES": "CRES", "LANE": "LANE", "LN": "LANE", "PLACE": "PL", "PL": "PL",
    "PARKWAY": "PKWY", "PKWY": "PKWY", "HIGHWAY": "HWY", "HWY": "HWY", "TRAIL": "TRL", "TRL": "TRL",
    "TERRACE": "TER", "TER": "TER", "GATE": "GT", "GT": "GT", "GARDENS": "GDNS", "GARDEN": "GDN",
    "GDNS": "GDNS", "GDN": "GDN", "WAY": "WAY", "SQUARE": "SQ", "SQ": "SQ",
}
DIRECTIONS = {"NORTH":"N","SOUTH":"S","EAST":"E","WEST":"W","N":"N","S":"S","E":"E","W":"W"}
PROPERTY_ADDRESS_KEYS = {"address", "siteaddress", "facilityaddress", "propertyaddress", "fulladdress", "premisesaddress", "locationaddress", "streetaddress", "address1"}
EXCLUDED_ADDRESS_KEY_FRAGMENTS = {"mail", "email", "owner", "contractor", "vendor", "consultant", "manager", "certifier", "billing", "contact", "head", "office"}

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def normalize_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())

def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()

def canonical_street_address(value: Any) -> str:
    text = clean_text(value).upper()
    if not text:
        return ""
    text = text.split(",")[0].strip()
    text = re.sub(r"\b(?:TORONTO|ETOBICOKE|NORTH YORK|SCARBOROUGH|EAST YORK|YORK)\b.*$", "", text).strip()
    text = re.sub(r"\bM\d[A-Z]\s*\d[A-Z]\d\b.*$", "", text).strip()
    text = re.sub(r"\b(?:ONTARIO|ON)\b.*$", "", text).strip()
    text = re.sub(r"\bUNIT\s+[A-Z0-9-]+\b", "", text)
    text = re.sub(r"\b(?:SUITE|STE)\s+[A-Z0-9-]+\b", "", text)
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    tokens = [t for t in text.split() if t]
    out: list[str] = []
    for token in tokens:
        if token in STREET_TYPES:
            out.append(STREET_TYPES[token])
        elif token in DIRECTIONS:
            out.append(DIRECTIONS[token])
        else:
            out.append(token)
    return " ".join(out)

def get_value(record: dict[str, Any], *names: str) -> Any:
    index = {normalize_key(k): v for k, v in record.items()}
    for name in names:
        key = normalize_key(name)
        if key in index:
            return index[key]
    return None

def iter_record_objects(payload: Any) -> Iterable[dict[str, Any]]:
    if isinstance(payload, list):
        for item in payload:
            yield from iter_record_objects(item)
    elif isinstance(payload, dict):
        for key in ("records", "rows", "toronto_rows", "features", "applications", "matches", "properties", "notices"):
            value = payload.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and key == "features" and isinstance(item.get("attributes"), dict):
                        yield item["attributes"]
                    elif isinstance(item, dict):
                        yield item
                return
        keys = {normalize_key(k) for k in payload}
        if keys & PROPERTY_ADDRESS_KEYS:
            yield payload

def record_property_addresses(record: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for key, value in record.items():
        nk = normalize_key(key)
        if any(fragment in nk for fragment in EXCLUDED_ADDRESS_KEY_FRAGMENTS):
            continue
        if nk in PROPERTY_ADDRESS_KEYS or ("address" in nk and not any(fragment in nk for fragment in EXCLUDED_ADDRESS_KEY_FRAGMENTS)):
            if isinstance(value, (str, int, float)):
                canon = canonical_street_address(value)
                if re.match(r"^\d+[A-Z]?(?:-\d+[A-Z]?)?\s+", canon):
                    found.append(clean_text(value))
    return list(dict.fromkeys(found))

def request_bytes(url: str, *, timeout: int = 90, retries: int = 4, max_bytes: int | None = None) -> bytes:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,text/html,application/pdf,text/plain,*/*;q=0.7", "Accept-Language": "en-CA,en;q=0.9"})
            with urlopen(req, timeout=timeout) as response:
                if max_bytes is None:
                    return response.read()
                data = response.read(max_bytes + 1)
                if len(data) > max_bytes:
                    raise RuntimeError(f"Response exceeded {max_bytes} bytes: {url}")
                return data
        except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed to retrieve {url}: {last_error}")

def request_json(url: str, *, timeout: int = 90) -> Any:
    return json.loads(request_bytes(url, timeout=timeout).decode("utf-8"))

def write_json(path: Path, payload: Any, *, pretty: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2 if pretty else None, ensure_ascii=False, default=str), encoding="utf-8")

def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def is_city_of_toronto_url(url: str) -> bool:
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or "").lower()
    return host == "toronto.ca" or host.endswith(".toronto.ca")

def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
