import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import { PortfoliosPage } from '../../src/components/PortfoliosPage'
import type { SystemSummary, SystemsPayload } from '../../src/types/data'

function row(system_id: string, owner: string): SystemSummary {
  return {
    system_id,
    bin: system_id,
    bbl: system_id,
    address: `${system_id} TEST ST`,
    borough: 'Manhattan',
    zip: '10001',
    active_equipment: 1,
    latitude: 40.7,
    longitude: -73.9,
    coordinate_status: 'VALID',
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
    priority_score: 20,
    score_components: [],
    pluto_match: true,
    pluto_owner_name: owner,
    pluto_building_area_sqft: 100000,
    hpd_contact_count: 0,
  }
}

const payload = {
  metadata: { source_health: [] },
  systems: [
    row('A1', 'UNAVAILABLE OWNER'),
    row('A2', 'UNAVAILABLE OWNER'),
    row('B1', 'REAL OWNER LLC'),
    row('B2', 'REAL OWNER LLC'),
  ],
} as unknown as SystemsPayload

beforeEach(() => { window.location.hash = '#/portfolios' })

test('excludes placeholder PLUTO owner values and deep-links a selected portfolio group', async () => {
  const user = userEvent.setup()
  render(<PortfoliosPage payload={payload} watchedSystemIds={new Set()} onOpenAccount={vi.fn()} />)

  expect(screen.queryByText('UNAVAILABLE OWNER')).not.toBeInTheDocument()
  expect(screen.getByText('1 multi-property group')).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: /REAL OWNER LLC/ }))
  expect(window.location.hash).toBe('#/portfolios?owner=REAL%20OWNER%20LLC')
  expect(screen.getByRole('button', { name: 'Share this portfolio view' })).toBeInTheDocument()
})
