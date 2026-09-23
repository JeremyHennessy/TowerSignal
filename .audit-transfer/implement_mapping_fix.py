from pathlib import Path
import re
R=Path.cwd()
def replace(path,old,new,count=1):
 p=R/path;s=p.read_text();n=s.count(old)
 if n!=count:raise RuntimeError(f'{path}: expected {count} anchors, found {n}: {old[:100]}')
 p.write_text(s.replace(old,new))
def function(path,name,body):
 p=R/path;s=p.read_text();start=s.index('def '+name+'(')
 match=re.search(r'\n(?=def |class )',s[start+1:]);end=(start+1+match.start()) if match else -1
 if end<0:raise RuntimeError('No following function '+path+' '+name)
 p.write_text(s[:start]+body.rstrip()+'\n\n'+s[end+1:])
replace('scripts/towersignal/planimetrics.py','from datetime import datetime, timezone','from datetime import datetime, timezone\nimport re')
function('scripts/towersignal/planimetrics.py','normalize_bin','''def normalize_bin(value: Any) -> str | None:
    """Only assigned NYC building IDs may create relationships; borough-only IDs are unknown."""
    text = str(value).strip() if value is not None else ""
    match = re.fullmatch(r"([1-5][0-9]{6})(?:\\.0+)?", text)
    if not match or match[1][1:] == "000000":
        return None
    return match[1]
''')
for path,name in [('scripts/attach_nyc_water_signals.py','_normalize_bin'),('scripts/towersignal/nyc_water_signals.py','_normalize_bin'),('scripts/towersignal/cms_institutional.py','normalize_bin'),('scripts/towersignal/legionella_matching.py','canonical_bin')]:
 function(path,name,f'''def {name}(value: Any) -> str | None:
    from towersignal.planimetrics import normalize_bin as assigned_bin
    return assigned_bin(value)
''')
replace('scripts/towersignal/normalize.py','"bin": normalize_bin(row.get("bin")),','"bin": normalize_bin(row.get("bin")),\n                "source_bin_raw": _clean(row.get("bin")),')
replace('scripts/towersignal/pluto.py','"owner_name": _text(row.get("ownername")),','"owner_name": None if (_text(row.get("ownername")) or "").upper() == "UNAVAILABLE OWNER" else _text(row.get("ownername")),\n        "source_owner_name_raw": _text(row.get("ownername")),')
replace('scripts/towersignal/hpd.py','if row.get("registrationid")})','if str(row.get("registrationid") or "").strip().isdigit() and int(row["registrationid"]) > 0})')
(R/'scripts/towersignal/hpd_identity.py').write_text('''"""Source-native HPD identities and contacts, without address guessing or sentinel joins."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from .fetch import SourceFetchError, fetch_count, fetch_metadata, fetch_where
from .hpd import (HPD_REGISTRATION_DATASET_ID, HPD_CONTACTS_DATASET_ID,
                  HPD_REGISTRATION_URL, HPD_CONTACTS_URL, REGISTRATION_SELECT,
                  CONTACT_SELECT, parts_to_bbl, normalize_contact, _registration_rank)
from .planimetrics import normalize_bin
from .pluto import normalize_bbl


def positive_id(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return str(int(text)) if text.isascii() and text.isdigit() and int(text) > 0 else None


def registration_bbl(row: dict) -> str | None:
    return parts_to_bbl(row.get("boroid"), row.get("block"), row.get("lot"))


def key_digest(values) -> str:
    return hashlib.sha256("\\n".join(sorted(set(str(v) for v in values))).encode()).hexdigest()


def index_registrations(rows: list[dict]) -> dict:
    by_bbl, by_bin, identities = defaultdict(list), defaultdict(list), defaultdict(set)
    for row in rows:
        bbl = registration_bbl(row)
        bin_value = normalize_bin(row.get("bin"))
        rid = positive_id(row.get("registrationid"))
        if bbl:
            by_bbl[bbl].append(row)
        if bin_value:
            by_bin[bin_value].append(row)
        if rid:
            identities[rid].add((str(row.get("buildingid") or ""), bin_value, bbl))
    conflicts = {rid for rid, keys in identities.items() if len(keys) > 1}
    eligible_by_bin = {
        bin_value: [r for r in group if positive_id(r.get("registrationid"))
                    and positive_id(r.get("registrationid")) not in conflicts and registration_bbl(r)]
        for bin_value, group in by_bin.items()
    }
    return {"by_bbl": dict(by_bbl), "by_bin": dict(by_bin),
            "eligible_by_bin": eligible_by_bin, "conflicting_registration_ids": conflicts}


def fetch_registration_snapshot() -> dict:
    before = fetch_metadata(HPD_REGISTRATION_DATASET_ID)
    expected = fetch_count(HPD_REGISTRATION_DATASET_ID)
    rows = []
    for offset in range(0, expected, 50000):
        rows.extend(fetch_where(HPD_REGISTRATION_DATASET_ID, "1=1",
                    "registrationid,buildingid,:id", REGISTRATION_SELECT, offset=offset))
    after = fetch_metadata(HPD_REGISTRATION_DATASET_ID)
    if len(rows) != expected or before.get("source_last_updated_at") != after.get("source_last_updated_at"):
        raise SourceFetchError("HPD registration snapshot changed or is incomplete; not negative evidence")
    index = index_registrations(rows)
    index["source"] = {**after, "source_record_count": expected,
        "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "registration_identity_sha256": hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}
    return index


def select_registration(system: dict, index: dict) -> tuple[dict | None, str]:
    bin_value = normalize_bin(system.get("bin"))
    bbl = normalize_bbl(system.get("bbl"))
    # Prefer the building's own registration. Do not replace a current empty
    # registration with an older contact-bearing one.
    exact = index["by_bin"].get(bin_value, []) if bin_value else []
    if exact:
        properties = {registration_bbl(r) for r in exact if registration_bbl(r)}
        if len(properties) != 1:
            return None, "AMBIGUOUS_HPD_BUILDING_PROPERTY"
        candidates, basis = exact, "BIN_EXACT"
    else:
        candidates, basis = index["by_bbl"].get(bbl, []) if bbl else [], "BBL_PARCEL_EXACT"
    if not candidates:
        return None, "NO_REGISTRATION_ON_CHECKED_KEYS" if bin_value or bbl else "IDENTITY_UNRESOLVED"
    row = max(candidates, key=lambda r: (_registration_rank(r), str(r.get("buildingid") or "")))
    rid = positive_id(row.get("registrationid"))
    if rid is None:
        return row, "UNUSABLE_SOURCE_REGISTRATION_ID"
    if rid in index["conflicting_registration_ids"]:
        return row, "COLLIDING_SOURCE_REGISTRATION_ID"
    return row, basis


def assemble_contacts(systems: list[dict], index: dict, rows: list[dict]) -> dict[str, dict]:
    by_id = defaultdict(list)
    for row in rows:
        rid = positive_id(row.get("registrationid"))
        if rid and rid not in index["conflicting_registration_ids"]:
            by_id[rid].append(normalize_contact(row))
    result = {}
    for system in systems:
        row, basis = select_registration(system, index)
        sid = str(system["system_id"])
        if row is None:
            result[sid] = {"registration": None, "status": basis}
            continue
        rid = positive_id(row.get("registrationid"))
        safe = basis in {"BIN_EXACT", "BBL_PARCEL_EXACT"}
        contacts = by_id.get(rid, []) if safe else []
        contacts = sorted({json.dumps(c, sort_keys=True): c for c in contacts}.values(),
                          key=lambda c: (c.get("type") or "", c.get("registration_contact_id") or ""))
        status = ("MATCHED" if contacts else "VERIFIED_EMPTY_CONTACTS") if safe else basis
        result[sid] = {"status": status, "registration": {
            "registration_id": rid,
            "source_registration_id_raw": row.get("registrationid"),
            "building_id": str(row.get("buildingid") or "") or None,
            "source_bin": normalize_bin(row.get("bin")),
            "source_bbl": registration_bbl(row),
            "last_registration_date": str(row.get("lastregistrationdate") or "")[:10] or None,
            "contacts": contacts, "lookup_status": status,
            "match_basis": basis if safe else None,
            "property_identity_agrees": registration_bbl(row) in (system.get("bbl_aliases") or [system.get("bbl")]),
            "source": "NYC_HPD_MULTIPLE_DWELLING_REGISTRATION",
        }}
    return result


def fetch_contacts_for_systems(systems: list[dict], index: dict) -> tuple[dict, dict]:
    ids = set()
    for system in systems:
        row, basis = select_registration(system, index)
        if row and basis in {"BIN_EXACT", "BBL_PARCEL_EXACT"}:
            ids.add(positive_id(row.get("registrationid")))
    ids = sorted(ids, key=int)
    rows = []
    for start in range(0, len(ids), 250):
        batch = ids[start:start + 250]
        found = fetch_where(HPD_CONTACTS_DATASET_ID, f"registrationid in ({','.join(batch)})",
                            "registrationid,type,registrationcontactid", CONTACT_SELECT)
        if len(found) >= 50000 or any(positive_id(r.get("registrationid")) not in batch for r in found):
            raise SourceFetchError("HPD contact lookup hit row cap or returned an unrequested registration")
        rows.extend(found)
    by_system = assemble_contacts(systems, index, rows)
    source, contacts_meta = index["source"], fetch_metadata(HPD_CONTACTS_DATASET_ID)
    bbls = {s["bbl"] for s in systems if s.get("bbl")}
    bins = {v for s in systems if (v := normalize_bin(s.get("bin")))}
    return by_system, {
        "registration_dataset_id": HPD_REGISTRATION_DATASET_ID,
        "registration_name": source["name"], "registration_url": HPD_REGISTRATION_URL,
        "registration_source_record_count": source["source_record_count"],
        "registration_source_last_updated_at": source.get("source_last_updated_at"),
        "contacts_dataset_id": HPD_CONTACTS_DATASET_ID,
        "contacts_name": contacts_meta["name"], "contacts_url": HPD_CONTACTS_URL,
        "contacts_source_record_count": fetch_count(HPD_CONTACTS_DATASET_ID),
        "contacts_source_last_updated_at": contacts_meta.get("source_last_updated_at"),
        "retrieved_at": source["retrieved_at"], "requested_bbl_count": len(bbls),
        "requested_assigned_bin_count": len(bins), "queried_registration_id_count": len(ids),
        "queried_registration_ids_sha256": key_digest(ids), "queried_bbls_sha256": key_digest(bbls),
        "queried_bins_sha256": key_digest(bins),
        "registration_identity_sha256": source["registration_identity_sha256"],
        "matched_registration_bbl_count": len({s.get("bbl") for s in systems if by_system[str(s["system_id"])]["registration"] and s.get("bbl")}),
        "matched_contact_bbl_count": len({s.get("bbl") for s in systems if by_system[str(s["system_id"])]["status"] == "MATCHED" and s.get("bbl")}),
        "matched_contact_record_count": len(rows),
        "source_query_scope": "Complete stable HPD identity snapshot; assigned BIN first, canonical BBL parcel second; positive unique registration IDs only",
    }
''')
replace('scripts/towersignal/bbl_identity.py','    footprints: list[dict[str, Any]],\n) -> dict[str, Any]:','    footprints: list[dict[str, Any]],\n    hpd_rows: list[dict[str, Any]] | None = None,\n) -> dict[str, Any]:')
replace('scripts/towersignal/bbl_identity.py','    registry_bbl = normalize_bbl(system.get("bbl"))','    registry_bbl = normalize_bbl(system.get("registry_bbl") if "registry_bbl" in system else system.get("bbl"))')
replace('scripts/towersignal/bbl_identity.py','    candidates = _mappluto_candidates(footprints)','    footprints = [f for f in footprints if bin_value and (not f.get("bin") or normalize_bin(f.get("bin")) == bin_value)]\n    candidates = _mappluto_candidates(footprints)')
replace('scripts/towersignal/bbl_identity.py','    aliases = sorted({value for value in (canonical, registry_bbl) if value})','''    from .hpd import parts_to_bbl
    hpd_candidates = {
        b for row in (hpd_rows or [])
        if bin_value and normalize_bin(row.get("bin")) == bin_value
        and (b := parts_to_bbl(row.get("boroid"), row.get("block"), row.get("lot")))
        and (not expected_prefix or b[0] == expected_prefix)
    }
    contradicted_registry = False
    if bin_value and len(hpd_candidates) == 1:
        hpd_bbl = next(iter(hpd_candidates))
        if status == "REGISTRY_SOURCE_BBL_MAPPLUTO_CONFLICT" and candidates == {hpd_bbl}:
            canonical = hpd_bbl
            status = "RECONCILED_REGISTRY_CONFLICT_BY_FOOTPRINT_AND_HPD_EXACT_BIN"
            identity_basis = "FOOTPRINT_AND_HPD_BBL_EXACT_BIN"
            source_dataset = "NYC_OTI_BUILDING_FOOTPRINTS+NYC_HPD_MULTIPLE_DWELLING_REGISTRATIONS"
            source_field = "mappluto_bbl+boroid/block/lot"
            contradicted_registry = True
        elif not canonical and not candidates:
            canonical = hpd_bbl
            status = "RECOVERED_EXACT_BIN_HPD_REGISTRATION_BBL"
            identity_basis = "HPD_REGISTRATION_BBL_EXACT_BIN"
            source_dataset = "NYC_HPD_MULTIPLE_DWELLING_REGISTRATIONS"
            source_field = "boroid/block/lot"
    aliases = {value for value in (canonical, None if contradicted_registry else registry_bbl) if value}
    confirmed_base = None
    if bin_value and canonical and candidates == {canonical} and len(base_context) == 1:
        base = base_context[0]
        if base[:6] == canonical[:6]:
            aliases.add(base)
            confirmed_base = base
    aliases = sorted(aliases)''')
