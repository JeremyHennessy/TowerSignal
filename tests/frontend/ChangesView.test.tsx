import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ChangesView } from '../../src/components/ChangesView'
import type { ChangesPayload } from '../../src/types/history'
const payload: ChangesPayload = { history_schema_version: '1.0', history_started_at: '2026-09-01', observed_at: '2026-09-15T16:56:42Z', baseline_initialized: false, new_event_count: 1, events: [{ event_type: 'VIOLATION_ADDED', system_id: '2000015925', bbl: null, bin: null, address: '1414 MADISON AVE', borough: 'Manhattan', detected_at: '2026-09-15T16:56:42Z', source_observation_date: '2026-07-14', previous_value: null, new_value: { inspection_date: '2026-07-14', description: 'No Maintenance Program or Plan', violation_code: 'AH8A', law_section: '24 RCNY §8-03', violation_type: 'PHH', summons_number: '0881341735' }, source: 'NYC_COOLING_TOWER_INSPECTIONS', evidence_basis: 'SYSTEM_ID_EXACT', priority_score: 78, evidence_confidence: 'CONFIRMED', contact_available: true }] }
afterEach(cleanup)
describe('Monitor table', () => {
  it('renders the true source date and complete, readable violation details', () => {
    render(<ChangesView payload={payload} onSelectSystem={vi.fn()} />)
    const row = screen.getAllByRole('row')[1]
    expect(within(row).getByText('Jul 14, 2026')).toBeInTheDocument()
    expect(within(row).getByText('Inspection date')).toBeInTheDocument()
    expect(within(row).getByText('No Maintenance Program or Plan')).toBeInTheDocument()
    expect(within(row).getByText('Summons 0881341735')).toBeInTheDocument()
    expect(within(row).getByText('NYC Health inspections')).toBeInTheDocument()
    expect(within(row).getByRole('link', { name: 'Open account' })).toHaveAttribute('href', '#/account/2000015925')
    expect(screen.queryByText(/\{"summons_number"/)).not.toBeInTheDocument()
    expect(screen.getByTestId('monitor-event-count')).toHaveTextContent('1 recorded events')
  })
  it('date controls and category counts use the same event-date predicate', async () => {
    const user = userEvent.setup(); render(<ChangesView payload={payload} onSelectSystem={vi.fn()} />)
    await user.selectOptions(screen.getByLabelText('Event date range'), 'custom')
    await user.type(screen.getByLabelText('From'), '2026-09-01')
    await user.type(screen.getByLabelText('To'), '2026-09-15')
    expect(screen.getByTestId('monitor-event-count')).toHaveTextContent('0 recorded events')
    await user.click(screen.getByRole('button', { name: 'Clear all' }))
    await user.click(screen.getByRole('tab', { name: 'Violations 1' }))
    expect(screen.getByText('No Maintenance Program or Plan')).toBeInTheDocument()
  })
})
