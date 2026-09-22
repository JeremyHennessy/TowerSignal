from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SYSTEM_ID = "2000014227"
EXPECTED_REGISTRY_BBL = "1011710154"
EXPECTED_PROPERTY_BBL = "1011717513"
EXPECTED_BIN = "1089723"


def detail_path(output: Path, system_id: str) -> Path:
    return output / "details" / system_id[:2] / f"{system_id}.json"


def validate(output: Path, *, require_acris: bool = False) -> dict[str, Any]:
    systems_payload = json.loads((output / "systems.json").read_text(encoding="utf-8"))
    rows = {
        str(row.get("system_id")): row
        for row in (systems_payload.get("systems") or [])
        if isinstance(row, dict) and row.get("system_id")
    }
    row = rows.get(SYSTEM_ID)
    if not row:
        raise RuntimeError(f"Required identity-regression system is missing: {SYSTEM_ID}")

    expected = {
        "bin": EXPECTED_BIN,
        "registry_bbl": EXPECTED_REGISTRY_BBL,
        "property_bbl": EXPECTED_PROPERTY_BBL,
        "bbl": EXPECTED_PROPERTY_BBL,
        "bbl_identity_status": "RECONCILED_REGISTRY_BASE_TO_MAPPLUTO_BBL",
        "bbl_identity_basis": "REGISTRY_BASE_BBL_TO_MAPPLUTO_BBL_EXACT_BIN",
    }
    for field, value in expected.items():
        actual = str(row.get(field) or "")
        if actual != value:
            raise RuntimeError(f"{SYSTEM_ID} {field} mismatch: {actual!r} != {value!r}")

    aliases = sorted(str(value) for value in (row.get("bbl_aliases") or []))
    if aliases != [EXPECTED_REGISTRY_BBL, EXPECTED_PROPERTY_BBL]:
        raise RuntimeError(f"{SYSTEM_ID} BBL aliases mismatch: {aliases}")

    detail = json.loads(detail_path(output, SYSTEM_ID).read_text(encoding="utf-8"))
    identity = detail.get("identity") or {}
    for field, value in expected.items():
        if field == "bin":
            continue
        actual = str(identity.get(field) or "")
        if actual != value:
            raise RuntimeError(f"{SYSTEM_ID} detail identity {field} mismatch: {actual!r} != {value!r}")

    evidence = identity.get("bbl_identity_evidence") or {}
    if evidence.get("registry_base_bridge_confirmed") is not True:
        raise RuntimeError(f"{SYSTEM_ID} lacks confirmed exact-BIN base→MapPLUTO bridge provenance")
    if evidence.get("address_matching_used") is not False or evidence.get("fuzzy_matching_used") is not False:
        raise RuntimeError(f"{SYSTEM_ID} property identity used prohibited fuzzy/address matching")

    building = detail.get("building_context")
    if not isinstance(building, dict):
        raise RuntimeError(f"{SYSTEM_ID} still lacks PLUTO building context after property-BBL reconciliation")
    if str(building.get("bbl") or "") != EXPECTED_PROPERTY_BBL:
        raise RuntimeError(f"{SYSTEM_ID} PLUTO context is attached to the wrong BBL: {building.get('bbl')!r}")
    if not str(building.get("owner_name") or "").strip():
        raise RuntimeError(f"{SYSTEM_ID} PLUTO owner is still missing after property-BBL reconciliation")

    hpd = detail.get("hpd_registration")
    if not isinstance(hpd, dict) or not hpd.get("registration_id"):
        raise RuntimeError(f"{SYSTEM_ID} still lacks HPD registration after property-BBL reconciliation")
    contacts = hpd.get("contacts") or []
    if not isinstance(contacts, list) or not contacts:
        raise RuntimeError(f"{SYSTEM_ID} still lacks HPD contacts after property-BBL reconciliation")

    footprints = detail.get("building_footprints") or []
    bridges = [
        item for item in footprints
        if isinstance(item, dict)
        and str(item.get("base_bbl") or "") == EXPECTED_REGISTRY_BBL
        and str(item.get("mappluto_bbl") or "") == EXPECTED_PROPERTY_BBL
    ]
    if not bridges:
        raise RuntimeError(f"{SYSTEM_ID} exact-BIN footprint bridge evidence is missing")

    acris = detail.get("acris_activity")
    if require_acris:
        if not isinstance(acris, dict) or int(acris.get("recent_document_count") or 0) <= 0:
            raise RuntimeError(f"{SYSTEM_ID} still lacks recent ACRIS activity after condo/property reconciliation")
        documents = acris.get("documents") or []
        if not documents:
            raise RuntimeError(f"{SYSTEM_ID} ACRIS activity has no retained source documents")
        allowed = {
            "BBL_EXACT_DOCUMENT_ID_EXACT",
            "BBL_ALIAS_EXACT_DOCUMENT_ID_EXACT",
            "CONDO_BILLING_BBL_BLOCK_ADDRESS_EXACT",
        }
        if any(str(doc.get("match_basis") or "") not in allowed for doc in documents if isinstance(doc, dict)):
            raise RuntimeError(f"{SYSTEM_ID} ACRIS activity contains an unapproved match basis")

    metadata = systems_payload.get("metadata") or {}
    reconciled_count = int(metadata.get("bbl_reconciled_registry_base_to_mappluto_count") or 0)
    if reconciled_count <= 0:
        raise RuntimeError("Generated NYC metadata reports no reconciled registry/base property identities")

    result = {
        "system_id": SYSTEM_ID,
        "registry_bbl": row["registry_bbl"],
        "property_bbl": row["property_bbl"],
        "owner_name": building.get("owner_name"),
        "hpd_registration_id": hpd.get("registration_id"),
        "hpd_contact_count": len(contacts),
        "acris_recent_document_count": int(acris.get("recent_document_count") or 0) if isinstance(acris, dict) else None,
        "acris_displayed_document_count": int(acris.get("displayed_document_count") or 0) if isinstance(acris, dict) else None,
        "reconciled_system_count": reconciled_count,
    }
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the TowerSignal property-identity regression account")
    parser.add_argument("--output", type=Path, default=Path("public/data"))
    parser.add_argument("--require-acris", action="store_true")
    args = parser.parse_args()
    validate(args.output, require_acris=args.require_acris)


if __name__ == "__main__":
    main()
