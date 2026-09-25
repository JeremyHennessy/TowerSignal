import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { PasswordSetupPage } from '../../src/components/PasswordSetupPage'
import { completeWorkflowPasswordSetup, requestWorkflowPasswordSetup } from '../../src/workflow/remoteClient'

vi.mock('../../src/workflow/remoteClient', () => ({
  completeWorkflowPasswordSetup: vi.fn(), requestWorkflowPasswordSetup: vi.fn(),
}))

beforeEach(() => {
  vi.resetAllMocks()
  window.history.replaceState(null, '', '/TowerSignal/#/password-setup')
})
afterEach(() => { cleanup(); window.history.replaceState(null, '', '/TowerSignal/') })

test('requests setup without exposing whether an account exists or allowing signup', async () => {
  const events = userEvent.setup()
  render(<PasswordSetupPage />)
  await events.type(screen.getByLabelText('Email'), 'existing@example.com')
  await events.click(screen.getByRole('button', { name: 'Send setup email' }))
  expect(requestWorkflowPasswordSetup).toHaveBeenCalledWith('existing@example.com')
  expect(screen.getByRole('status')).toHaveTextContent('If this email belongs to a TowerSignal account')
  expect(screen.queryByRole('button', { name: 'Create account' })).toBeNull()
})

test.each([
  '/TowerSignal/?token=test-token#/password-setup',
  '/TowerSignal/#/password-setup?token=test-token',
])('handles emailed callback %s and removes its token from the URL', async callback => {
  window.history.replaceState(null, '', callback)
  const events = userEvent.setup()
  render(<PasswordSetupPage />)
  expect(window.location.href).not.toContain('test-token')
  await events.type(screen.getByLabelText('New password'), 'a-test-password')
  await events.type(screen.getByLabelText('Confirm password'), 'different-password')
  await events.click(screen.getByRole('button', { name: 'Save password' }))
  expect(completeWorkflowPasswordSetup).not.toHaveBeenCalled()
  expect(screen.getByRole('alert')).toHaveTextContent('do not match')
  await events.clear(screen.getByLabelText('Confirm password'))
  await events.type(screen.getByLabelText('Confirm password'), 'a-test-password')
  await events.click(screen.getByRole('button', { name: 'Save password' }))
  expect(completeWorkflowPasswordSetup).toHaveBeenCalledWith('test-token', 'a-test-password')
  expect(screen.getByRole('heading', { name: 'Password saved' })).toBeVisible()
  expect(screen.queryByLabelText('New password')).toBeNull()
  expect(screen.getByRole('link', { name: 'Back to sign in' }).getAttribute('href')).not.toContain('token')
})

test.each([
  '/TowerSignal/?error=INVALID_TOKEN#/password-setup',
  '/TowerSignal/?token=one#/password-setup?token=two',
])('fails closed for expired or ambiguous callback %s', callback => {
  window.history.replaceState(null, '', callback)
  render(<PasswordSetupPage />)
  expect(screen.getByRole('alert')).toHaveTextContent('invalid or expired')
  expect(screen.getByLabelText('Email')).toBeVisible()
  expect(screen.queryByLabelText('New password')).toBeNull()
  expect(completeWorkflowPasswordSetup).not.toHaveBeenCalled()
  expect(window.location.href).not.toContain('token=')
})

test('failed saves stay recoverable and are never reported as success', async () => {
  window.history.replaceState(null, '', '/TowerSignal/?token=test-token#/password-setup')
  vi.mocked(completeWorkflowPasswordSetup).mockRejectedValue(new Error('The link has expired.'))
  const events = userEvent.setup()
  render(<PasswordSetupPage />)
  await events.type(screen.getByLabelText('New password'), 'a-test-password')
  await events.type(screen.getByLabelText('Confirm password'), 'a-test-password')
  await events.click(screen.getByRole('button', { name: 'Save password' }))
  expect(screen.getByRole('alert')).toHaveTextContent('expired')
  expect(screen.queryByRole('heading', { name: 'Password saved' })).toBeNull()
  await events.click(screen.getByRole('button', { name: 'Request a new setup email' }))
  expect(screen.getByLabelText('Email')).toBeVisible()
  expect(screen.queryByLabelText('New password')).toBeNull()
})
