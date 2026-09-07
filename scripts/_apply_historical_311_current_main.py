from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text()
    if old not in text:
        raise SystemExit(f'patch target not found in {path}: {old[:100]!r}')
    file.write_text(text.replace(old, new, 1))

replace_once(
    'src/types/data.ts',
    "  nyc_lead_service_line_match_basis?: 'BBL_EXACT'\n  rules_version: string\n",
    "  nyc_lead_service_line_match_basis?: 'BBL_EXACT'\n  nyc_historical_311_context_available?: boolean\n  nyc_historical_311_match_basis?: 'BBL_EXACT'\n  nyc_historical_311_requested_bbl_count?: number\n  nyc_historical_311_matched_bbl_count?: number\n  nyc_historical_311_systems_attached?: number\n  nyc_historical_311_attached_request_count?: number\n  rules_version: string\n",
)
replace_once(
    'src/types/data.ts',
    "    systems_with_nyc_building_water_signals?: number\n    systems_with_nyc_lead_service_line_records?: number\n",
    "    systems_with_nyc_building_water_signals?: number\n    systems_with_nyc_historical_water_context?: number\n    systems_with_nyc_lead_service_line_records?: number\n",
)
interface_marker = "export interface HistoricalProfile {\n"
historical_interface = """export interface NycHistoricalWaterContext {
  summary: {
    bbl: string
    request_count: number
    category_counts: Record<string, number>
    years: string[]
    year_count: number
    first_reported_date: string | null
    latest_reported_date: string | null
    recurrent_history: boolean
    has_2024_activity: boolean
    property_link_confidence: 'CONFIRMED_SOURCE_BBL'
    evidence_semantics: 'REPORTED_SERVICE_REQUEST'
  }
  evidence_boundaries: {
    historical_not_current: string
    property_link: string
    raw_rows: string
    provider: string
  }
  source: {
    dataset_ids: string[]
    generated_at: string
    query_boundaries: Record<string, unknown>
  }
}

"""
replace_once('src/types/data.ts', interface_marker, historical_interface + interface_marker)
replace_once(
    'src/types/data.ts',
    "  nyc_building_water_signals?: NycBuildingWaterSignalsContext | null\n  nyc_lead_service_lines?: NycLeadServiceLineContext | null\n",
    "  nyc_building_water_signals?: NycBuildingWaterSignalsContext | null\n  nyc_historical_water_context?: NycHistoricalWaterContext | null\n  nyc_lead_service_lines?: NycLeadServiceLineContext | null\n",
)
replace_once(
    'src/components/DetailPanel.tsx',
    "import { BuildingWaterSignalsSection } from './BuildingWaterSignalsSection'\nimport { LeadServiceLineSection } from './LeadServiceLineSection'\n",
    "import { BuildingWaterSignalsSection } from './BuildingWaterSignalsSection'\nimport { HistoricalWaterContextSection } from './HistoricalWaterContextSection'\nimport { LeadServiceLineSection } from './LeadServiceLineSection'\n",
)
replace_once(
    'src/components/DetailPanel.tsx',
    "      <BuildingWaterSignalsSection detail={detail} />\n      <LeadServiceLineSection detail={detail} />\n",
    "      <BuildingWaterSignalsSection detail={detail} />\n      <HistoricalWaterContextSection detail={detail} />\n      <LeadServiceLineSection detail={detail} />\n",
)
replace_once(
    'src/components/AccountSectionNavigator.tsx',
    "  { label: 'Domestic water', selector: '.account-profile-page section.domestic-water-section' },\n  { label: 'Property & contacts', selector: '.account-profile-page section.property-context-section' },\n",
    "  { label: 'Domestic water', selector: '.account-profile-page section.domestic-water-section' },\n  { label: 'Water history', heading: 'Historical water context' },\n  { label: 'Property & contacts', selector: '.account-profile-page section.property-context-section' },\n",
)
replace_once(
    'scripts/build_coverage_audit.py',
    '    ("legacy_dob_projects", "legacy-dob-projects.json", "Exact canonical BBL; bounded explicit cooling-tower and recent relevant legacy project evidence; recorded roles only", ["WHEN_TO_ACT", "WHY_ACCOUNT_MATTERS"]),\n',
    '    ("legacy_dob_projects", "legacy-dob-projects.json", "Exact canonical BBL; bounded explicit cooling-tower and recent relevant legacy project evidence; recorded roles only", ["WHEN_TO_ACT", "WHY_ACCOUNT_MATTERS"]),\n    ("nyc_historical_311_context", "historical-311-context.json", "2010-2024 DEP building-water requests aggregated by current exact TowerSignal BBL; raw events omitted", ["WHY_ACCOUNT_MATTERS"]),\n',
)
replace_once(
    'scripts/build_coverage_audit.py',
    '            "gap_key": "NYC_311_HISTORICAL",\n            "classification": "DIAGNOSTIC_NOT_PRODUCTION_SCOPE",\n            "observed": {"current_production_window": "2025+", "historical_proof_pr": 106, "historical_candidate_window": "2010+"},\n            "interpretation": "PR #106 proves a broader 2010+ source history than the current production 2025+ commercial window. The extra depth is not equivalent to a current-source defect.",\n            "next_action": "Quantify whether older 311 history materially changes who to pursue, when to act, or why an account matters before accepting its runtime/storage cost.",\n',
    '            "gap_key": "NYC_311_HISTORICAL",\n            "classification": "BOUNDED_HISTORICAL_CONTEXT_INTEGRATED",\n            "observed": {"integrated": True, "current_signal_window": "2025+", "historical_context_window": "2010-2024", "commercial_lift_run": 34158852047, "historical_only_tower_bbl_count": 1908},\n            "interpretation": "Measured exact-BBL lift justified compact 2010-2024 building-water context for why an account matters. Historical requests remain explicitly separate from current signals and are not current-condition or timing evidence.",\n            "next_action": "Retain compact per-BBL counts/categories/years/dates only; no raw historical events, score changes, current trigger, fuzzy matching, or provider inference.",\n',
)
replace_once(
    'scripts/validate_coverage_audit.py',
    '    if historical_311.get("classification") != "DIAGNOSTIC_NOT_PRODUCTION_SCOPE":\n        raise RuntimeError("Historical 311 must remain diagnostic until commercial lift is measured")\n',
    '    if historical_311.get("classification") != "BOUNDED_HISTORICAL_CONTEXT_INTEGRATED" or (historical_311.get("observed") or {}).get("integrated") is not True:\n        raise RuntimeError("Historical 311 must remain a bounded exact-BBL context integration after measured commercial lift")\n',
)
replace_once(
    'tests/python/test_coverage_audit.py',
    '            self.assertEqual(gaps["NYC_311_HISTORICAL"]["observed"]["historical_proof_pr"], 106)\n',
    '            self.assertEqual(gaps["NYC_311_HISTORICAL"]["classification"], "BOUNDED_HISTORICAL_CONTEXT_INTEGRATED")\n            self.assertTrue(gaps["NYC_311_HISTORICAL"]["observed"]["integrated"])\n',
)
