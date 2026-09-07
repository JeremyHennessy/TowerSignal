from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def patch_detail_panel() -> None:
    path = ROOT / "src/components/DetailPanel.tsx"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "import { LeadServiceLineSection } from './LeadServiceLineSection'\n",
        "import { LeadServiceLineSection } from './LeadServiceLineSection'\nimport { LegacyDobProjectSection } from './LegacyDobProjectSection'\n",
        "DetailPanel legacy component import",
    )
    text = replace_once(
        text,
        "        <AcrisActivitySection row={row} detail={detail} metadata={metadata} />\n",
        "        <LegacyDobProjectSection detail={detail} />\n        <AcrisActivitySection row={row} detail={detail} metadata={metadata} />\n",
        "DetailPanel legacy component placement",
    )
    path.write_text(text, encoding="utf-8")


def patch_source_health() -> None:
    path = ROOT / "scripts/build_source_health.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "    building_footprint_systems = sum(1 for row in systems if bool(row.get(\"building_footprint_bin_match\")))\n",
        "    building_footprint_systems = sum(1 for row in systems if bool(row.get(\"building_footprint_bin_match\")))\n"
        "    legacy_dob_systems = sum(1 for row in systems if int(row.get(\"legacy_dob_project_record_count\") or 0) > 0)\n",
        "legacy DOB attached-system count",
    )
    text = replace_once(
        text,
        "    dob = sources.get(\"w9ak-ipjd\", {})\n",
        "    dob = sources.get(\"w9ak-ipjd\", {})\n    legacy_dob = sources.get(\"ic3t-wcy2\", {})\n",
        "legacy DOB source metadata",
    )
    anchor = '''        health_entry(source_key="dob_now_jobs", dataset_id=str(dob.get("dataset_id") or "w9ak-ipjd"), name=str(dob.get("name") or "DOB NOW: Build – Job Application Filings"), entity_unit="BBLs with DOB NOW job filings", retrieved_record_count=int(dob.get("source_record_count") or 0), requested_entity_count=int(metadata.get("dob_requested_bbl_count") or 0), normalized_entity_count=int(metadata.get("dob_matched_bbl_count") or 0), matched_entity_count=int(metadata.get("dob_matched_bbl_count") or 0), attached_entity_count=dob_systems, displayed_entity_count=dob_systems, previous_coverage_percentage=previous_coverage("dob_now_jobs"), coverage_note="Coverage is exact BBL job-filing coverage. A missing DOB NOW match means no matching DOB NOW job filing was returned; it is not evidence that no construction or mechanical work ever occurred."),
'''
    addition = anchor + '''        health_entry(
            source_key="legacy_dob_jobs",
            dataset_id=str(legacy_dob.get("dataset_id") or "ic3t-wcy2"),
            name=str(legacy_dob.get("name") or "DOB Job Application Filings"),
            entity_unit="canonical BBLs with bounded legacy project evidence",
            retrieved_record_count=int(metadata.get("legacy_dob_project_exact_bbl_job_count") or 0),
            requested_entity_count=int(metadata.get("legacy_dob_project_requested_bbl_count") or 0),
            normalized_entity_count=int(metadata.get("legacy_dob_project_retained_record_count") or 0),
            matched_entity_count=int(metadata.get("legacy_dob_project_retained_bbl_count") or 0),
            attached_entity_count=legacy_dob_systems,
            displayed_entity_count=legacy_dob_systems,
            previous_coverage_percentage=previous_coverage("legacy_dob_jobs"),
            coverage_note=(
                "Coverage is prevalence of bounded exact-BBL legacy DOB/BIS evidence: all explicit cooling-tower text plus recent mechanical/boiler/plumbing/equipment project records. "
                "It is not expected-completeness coverage and recorded applicants/owners are project roles, not service-provider claims."
            ),
        ),
'''
    text = replace_once(text, anchor, addition, "legacy DOB source-health entry")
    path.write_text(text, encoding="utf-8")


def patch_coverage_audit() -> None:
    path = ROOT / "scripts/build_coverage_audit.py"
    text = path.read_text(encoding="utf-8")
    anchor = '    ("nyc_building_water_signals", "nyc-water-signals.json", "Exact source BBL/BIN where published; context-only records remain unlinked", ["WHEN_TO_ACT", "WHY_ACCOUNT_MATTERS"]),\n'
    addition = anchor + '    ("legacy_dob_projects", "legacy-dob-projects.json", "Exact canonical BBL; bounded explicit cooling-tower and recent relevant legacy project evidence; recorded roles only", ["WHEN_TO_ACT", "WHY_ACCOUNT_MATTERS"]),\n'
    text = replace_once(text, anchor, addition, "coverage artifact contract")
    path.write_text(text, encoding="utf-8")


def patch_pages_workflow() -> None:
    path = ROOT / ".github/workflows/pages.yml"
    text = path.read_text(encoding="utf-8")
    anchor = '''      - name: Fetch, validate and generate current NYC data
        timeout-minutes: 45
        run: python scripts/build_data.py --output public/data
'''
    addition = anchor + '''      - name: Build bounded legacy DOB/BIS project context
        timeout-minutes: 15
        run: python scripts/build_legacy_dob_project_cache.py --output public/data
      - name: Validate bounded legacy DOB/BIS project context
        run: python scripts/validate_legacy_dob_project_cache.py --cache public/data/legacy-dob-projects.json --max-age-days 1 --require-production-volume
      - name: Attach exact-BBL legacy DOB/BIS project context
        run: python scripts/attach_legacy_dob_project_context.py --output public/data --cache public/data/legacy-dob-projects.json
'''
    text = replace_once(text, anchor, addition, "Pages legacy DOB steps")
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    patch_detail_panel()
    patch_source_health()
    patch_coverage_audit()
    patch_pages_workflow()
