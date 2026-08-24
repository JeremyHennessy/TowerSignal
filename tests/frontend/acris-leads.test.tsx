import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { Filters, filterSystems, initialFilters } from '../../src/components/Filters'
import { SystemTable } from '../../src/components/SystemTable'
import type { SystemSummary } from '../../src/types/data'
import type { AcrisSummaryFields } from '../../src/types/acris'

type EnrichedSystemSummary = SystemSummary & AcrisSummaryFields

function row(systemId: string, address: string, priority: number, acrisCount: number, acrisDate: string | null): EnrichedSystemSummary {
  return {
    system_id: systemId,
    bin: systemId,
    bbl: systemId,
    address,
    borough: 'Manhattan',
    zip: '10001',
    active_equipment: 1,
    latitude: 40.75,
    longitude: -73.99,
    coordinate_status: 'VALID',
    registration_date: '2020-01-01',
    sample_count: 1,
    inspection_count: 0,
    violation_citation_count: 0,
    latest_violation_date: null,
    oath_balance_due_total: 0,
    latest_sample_date: '2026-08-01',
    days_since_latest_sample: 23,
    latest_inspection_date: null,
    latest_inspection_type: null,
    confirmed_violation: false,
    recent_confirmed_violation: false,
    violation_types: [],
    signal_types: [],
    primary_signal: 'NO_CURRENT_SIGNAL',
    evidence_confidence: 'STRONG_SIGNAL',
    priority_score: priority,
    score_components: [],
    oath_case_count: 0,
    pluto_match: false,
    dob_activity_count: 0,
    dob_recent_activity_count: 0,
    dob_explicit_cooling_tower_count: 0,
    dob_mechanical_or_boiler_count: 0,
    latest_dob_activity_date: null,
    hpd_contact_count: 0,
    acris_recent_document_count: acrisCount,
    latest_acris_recorded_date: acrisDate,
    acris_deed_count: 0,
    acris_mortgage_count: acrisCount,
    acris_lease_count: 0,
    acris_recorded_party_count: acrisCount * 2,
  }
}

const recent = row('1000000001', '10 ALPHA ST', 10, 3, '2026-08-20')
const quiet = row('1000000002', '20 BETA AVE', 90, 0, null)

test('recent ACRIS filter selects only systems with exact-BBL cached activity', () => {
  const result = filterSystems([recent, quiet], { ...initialFilters, acrisActivity: 'true' })
  expect(result.map(item => item.system_id)).toEqual([recent.system_id])
})

test('commercial filter rail exposes ACRIS only when verified cache is available', async () => {
  const user = userEvent.setup()
  const onQuick = vi.fn()
  const { rerender } = render(<Filters rows={[recent, quiet]} value={initialFilters} onChange={vi.fn()} onQuick={onQuick} acrisAvailable={true} />)
  await user.click(screen.getByRole('button', { name: 'Recent ACRIS activity' }))
  expect(onQuick).toHaveBeenCalledWith('Recent ACRIS activity')
  expect(screen.getByLabelText('ACRIS recorded activity')).toBeEnabled()

  rerender(<Filters rows={[recent, quiet]} value={initialFilters} onChange={vi.fn()} onQuick={onQuick} acrisAvailable={false} />)
  expect(screen.queryByRole('button', { name: 'Recent ACRIS activity' })).not.toBeInTheDocument()
  expect(screen.getByLabelText('ACRIS recorded activity')).toBeDisabled()
})

test('commercial account table surfaces ACRIS inside the existing Activity column', () => {
  render(<SystemTable rows={[quiet, recent]} onSelect={vi.fn()} />)
  expect(screen.getByText('ACRIS · 3')).toBeInTheDocument()
  expect(screen.getByText('10 ALPHA ST')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Activity' })).toBeInTheDocument()
})