replace('scripts/towersignal/bbl_identity.py','        "canonical_bbl": canonical,','        "hpd_bbl_candidates": sorted(hpd_candidates),\n        "hpd_identity_rows": hpd_rows or [],\n        "contradicted_registry_bbl_excluded": contradicted_registry,\n        "confirmed_footprint_base_alias": confirmed_base,\n        "canonical_bbl": canonical,')
replace('scripts/towersignal/bbl_identity.py','    footprints_by_bin: dict[str, list[dict[str, Any]]],\n) -> dict[str, Any]:','    footprints_by_bin: dict[str, list[dict[str, Any]]],\n    hpd_by_bin: dict[str, list[dict[str, Any]]] | None = None,\n) -> dict[str, Any]:')
replace('scripts/towersignal/bbl_identity.py','evidence = resolve_system_bbl_identity(system, footprints_by_bin.get(bin_value or "", []))','evidence = resolve_system_bbl_identity(system, footprints_by_bin.get(bin_value or "", []), (hpd_by_bin or {}).get(bin_value or "", []))')
replace('scripts/towersignal/bbl_identity.py','elif evidence["status"] == "RECOVERED_EXACT_BIN_MAPPLUTO_BBL":','elif evidence["status"] in {"RECOVERED_EXACT_BIN_MAPPLUTO_BBL", "RECOVERED_EXACT_BIN_HPD_REGISTRATION_BBL"}:')
replace('scripts/towersignal/bbl_identity.py','        else:\n            # A registry BBL remains usable','''        elif evidence["status"] == "RECONCILED_REGISTRY_CONFLICT_BY_FOOTPRINT_AND_HPD_EXACT_BIN":
            source_bbl_count += 1
        else:
            # A registry BBL remains usable''')
