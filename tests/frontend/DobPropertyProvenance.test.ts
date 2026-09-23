import { describe, expect, it } from 'vitest'
import { collectAccountFirmRoleEvidence } from '../../src/domain/accountEvidence'
import { collectKnownAccountFirms } from '../../src/components/salesKnownFirms'
import type { SystemDetailWithDomesticWater } from '../../src/components/DomesticWaterSection'

function fixture(propertyLink: 'CONFIRMED_SOURCE_BIN' | 'CONFIRMED_SOURCE_BBL'): SystemDetailWithDomesticWater {
  return {
    identity: { system_id: 'audit', bin: '1001234', bbl: '1001230001' },
    domestic_water: null,
    nyc_building_water_signals: {
      summary: {
        record_count: 1,
        water_311_building_signal_count: 0,
        hpd_open_water_violation_count: 0,
        dob_water_job_filing_count: 1,
        dob_water_permit_count: 0,
        ll84_water_benchmark_count: 0,
        dob_applicant_business_count: 1,
        category_counts: {},
        latest_observation_date: '2026-01-02',
      },
      water_311_requests: [],
      hpd_open_water_violations: [],
      dob_water_job_filings: [{
        activity_id: 'a1',
        source_record_id: 'J1',
        applicant_business_raw: 'ACME WATER LLC',
        category: 'DOMESTIC_WATER_SYSTEM',
        property_link_confidence: propertyLink,
        relationship_evidence: 'RECORDED_DOB_ROLE',
        service_assignment_confidence: 'NOT_PROOF_OF_SERVICE_CONTRACT',
        filing_date: '2026-01-02',
      }],
      dob_water_permits: [],
      ll84_water_benchmarks: [],
      evidence_boundaries: { property_link: '', roles: '', ll84: '' },
      source: { dataset_ids: ['w9ak-ipjd'], source_record_count: 1, generated_at: '2026-01-02T00:00:00Z', query_boundaries: {} },
    },
    dob_activity_history: [],
  } as unknown as SystemDetailWithDomesticWater
}

describe('DOB property provenance', () => {
  it('keeps BIN-linked water-work roles labelled as exact BIN', () => {
    const detail = fixture('CONFIRMED_SOURCE_BIN')
    const role = collectAccountFirmRoleEvidence(detail)[0]
    expect(role.matchBasis).toBe('BIN_EXACT')
    expect(role.sourceReference).toContain('exact BIN')
    expect(role.sourceReference).not.toContain('exact BBL')
    expect(collectKnownAccountFirms(detail)[0].evidence.join(' ')).toContain('exact BIN')
  })

  it('keeps BBL-linked water-work roles labelled as exact BBL', () => {
    const detail = fixture('CONFIRMED_SOURCE_BBL')
    const role = collectAccountFirmRoleEvidence(detail)[0]
    expect(role.matchBasis).toBe('BBL_EXACT')
    expect(role.sourceReference).toContain('exact BBL')
    expect(collectKnownAccountFirms(detail)[0].evidence.join(' ')).toContain('exact BBL')
  })
})
