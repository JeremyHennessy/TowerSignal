from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text()
    if old not in text:
        raise SystemExit(f'patch target not found in {path}: {old[:120]!r}')
    file.write_text(text.replace(old, new, 1))

replace_once(
    'src/types/data.ts',
    "  nyc_historical_311_attached_request_count?: number\n  rules_version: string\n",
    "  nyc_historical_311_attached_request_count?: number\n  cms_institutional_context_available?: boolean\n  cms_institutional_match_basis?: 'PAD_EXACT_ADDRESS_BBL'\n  cms_institutional_exact_resolved_facility_count?: number\n  cms_institutional_tower_overlap_facility_count?: number\n  cms_institutional_systems_attached?: number\n  cms_institutional_resolved_non_tower_bbl_count?: number\n  rules_version: string\n",
)
replace_once(
    'src/types/data.ts',
    "  nyc_lead_service_line_materials?: string[]\n}\n\nexport interface SystemsPayload",
    "  nyc_lead_service_line_materials?: string[]\n  cms_institutional_facility_count?: number\n  cms_institutional_facility_types?: string[]\n}\n\nexport interface SystemsPayload",
)
replace_once(
    'src/types/data.ts',
    "    systems_with_nyc_historical_water_context?: number\n    systems_with_nyc_lead_service_line_records?: number\n",
    "    systems_with_nyc_historical_water_context?: number\n    systems_with_cms_institutional_context?: number\n    systems_with_nyc_lead_service_line_records?: number\n",
)
marker = "export interface HistoricalProfile {\n"
interface = """export interface CmsInstitutionalContext {
  facilities: Array<{
    source_dataset_id: string
    source_facility_id: string
    source_kind: 'HOSPITAL' | 'NURSING_HOME'
    facility_name: string | null
    facility_type: string | null
    ownership_type: string | null
    chain_name: string | null
    bbl: string
    bin: string | null
    property_link_confidence: 'CONFIRMED_PAD_EXACT_ADDRESS_BBL'
  }>
  evidence_boundaries: {
    property_link: string
    facility: string
    non_tower: string
    provider: string
  }
  source: {
    datasets: Array<{ dataset_id: string; name: string; source_record_count: number }>
    property_resolution: string
  }
  generated_at: string
}

"""
replace_once('src/types/data.ts', marker, interface + marker)
replace_once(
    'src/types/data.ts',
    "  nyc_historical_water_context?: NycHistoricalWaterContext | null\n  nyc_lead_service_lines?: NycLeadServiceLineContext | null\n",
    "  nyc_historical_water_context?: NycHistoricalWaterContext | null\n  cms_institutional_context?: CmsInstitutionalContext | null\n  nyc_lead_service_lines?: NycLeadServiceLineContext | null\n",
)
replace_once(
    'src/components/DetailPanel.tsx',
    "import { HistoricalWaterContextSection } from './HistoricalWaterContextSection'\nimport { LeadServiceLineSection } from './LeadServiceLineSection'\n",
    "import { HistoricalWaterContextSection } from './HistoricalWaterContextSection'\nimport { InstitutionalFacilitySection } from './InstitutionalFacilitySection'\nimport { LeadServiceLineSection } from './LeadServiceLineSection'\n",
)
replace_once(
    'src/components/DetailPanel.tsx',
    "      <HistoricalWaterContextSection detail={detail} />\n      <LeadServiceLineSection detail={detail} />\n",
    "      <HistoricalWaterContextSection detail={detail} />\n      <InstitutionalFacilitySection detail={detail} />\n      <LeadServiceLineSection detail={detail} />\n",
)
replace_once(
    'src/components/AccountSectionNavigator.tsx',
    "  { label: 'Water history', heading: 'Historical water context' },\n  { label: 'Property & contacts', selector: '.account-profile-page section.property-context-section' },\n",
    "  { label: 'Water history', heading: 'Historical water context' },\n  { label: 'Institutional', heading: 'Institutional facility context' },\n  { label: 'Property & contacts', selector: '.account-profile-page section.property-context-section' },\n",
)
replace_once(
    'scripts/build_coverage_audit.py',
    '    ("nyc_historical_311_context", "historical-311-context.json", "2010-2024 DEP building-water requests aggregated by current exact TowerSignal BBL; raw events omitted", ["WHY_ACCOUNT_MATTERS"]),\n',
    '    ("nyc_historical_311_context", "historical-311-context.json", "2010-2024 DEP building-water requests aggregated by current exact TowerSignal BBL; raw events omitted", ["WHY_ACCOUNT_MATTERS"]),\n    ("cms_institutional_context", "cms-institutional-context.json", "CMS facility/provider identity joined only through exact NYC PAD address reconciliation to one BBL; tower-overlap accounts only", ["WHO_TO_PURSUE", "WHY_ACCOUNT_MATTERS"]),\n',
)
replace_once(
    'scripts/build_coverage_audit.py',
    '            "gap_key": "CMS",\n            "classification": "NOT_INTEGRATED_SOURCE_CONTRACT_REQUIRED",\n            "observed": {"integrated": False},\n            "interpretation": "No authoritative CMS dataset and exact TowerSignal join contract is currently integrated in the repository.",\n            "next_action": "Before ingestion, identify the exact CMS dataset, authoritative entity key, incremental matched population, freshness/runtime footprint, and a concrete who/when/why decision it improves. No fuzzy name/address attachment.",\n',
    '            "gap_key": "CMS",\n            "classification": "BOUNDED_EXACT_PROPERTY_CONTEXT_INTEGRATED",\n            "observed": {"integrated": True, "live_diagnostic_run": 34160957127, "nyc_candidate_facility_count": 210, "exact_resolved_facility_count": 116, "tower_overlap_facility_count": 47, "resolved_non_tower_bbl_count": 70},\n            "interpretation": "CMS hospitals and nursing homes are retained only when source facility identity resolves through exact NYC GeoSearch/PAD house number, normalized street, ZIP and one published BBL that overlaps the current TowerSignal tower universe.",\n            "next_action": "Use facility type, ownership and chain for who/why account qualification only. CMS-only resolved properties remain market-expansion context and cannot become tower prospects without independent tower evidence.",\n',
)
replace_once(
    'scripts/validate_coverage_audit.py',
    '    if cms.get("classification") != "NOT_INTEGRATED_SOURCE_CONTRACT_REQUIRED" or (cms.get("observed") or {}).get("integrated") is not False:\n        raise RuntimeError("CMS must remain explicitly not integrated until an authoritative source/join contract is proven")\n',
    '    if cms.get("classification") != "BOUNDED_EXACT_PROPERTY_CONTEXT_INTEGRATED" or (cms.get("observed") or {}).get("integrated") is not True:\n        raise RuntimeError("CMS must remain bounded exact-property context after the authoritative source/join contract was proven")\n',
)
replace_once(
    'tests/python/test_coverage_audit.py',
    '            self.assertEqual(gaps["CMS"]["classification"], "NOT_INTEGRATED_SOURCE_CONTRACT_REQUIRED")\n            self.assertFalse(gaps["CMS"]["observed"]["integrated"])\n',
    '            self.assertEqual(gaps["CMS"]["classification"], "BOUNDED_EXACT_PROPERTY_CONTEXT_INTEGRATED")\n            self.assertTrue(gaps["CMS"]["observed"]["integrated"])\n',
)
replace_once(
    'tests/python/test_coverage_audit.py',
    '    def test_validator_rejects_cms_promotion_without_source_contract(self):\n',
    '    def test_validator_rejects_cms_semantic_drift(self):\n',
)
replace_once(
    'tests/python/test_coverage_audit.py',
    '            cms["classification"] = "INTEGRATED"\n            cms["observed"]["integrated"] = True\n',
    '            cms["classification"] = "UNBOUNDED_CMS_PROSPECTS"\n            cms["observed"]["integrated"] = True\n',
)
