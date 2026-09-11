import { fireEvent, render, screen, within } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import type { ChangeEvent } from '../../src/types/history'
import type { SystemSummary } from '../../src/types/data'
import { WorkflowScaleWorkspace } from '../../src/components/WorkflowScaleWorkspace'

vi.mock('../../src/components/TowerMap', () => ({
  TowerMap: ({ systems, onSelect }: { systems: SystemSummary[]; onSelect: (row: SystemSummary) => void }) => <div data-testid="workflow-map"><span>{systems.length} mapped</span>{systems[0] && <button type="button" onClick={() => onSelect(systems[0])}>Select first marker</button>}</div>,
}))

const systems = [
  {
    system_id: 'SYS-1', address: '16 E 39TH ST', borough: 'Manhattan', zip: '10016', priority_score: 84,
    primary_signal: 'CONFIRMED_RECENT_VIOLATION', signal_types: ['CONFIRMED_RECENT_VIOLATION'], recent_confirmed_violation: true,
    latitude: 40.75, longitude: -73.98, active_equipment: 2, latest_sample_date: '2026-08-20', hpd_contact_count: 3, dob_recent_activity_count: 1,
  },
  {
    system_id: 'SYS-2', address: '100 BROADWAY', borough: 'Manhattan', zip: '10005', priority_score: 48,
    primary_signal: 'POTENTIAL_SAMPLING_GAP', signal_types: ['POTENTIAL_SAMPLING_GAP'], recent_confirmed_violation: false,
    latitude: 40.71, longitude: -74.01, active_equipment: 1, latest_sample_date: null, hpd_contact_count: 0, dob_recent_activity_count: 0,
  },
] as SystemSummary[]

const accounts = [
  { system_id: 'SYS-1', status: 'investigate' as const, note: 'Call facilities before Friday', next_action_date: '2026-09-11' },
  { system_id: 'SYS-2', status: 'follow-up' as const, note: 'Need owner contact', next_action_date: null },
]
const watchlists = [{ id: 'priority', name: 'Priority outreach' }]
const memberships = [{ watchlist_id: 'priority', system_id: 'SYS-1' }]
const recentEvents = [{
  event_type: 'VIOLATION_ADDED', system_id: 'SYS-1', bbl: null, bin: null, address: '16 E 39TH ST', borough: 'Manhattan',
  detected_at: '2026-09-11T10:00:00Z', source_observation_date: '2026-09-10', previous_value: null, new_value: 'violation', source: 'NYC', evidence_basis: 'test', priority_score: 84, evidence_confidence: 'CONFIRMED', contact_available: true,
}] as ChangeEvent[]
const eventsBySystem = new Map([['SYS-1', recentEvents]])

function renderWorkspace() {
  const onOpenAccount = vi.fn()
  render(<WorkflowScaleWorkspace systems={systems} marketCount={4894} accounts={accounts} watchlists={watchlists} memberships={memberships} savedViews={[{ id: 'view-1', name: 'Manhattan follow-up', filters: {} as never }]} recentEvents={recentEvents} eventsBySystem={eventsBySystem} today="2026-09-11" onOpenAccount={onOpenAccount} />)
  return onOpenAccount
}

test('keeps map table filters and selected account inspector synchronized', () => {
  const onOpenAccount = renderWorkspace()
  expect(screen.getByTestId('workflow-map')).toHaveTextContent('2 mapped')
  expect(screen.getByText('16 E 39TH ST')).toBeInTheDocument()
  expect(screen.getByText('100 BROADWAY')).toBeInTheDocument()

  fireEvent.change(screen.getByLabelText('Workflow status filter'), { target: { value: 'investigate' } })
  expect(screen.getByTestId('workflow-map')).toHaveTextContent('1 mapped')
  expect(screen.getByText('16 E 39TH ST')).toBeInTheDocument()
  expect(screen.queryByText('100 BROADWAY')).not.toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Select first marker' }))
  const inspector = screen.getByRole('complementary')
  expect(within(inspector).getByText('Investigate')).toBeInTheDocument()
  expect(within(inspector).getByText('Call facilities before Friday')).toBeInTheDocument()
  expect(within(inspector).getByText('Priority outreach')).toBeInTheDocument()

  fireEvent.click(within(inspector).getByRole('button', { name: 'Open account to manage →' }))
  expect(onOpenAccount).toHaveBeenCalledWith(expect.objectContaining({ system_id: 'SYS-1' }))
})

test('uses scalable quick views for changes actions status and watchlists', () => {
  renderWorkspace()

  fireEvent.click(screen.getByRole('button', { name: /Changed · 7d/i }))
  expect(screen.getByRole('tab', { name: /Changes/i })).toHaveAttribute('aria-selected', 'true')
  expect(screen.getByText('Violation Added')).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: /Needs a date/i }))
  expect(screen.getByRole('tab', { name: /Actions/i })).toHaveAttribute('aria-selected', 'true')
  expect(screen.getByText('Need owner contact')).toBeInTheDocument()
  expect(screen.getByText('Needs date')).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Clear' }))
  fireEvent.click(screen.getByRole('tab', { name: /Accounts/i }))
  fireEvent.change(screen.getByLabelText('Workflow watchlist filter'), { target: { value: 'priority' } })
  expect(screen.getByTestId('workflow-map')).toHaveTextContent('1 mapped')
  expect(screen.queryByText('100 BROADWAY')).not.toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: /Follow-up 1/i }))
  expect(screen.getByText('0 matching accounts')).toBeInTheDocument()
})
