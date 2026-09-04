import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, afterEach, expect, test, vi } from 'vitest'
import { TorontoParityShell } from '../../src/components/TorontoParityShell'

const historyPayload = {
  schema_version: 'toronto-history-1.0',
  history_started_at: '2026-09-03T00:00:00Z',
  observed_at: '2026-09-04T12:00:00Z',
  previous_release_sha: 'oldsha',
  current_release_sha: 'newsha',
  event_count: 1,
  properties_with_changes: 1,
  event_type_counts: { PERMIT_RECORD_ADDED: 1 },
  source_counts: { toronto_building_permits_active_targeted: 1 },
  contract: {
    identity: 'Exact property ids and stable source record ids.',
    semantics: 'Observed dataset changes only; no compliance inference.',
    baseline: 'Last verified deployed Toronto checkpoint.',
  },
  events: [{
    event_id: 'event:1',
    event_type: 'PERMIT_RECORD_ADDED',
    property_id: 'toronto-address-point:100',
    address_point_id: '100',
    address: '10 Alpha St',
    detected_at: '2026-09-04T12:00:00Z',
    source_observation_date: '2026-09-03',
    source_key: 'toronto_building_permits_active_targeted',
    source_record_id: 'permit:1',
    record_title: 'Mechanical permit',
    record_status: 'Permit Issued',
    evidence_basis: 'PROPERTY_ID_EXACT_AND_STABLE_SOURCE_RECORD_ID',
    previous_value: null,
    new_value: {},
    tower_evidence_status: 'NO_TOWER_ASSERTION',
  }],
}

vi.mock('../../src/data/api', () => ({ loadTorontoMarket: vi.fn() }))

beforeEach(() => {
  window.location.hash = '#/toronto'
  window.localStorage.clear()
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => historyPayload }))
})

afterEach(() => vi.unstubAllGlobals())

test('opens verified Monitor without requiring the commercial market payload', async () => {
  const user = userEvent.setup()
  render(<TorontoParityShell explorer={<div>Market explorer</div>} />)
  await user.click(screen.getByRole('button', { name: 'Monitor' }))
  expect(await screen.findByRole('heading', { name: 'Monitor' })).toBeInTheDocument()
  expect(screen.getByText('Mechanical permit')).toBeInTheDocument()
  expect(screen.getByText(/Observed dataset changes only; no compliance inference/i)).toBeInTheDocument()
  expect(screen.queryByText(/Toronto commercial workspace unavailable/i)).not.toBeInTheDocument()
})
