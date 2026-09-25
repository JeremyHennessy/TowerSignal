import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'
import { AdminCompanyProfilePage } from '../../src/components/AdminCompanyProfilePage'
import { loadCompanyAdminAccess, loadCompanyAdminOverview } from '../../src/companyAdmin/client'
import { loadKnownFirms } from '../../src/data/api'

vi.mock('../../src/companyAdmin/client', () => ({ loadCompanyAdminAccess: vi.fn(), loadCompanyAdminOverview: vi.fn() }))
vi.mock('../../src/data/api', () => ({ loadKnownFirms: vi.fn() }))

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(loadCompanyAdminAccess).mockResolvedValue(true)
  vi.mocked(loadKnownFirms).mockResolvedValue({ firms: [] } as unknown as Awaited<ReturnType<typeof loadKnownFirms>>)
})

test('data failure preserves the distinction from denied access and supports retry', async () => {
  vi.mocked(loadCompanyAdminOverview).mockRejectedValueOnce(new Error('Response too large'))
    .mockResolvedValueOnce({ profiles: [], accounts: [], members: [], contacts: [], activities: [], queue: [], opportunities: [], tasks: [], demos: [], proposals: [], subscriptions: [], renewals: [] })
  render(<AdminCompanyProfilePage companyId="missing" />)
  expect(await screen.findByText('Response too large')).toBeInTheDocument()
  expect(screen.queryByText('Administrator access required.')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Retry loading' }))
  expect(await screen.findByText('Private company profile not found.')).toBeInTheDocument()
  await waitFor(() => expect(loadCompanyAdminAccess).toHaveBeenCalledTimes(2))
})

test('an actual denied role does not request private records', async () => {
  vi.mocked(loadCompanyAdminAccess).mockResolvedValue(false)
  render(<AdminCompanyProfilePage companyId="private" />)
  expect(await screen.findByText('Administrator access required.')).toBeInTheDocument()
  expect(loadCompanyAdminOverview).not.toHaveBeenCalled()
})
