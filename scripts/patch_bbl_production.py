from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"{label}: expected one match, found {text.count(old)}")
    return text.replace(old, new, 1)


def patch_build_data() -> None:
    path = ROOT / "scripts/build_data.py"
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "from towersignal.building_footprints import fetch_building_footprints_by_bin  # noqa: E402\n",
        "from towersignal.building_footprints import fetch_building_footprints_by_bin  # noqa: E402\n"
        "from towersignal.bbl_identity import apply_bbl_identity_recovery  # noqa: E402\n",
        "BBL identity import",
    )

    start = text.index('    bbl_values = {system["bbl"] for system in systems if system.get("bbl")}\n')
    end = text.index('    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")\n', start)
    replacement = '''    bin_values = {system["bin"] for system in systems if system.get("bin")}
    oath_ticket_numbers = summons_numbers_from_inspections(inspections_by_system)

    progress(f"Fetching OATH cases for {len(oath_ticket_numbers):,} summons tickets")
    oath_cases_by_ticket, oath_meta = fetch_oath_cases(oath_ticket_numbers)
    progress(f"Matched {len(oath_cases_by_ticket):,} OATH cases")

    progress(f"Fetching Planimetrics cooling-tower geometry for {len(bin_values):,} BINs")
    planimetric_by_bin, planimetric_meta = fetch_planimetric_towers_by_bin(bin_values)
    progress(f"Matched Planimetrics geometry for {len(planimetric_by_bin):,} BINs")

    progress(f"Fetching building footprints for {len(bin_values):,} BINs")
    building_footprints_by_bin, building_footprint_meta = fetch_building_footprints_by_bin(bin_values)
    progress(f"Matched building footprints for {len(building_footprints_by_bin):,} BINs")

    progress("Recovering missing registry BBL identity from exact-BIN published MapPLUTO BBLs")
    bbl_identity_meta = apply_bbl_identity_recovery(systems, building_footprints_by_bin)
    bbl_values = {system["bbl"] for system in systems if system.get("bbl")}
    progress(
        f"Canonical BBL identity: {bbl_identity_meta['canonical_bbl_count']:,}/{len(systems):,}; "
        f"{bbl_identity_meta['recovered_bbl_count']:,} recovered; "
        f"{bbl_identity_meta['unresolved_bbl_count']:,} unresolved"
    )

    progress(f"Fetching PLUTO context for {len(bbl_values):,} canonical BBLs")
    pluto_by_bbl, pluto_meta = fetch_pluto_by_bbl(bbl_values)
    progress(f"Matched PLUTO context for {len(pluto_by_bbl):,} BBLs")

    progress(f"Fetching DOB NOW activity for {len(bbl_values):,} canonical BBLs")
    dob_by_bbl, dob_meta = fetch_dob_activity_by_bbl(bbl_values)
    progress(f"Matched DOB NOW activity for {len(dob_by_bbl):,} BBLs")

    progress(f"Fetching HPD contacts for {len(bbl_values):,} canonical BBLs")
    hpd_by_bbl, hpd_meta = fetch_hpd_contacts_by_bbl(bbl_values)
    progress(f"Matched HPD contacts for {len(hpd_by_bbl):,} BBLs")

'''
    text = text[:start] + replacement + text[end:]

    text = replace_once(
        text,
        '        "building_footprint_match_basis": building_footprint_meta["match_basis"],\n        "rules_version": rules["rules_version"],\n',
        '        "building_footprint_match_basis": building_footprint_meta["match_basis"],\n'
        '        "bbl_registry_source_count": bbl_identity_meta["registry_source_bbl_count"],\n'
        '        "bbl_recovered_exact_bin_mappluto_count": bbl_identity_meta["recovered_bbl_count"],\n'
        '        "bbl_canonical_count": bbl_identity_meta["canonical_bbl_count"],\n'
        '        "bbl_unresolved_count": bbl_identity_meta["unresolved_bbl_count"],\n'
        '        "bbl_identity_recovery_contract": bbl_identity_meta["recovery_contract"],\n'
        '        "rules_version": rules["rules_version"],\n',
        "BBL metadata",
    )

    text = replace_once(
        text,
        '        row = {\n            "system_id": system["system_id"],\n            "bin": system["bin"],\n            "bbl": system["bbl"],\n            "address": system["address"],\n',
        '        row = {\n            "system_id": system["system_id"],\n            "bin": system["bin"],\n            "bbl": system["bbl"],\n            "registry_bbl": system.get("registry_bbl"),\n            "bbl_identity_basis": system.get("bbl_identity_basis"),\n            "bbl_identity_status": system.get("bbl_identity_status"),\n            "address": system["address"],\n',
        "summary identity provenance",
    )

    text = replace_once(
        text,
        '            "identity": {\n                "system_id": system["system_id"],\n                "bin": system["bin"],\n                "bbl": system["bbl"],\n                "address": system["address"],\n',
        '            "identity": {\n                "system_id": system["system_id"],\n                "bin": system["bin"],\n                "bbl": system["bbl"],\n                "registry_bbl": system.get("registry_bbl"),\n                "bbl_identity_basis": system.get("bbl_identity_basis"),\n                "bbl_identity_status": system.get("bbl_identity_status"),\n                "bbl_identity_evidence": system.get("bbl_identity_evidence"),\n                "address": system["address"],\n',
        "detail identity provenance",
    )

    text = replace_once(
        text,
        '            "systems_with_building_footprint_match": systems_with_building_footprint_match,\n        },\n',
        '            "systems_with_building_footprint_match": systems_with_building_footprint_match,\n'
        '            "systems_with_registry_source_bbl": bbl_identity_meta["registry_source_bbl_count"],\n'
        '            "systems_with_recovered_bbl": bbl_identity_meta["recovered_bbl_count"],\n'
        '            "systems_with_canonical_bbl": bbl_identity_meta["canonical_bbl_count"],\n'
        '            "systems_with_unresolved_bbl": bbl_identity_meta["unresolved_bbl_count"],\n'
        '        },\n',
        "BBL summary counts",
    )

    text = replace_once(
        text,
        '    print(f"Building-footprint exact BIN matches: {building_footprint_meta[\'matched_bin_count\']:,}/{building_footprint_meta[\'requested_bin_count\']:,}; {building_footprint_meta[\'matched_feature_count\']:,} footprint features")\n    print(f"Generated {len(summary_rows):,} systems at {generated_at}")\n',
        '    print(f"Building-footprint exact BIN matches: {building_footprint_meta[\'matched_bin_count\']:,}/{building_footprint_meta[\'requested_bin_count\']:,}; {building_footprint_meta[\'matched_feature_count\']:,} footprint features")\n'
        '    print(f"BBL identity: {bbl_identity_meta[\'registry_source_bbl_count\']:,} registry-source + {bbl_identity_meta[\'recovered_bbl_count\']:,} exact-BIN MapPLUTO recovered; {bbl_identity_meta[\'unresolved_bbl_count\']:,} unresolved")\n'
        '    print(f"Generated {len(summary_rows):,} systems at {generated_at}")\n',
        "BBL build report",
    )

    path.write_text(text, encoding="utf-8")