replace('scripts/towersignal/bbl_identity.py','"historical_bbl_aliases": "Canonical property BBL plus distinct registry/base BBL; aliases are exact identifiers, never fuzzy matches.",','"historical_bbl_aliases": "Canonical property, non-contradicted registry, and unique same-block exact-BIN footprint base lot agreeing with canonical MapPLUTO; never fuzzy matches.",')
replace('scripts/build_data_live.py','from towersignal.hpd import fetch_hpd_contacts_by_bbl  # noqa: E402','from towersignal.hpd_identity import fetch_registration_snapshot, fetch_contacts_for_systems  # noqa: E402')
replace('scripts/build_data_live.py','bbl_identity_meta = apply_bbl_identity_recovery(systems, building_footprints_by_bin)','hpd_index = fetch_registration_snapshot()\n    bbl_identity_meta = apply_bbl_identity_recovery(systems, building_footprints_by_bin, hpd_index["eligible_by_bin"])')
replace('scripts/build_data_live.py','hpd_by_bbl, hpd_meta = fetch_hpd_contacts_by_bbl(bbl_values)','hpd_by_system, hpd_meta = fetch_contacts_for_systems(systems, hpd_index)')
replace('scripts/build_data_live.py','hpd_registration = hpd_by_bbl.get(bbl_key) if bbl_key else None','hpd_lookup = hpd_by_system[system["system_id"]]\n        hpd_registration = hpd_lookup["registration"]')
replace('scripts/build_data_live.py','            "bin": system["bin"],','            "bin": system["bin"],\n            "source_bin_raw": system.get("source_bin_raw"),',2)
replace('scripts/build_data_live.py','            "hpd_contact_count": hpd_contact_count,','            "hpd_contact_count": hpd_contact_count,\n            "hpd_lookup_status": hpd_lookup["status"],')
replace('scripts/build_data_live.py','            "hpd_registration": hpd_registration,','            "hpd_registration": hpd_registration,\n            "hpd_lookup_status": hpd_lookup["status"],')
replace('scripts/build_data_live.py','        "normalized_system_count": len(systems),','        "normalized_system_count": len(systems),\n        "hpd_identity_lookup": hpd_meta,')
replace('scripts/build_acris_cache.py','from towersignal.fetch import fetch_dataset  # noqa: E402','from towersignal.fetch import fetch_dataset  # noqa: E402\nfrom towersignal.hpd_identity import fetch_registration_snapshot  # noqa: E402')
replace('scripts/build_acris_cache.py','identity_meta = apply_bbl_identity_recovery(systems, footprints_by_bin)','hpd_index = fetch_registration_snapshot()\n    identity_meta = apply_bbl_identity_recovery(systems, footprints_by_bin, hpd_index["eligible_by_bin"])')
replace('scripts/build_acris_cache.py','        property_targets: dict[str, dict[str, Any]] = {}','        payload = json.loads(tower_snapshot.read_text(encoding="utf-8"))\n        property_targets = property_targets_from_systems(payload.get("systems") or payload.get("observations") or [])')
replace('scripts/towersignal/inspections.py','    seen_violations: dict','    observed_statuses: dict = defaultdict(set)\n    observed_equipment: dict = defaultdict(set)\n    seen_violations: dict')
replace('scripts/towersignal/inspections.py','        key = _inspection_key(row)','        key = _inspection_key(row)\n        observed_statuses[key].add(_clean(row.get("status")))\n        observed_equipment[key].add(_int(row.get("active_equip"), 0))')
replace('scripts/towersignal/inspections.py','    for inspection in grouped.values():\n        inspection["violation_count"]','''    for key, inspection in grouped.items():
        statuses = sorted(observed_statuses[key], key=lambda v: v or "")
        equipment = sorted(observed_equipment[key])
        inspection["status"] = statuses[0] if len(statuses) == 1 else "SOURCE_CONFLICT"
        inspection["active_equipment_at_publication"] = equipment[0] if len(equipment) == 1 else None
        if len(statuses) > 1 or len(equipment) > 1:
            inspection["source_metadata_conflicts"] = {"statuses": statuses, "active_equipment": equipment}
        inspection["violations"].sort(key=lambda r: tuple(str(r.get(f) or "") for f in VIOLATION_FIELDS))
        inspection["violation_count"]''')
