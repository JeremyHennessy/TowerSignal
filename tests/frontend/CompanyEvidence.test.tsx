import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import { CompanyEvidencePanel } from '../../src/components/CompanyEvidencePanel'
import * as api from '../../src/companyAdmin/client'
import type { CompanyEvidence } from '../../src/companyAdmin/evidence'
import { httpsUrl, validObservationDate } from '../../src/companyAdmin/evidence'
import type { CompanySalesAccount } from '../../src/types/companyAdmin'

vi.mock('../../src/companyAdmin/client',()=>({
  loadCompanyEvidence:vi.fn(),addCompanyParent:vi.fn(),proposeCompanyParent:vi.fn(),reviewCompanyParent:vi.fn(),
  addCompanyEnrichmentSource:vi.fn(),setCompanyEnrichmentSourceEnabled:vi.fn(),reviewCompanyEnrichmentCandidate:vi.fn(),
}))
const empty:CompanyEvidence={parents:[],relationships:[],sources:[],runs:[],candidates:[]}
const accounts=[{sales_account_id:'account',primary_company_id:'company',display_name:'Example Water',record_status:'active'}] as CompanySalesAccount[]
beforeEach(()=>{vi.clearAllMocks();vi.mocked(api.loadCompanyEvidence).mockResolvedValue(structuredClone(empty))})

test('unavailable database is explicit and does not report zero coverage',async()=>{
  vi.mocked(api.loadCompanyEvidence).mockRejectedValue(new Error('missing migration'))
  render(<CompanyEvidencePanel accounts={accounts}/>)
  expect(await screen.findByRole('alert')).toHaveTextContent('unavailable')
  expect(screen.queryByText('No pending observations.')).not.toBeInTheDocument()
})

test('review closes an observation without publishing a profile or ownership change',async()=>{
  vi.mocked(api.loadCompanyEvidence).mockResolvedValue({...empty,candidates:[{
    candidate_id:'candidate',sales_account_id:'account',source_id:'source',field_name:'legal_name',proposed_value:'Example Water LLC',
    source_url:'https://example.com',evidence_excerpt:'Official structured data',last_observed_at:'2026-09-25T12:00:00Z',status:'pending',
  }]})
  render(<CompanyEvidencePanel accounts={accounts}/>)
  await userEvent.click(await screen.findByText('Review enrichment observations'))
  expect(screen.getByText(/does not publish a profile change/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button',{name:'Reviewed'}))
  await waitFor(()=>expect(api.reviewCompanyEnrichmentCandidate).toHaveBeenCalledWith('candidate','reviewed'))
  expect(api.proposeCompanyParent).not.toHaveBeenCalled()
  expect(api.reviewCompanyParent).not.toHaveBeenCalled()
})

test('source approval requires chosen account and explicit official source input',async()=>{
  render(<CompanyEvidencePanel accounts={accounts}/>)
  await userEvent.click(await screen.findByText('Approved enrichment sources'))
  expect(screen.getByRole('button',{name:'Approve source for checks'})).toBeDisabled()
  await userEvent.selectOptions(screen.getByLabelText('Evidence company account'),'account')
  await userEvent.type(screen.getByLabelText('Official source URL'),'https://example.com/about')
  await userEvent.type(screen.getByLabelText('Exact published organization name'),'Example Water')
  await userEvent.click(screen.getByRole('button',{name:'Approve source for checks'}))
  await waitFor(()=>expect(api.addCompanyEnrichmentSource).toHaveBeenCalledWith('account','https://example.com/about','Example Water'))
})

test('source URLs reject credentials and insecure schemes',()=>{
  expect(httpsUrl('https://example.com/about')).toBe(true)
  for(const value of ['http://example.com','javascript:alert(1)','https://user:pass@example.com','https://example.com:8443'])expect(httpsUrl(value)).toBe(false)
})

test('typed evidence dates reject impossible dates without depending on a native calendar',()=>{
  expect(validObservationDate('2024-02-29')).toBe(true)
  expect(validObservationDate('2026-09-25')).toBe(true)
  for(const value of ['2026-02-29','2026-04-31','09/25/2026','2026-13-01','', '0000-01-01'])expect(validObservationDate(value)).toBe(false)
})

test('parent evidence accepts a typed date and sends the exact reviewed date',async()=>{
  vi.mocked(api.loadCompanyEvidence).mockResolvedValue({...empty,parents:[{parent_entity_id:'parent',display_name:'Example Group',website:null}]})
  render(<CompanyEvidencePanel accounts={accounts}/>)
  await userEvent.click(await screen.findByText('Parent entities and ownership evidence'))
  await userEvent.selectOptions(screen.getByLabelText('Evidence company account'),'account')
  await userEvent.selectOptions(screen.getByLabelText('Parent entity'),'parent')
  await userEvent.type(screen.getByLabelText('Ownership evidence URL'),'https://example.com/brands')
  await userEvent.type(screen.getByLabelText('What the source establishes'),'Official portfolio lists the operating company.')
  await userEvent.type(screen.getByLabelText('Observed on'),'2026-02-30')
  expect(screen.getByRole('button',{name:'Propose parent link'})).toBeDisabled()
  await userEvent.clear(screen.getByLabelText('Observed on'))
  await userEvent.type(screen.getByLabelText('Observed on'),'2026-09-25')
  await userEvent.click(screen.getByRole('button',{name:'Propose parent link'}))
  await waitFor(()=>expect(api.proposeCompanyParent).toHaveBeenCalledWith(expect.objectContaining({observed_on:'2026-09-25',sales_account_id:'account',parent_entity_id:'parent'})))
})
