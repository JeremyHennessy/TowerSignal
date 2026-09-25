import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { buildCompanyDirectory } from '../../src/companyAdmin/directory'
import { AdminFirmDirectory } from '../../src/components/AdminFirmDirectory'
import type { CompanyAdminProfile, CompanySalesAccount, CompanySalesAccountMember } from '../../src/types/companyAdmin'
import type { KnownFirmSummaryRecord } from '../../src/types/firm'
import type { CompanyEvidence } from '../../src/companyAdmin/evidence'
const mocks=vi.hoisted(()=>({evidence:vi.fn()}))
vi.mock('../../src/companyAdmin/client',()=>({loadCompanyEvidence:mocks.evidence}))
afterEach(()=>{cleanup();vi.resetAllMocks()})
beforeEach(()=>window.history.replaceState(null,'','#/admin-companies'))
const firm=(id:string,name:string,normalized=name)=>({firm_id:id,canonical_name:name,normalized_name:normalized,roles:['DWT_INSPECTION_PROVIDER'],observation_count:10} as KnownFirmSummaryRecord)
const accounts=[{sales_account_id:'master',display_name:'Reviewed Water',primary_company_id:'one',record_status:'active',account_classification:'target',parent_name:'Recorded Group',parent_source_url:'https://example.com/recorded'}] as CompanySalesAccount[]
const profiles=[{company_id:'one',canonical_name:'Water LLC'},{company_id:'two',canonical_name:'Water Ltd'},{company_id:'private',canonical_name:'Private legacy name'}] as CompanyAdminProfile[]
const members=[{sales_account_id:'master',company_id:'one'},{sales_account_id:'master',company_id:'two'},{sales_account_id:'master',company_id:'private'}] as CompanySalesAccountMember[]
const firms=[firm('one','Water LLC','WATER'),firm('two','Water Ltd','WATER'),firm('other','Water Inc','WATER')]
const evidence:CompanyEvidence={parents:[],relationships:[],sources:[],runs:[],candidates:[]}

test('all source identities survive, including unmapped firms and private-only aliases; equal normalized names do not merge',()=>{
  const rows=buildCompanyDirectory(firms,profiles,accounts,members,null)
  expect(rows).toHaveLength(2)
  expect(rows.find(row=>row.id==='master')?.identities.map(identity=>identity.id)).toEqual(['one','two','private'])
  expect(rows.find(row=>row.id==='other')?.account).toBeNull()
  expect(new Set(rows.flatMap(row=>row.identities.map(identity=>identity.id))).size).toBe(4)
})

test('only confirmed current ownership overrides the recorded parent, and subsidiary accounts stay separate',()=>{
  const current:CompanyEvidence={...evidence,parents:[{parent_entity_id:'parent',display_name:'Confirmed Group',website:null}],relationships:[{relationship_id:'r',sales_account_id:'master',parent_entity_id:'parent',relationship_type:'parent',evidence_url:'https://example.com/evidence',evidence_note:'',observed_on:'2026-09-25',valid_from:null,valid_to:null,status:'confirmed'}]}
  expect(buildCompanyDirectory(firms,profiles,accounts,members,current)[0].parents[0].name).toBe('Confirmed Group')
  current.relationships[0].status='proposed'
  expect(buildCompanyDirectory(firms,profiles,accounts,members,current)[0].parents[0].name).toBe('Recorded Group')
  current.relationships[0].status='confirmed';current.relationships[0].valid_to='2025-01-01'
  expect(buildCompanyDirectory(firms,profiles,accounts,members,current)[0].parents[0].name).toBe('Recorded Group')
})

test('company table loads without tab hunting, searches retained aliases, and shows navigable parent groups',async()=>{
  mocks.evidence.mockResolvedValue(evidence)
  render(<AdminFirmDirectory firms={firms} profiles={profiles} accounts={accounts} members={members}/>)
  expect(screen.getByRole('table')).toBeTruthy()
  expect(screen.getByRole('link',{name:'Reviewed Water'}).getAttribute('href')).toBe('#/admin-company/master')
  fireEvent.change(screen.getByLabelText('Search all firms'),{target:{value:'Private legacy'}})
  expect(screen.getByRole('link',{name:'Reviewed Water'})).toBeTruthy()
  expect(screen.queryByRole('link',{name:'Water Inc'})).toBeNull()
  fireEvent.click(screen.getByRole('link',{name:'Parent groups'}))
  expect(await screen.findByText('Recorded Group')).toBeTruthy()
  expect((await screen.findByRole('link',{name:'Reviewed Water evidence ↗'})).getAttribute('href')).toBe('https://example.com/recorded')
})

test('pagination and coverage filters include firms beyond the first page; evidence failure never empties the directory',async()=>{
  mocks.evidence.mockRejectedValue(new Error('API unavailable'))
  const many=Array.from({length:125},(_,i)=>firm(`id${i}`,`Firm ${String(i).padStart(3,'0')}`))
  render(<AdminFirmDirectory firms={many} profiles={[]} accounts={[]} members={[]}/>)
  expect(await screen.findByRole('alert')).toHaveTextContent('API unavailable')
  expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(51)
  fireEvent.click(screen.getByRole('button',{name:'Next'}))
  expect(screen.getAllByRole('link',{name:'Firm 050'})[0]).toBeTruthy()
  fireEvent.change(screen.getByLabelText('Search all firms'),{target:{value:'Firm 124'}})
  expect(screen.getAllByRole('link',{name:'Firm 124'})[0]).toBeTruthy()
  expect(await screen.findByRole('alert')).toHaveTextContent('API unavailable')
  fireEvent.change(screen.getByLabelText('Firm mapping coverage'),{target:{value:'mapped'}})
  expect(screen.getByText(/No companies match/)).toBeTruthy()
})
