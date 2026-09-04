import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { AuthLandingPage } from '../../src/components/AuthLandingPage'

const user = { id: 'user-1', email: 'user@example.com', name: 'Test User' }

beforeEach(() => {
  window.history.replaceState(null, '', window.location.pathname)
})

afterEach(() => {
  window.history.replaceState(null, '', window.location.pathname)
  document.body.style.overflow = ''
})

test('signed-out root renders the marketing page with login in the top navigation', () => {
  render(<AuthLandingPage onSignIn={vi.fn().mockResolvedValue(user)} onSignUp={vi.fn().mockResolvedValue(user)} />)

  expect(screen.getByRole('heading', { name: /Know which accounts matter/i })).toBeVisible()
  expect(screen.getByRole('button', { name: 'Log in' })).toBeVisible()
  expect(screen.queryByRole('heading', { name: 'Sign in to TowerSignal' })).toBeNull()
})

test('login button opens the existing authentication contract', async () => {
  const events = userEvent.setup()
  render(<AuthLandingPage onSignIn={vi.fn().mockResolvedValue(user)} onSignUp={vi.fn().mockResolvedValue(user)} />)

  await events.click(screen.getByRole('button', { name: 'Log in' }))

  expect(screen.getByRole('heading', { name: 'Sign in to TowerSignal' })).toBeVisible()
  expect(screen.getByLabelText('Email')).toBeVisible()
  expect(screen.getByLabelText('Password', { selector: 'input' })).toBeVisible()
  expect(screen.getByRole('tab', { name: 'Create account' })).toBeVisible()
})

test('protected deep links keep the sign-in gate visible for hosted route tests', () => {
  window.location.hash = '#/companies'
  render(<AuthLandingPage onSignIn={vi.fn().mockResolvedValue(user)} onSignUp={vi.fn().mockResolvedValue(user)} />)

  expect(screen.getByRole('heading', { name: 'Sign in to TowerSignal' })).toBeVisible()
  expect(screen.getByRole('tab', { name: 'Create account' })).toBeVisible()
  expect(screen.queryByRole('heading', { name: 'Companies' })).toBeNull()
})