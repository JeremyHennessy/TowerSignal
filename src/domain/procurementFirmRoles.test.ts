import { describe, expect, it } from 'vitest'
import type { ProcurementRecord } from '../types/procurement'
import { collectProcurementFirmRoleEvidence } from './procurementFirmRoles'

function record(overrides: Partial<ProcurementRecord>): ProcurementRecord {
  return {
    schema_version: '1.0',
    procurement_id: 'proc-1',
    source: 'NYC_CHECKBOOK',
    source_record_id: 'source-1',
    service_category: 'WATER_TREATMENT',
    service_confidence: 'CONFIRMED',
    retrieved_at: '2026-09-17T00:00:00Z',
    ...overrides,
  }
}

describe('procurement firm role evidence', () => {
  it('retains only explicit CONFIRMED/STRONG account-linked vendor records and never creates a name-only relationship', () => {
    const rows = collectProcurementFirmRoleEvidence([
      record({ procurement_id: 'confirmed', vendor_raw: 'Exact Water LLC', company_id: 'company-1', tower_account_system_ids: ['2000015564'], tower_link_confidence: 'CONFIRMED', status: 'AWARDED', award_date: '2026-06-01', source_url: 'https://example.test/confirmed' }),
      record({ procurement_id: 'strong', vendor_raw: 'Strong Mechanical Inc', tower_account_system_ids: ['2000015564'], tower_link_confidence: 'STRONG', start_date: '2026-05-01' }),
      record({ procurement_id: 'context', vendor_raw: 'Context Vendor', tower_account_system_ids: ['2000015564'], tower_link_confidence: 'CONTEXT' }),
      record({ procurement_id: 'unlinked', vendor_raw: 'Exact Water LLC', tower_account_system_ids: [], tower_link_confidence: 'UNLINKED' }),
      record({ procurement_id: 'no-vendor', vendor_raw: null, tower_account_system_ids: ['2000015564'], tower_link_confidence: 'CONFIRMED' }),
    ])

    expect(rows.map(row => row.key)).toEqual(['procurement::confirmed', 'procurement::strong'])
    expect(rows[0]).toMatchObject({
      name: 'Exact Water LLC',
      role: 'Awarded / contracted vendor',
      relationship: 'CONTRACT_AWARD_EVIDENCE',
      factClass: 'CONFIRMED_FACT',
      confidence: 'CONFIRMED',
      matchBasis: 'SYSTEM_ID_EXPLICIT',
      companyIdentity: 'company-1',
    })
    expect(rows[0].sourceUrls).toEqual(['https://example.test/confirmed'])
    expect(rows[0].serviceAssignmentBoundary).toMatch(/no relationship is created from name or mailing-address similarity/i)
    expect(rows[1]).toMatchObject({ name: 'Strong Mechanical Inc', confidence: 'STRONG_SIGNAL' })
  })
})
