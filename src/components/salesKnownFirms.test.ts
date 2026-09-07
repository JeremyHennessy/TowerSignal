import { describe, expect, it } from 'vitest'
import type { SystemDetailWithDomesticWater } from './DomesticWaterSection'
import { collectKnownAccountFirms } from './salesKnownFirms'

describe('collectKnownAccountFirms', () => {
  it('combines exact-asset inspection and laboratory evidence with recorded DOB roles without inferring incumbency', () => {
    const detail = {
      domestic_water: {
        self_report_history: [
          {
            inspection_by_firm: 'Example Water Services LLC',
            lab_name: 'Example Environmental Lab',
            inspection_date: '2026-06-15',
            reporting_year: '2026',
          },
          {
            inspection_by_firm: 'example water services llc',
            lab_name: 'Example Environmental Lab',
            inspection_date: '2025-06-10',
            reporting_year: '2025',
          },
          {
            inspection_by_firm: 'N/A',
            lab_name: 'UNKNOWN',
            inspection_date: '2026-01-01',
            reporting_year: '2026',
          },
        ],
      },
      nyc_building_water_signals: {
        dob_water_job_filings: [
          {
            applicant_business_raw: 'Mechanical Project Co.',
            category: 'DOMESTIC_WATER_TANK',
            filing_date: '2026-04-20',
            relationship_evidence: 'RECORDED_DOB_ROLE',
            service_assignment_confidence: 'NOT_PROOF_OF_SERVICE_CONTRACT',
          },
        ],
        dob_water_permits: [],
      },
      dob_activity_history: [
        {
          applicant_business_name: 'Mechanical Project Co.',
          owner_business_name: 'Building Owner LLC',
          explicit_cooling_tower_mention: true,
          mechanical_systems: true,
          boiler_equipment: false,
          activity_date: '2026-05-01',
          first_permit_date: null,
          approved_date: null,
          filing_date: '2026-04-01',
        },
      ],
    } as unknown as SystemDetailWithDomesticWater

    const firms = collectKnownAccountFirms(detail)

    expect(firms.map(firm => firm.name)).toEqual([
      'Example Environmental Lab',
      'Example Water Services LLC',
      'Mechanical Project Co.',
    ])

    const inspectionFirm = firms.find(firm => firm.key === 'EXAMPLE WATER SERVICES LLC')
    expect(inspectionFirm).toMatchObject({
      latestObservedDate: '2026-06-15',
      relationship: 'OBSERVED_SERVICE',
    })
    expect(inspectionFirm?.roles).toContain('Drinking-water tank inspection firm')

    const laboratory = firms.find(firm => firm.key === 'EXAMPLE ENVIRONMENTAL LAB')
    expect(laboratory).toMatchObject({
      latestObservedDate: '2026-06-15',
      relationship: 'OBSERVED_SERVICE',
    })
    expect(laboratory?.roles).toContain('Drinking-water testing laboratory')

    const dobFirm = firms.find(firm => firm.key === 'MECHANICAL PROJECT CO.')
    expect(dobFirm?.relationship).toBe('RECORDED_ROLE')
    expect(dobFirm?.latestObservedDate).toBe('2026-05-01')
    expect(dobFirm?.roles).toEqual(expect.arrayContaining([
      'Cooling-tower filing applicant business',
      'DOB Domestic water tank applicant business',
    ]))
    expect(dobFirm?.evidence.join(' ')).toMatch(/not proof/i)

    expect(firms.some(firm => firm.name === 'Building Owner LLC')).toBe(false)
    expect(firms.some(firm => firm.name === 'N/A')).toBe(false)
  })
})
