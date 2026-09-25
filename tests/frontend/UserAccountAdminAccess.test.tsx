import { render, screen } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'
import { UserAccountPage } from '../../src/components/UserAccountPage'
import * as adminClient from '../../src/companyAdmin/client'

vi.mock('../../src/companyAdmin/client', () => ({
  loadCompanyAdminAccess: vi.fn(),
}))

const user = {
  id:'user-2',
  email:'jeremy@example.test',
  name:'jeremy.hennessy',
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(adminClient.loadCompanyAdminAccess).mockResolvedValue(true)
})

test('my account shows administrator access and private workspace shortcuts', async () => {
  render(<UserAccountPage user={user} onSignOut={vi.fn(async () => {})} />)

  expect((await screen.findAllByText('Administrator')).length).toBeGreaterThanOrEqual(2)
  expect(screen.getByRole('link', { name:'Company database' })).toHaveAttribute('href', '#/admin-companies')
  expect(screen.getByRole('link', { name:'Service operations' })).toHaveAttribute('href', '#/service')
})

test('standard authenticated account does not show admin shortcuts', async () => {
  vi.mocked(adminClient.loadCompanyAdminAccess).mockResolvedValue(false)
  render(<UserAccountPage user={user} onSignOut={vi.fn(async () => {})} />)

  expect(await screen.findByText('Authenticated user')).toBeInTheDocument()
  expect(screen.queryByRole('link', { name:'Company database' })).not.toBeInTheDocument()
  expect(screen.queryByRole('link', { name:'Service operations' })).not.toBeInTheDocument()
})

test('a failed access check is not shown as a standard user role',async()=>{
  vi.mocked(adminClient.loadCompanyAdminAccess).mockRejectedValue(new Error('Unavailable'))
  render(<UserAccountPage user={user} onSignOut={vi.fn(async()=>{})}/>)
  expect(await screen.findByText('Access check unavailable; reload to retry.')).toBeInTheDocument()
  expect(screen.queryByText('Authenticated user')).not.toBeInTheDocument()
})
