import { describe, expect, it } from 'vitest'
import { filterSystems, initialFilters } from '../../src/components/Filters'
import type { SystemSummary } from '../../src/types/data'

function row(systemId: string, hpdContactCount: number): SystemSummary {
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
  }
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
