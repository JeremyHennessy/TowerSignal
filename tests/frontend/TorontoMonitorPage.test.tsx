import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { TorontoMonitorPage } from '../../src/components/TorontoMonitorPage'

const payload = {
  schema_version: 'toronto-history-1.0',
  history_started_at: '2026-09-03T00:00:00Z',
  observed_at: '2026-09-04T12:00:00Z',
  previous_release_sha: 'oldsha',
  current_release_sha: 'newsha',
  event_count: 3,
  properties_with_changes: 2,
  event_type_counts: { PERMIT_RECORD_ADDED: 1, RELATIONSHIP_ADDED: 1, TOWER_EVIDENCE_CHANGED: 1 },
  source_counts: { toronto_building_permits_active_targeted: 1, tobids_awarded_contracts: 1 },
  contract: {
    identity: 'Exact property ids and stable source record ids.',
    semantics: 'Observed dataset changes only; no compliance inference.',
    baseline: 'Last verified deployed Toronto checkpoint.',
  },
  events: [
    {
      event_id: 'event:1', event_type: 'PERMIT_RECORD_ADDED', property_id: 'toronto-address-point:1', address_point_id: '1', address: '10 Bay St', detected_at: '2026-09-04T12:00:00Z', source_observation_date: '2026-09-03', source_key: 'toronto_building_permits_active_targeted', source_record_id: 'permit:1', record_title: 'Mechanical permit', record_status: 'Permit Issued', evidence_basis: 'PROPERTY_ID_EXACT_AND_STABLE_SOURCE_RECORD_ID', previous_value: null, new_value: {}, tower_evidence_status: 'NO_TOWER_ASSERTION',
    },
    {
      event_id: 'event:2', event_type: 'RELATIONSHIP_ADDED', property_id: 'toronto-address-point:1', address: '10 Bay St', detected_at: '2026-09-04T12:00:00Z', source_key: 'tobids_awarded_contracts', evidence_basis: 'PROPERTY_ID_EXACT_AND_SOURCE_ROLE_PRESERVED', previous_value: null, new_value: { organization: 'Active Mechanical Services', relationship: 'SUCCESSFUL_BIDDER_AT_PROPERTY' }, tower_evidence_status: 'NO_TOWER_ASSERTION',
    },
    {
      event_id: 'event:3', event_type: 'TOWER_EVIDENCE_CHANGED', property_id: 'toronto-address-point:2', address: '20 Bay St', detected_at: '2026-09-04T12:00:00Z', source_key: null, evidence_basis: 'PROPERTY_ID_EXACT_TOWERSIGNAL_EVIDENCE_CONTRACT', previous_value: 'NO_TOWER_ASSERTION', new_value: 'CONFIRMED_DOCUMENTARY_TOWER', tower_evidence_status: 'CONFIRMED_DOCUMENTARY_TOWER',
    },
  ],
}

afterEach(() => vi.unstubAllGlobals())

test('renders verified Toronto release change metrics and bounded semantics', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => payload }))
  render(<TorontoMonitorPage />)
  expect(await screen.findByRole('heading', { name: 'Monitor' })).toBeInTheDocument()
  expect(screen.getByText('Observed dataset changes only; no compliance inference.')).toBeInTheDocument()
  expect(screen.getByText('3')).toBeInTheDocument()
  expect(screen.getByText('Mechanical permit')).toBeInTheDocument()
  expect(screen.getByText(/Active Mechanical Services/)).toBeInTheDocument()
})

test('filters change events by event type and source', async () => {
  const user = userEvent.setup()
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => payload }))
  render(<TorontoMonitorPage />)
  await screen.findByRole('heading', { name: 'Monitor' })
  const selects = screen.getAllByRole('combobox')
  await user.selectOptions(selects[0], 'PERMIT_RECORD_ADDED')
  expect(screen.getByText('Mechanical permit')).toBeInTheDocument()
  expect(screen.queryByText(/Active Mechanical Services/)).not.toBeInTheDocument()
  await user.selectOptions(selects[0], '')
  await user.selectOptions(selects[1], 'tobids_awarded_contracts')
  expect(screen.getByText(/Active Mechanical Services/)).toBeInTheDocument()
  expect(screen.queryByText('Mechanical permit')).not.toBeInTheDocument()
})

test('keeps Toronto Monitor free of NYC-specific compliance semantics', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => payload }))
  render(<TorontoMonitorPage />)
  await screen.findByRole('heading', { name: 'Monitor' })
  expect(screen.queryByText(/sampling gap/i)).not.toBeInTheDocument()
  expect(screen.queryByText(/oath/i)).not.toBeInTheDocument()
  expect(screen.queryByText(/priority score/i)).not.toBeInTheDocument()
})
