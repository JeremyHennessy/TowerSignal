import { describe, expect, it } from 'vitest'
import { filterSystems, initialFilters } from '../../src/components/Filters'
import type { SystemSummary } from '../../src/types/data'
import type { PropertyEnforcementSummaryFields } from '../../src/types/enforcement'

function row(systemId: string, hpdContactCount: number, enforcement: PropertyEnforcementSummaryFields = {}): SystemSummary {
  return {
    system_id: systemId,
    bin: null,
    bbl: null,
    address: `${systemId} MAIN ST`,
    borough: 'Manhattan',
    zip: '10001',
    active_equipment: 1,
    latitude: null,
    longitude: null,
    coordinate_status: 'MISSING',
    latest_sample_date: null,
    days_since_latest_sample: null,
    latest_inspection_date: null,
    latest_inspection_type: null,
    confirmed_violation: false,
    recent_confirmed_violation: false,
    violation_types: [],
    signal_types: [],
    primary_signal: 'NO_CURRENT_SIGNAL',
    evidence_confidence: 'STRONG_SIGNAL',
    priority_score: 0,
    score_components: [],
    oath_case_count: 0,
    pluto_match: true,
    hpd_contact_count: hpdContactCount,
    ...enforcement,
  } as SystemSummary
}

describe('HPD contact availability filtering', () => {
  const rows = [row('WITH-CONTACT', 3), row('WITHOUT-CONTACT', 0)]

  it('returns only systems with exact-matched HPD contact rows when requested', () => {
    expect(filterSystems(rows, { ...initialFilters, hpdContacts: 'true' }).map(item => item.system_id)).toEqual(['WITH-CONTACT'])
  })

  it('returns only systems without matched HPD contact rows when requested', () => {
    expect(filterSystems(rows, { ...initialFilters, hpdContacts: 'false' }).map(item => item.system_id)).toEqual(['WITHOUT-CONTACT'])
  })

  it('does not change the result set when the filter is unset', () => {
    expect(filterSystems(rows, initialFilters)).toHaveLength(2)
  })
})

describe('property enforcement filtering', () => {
  const rows = [
    row('ENFORCEMENT', 1, {
      hpd_open_violation_count: 4,
      stop_work_order_event_count: 2,
      facade_latest_status: 'UNSAFE',
    }),
    row('CLEAN', 1, {
      hpd_open_violation_count: 0,
      stop_work_order_event_count: 0,
      facade_latest_status: 'SAFE',
    }),
  ]

  it('filters to properties with source-published open HPD violations', () => {
    expect(filterSystems(rows, { ...initialFilters, hpdOpenViolations: 'true' }).map(item => item.system_id)).toEqual(['ENFORCEMENT'])
  })

  it('filters to properties with DOB SWO disposition evidence without inferring active status', () => {
    expect(filterSystems(rows, { ...initialFilters, stopWorkOrders: 'true' }).map(item => item.system_id)).toEqual(['ENFORCEMENT'])
  })

  it('filters by the latest published FISP status', () => {
    expect(filterSystems(rows, { ...initialFilters, facadeStatus: 'UNSAFE' }).map(item => item.system_id)).toEqual(['ENFORCEMENT'])
    expect(filterSystems(rows, { ...initialFilters, facadeStatus: 'SAFE' }).map(item => item.system_id)).toEqual(['CLEAN'])
  })
})
