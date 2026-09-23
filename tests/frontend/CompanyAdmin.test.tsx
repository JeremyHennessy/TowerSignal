import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import { CompanyAdminPanel } from '../../src/components/CompanyAdminPanel'
import * as adminClient from '../../src/companyAdmin/client'

vi.mock('../../src/companyAdmin/client', () => ({
  loadCompanyAdminAccess: vi.fn(),
  loadCompanyAdminSnapshot: vi.fn(),
  saveCompanyAdminProfile: vi.fn(),
  addCompanyContact: vi.fn(),
  addCompanyActivity: vi.fn(),
  addCompanyNote: vi.fn(),
  updateCompanyNote: vi.fn(),
}))

const profile = {
  company_id:'observed-company-alpha',
  canonical_name:'ALPHA WATER SERVICES LLC',
  legal_name:'Alpha Water Services LLC',
  rollup_name:'ALPHA WATER',
  rollup_company_id:null,
  website:'https://alpha.example',
  headquarters_address:'1 Water Way',
  headquarters_city:'New York',
  headquarters_region:'NY',
  headquarters_postal_code:'10001',
  headquarters_country:'US',
  parent_company_id:null,
  parent_company_name:null,
  company_type:'Water treatment',
  revenue_amount:12000000,
  revenue_low:null,
  revenue_high:null,
  revenue_currency:'USD',
  revenue_year:2025,
  revenue_type:'estimated',
  revenue_source_name:'Fixture',
  revenue_source_url:'https://example.test/revenue',
  revenue_confidence:'verify',
  relationship_status:'contacted',
  last_contacted_at:'2026-09-20T14:00:00Z',
  next_action_date:'2026-09-30',
  account_owner:'Jeremy',
  internal_summary:'Private relationship context',
  created_at:'2026-09-20T00:00:00Z',
  updated_at:'2026-09-20T00:00:00Z',
  created_by:'u1',
  updated_by:'u1',
} as const

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(adminClient.loadCompanyAdminAccess).mockResolvedValue(true)
  vi.mocked(adminClient.loadCompanyAdminSnapshot).mockResolvedValue({
    profile:{ ...profile },
    contacts:[],
    activities:[],
    notes:[{ note_id:'n1', company_id:'observed-company-alpha', note:'Existing private note', updated_at:'2026-09-20T00:00:00Z' }],
  })
  vi.mocked(adminClient.saveCompanyAdminProfile).mockImplementation(async (companyId, canonicalName, patch) => ({
    company_id:companyId,
    canonical_name:canonicalName,
    ...profile,
    ...patch,
  }))
  vi.mocked(adminClient.addCompanyNote).mockResolvedValue({ note_id:'n2', company_id:'observed-company-alpha', note:'New note' })
  vi.mocked(adminClient.updateCompanyNote).mockResolvedValue({ note_id:'n1', company_id:'observed-company-alpha', note:'Updated note' })
})

test('admin company panel exposes private enrichment without changing public evidence', async () => {
  const user = userEvent.setup()
  render(<CompanyAdminPanel companyId="observed-company-alpha" canonicalName="ALPHA WATER SERVICES LLC" />)

  expect(await screen.findByRole('region', { name:'Admin company database' })).toBeInTheDocument()
  expect(screen.getByDisplayValue('https://alpha.example')).toBeInTheDocument()
  expect(screen.getByDisplayValue('ALPHA WATER')).toBeInTheDocument()
  expect(screen.getByText('$12,000,000')).toBeInTheDocument()
  expect(screen.getByDisplayValue('Existing private note')).toBeInTheDocument()

  const website = screen.getByDisplayValue('https://alpha.example')
  await user.clear(website)
  await user.type(website, 'https://alpha-water.example')
  await user.click(screen.getByRole('button', { name:'Save company' }))

  expect(adminClient.saveCompanyAdminProfile).toHaveBeenCalled()
  const savedPatch = vi.mocked(adminClient.saveCompanyAdminProfile).mock.calls.at(-1)?.[2]
  expect(savedPatch?.website).toBe('https://alpha-water.example')
})

test('non-admin user never receives the private editor', async () => {
  vi.mocked(adminClient.loadCompanyAdminAccess).mockResolvedValue(false)
  render(<CompanyAdminPanel companyId="observed-company-alpha" canonicalName="ALPHA WATER SERVICES LLC" />)
  await vi.waitFor(() => expect(adminClient.loadCompanyAdminAccess).toHaveBeenCalled())
  expect(screen.queryByRole('region', { name:'Admin company database' })).not.toBeInTheDocument()
  expect(adminClient.loadCompanyAdminSnapshot).not.toHaveBeenCalled()
})
