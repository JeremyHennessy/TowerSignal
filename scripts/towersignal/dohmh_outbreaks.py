from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HEALTH_TOPIC_URL = "https://www.nyc.gov/site/doh/health/health-topics/legionnaires-disease.page"
SOUTH_BRONX_PRESS_RELEASE_URL = "https://www.nyc.gov/site/doh/about/press/pr2026/nyc-health-department-orders-cooling-towers-to-be-cleaned-in-south-bronx.page"
SOURCE_ID = "NYC_DOHMH_LEGIONNAIRES_INVESTIGATIONS"
SOURCE_NAME = "NYC DOHMH Legionnaires' Disease Investigations"
USER_AGENT = "TowerSignal/1.0 (+https://github.com/JeremyHennessy/TowerSignal)"


class DohmhOutbreakSourceError(RuntimeError):
    pass


class _BlockParser(HTMLParser):
    BLOCK_TAGS = {"h1", "h2", "h3", "h4", "p", "li"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._stack: list[tuple[str, list[str]]] = []
        self.blocks: list[tuple[str, str]] = []
        self._suppressed = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style"}:
            self._suppressed += 1
            return
        if not self._suppressed and lowered in self.BLOCK_TAGS:
            self._stack.append((lowered, []))

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style"}:
            self._suppressed = max(0, self._suppressed - 1)
            return
        if self._suppressed or lowered not in self.BLOCK_TAGS:
            return
        for index in range(len(self._stack) - 1, -1, -1):
            block_tag, parts = self._stack[index]
            if block_tag != lowered:
                continue
            text = _clean_text(" ".join(parts))
            del self._stack[index]
            if text:
                self.blocks.append((lowered, text))
            break

    def handle_data(self, data: str) -> None:
        if self._suppressed:
            return
        for _, parts in self._stack:
            parts.append(data)


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def html_blocks(html: str) -> list[tuple[str, str]]:
    parser = _BlockParser()
    parser.feed(html)
    return parser.blocks


def _request_text(url: str, retries: int = 4, timeout: int = 60) -> str:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
            with urlopen(request, timeout=timeout) as response:
                content_type = str(response.headers.get("Content-Type") or "")
                if "html" not in content_type.lower():
                    raise DohmhOutbreakSourceError(f"Unexpected content type for {url}: {content_type or 'missing'}")
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except (HTTPError, URLError, TimeoutError, UnicodeDecodeError, DohmhOutbreakSourceError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(2**attempt)
    raise DohmhOutbreakSourceError(f"Failed to retrieve DOHMH source after {retries} attempts: {url}: {last_error}")


def normalize_address(value: Any) -> str:
    text = str(value or "").upper().replace("’", "'")
    text = re.sub(r"[^A-Z0-9' ]+", " ", text)
    tokens = [_normalize_address_token(token) for token in text.split() if token]
    return " ".join(token for token in tokens if token)


def _normalize_address_token(token: str) -> str:
    token = token.strip("'")
    ordinal = re.fullmatch(r"(\d+)(ST|ND|RD|TH)", token)
    if ordinal:
        return ordinal.group(1)
    mapping = {
        "E": "EAST", "W": "WEST", "N": "NORTH", "S": "SOUTH",
        "ST": "STREET", "STR": "STREET", "AVE": "AVENUE", "AV": "AVENUE",
        "RD": "ROAD", "BLVD": "BOULEVARD", "DR": "DRIVE", "PL": "PLACE",
        "LN": "LANE", "PKWY": "PARKWAY", "HWY": "HIGHWAY", "CT": "COURT",
    }
    return mapping.get(token, token)


def normalize_borough(value: Any) -> str:
    token = _clean_text(value).upper()
    mapping = {"MN": "MANHATTAN", "NEW YORK": "MANHATTAN", "BX": "BRONX", "BK": "BROOKLYN", "QN": "QUEENS", "SI": "STATEN ISLAND"}
    return mapping.get(token, token)


def _looks_like_address(value: str) -> bool:
    return bool(re.match(r"^\d+\s+[A-Za-z0-9]", value.strip()))


def _first_match(blocks: list[tuple[str, str]], pattern: str) -> re.Match[str] | None:
    compiled = re.compile(pattern, flags=re.IGNORECASE)
    for _, text in blocks:
        match = compiled.search(text)
        if match:
            return match
    return None


def _addresses_after_marker(blocks: list[tuple[str, str]], marker: str, stop_markers: tuple[str, ...]) -> list[str]:
    started = False
    addresses: list[str] = []
    marker_lower = marker.lower()
    for tag, text in blocks:
        lowered = text.lower()
        if not started:
            if marker_lower in lowered:
                started = True
            continue
        if any(stop.lower() in lowered for stop in stop_markers):
            break
        if tag == "li" and _looks_like_address(text):
            addresses.append(text)
    return addresses


def parse_health_topic_html(html: str) -> dict[str, Any]:
    blocks = html_blocks(html)
    headings = [text for tag, text in blocks if tag in {"h1", "h2", "h3", "h4"}]
    if not any("Legionnaires' Disease Cluster in the South Bronx" in heading or "Legionnaires’ Disease Cluster in the South Bronx" in heading for heading in headings):
        raise DohmhOutbreakSourceError("DOHMH health-topic page no longer exposes the expected South Bronx cluster heading; source adapter requires review")
    addresses = _addresses_after_marker(
        blocks,
        "The following buildings have cooling towers that tested positive in a PCR test",
        ("In addition to the PCR screening tests", "Expand All", "About Legionnaires"),
    )
    if not addresses:
        raise DohmhOutbreakSourceError("DOHMH health-topic page exposed the South Bronx cluster but no PCR-positive building list")
    case_match = _first_match(blocks, r"(\d+)\s+people have tested positive for Legionnaires")
    updated_match = _first_match(blocks, r"Last updated\s+(.+)$")
    culture_pending = any("culture test" in text.lower() and "being conducted" in text.lower() for _, text in blocks)
    remediation_ordered = any("ordered to clean and disinfect by September 14" in text for _, text in blocks)
    return {
        "cluster_status": "ACTIVE",
        "case_count": int(case_match.group(1)) if case_match else None,
        "last_updated_text": updated_match.group(1) if updated_match else None,
        "pcr_positive_buildings": addresses,
        "culture_testing_pending": culture_pending,
        "remediation_ordered": remediation_ordered,
    }


def parse_south_bronx_press_release_html(html: str) -> dict[str, Any]:
    blocks = html_blocks(html)
    addresses = _addresses_after_marker(
        blocks,
        "The 10 cooling towers with positive PCR results are located at",
        ("Eight of the 10 cooling towers", "The Health Department has tested"),
    )
    if len(addresses) != 10:
        raise DohmhOutbreakSourceError(f"Expected 10 South Bronx PCR-positive building addresses in September 13 press release; found {len(addresses)}")
    reporting_text = next((text for _, text in blocks if "did not provide testing information as required" in text), "")
    non_reporting = [address for address in addresses if normalize_address(address) in {
        normalize_address("820 Concourse Village West"),
        normalize_address("1265 Franklin Ave."),
    }]
    if len(non_reporting) != 2 or not reporting_text:
        raise DohmhOutbreakSourceError("Could not verify the two South Bronx testing-information exceptions in the September 13 press release")
    sampled_match = _first_match(blocks, r"tested\s+(\d+)\s+cooling towers as part of this investigation")
    return {
        "source_date": "2026-09-13",
        "pcr_positive_buildings": addresses,
        "testing_information_not_provided_as_required": non_reporting,
        "investigation_towers_tested": int(sampled_match.group(1)) if sampled_match else None,
    }


def load_reference(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0" or payload.get("domain") != "NYC_DOHMH_LEGIONNAIRES_INVESTIGATIONS_REFERENCE":
        raise DohmhOutbreakSourceError(f"Unexpected DOHMH reference payload: {path}")
    return payload


def _base_observation(cluster: dict[str, Any], address: str, *, active: bool) -> dict[str, Any]:
    return {
        "cluster_id": cluster["cluster_id"],
        "cluster_name": cluster["cluster_name"],
        "cluster_status": cluster["status"],
        "active_investigation": active,
        "borough": cluster["borough"],
        "address": _clean_text(address),
        "normalized_address": normalize_address(address),
        "source_observation_date": cluster.get("source_observation_date"),
        "attribution_scope": "BUILDING_ADDRESS",
        "system_specific_test_identity": False,
        "causation_established": False,
        "registry_match_expected": True,
    }


def upper_east_side_observations(reference: dict[str, Any]) -> list[dict[str, Any]]:
    cluster = reference["upper_east_side_2026"]
    raw_pcr = {normalize_address(value): value for value in cluster["pcr_positive_buildings_raw_pdf"]}
    corrected = {normalize_address(value) for value in cluster["corrected_unregistered_pcr_negative_culture_negative_buildings"]}
    culture_positive = {normalize_address(value): value for value in cluster["culture_positive_buildings"]}
    culture_negative = {normalize_address(value): value for value in cluster["culture_negative_buildings"]}
    pcr_negative_culture_positive = {normalize_address(value) for value in cluster["pcr_negative_culture_positive_buildings"]}

    final_pcr_positive = set(raw_pcr) - corrected
    if len(final_pcr_positive) != int(cluster["aggregate"]["pcr_positive_buildings"]):
        raise DohmhOutbreakSourceError("UES reference reconciliation failed for PCR-positive building count")
    if len(culture_positive) != int(cluster["aggregate"]["culture_positive_buildings"]):
        raise DohmhOutbreakSourceError("UES reference reconciliation failed for culture-positive building count")
    if pcr_negative_culture_positive - set(culture_positive):
        raise DohmhOutbreakSourceError("UES PCR-negative/culture-positive correction list is not contained in the culture-positive list")
    if final_pcr_positive - (set(culture_positive) | set(culture_negative)):
        raise DohmhOutbreakSourceError("UES final PCR-positive buildings are missing final culture classifications")

    all_keys = sorted(set(raw_pcr) | set(culture_positive) | set(culture_negative))
    observations: list[dict[str, Any]] = []
    for key in all_keys:
        address = raw_pcr.get(key) or culture_positive.get(key) or culture_negative.get(key) or key
        observation = _base_observation(cluster, address, active=False)
        observation.update({
            "pcr_result": "POSITIVE" if key in final_pcr_positive else "NEGATIVE",
            "culture_result": "POSITIVE" if key in culture_positive else "NEGATIVE" if key in culture_negative else "NOT_PUBLISHED",
            "culture_result_source_date": "2026-07-29" if key in culture_positive or key in culture_negative else None,
            "pcr_result_source_date": "2026-07-20" if key in raw_pcr else "2026-07-29" if key in pcr_negative_culture_positive else None,
            "testing_information_status": "NOT_APPLICABLE_HISTORICAL_CLUSTER",
            "remediation_status": (
                "CLEANED_AND_DISINFECTED_REPORTED" if key in culture_positive
                else "CLEANING_COMPLETE_REPORTED" if key in final_pcr_positive
                else "NOT_APPLICABLE_TO_FINAL_POSITIVE_RESULT"
            ),
            "remediation_source_date": "2026-08-28" if key in culture_positive else "2026-07-20" if key in final_pcr_positive else None,
            "registry_match_expected": key not in corrected,
            "source_urls": [reference["sources"]["ues_pcr_pdf"], reference["sources"]["ues_culture_pdf"], reference["sources"]["health_topic"]],
        })
        observations.append(observation)
    return observations


def south_bronx_observations(reference: dict[str, Any], health: dict[str, Any], press: dict[str, Any]) -> list[dict[str, Any]]:
    cluster = dict(reference["south_bronx_2026"])
    cluster["status"] = health["cluster_status"]
    current_addresses = health["pcr_positive_buildings"]
    press_addresses = {normalize_address(value) for value in press["pcr_positive_buildings"]}
    non_reporting = {normalize_address(value) for value in press["testing_information_not_provided_as_required"]}
    observations: list[dict[str, Any]] = []
    for address in current_addresses:
        key = normalize_address(address)
        testing_status = "UNKNOWN_CURRENT_SOURCE"
        if key in non_reporting:
            testing_status = "TESTING_INFORMATION_NOT_PROVIDED_AS_REQUIRED"
        elif key in press_addresses:
            testing_status = "COMPLIANT_WITH_31_DAY_TESTING_REQUIREMENT_AS_OF_2026_09_13"
        observation = _base_observation(cluster, address, active=True)
        observation.update({
            "pcr_result": "POSITIVE",
            "culture_result": "PENDING" if health.get("culture_testing_pending") else "NOT_PUBLISHED",
            "pcr_result_source_date": "2026-09-12",
            "culture_result_source_date": None,
            "testing_information_status": testing_status,
            "remediation_status": "ORDERED_CLEAN_AND_DISINFECT" if health.get("remediation_ordered") else "ORDER_REPORTED_IN_PRESS_RELEASE",
            "remediation_order_date": cluster.get("remediation_order_date"),
            "remediation_deadline": cluster.get("remediation_deadline"),
            "source_urls": [reference["sources"]["health_topic"], reference["sources"]["south_bronx_press_release"]],
        })
        observations.append(observation)
    return observations


def match_observations_to_systems(observations: list[dict[str, Any]], systems: list[dict[str, Any]]) -> dict[str, Any]:
    systems_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for system in systems:
        address = normalize_address(system.get("address"))
        borough = normalize_borough(system.get("borough"))
        if not address or not borough:
            continue
        systems_by_key.setdefault((borough, address), []).append(system)

    matched_observations = 0
    matched_system_ids: set[str] = set()
    unmatched_expected: list[str] = []
    for observation in observations:
        key = (normalize_borough(observation.get("borough")), normalize_address(observation.get("address")))
        matches = sorted(systems_by_key.get(key, []), key=lambda item: str(item.get("system_id") or ""))
        system_ids = [str(item.get("system_id")) for item in matches if item.get("system_id")]
        observation["matched_system_ids"] = system_ids
        observation["matched_system_count"] = len(system_ids)
        if len(system_ids) == 1:
            observation["match_basis"] = "EXACT_NORMALIZED_BUILDING_ADDRESS_SINGLE_SYSTEM"
        elif len(system_ids) > 1:
            observation["match_basis"] = "EXACT_NORMALIZED_BUILDING_ADDRESS_MULTI_SYSTEM_BUILDING"
        else:
            observation["match_basis"] = "UNMATCHED_CURRENT_REGISTRY"
        if system_ids:
            matched_observations += 1
            matched_system_ids.update(system_ids)
        elif observation.get("registry_match_expected"):
            unmatched_expected.append(str(observation.get("address") or ""))

    expected = [item for item in observations if item.get("registry_match_expected")]
    return {
        "observation_count": len(observations),
        "registry_match_expected_observation_count": len(expected),
        "matched_observation_count": matched_observations,
        "matched_system_count": len(matched_system_ids),
        "unmatched_expected_observation_count": len(unmatched_expected),
        "unmatched_expected_addresses": sorted(unmatched_expected),
    }


def build_cache(
    systems: list[dict[str, Any]],
    reference: dict[str, Any],
    fetch_text: Callable[[str], str] = _request_text,
) -> dict[str, Any]:
    health_html = fetch_text(reference["sources"]["health_topic"])
    press_html = fetch_text(reference["sources"]["south_bronx_press_release"])
    health = parse_health_topic_html(health_html)
    press = parse_south_bronx_press_release_html(press_html)

    observations = upper_east_side_observations(reference) + south_bronx_observations(reference, health, press)
    observations.sort(key=lambda item: (str(item.get("cluster_id")), normalize_address(item.get("address"))))
    match_summary = match_observations_to_systems(observations, systems)
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    active = [item for item in observations if item.get("active_investigation")]
    return {
        "schema_version": "1.0",
        "domain": "NYC_DOHMH_LEGIONNAIRES_INVESTIGATIONS",
        "generated_at": generated_at,
        "source": {
            "dataset_id": SOURCE_ID,
            "name": SOURCE_NAME,
            "retrieved_at": generated_at,
            "source_record_count": len(observations),
            "source_last_updated_at": "2026-09-14T18:50:00-04:00" if health.get("last_updated_text") else None,
            "url": reference["sources"]["health_topic"],
            "urls": reference["sources"],
            "source_query_scope": "Official DOHMH Legionnaires community-cluster address publications; current South Bronx page + September 13 release and reconciled 2026 Upper East Side official PDFs",
        },
        "evidence_boundaries": reference["evidence_boundaries"],
        "summary": {
            **match_summary,
            "active_cluster_count": len({item["cluster_id"] for item in active}),
            "active_observation_count": len(active),
            "active_matched_system_count": len({system_id for item in active for system_id in item.get("matched_system_ids", [])}),
            "south_bronx_case_count": health.get("case_count"),
            "south_bronx_last_updated_text": health.get("last_updated_text"),
            "south_bronx_investigation_towers_tested_as_of_2026_09_13": press.get("investigation_towers_tested"),
            "upper_east_side_pcr_positive_buildings": reference["upper_east_side_2026"]["aggregate"]["pcr_positive_buildings"],
            "upper_east_side_culture_positive_buildings": reference["upper_east_side_2026"]["aggregate"]["culture_positive_buildings"],
        },
        "observations": observations,
    }


def validate_cache(payload: dict[str, Any], *, require_production_volume: bool = False) -> None:
    if payload.get("schema_version") != "1.0" or payload.get("domain") != "NYC_DOHMH_LEGIONNAIRES_INVESTIGATIONS":
        raise DohmhOutbreakSourceError("Unexpected DOHMH outbreak cache schema/domain")
    observations = payload.get("observations")
    if not isinstance(observations, list) or not observations:
        raise DohmhOutbreakSourceError("DOHMH outbreak cache has no observations")
    source = payload.get("source") or {}
    if source.get("dataset_id") != SOURCE_ID or int(source.get("source_record_count") or 0) != len(observations):
        raise DohmhOutbreakSourceError("DOHMH outbreak cache source metadata does not reconcile")
    for item in observations:
        if item.get("attribution_scope") != "BUILDING_ADDRESS" or item.get("system_specific_test_identity") is not False:
            raise DohmhOutbreakSourceError("DOHMH outbreak observation violated building-level attribution boundary")
        if item.get("causation_established") is not False:
            raise DohmhOutbreakSourceError("DOHMH outbreak cache must not assert outbreak causation")
        if item.get("culture_result") == "PENDING" and item.get("cluster_status") != "ACTIVE":
            raise DohmhOutbreakSourceError("Pending culture result attached to a non-active cluster")
    summary = payload.get("summary") or {}
    if int(summary.get("upper_east_side_pcr_positive_buildings") or 0) != 75:
        raise DohmhOutbreakSourceError("UES final PCR-positive building reconciliation must equal 75")
    if int(summary.get("upper_east_side_culture_positive_buildings") or 0) != 58:
        raise DohmhOutbreakSourceError("UES culture-positive building reconciliation must equal 58")
    active = [item for item in observations if item.get("active_investigation")]
    if require_production_volume:
        if len(active) != 10:
            raise DohmhOutbreakSourceError(f"Expected 10 active South Bronx PCR-positive building observations; found {len(active)}")
        if int(summary.get("active_matched_system_count") or 0) <= 0:
            raise DohmhOutbreakSourceError("Active DOHMH outbreak observations did not match any current registry systems")
        if int(summary.get("south_bronx_case_count") or 0) < 1:
            raise DohmhOutbreakSourceError("Current South Bronx case count was not parsed from the official DOHMH page")


def reference_path(root: Path) -> Path:
    return root / "data" / "reference" / "dohmh-legionnaires-2026.json"
