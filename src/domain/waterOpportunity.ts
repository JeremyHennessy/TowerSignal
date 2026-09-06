import type { SystemSummary } from '../types/data'

export type WaterOpportunityFilter = '' | 'ANY_EVIDENCE' | 'MULTI_SOURCE' | 'OBSERVED_PROVIDER'

export type WaterOpportunityFields = {
  dwt_violation_record_count?: number
  dwt_market_exact_bin_match?: boolean
  dwt_market_inspection_count?: number
  dwt_market_observed_provider_count?: number
  dwt_market_current_provider_id?: string | null
  dwt_market_current_provider_raw?: string | null
  dwt_market_latest_inspection_date?: string | null
  dwt_market_observed_lab_count?: number
  dwt_market_current_lab_id?: string | null
  dwt_market_current_lab_raw?: string | null
  dwt_market_compliance_activity_count?: number
  dwt_market_violation_count?: number
  dwt_market_latest_violation_date?: string | null
}

export type WaterEnrichedSystemSummary = SystemSummary & WaterOpportunityFields

export type WaterEvidenceFamily =
  | 'DWT_VIOLATION'
  | 'SPECIFIC_BUILDING_WATER'
  | 'LEAD_SERVICE_LINE_REPLACEMENT'

const SPECIFIC_BUILDING_WATER_TYPES = new Set([
  'BUILDING_WATER_QUALITY',
  'BUILDING_NO_WATER_OR_PRESSURE',
  'DOMESTIC_WATER_STORAGE',
  'DOMESTIC_WATER_SYSTEM',
  'BACKFLOW_PREVENTION',
  'WATER_PUMP',
])

const REPLACEMENT_SERVICE_LINE_MATERIALS = new Set([
  'Lead',
  'Galvanized Service Line Requiring Replacement',
])

export function isSpecificBuildingWaterSignalType(value: string): boolean {
  return SPECIFIC_BUILDING_WATER_TYPES.has(value)
}

export function isReplacementServiceLineMaterial(value: string): boolean {
  return REPLACEMENT_SERVICE_LINE_MATERIALS.has(value)
}

export function specificBuildingWaterSignalTypes(row: SystemSummary): string[] {
  return [...new Set((row.nyc_building_water_signal_types ?? []).filter(isSpecificBuildingWaterSignalType))].sort()
}

export function replacementServiceLineMaterials(row: SystemSummary): string[] {
  return [...new Set((row.nyc_lead_service_line_materials ?? []).filter(isReplacementServiceLineMaterial))].sort()
}

export function waterEvidenceFamilies(row: SystemSummary): WaterEvidenceFamily[] {
  const water = row as WaterEnrichedSystemSummary
  const families: WaterEvidenceFamily[] = []
  if ((water.dwt_violation_record_count ?? 0) > 0 || (water.dwt_market_violation_count ?? 0) > 0) families.push('DWT_VIOLATION')
  if (specificBuildingWaterSignalTypes(row).length > 0) families.push('SPECIFIC_BUILDING_WATER')
  if (replacementServiceLineMaterials(row).length > 0) families.push('LEAD_SERVICE_LINE_REPLACEMENT')
  return families
}

export function waterEvidenceFamilyLabel(value: WaterEvidenceFamily): string {
  if (value === 'DWT_VIOLATION') return 'DWT violation activity'
  if (value === 'SPECIFIC_BUILDING_WATER') return 'Specific building-water signal'
  return 'Lead / replacement service line'
}

export function observedDwtProvider(row: SystemSummary): { id: string; name: string; observedDate: string | null } | null {
  const water = row as WaterEnrichedSystemSummary
  const id = water.dwt_market_current_provider_id?.trim()
  const name = water.dwt_market_current_provider_raw?.trim()
  if (!id || !name) return null
  return { id, name, observedDate: water.dwt_market_latest_inspection_date ?? null }
}

export function matchesWaterOpportunity(row: SystemSummary, filter: WaterOpportunityFilter): boolean {
  if (!filter) return true
  if (filter === 'OBSERVED_PROVIDER') return observedDwtProvider(row) !== null
  const familyCount = waterEvidenceFamilies(row).length
  if (filter === 'MULTI_SOURCE') return familyCount >= 2
  return familyCount >= 1
}

export function waterOpportunityLabel(row: SystemSummary): string {
  const provider = observedDwtProvider(row)
  const familyCount = waterEvidenceFamilies(row).length
  if (provider && familyCount > 0) return `${provider.name} · ${familyCount} specific ${familyCount === 1 ? 'family' : 'families'}`
  if (provider) return provider.name
  if (familyCount >= 2) return `${familyCount} specific water evidence families`
  if (familyCount === 1) return '1 specific water evidence family'
  return 'No specific water evidence'
}
