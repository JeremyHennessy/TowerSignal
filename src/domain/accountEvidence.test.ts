import { describe, expect, it } from 'vitest'
import type { ProcurementBundle, ProcurementRecord } from '../types/procurement'
import type { SystemDetailWithDomesticWater } from '../components/DomesticWaterSection'
import { collectAccountFirmRoleEvidence, explicitAccountProcurementRecords } from './accountEvidence'

function procurement(overrides: Partial<ProcurementRecord>): ProcurementRecord {
  return {
    schema_version: '1.0', procurement_id: 'p-base', source: 'TEST', source_record_id: 'source-base',
    service_category: 'WATER_TREATMENT', service_confidence: 'CONFIRMED', retrieved_at: '2026-09-17T00:00:00Z',
    ...overrides,
  }
}

describe('account evidence contracts', () => {
  it('keeps only explicit CONFIRMED/STRONG procurement links for the current system and deduplicates procurement ids', () => {
    const exact = procurement({ procurement_id: 'p-1', tower_account_system_ids: ['2000015564'], tower_link_confidence: 'CONFIRMED' })
    const duplicate = procurement({ procurement_id: 'p-1', source: 'OTHER', tower_account_system_ids: ['2000015564'], tower_link_confidence: 'STRONG' })
    const strong = procurement({ procurement_id: 'p-2', tower_account_system_ids: ['2000015564'], tower_link_confidence: 'STRONG' })
    const context = procurement({ procurement_id: 'p-3', tower_account_system_ids: ['2000015564'], tower_link_confidence: 'CONTEXT' })
    const other = procurement({ procurement_id: 'p-4', tower_account_system_ids: ['other-system'], tower_link_confidence: 'CONFIRMED' })
    const unlinked = procurement({ procurement_id: 'p-5', tower_account_system_ids: ['2000015564'], tower_link_confidence: 'UNLINKED' })
    const bundle = {
      cityRecord: { notices: [exact, context] },
      checkbook: { contracts: [duplicate, other] },
      nysAuthorities: { contracts: [strong] },
      openBookWater: { contracts: [unlinked] },
      nychaWater: { records: [] },
    } as unknown as ProcurementBundle

    expect(explicitAccountProcurementRecords(bundle, '2000015564').map(row => row.procurement_id)).toEqual(['p-1', 'p-2'])
  })

  it('preserves observed-service vs recorded-role evidence with exact dataset identity and never relabels the DOB owner as a service firm', () => {
    const detail = {
      identity: { bin: '1234567', bbl: '1000010001' },
      domestic_water: {
        self_report_history: [{
          bin: '1234567', tank_num: '1', reporting_year: '2026', inspection_date: '2026-06-15',
          inspection_by_firm: 'Example Water Services LLC', lab_name: 'Example Environmental Lab',
        }],
      },
      nyc_building_water_signals: {
        dob_water_job_filings: [{
          applicant_business_raw: 'Mechanical Project Co.', category: 'DOMESTIC_WATER_TANK', filing_date: '2026-04-20',
          source_record_id: 'DOB-WATER-1', property_link_confidence: 'CONFIRMED_SOURCE_BBL',
          relationship_evidence: 'RECORDED_DOB_ROLE', service_assignment_confidence: 'NOT_PROOF_OF_SERVICE_CONTRACT',
        }],
        dob_water_permits: [],
      },
      dob_activity_history: [{
        job_filing_number: 'M123', applicant_business_name: 'Mechanical Project Co.', owner_business_name: 'Building Owner LLC',
        explicit_cooling_tower_mention: true, mechanical_systems: true, boiler_equipment: false, activity_date: '2026-05-01',
        first_permit_date: null, approved_date: null, filing_date: '2026-04-01',
      }],
    } as unknown as SystemDetailWithDomesticWater

    const rows = collectAccountFirmRoleEvidence(detail)
    expect(rows.some(row => row.name === 'Building Owner LLC')).toBe(false)
    expect(rows.find(row => row.name === 'Example Water Services LLC')).toMatchObject({
      relationship: 'OBSERVED_SERVICE', datasetId: 'gjm4-k24g', matchBasis: 'BIN_EXACT', factClass: 'CONFIRMED_FACT', confidence: 'CONFIRMED',
    })
    expect(rows.find(row => row.name === 'Example Environmental Lab')).toMatchObject({
      relationship: 'OBSERVED_SERVICE', datasetId: 'gjm4-k24g', matchBasis: 'BIN_EXACT',
    })
    const mechanical = rows.filter(row => row.name === 'Mechanical Project Co.')
    expect(mechanical.length).toBeGreaterThanOrEqual(2)
    expect(mechanical.every(row => row.relationship === 'RECORDED_ROLE' && row.matchBasis === 'BBL_EXACT')).toBe(true)
    expect(new Set(mechanical.map(row => row.datasetId))).toEqual(new Set(['w9ak-ipjd']))
    expect(mechanical.map(row => row.serviceAssignmentBoundary).join(' ')).toMatch(/not proof/i)
  })

  it('labels DOB building-water role evidence with the actual exact source key', () => {
    const detail = {
      identity: { bin: '1087293', bbl: '1013730040' },
      domestic_water: { self_report_history: [] },
      nyc_building_water_signals: {
        dob_water_job_filings: [{
          applicant_business_raw: 'Reform Architecture PLLC',
          category: 'PLUMBING_WATER_RELATED',
          filing_date: '2026-04-20',
          source_record_id: 'M01287692-S1',
          bin: '1087293',
          bbl: null,
          property_link_confidence: 'CONFIRMED_SOURCE_BIN',
          relationship_evidence: 'RECORDED_DOB_ROLE',
          service_assignment_confidence: 'NOT_PROOF_OF_SERVICE_CONTRACT',
        }],
        dob_water_permits: [{
          applicant_business_raw: 'Exact BBL Plumbing LLC',
          category: 'PLUMBING_WATER_RELATED',
          issued_date: '2026-05-01',
          source_record_id: 'P-BBL-1',
          bin: null,
          bbl: '1013730040',
          property_link_confidence: 'CONFIRMED_SOURCE_BBL',
          relationship_evidence: 'RECORDED_DOB_ROLE',
          service_assignment_confidence: 'NOT_PROOF_OF_SERVICE_CONTRACT',
        }],
      },
      dob_activity_history: [],
    } as unknown as SystemDetailWithDomesticWater

    const rows = collectAccountFirmRoleEvidence(detail)
    expect(rows.find(row => row.name === 'Reform Architecture PLLC')).toMatchObject({
      matchBasis: 'BIN_EXACT',
      sourceReference: expect.stringContaining('exact BIN'),
    })
    expect(rows.find(row => row.name === 'Exact BBL Plumbing LLC')).toMatchObject({
      matchBasis: 'BBL_EXACT',
      sourceReference: expect.stringContaining('exact BBL'),
    })
  })

})
