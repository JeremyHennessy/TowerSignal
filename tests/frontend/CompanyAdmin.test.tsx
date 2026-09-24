import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import { CompanyAdminPanel } from '../../src/components/CompanyAdminPanel'
import * as adminClient from '../../src/companyAdmin/client'

vi.mock('../../src/companyAdmin/client', () => ({
  loadCompanyAdminAccess: vi.fn(),
  loadCompanyAdminSnapshot: vi.fn(),
  saveCompanyAdminProfile: vi.fn(),
  saveCompanyAdminContact: vi.fn(),
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
  rollup_source_name:'Fixture rollup evidence',
  rollup_source_url:'https://example.test/rollup',
  website:'https://alpha.example',
  website_source_name:'Official site',
  website_source_url:'https://alpha.example',
  identity_source_name:'Official site',
  identity_source_url:'https://alpha.example/about',
  headquarters_address:'1 Water Way',
  headquarters_city:'New York',
  headquarters_region:'NY',
  headquarters_postal_code:'10001',
  headquarters_country:'US',
  headquarters_source_name:'Official contact page',
  headquarters_source_url:'https://alpha.example/contact',
  parent_company_id:null,
  parent_company_name:null,
  parent_source_name:null,
  parent_source_url:null,
  company_type:'Water treatment',
  enrichment_checked_at:'2026-09-23T18:00:00Z',
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
    contacts:[{
      contact_id:'c1', company_id:'observed-company-alpha', name:'Alex Buyer', title:'Facilities Manager',
      email:'alex@example.test', phone:'212-555-0100', linkedin_url:'https://linkedin.example/alex',
      notes:null, source_name:'Official staff page', source_url:'https://alpha.example/team',
      verified_at:'2026-09-23T18:00:00Z', active:true,
      created_at:'2026-09-20T00:00:00Z', updated_at:'2026-09-20T00:00:00Z',
    }],
    activities:[],
    notes:[{ note_id:'n1', company_id:'observed-company-alpha', note:'Existing private note', updated_at:'2026-09-20T00:00:00Z' }],
  })
  vi.mocked(adminClient.saveCompanyAdminProfile).mockImplementation(async (companyId, canonicalName, patch) => ({
    ...profile,
    ...patch,
    company_id:companyId,
    canonical_name:canonicalName,
  }))
  vi.mocked(adminClient.saveCompanyAdminContact).mockImplementation(async (contactId, companyId, values) => ({
    contact_id:contactId, company_id:companyId, ...values,
    created_at:'2026-09-20T00:00:00Z', updated_at:'2026-09-24T00:00:00Z',
  }))
  vi.mocked(adminClient.addCompanyActivity).mockImplementation(async (companyId, values) => ({
    activity_id:'a1', company_id:companyId, ...values, created_at:'2026-09-24T00:00:00Z', created_by:'u1',
  }))
  vi.mocked(adminClient.addCompanyNote).mockResolvedValue({ note_id:'n2', company_id:'observed-company-alpha', note:'New note' })
  vi.mocked(adminClient.updateCompanyNote).mockResolvedValue({ note_id:'n1', company_id:'observed-company-alpha', note:'Updated note' })
})

test('admin company panel exposes private enrichment without changing public evidence', async () => {
  const user = userEvent.setup()
  render(<CompanyAdminPanel companyId="observed-company-alpha" canonicalName="ALPHA WATER SERVICES LLC" />)

  expect(await screen.findByRole('region', { name:'Admin company database' })).toBeInTheDocument()
  expect(screen.getAllByDisplayValue('https://alpha.example').length).toBeGreaterThan(0)
  expect(screen.getByDisplayValue('Official contact page')).toBeInTheDocument()
  expect(screen.getByDisplayValue('ALPHA WATER')).toBeInTheDocument()
  expect(screen.getByText('$12,000,000')).toBeInTheDocument()
  expect(screen.getByDisplayValue('Existing private note')).toBeInTheDocument()

  const website = screen.getAllByDisplayValue('https://alpha.example')[0]
  await user.clear(website)
  await user.type(website, 'https://alpha-water.example')
  const legalName = screen.getByDisplayValue('Alpha Water Services LLC')
  await user.clear(legalName)
  await user.type(legalName, 'Alpha Water Group LLC')
  await user.click(screen.getByRole('button', { name:'Save company' }))

  expect(adminClient.saveCompanyAdminProfile).toHaveBeenCalled()
  const savedPatch = vi.mocked(adminClient.saveCompanyAdminProfile).mock.calls.at(-1)?.[2]
  expect(savedPatch?.website).toBe('https://alpha-water.example')
  expect(savedPatch?.legal_name).toBe('Alpha Water Group LLC')
})

test('non-admin user never receives the private editor', async () => {
  vi.mocked(adminClient.loadCompanyAdminAccess).mockResolvedValue(false)
  render(<CompanyAdminPanel companyId="observed-company-alpha" canonicalName="ALPHA WATER SERVICES LLC" />)
  await vi.waitFor(() => expect(adminClient.loadCompanyAdminAccess).toHaveBeenCalled())
  expect(screen.queryByRole('region', { name:'Admin company database' })).not.toBeInTheDocument()
  expect(adminClient.loadCompanyAdminSnapshot).not.toHaveBeenCalled()
})


test('admin can edit a contact and associate outreach with that contact', async () => {
  const user = userEvent.setup()
  render(<CompanyAdminPanel companyId="observed-company-alpha" canonicalName="ALPHA WATER SERVICES LLC" />)

  const editContact = await screen.findByRole('button', { name:'Edit contact' })
  await user.click(editContact)

  const title = screen.getByLabelText('Edit contact title')
  await user.clear(title)
  await user.type(title, 'Director of Facilities')
  await user.click(screen.getByRole('button', { name:'Save contact' }))

  expect(adminClient.saveCompanyAdminContact).toHaveBeenCalled()
  expect(vi.mocked(adminClient.saveCompanyAdminContact).mock.calls.at(-1)?.[0]).toBe('c1')
  expect(vi.mocked(adminClient.saveCompanyAdminContact).mock.calls.at(-1)?.[2].title).toBe('Director of Facilities')

  await user.selectOptions(screen.getByLabelText('Activity contact'), 'c1')
  await user.type(screen.getByLabelText('Activity subject'), 'Quarterly service follow-up')
  await user.type(screen.getByLabelText('Activity outcome'), 'Requested proposal')
  await user.click(screen.getByRole('button', { name:'Log interaction' }))

  const activity = vi.mocked(adminClient.addCompanyActivity).mock.calls.at(-1)?.[1]
  expect(activity?.contact_id).toBe('c1')
  expect(activity?.subject).toBe('Quarterly service follow-up')
  expect(activity?.outcome).toBe('Requested proposal')
})
