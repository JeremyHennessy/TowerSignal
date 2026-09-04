from __future__ import annotations

from pathlib import Path


def replace_once(path_name: str, old: str, new: str) -> None:
    path = Path(path_name)
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Patch anchor changed: {path_name}: {old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    app_sources = "scripts/toronto_app_sources.py"
    replace_once(
        app_sources,
        '    "toronto_building_permits_cleared_targeted_since_2017": "https://open.toronto.ca/dataset/building-permits-cleared-permits/",\n    "toronto_public_notices_exact_prior_poc": "https://open.toronto.ca/dataset/public-notices/",',
        '    "toronto_building_permits_cleared_targeted_since_2017": "https://open.toronto.ca/dataset/building-permits-cleared-permits/",\n    "tdsb_facility_condition_renewal": "https://www.tdsb.on.ca/Community/Planning/School-Facilities/Facility-Condition-Index",\n    "toronto_public_notices_exact_prior_poc": "https://open.toronto.ca/dataset/public-notices/",',
    )
    replace_once(
        app_sources,
        '    "www.toronto.ca",\n}',
        '    "www.toronto.ca",\n    "www.tdsb.on.ca",\n}',
    )
    replace_once(
        app_sources,
        '        "toronto_building_permits_cleared_targeted_since_2017": warehouse / "open_licensed/toronto_building_permits_cleared_targeted_since_2017.json",\n        "toronto_public_notices_exact_prior_poc": warehouse / "open_licensed/toronto_public_notices.json",',
        '        "toronto_building_permits_cleared_targeted_since_2017": warehouse / "open_licensed/toronto_building_permits_cleared_targeted_since_2017.json",\n        "tdsb_facility_condition_renewal": warehouse / "open_licensed/tdsb_facility_condition_renewal.json",\n        "toronto_public_notices_exact_prior_poc": warehouse / "open_licensed/toronto_public_notices.json",',
    )

    public_notice_anchor = '    elif key == "toronto_public_notices_exact_prior_poc":\n'
    tdsb_projection = (
        '    elif key == "tdsb_facility_condition_renewal":\n'
        '        record_url = valid_public_url(row.get("school_page_url"))\n'
        '        signals = ", ".join(str(value).replace("_", " ") for value in (row.get("signals") or []))\n'
        '        priority = text(row.get("priority"))\n'
        '        result.update(\n'
        '            dataset_link_label="Open TDSB facility condition source",\n'
        '            record_url=record_url,\n'
        '            record_link_label="Open official TDSB facility condition page" if record_url else None,\n'
        '            record_title=text(row.get("school_name")),\n'
        '            record_date=None,\n'
        '            record_status=f"{priority.title()} priority renewal" if priority else "Published renewal evidence",\n'
        '            record_details=details(\n'
        '                ("School number", row.get("school_id")),\n'
        '                ("Published school address", row.get("published_address")),\n'
        '                ("Renewal priority", row.get("priority")),\n'
        '                ("Mechanical signals", signals),\n'
        '                ("Renewal scope", row.get("renewal_text")),\n'
        '            ),\n'
        '        )\n'
    )
    replace_once(app_sources, public_notice_anchor, tdsb_projection + public_notice_anchor)

    replace_once(
        "scripts/audit_toronto_source_row_resolution.py",
        '    "toronto_building_permits_cleared_targeted_since_2017": ("_towersignal_source_address",),\n    "renewable_energy_installations": ("CLIENT_ADDRESS", "ADDRESS_FULL"),',
        '    "toronto_building_permits_cleared_targeted_since_2017": ("_towersignal_source_address",),\n    "tdsb_facility_condition_renewal": ("_towersignal_source_address",),\n    "renewable_energy_installations": ("CLIENT_ADDRESS", "ADDRESS_FULL"),',
    )

    replace_once(
        "src/components/TorontoMarketPage.tsx",
        "  toronto_building_permits_cleared_targeted_since_2017: 'Toronto cleared building permits',\n  ontario_environmental_compliance_reports: 'Ontario environmental compliance',",
        "  toronto_building_permits_cleared_targeted_since_2017: 'Toronto cleared building permits',\n  tdsb_facility_condition_renewal: 'TDSB facility condition renewals',\n  ontario_environmental_compliance_reports: 'Ontario environmental compliance',",
    )


if __name__ == "__main__":
    main()
