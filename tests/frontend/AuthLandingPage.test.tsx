import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { AuthLandingPage } from '../../src/components/AuthLandingPage'
import { MarketingLandingPage } from '../../src/components/MarketingLandingPage'

const user = { id: 'user-1', email: 'user@example.com', name: 'Test User' }

beforeEach(() => {
  window.history.replaceState(null, '', window.location.pathname)
})

afterEach(() => {
  window.history.replaceState(null, '', window.location.pathname)
})

test('existing TowerSignal login page remains the authentication surface', () => {
  render(<AuthLandingPage onSignIn={vi.fn().mockResolvedValue(user)} onSignUp={vi.fn().mockResolvedValue(user)} />)

  expect(screen.getByRole('heading', { name: 'Sign in to TowerSignal' })).toBeVisible()
  expect(screen.getByLabelText('Email')).toBeVisible()
  expect(screen.getByLabelText('Password', { selector: 'input' })).toBeVisible()
  expect(screen.getByRole('tab', { name: 'Create account' })).toBeVisible()
})

test('existing account-creation mode is preserved on the login page', async () => {
  const events = userEvent.setup()
  render(<AuthLandingPage onSignIn={vi.fn().mockResolvedValue(user)} onSignUp={vi.fn().mockResolvedValue(user)} />)

  await events.click(screen.getByRole('tab', { name: 'Create account' }))

  expect(screen.getByRole('heading', { name: 'Create your TowerSignal account' })).toBeVisible()
  expect(screen.getByLabelText('Full name')).toBeVisible()
  expect(screen.getByLabelText('Confirm password')).toBeVisible()
})

test('public marketing page uses the TowerSignal product positioning and a dedicated login route', () => {
  render(<MarketingLandingPage />)

  expect(screen.getByRole('heading', { name: /Find the buildings that need you next/i })).toBeVisible()
  expect(screen.getByText('New York City')).toBeVisible()
  expect(screen.getByText('Toronto expansion')).toBeVisible()
  expect(screen.getAllByRole('link', { name: /Log in/i })[0]).toHaveAttribute('href', '#/login')
  expect(screen.queryByRole('heading', { name: 'Sign in to TowerSignal' })).toBeNull()
})

test('demo contact sheet validates locally without pretending email delivery is connected', async () => {
  const events = userEvent.setup()
  render(<MarketingLandingPage />)

  await events.type(screen.getByLabelText('Full name'), 'Alex Morgan')
  await events.type(screen.getByLabelText('Work email'), 'alex@example.com')
  await events.type(screen.getByLabelText('Company'), 'Example Water')
  await events.click(screen.getByRole('button', { name: /Request a demo/i }))

  expect(screen.getByRole('status')).toHaveTextContent('Email delivery is not connected yet')
  expect(screen.getByRole('status')).toHaveTextContent('has not been sent')
})
