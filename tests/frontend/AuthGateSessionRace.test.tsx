import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { AuthGate } from '../../src/auth/AuthGate'
import { getWorkflowSession } from '../../src/workflow/client'
import type { WorkflowUser } from '../../src/types/workflow'

vi.mock('../../src/App', () => ({ default: () => <div>Private application</div> }))
vi.mock('../../src/components/MarketingLandingPage', () => ({ MarketingLandingPage: () => <div>Marketing</div> }))
vi.mock('../../src/components/HomePage', () => ({ HomePage: () => <div>Private home</div> }))
vi.mock('../../src/components/AuthLandingPage', () => ({ AuthLandingPage: () => <div>Sign in required</div> }))
vi.mock('../../src/components/UserAccountPage', () => ({ UserAccountPage: ({ onSignOut }: { onSignOut: () => Promise<void> }) => <button onClick={() => void onSignOut()}>Sign out test account</button> }))
vi.mock('../../src/workflow/client', () => ({ getWorkflowSession: vi.fn(), signInWorkflow: vi.fn(), signOutWorkflow: vi.fn(async () => {}) }))

afterEach(() => { cleanup(); window.history.replaceState(null, '', '/TowerSignal/'); vi.clearAllMocks() })

test('a delayed focus check cannot restore an account after sign-out', async () => {
  const user = { id: 'administrator', email: 'admin@example.test', name: 'Administrator' }
  vi.mocked(getWorkflowSession).mockResolvedValueOnce(user)
  window.history.replaceState(null, '', '/TowerSignal/#/my-account')
  render(<AuthGate />)
  const signOut = await screen.findByRole('button', { name: 'Sign out test account' })
  let finish!: (user: WorkflowUser) => void
  vi.mocked(getWorkflowSession).mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
  fireEvent.focus(window)
  fireEvent.click(signOut)
  await screen.findByText('Marketing')
  await act(async () => { finish(user) })
  await act(async () => { window.location.hash = '#/my-account'; window.dispatchEvent(new HashChangeEvent('hashchange')) })
  expect(await screen.findByText('Sign in required')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Sign out test account' })).not.toBeInTheDocument()
})