def patch_coverage_audit() -> None:
    path = ROOT / "scripts/build_coverage_audit.py"
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r"def _identifier_gap\(systems: list\[dict\[str, Any\]\]\) -> dict\[str, Any\]:\n.*?\n\ndef _storage", re.S)
    replacement = '''def _identifier_gap(systems: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(systems)

    def registry_bbl(row: dict[str, Any]) -> str | None:
        value = row.get("registry_bbl") if "registry_bbl" in row else row.get("bbl")
        return str(value) if value else None

    registry_bbls = [value for row in systems if (value := registry_bbl(row))]
    canonical_bbls = [str(row.get("bbl")) for row in systems if row.get("bbl")]
    usable_bin = [str(row.get("bin")) for row in systems if row.get("bin")]
    recovered = [row for row in systems if row.get("bbl_identity_status") == "RECOVERED_EXACT_BIN_MAPPLUTO_BBL"]

    by_borough: dict[str, dict[str, int]] = {}
    for row in systems:
        borough = str(row.get("borough") or "UNKNOWN")
        bucket = by_borough.setdefault(
            borough,
            {
                "systems": 0,
                "with_bbl": 0,
                "with_registry_source_bbl": 0,
                "with_canonical_bbl": 0,
                "recovered_bbl": 0,
                "with_bin": 0,
            },
        )
        source_bbl = registry_bbl(row)
        bucket["systems"] += 1
        bucket["with_bbl"] += int(bool(source_bbl))
        bucket["with_registry_source_bbl"] += int(bool(source_bbl))
        bucket["with_canonical_bbl"] += int(bool(row.get("bbl")))
        bucket["recovered_bbl"] += int(row.get("bbl_identity_status") == "RECOVERED_EXACT_BIN_MAPPLUTO_BBL")
        bucket["with_bin"] += int(bool(row.get("bin")))

    return {
        "systems": total,
        "with_bbl": len(registry_bbls),
        "missing_bbl": total - len(registry_bbls),
        "unique_bbl": len(set(registry_bbls)),
        "with_registry_source_bbl": len(registry_bbls),
        "missing_registry_source_bbl": total - len(registry_bbls),
        "with_canonical_bbl": len(canonical_bbls),
        "missing_canonical_bbl": total - len(canonical_bbls),
        "unique_canonical_bbl": len(set(canonical_bbls)),
        "recovered_bbl_count": len(recovered),
        "with_bin": len(usable_bin),
        "missing_bin": total - len(usable_bin),
        "unique_bin": len(set(usable_bin)),
        "bbl_semantics": {
            "with_bbl": "Registry-source BBL coverage; recovered identifiers do not inflate source completeness.",
            "with_canonical_bbl": "Canonical BBL available for exact downstream joins after conservative identity recovery.",
            "recovery": "Exact BIN to one unique published MapPLUTO BBL with borough-prefix reconciliation; no address or fuzzy matching.",
        },
        "by_borough": dict(sorted(by_borough.items())),
    }


def _storage'''
    patched, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError(f"coverage identifier-gap replacement expected one match, found {count}")
    path.write_text(patched, encoding="utf-8")


if __name__ == "__main__":
    patch_build_data()
    patch_coverage_audit()
