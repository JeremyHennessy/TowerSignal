import { describe, expect, it } from 'vitest'
import type { SystemSummary } from '../types/data'
import { domesticWaterPropertyKey, exactDomesticWaterProperty, indexDomesticWaterProperties, normalizeProspectPreset, type DomesticWaterPropertyObservation } from './prospectPreset'

const baseProperty: DomesticWaterPropertyObservation = {
  building_key: 'NYC-BIN-1234567', bin: '1234567', bbl: '1000010001', address: '1 TEST ST', borough: 'MANHATTAN', zip: '10001',
  inspection_count: 2, observed_tank_count: 1, observed_provider_ids: ['provider-1'], observed_lab_ids: ['lab-1'], latest_inspection_date: '2026-06-15', latest_reporting_year: '2026',
  current_observed_provider_id: 'provider-1', current_observed_provider_raw: 'Example Water LLC', current_observed_lab_id: 'lab-1', current_observed_lab_raw: 'Example Lab',
  compliance_activity_count: 1, violation_count: 0, latest_violation_date: null,
}

function row(bin: string | null, bbl: string | null): Pick<SystemSummary, 'bin' | 'bbl'> { return { bin, bbl } }

describe('prospect presets', () => {
  it('normalizes unknown preset values to Timing', () => {
    expect(normalizeProspectPreset('sales')).toBe('sales')
    expect(normalizeProspectPreset('field')).toBe('field')
    expect(normalizeProspectPreset('other')).toBe('timing')
    expect(normalizeProspectPreset(null)).toBe('timing')
  })

  it('uses exact BIN before BBL and never falls back from a present BIN to a BBL-only observation', () => {
    const bblOnly = { ...baseProperty, building_key: 'NYC-BBL-1000010001', bin: null }
    const index = indexDomesticWaterProperties([bblOnly])
    expect(domesticWaterPropertyKey(row('1234567', '1000010001'))).toBe('NYC-BIN-1234567')
    expect(exactDomesticWaterProperty(row('1234567', '1000010001'), index)).toBeNull()
    expect(exactDomesticWaterProperty(row(null, '1000010001'), index)).toEqual(bblOnly)
  })

  it('returns a unique exact BIN observation and rejects ambiguous duplicate building keys', () => {
    const exact = indexDomesticWaterProperties([baseProperty])
    expect(exactDomesticWaterProperty(row('1234567', '1000010001'), exact)?.current_observed_provider_raw).toBe('Example Water LLC')

    const ambiguous = indexDomesticWaterProperties([baseProperty, { ...baseProperty, current_observed_provider_raw: 'Other Water Co' }])
    expect(exactDomesticWaterProperty(row('1234567', '1000010001'), ambiguous)).toBeNull()
  })
})
