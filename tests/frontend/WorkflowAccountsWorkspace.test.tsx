import { fireEvent, render, screen, within } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import type { SystemSummary } from '../../src/types/data'
import { WorkflowAccountsWorkspace } from '../../src/components/WorkflowAccountsWorkspace'

vi.mock('../../src/components/TowerMap', () => ({
  TowerMap: ({ systems, onSelect }: { systems: SystemSummary[]; onSelect: (row: SystemSummary) => void }) => <div data-testid="workflow-map"><span>{systems.length} mapped</span>{systems[0] && <button type="button" onClick={() => onSelect(systems[0])}>Select first marker</button>}</div>,
}))

const systems = [
  {
    system_id: 'SYS-1', address: '16 E 39TH ST', borough: 'Manhattan', zip: '10016', priority_score: 84,
    primary_signal: 'CONFIRMED_RECENT_VIOLATION', signal_types: ['CONFIRMED_RECENT_VIOLATION'],
    latitude: 40.75, longitude: -73.98,
  },
  {
    system_id: 'SYS-2', address: '100 BROADWAY', borough: 'Manhattan', zip: '10005', priority_score: 48,
    primary_signal: 'POTENTIAL_SAMPLING_GAP', signal_types: ['POTENTIAL_SAMPLING_GAP'],
    latitude: 40.71, longitude: -74.01,
  },
] as SystemSummary[]

const accounts = [
  { system_id: 'SYS-1', status: 'investigate' as const, note: 'Call facilities before Friday', next_action_date: '2026-09-11' },
  { system_id: 'SYS-2', status: 'monitor' as const, note: '', next_action_date: null },
]

const watchlists = [{ id: 'priority', name: 'Priority outreach' }]
const memberships = [{ watchlist_id: 'priority', system_id: 'SYS-1' }]
const eventsBySystem = new Map([['SYS-1', [{ system_id: 'SYS-1' }, { system_id: 'SYS-1' }] as never[]]])

test('keeps workflow map, table and private filters synchronized', () => {
  const onOpenAccount = vi.fn()
  render(<WorkflowAccountsWorkspace systems={systems} accounts={accounts} watchlists={watchlists} memberships={memberships} eventsBySystem={eventsBySystem} today="2026-09-11" onOpenAccount={onOpenAccount} />)

  expect(screen.getByRole('heading', { name: 'Workflow accounts' })).toBeInTheDocument()
  expect(screen.getByTestId('workflow-map')).toHaveTextContent('2 mapped')
  expect(screen.getByText('16 E 39TH ST')).toBeInTheDocument()
  expect(screen.getByText('100 BROADWAY')).toBeInTheDocument()

  fireEvent.change(screen.getByLabelText('Workflow status filter'), { target: { value: 'investigate' } })
  expect(screen.getByTestId('workflow-map')).toHaveTextContent('1 mapped')
  expect(screen.getByText('16 E 39TH ST')).toBeInTheDocument()
  expect(screen.queryByText('100 BROADWAY')).not.toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Select first marker' }))
  const preview = screen.getByRole('complementary')
  expect(within(preview).getByText('Investigate')).toBeInTheDocument()
  expect(within(preview).getByText('Call facilities before Friday')).toBeInTheDocument()
  expect(within(preview).getByText('2')).toBeInTheDocument()
  expect(within(preview).getByText('Priority outreach')).toBeInTheDocument()

  fireEvent.click(within(preview).getByRole('button', { name: 'Open account →' }))
  expect(onOpenAccount).toHaveBeenCalledWith(expect.objectContaining({ system_id: 'SYS-1' }))

  fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
  expect(screen.getByTestId('workflow-map')).toHaveTextContent('2 mapped')
})

test('supports watchlist and attention filters without changing public scores', () => {
  render(<WorkflowAccountsWorkspace systems={systems} accounts={accounts} watchlists={watchlists} memberships={memberships} eventsBySystem={eventsBySystem} today="2026-09-11" onOpenAccount={vi.fn()} />)

  fireEvent.change(screen.getByLabelText('Workflow watchlist filter'), { target: { value: 'priority' } })
  expect(screen.getByTestId('workflow-map')).toHaveTextContent('1 mapped')
  expect(screen.queryByText('100 BROADWAY')).not.toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
  fireEvent.change(screen.getByLabelText('Workflow attention filter'), { target: { value: 'high' } })
  expect(screen.getByTestId('workflow-map')).toHaveTextContent('1 mapped')
  expect(screen.getByText('84')).toBeInTheDocument()
})
