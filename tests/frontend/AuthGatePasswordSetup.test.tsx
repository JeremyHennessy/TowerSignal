import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { AuthGate } from '../../src/auth/AuthGate'

vi.mock('../../src/App', () => ({ default: () => <div>Private application</div> }))
vi.mock('../../src/components/MarketingLandingPage', () => ({ MarketingLandingPage: () => <div>Marketing</div> }))
vi.mock('../../src/components/HomePage', () => ({ HomePage: () => <div>Private home</div> }))
vi.mock('../../src/components/UserAccountPage', () => ({ UserAccountPage: () => <div>Private account</div> }))
vi.mock('../../src/workflow/client', () => ({
  getWorkflowSession: vi.fn(() => new Promise(() => {})), signInWorkflow: vi.fn(), signOutWorkflow: vi.fn(),
}))
vi.mock('../../src/workflow/remoteClient', () => ({ completeWorkflowPasswordSetup: vi.fn(), requestWorkflowPasswordSetup: vi.fn() }))

afterEach(() => { cleanup(); window.history.replaceState(null, '', '/TowerSignal/') })

test('an emailed setup link opens before authentication completes, without exposing the private app', () => {
  window.history.replaceState(null, '', '/TowerSignal/?token=example-token#/password-setup')
  render(<AuthGate />)
  expect(screen.getByRole('heading', { name: 'Choose your password' })).toBeVisible()
  expect(screen.queryByText('Private application')).toBeNull()
  expect(window.location.href).not.toContain('example-token')
})

test('opening the setup page without a token only offers an email request', () => {
  window.history.replaceState(null, '', '/TowerSignal/#/password-setup')
  render(<AuthGate />)
  expect(screen.getByRole('button', { name: 'Send setup email' })).toBeVisible()
  expect(screen.queryByRole('button', { name: 'Save password' })).toBeNull()
  expect(screen.queryByText('Private application')).toBeNull()
})
