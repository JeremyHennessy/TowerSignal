import type { AcrisSummaryFields } from '../types/acris'
import type { SystemSummary } from '../types/data'
import type { PropertyEnforcementSummaryFields } from '../types/enforcement'
import type { DomesticWaterMarketPayload } from '../types/water'

export type ProspectPreset = 'timing' | 'sales' | 'field'

export const prospectPresets: Array<{ value: ProspectPreset; label: string; detail: string }> = [
  { value: 'timing', label: 'Timing', detail: 'Why now: score, sampling and regulatory activity' },
  { value: 'sales', label: 'Sales', detail: 'Who and what: contacts, property scale and observed firms' },
  { value: 'field', label: 'Field', detail: 'What is on site: equipment, water assets and enforcement context' },
]

export function normalizeProspectPreset(value: unknown): ProspectPreset {
  return value === 'sales' || value === 'field' ? value : 'timing'
}

export interface DomesticWaterPropertyObservation {
  building_key: string
  bin: string | null
  bbl: string | null
  address: string | null
  borough: string | null
  zip: string | null
  inspection_count: number
  observed_tank_count: number
  observed_provider_ids: string[]
  observed_lab_ids: string[]
  latest_inspection_date: string | null
  latest_reporting_year: string | null
  current_observed_provider_id: string | null
  current_observed_provider_raw: string | null
  current_observed_lab_id: string | null
  current_observed_lab_raw: string | null
  compliance_activity_count: number
  violation_count: number
  latest_violation_date: string | null
}

export type DomesticWaterMarketWithProperties = DomesticWaterMarketPayload & {
  properties?: DomesticWaterPropertyObservation[]
}

export type ProspectSystemSummary = SystemSummary & AcrisSummaryFields & PropertyEnforcementSummaryFields & {
  dwt_planimetric_bin_match?: boolean
  dwt_planimetric_tank_count?: number
  dwt_compliance_record_count?: number
  dwt_self_report_record_count?: number
  dwt_latest_status?: string | null
  dwt_latest_reported_tank_count?: number | null
  dwt_latest_activity_type?: string | null
  dwt_latest_activity_year?: string | null
  dwt_latest_self_report_inspection_date?: string | null
  dwt_violation_record_count?: number
}

export function domesticWaterPropertyKey(row: Pick<SystemSummary, 'bin' | 'bbl'>): string | null {
  const bin = String(row.bin ?? '').trim()
  if (/^\d{7}$/.test(bin)) return `NYC-BIN-${bin}`
  const bbl = String(row.bbl ?? '').trim()
  if (/^\d{10}$/.test(bbl)) return `NYC-BBL-${bbl}`
  return null
}

export function indexDomesticWaterProperties(properties: DomesticWaterPropertyObservation[]): Map<string, DomesticWaterPropertyObservation | null> {
  const byKey = new Map<string, DomesticWaterPropertyObservation | null>()
  for (const property of properties) {
    if (!/^NYC-(BIN-\d{7}|BBL-\d{10})$/.test(property.building_key)) continue
    if (byKey.has(property.building_key)) byKey.set(property.building_key, null)
    else byKey.set(property.building_key, property)
  }
  return byKey
}

export function exactDomesticWaterProperty(
  row: Pick<SystemSummary, 'bin' | 'bbl'>,
  index: Map<string, DomesticWaterPropertyObservation | null>,
): DomesticWaterPropertyObservation | null {
  const key = domesticWaterPropertyKey(row)
  return key ? index.get(key) ?? null : null
}