replace('scripts/towersignal/inspections.py','inspections.sort(key=lambda item: item.get("inspection_date") or "", reverse=True)','inspections.sort(key=lambda item: (item.get("inspection_date") or "", item.get("inspection_type") or ""), reverse=True)')
replace('scripts/validate_bbl_identity.py','        if aliases != expected_aliases:','''        # The expected alias set is derived below from retained source evidence.
        if canonical and canonical not in aliases:''')
anchor='        strong_bridge = (\n'
replace('scripts/validate_bbl_identity.py',anchor,'''        evidence = identity.get("bbl_identity_evidence") or {}
        from towersignal.bbl_identity import resolve_system_bbl_identity
        from towersignal.planimetrics import normalize_bin
        recomputed = resolve_system_bbl_identity(
            {**identity, "bbl": registry}, footprints, evidence.get("hpd_identity_rows") or [])
        if aliases != recomputed["bbl_aliases"] or canonical != recomputed["canonical_bbl"]:
            raise RuntimeError(f"System {system_id} identity is not supported by its exact-key sources")
        if identity.get("bin") and normalize_bin(identity["bin"]) is None:
            raise RuntimeError(f"System {system_id} uses an unassigned BIN as a relationship key")

'''+anchor)
replace('scripts/verify_live_data_live.py','        live_by_bbl, _ = fetch_hpd_contacts_by_bbl([bbl])\n        live = live_by_bbl.get(bbl)','''        from towersignal.hpd_identity import fetch_registration_snapshot, fetch_contacts_for_systems
        live_results, _ = fetch_contacts_for_systems([displayed], fetch_registration_snapshot())
        live = live_results[displayed["system_id"]]["registration"]''')
replace('tests/python/test_build_acris_cache.py','            patch.object(build_acris_cache, "fetch_building_footprints_by_bin", return_value=(footprints, {})) as footprints_fetch,','            patch.object(build_acris_cache, "fetch_building_footprints_by_bin", return_value=(footprints, {})) as footprints_fetch,\n            patch.object(build_acris_cache, "fetch_registration_snapshot", return_value={"eligible_by_bin": {}}),')
replace('tests/python/test_registry_bin_identity.py','        self.assertEqual(decimal, canonical)','        self.assertEqual(decimal[0].pop("source_bin_raw"), "1089723.0")\n        self.assertEqual(canonical[0].pop("source_bin_raw"), "1089723")\n        self.assertEqual(decimal, canonical)')
replace('tests/python/test_validate_bbl_identity.py','                "system_id": row["system_id"],','                "system_id": row["system_id"],\n                "bin": "1089723",\n                "borough": "Manhattan",')
replace('tests/python/test_validate_bbl_identity.py','"ignored exact-BIN"','"not supported by its exact-key sources"')
print('Complete source-level mapping corrections written; frontend and scoring unchanged')
