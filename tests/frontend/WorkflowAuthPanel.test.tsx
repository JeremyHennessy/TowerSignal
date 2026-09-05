import { render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import { WorkflowAuthPanel } from '../../src/components/WorkflowAuthPanel'

test('surfaces a signed-in workflow synchronization failure without claiming sync', () => {
  render(<WorkflowAuthPanel
    user={{ id:'user-1', email:'sales@example.test', name:'Sales User' }}
    loading={false}
    busy={false}
    error="Unable to save account workflow state"
    onSignIn={vi.fn()}
    onSignUp={vi.fn()}
    onSignOut={vi.fn()}
  />)
  expect(screen.getByText('Workflow session')).toBeInTheDocument()
  expect(screen.queryByText('Workflow synced')).not.toBeInTheDocument()
  expect(screen.getByRole('alert')).toHaveTextContent('Unable to save account workflow state')
})
