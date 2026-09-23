import { expect, test, vi } from 'vitest'
import { applyCompanyAdminImport, parseCompanyAdminImport, COMPANY_ADMIN_IMPORT_SCHEMA } from '../../src/companyAdmin/import'
import * as client from '../../src/companyAdmin/client'
import type { KnownFirmSummaryRecord } from '../../src/types/firm'

vi.mock('../../src/companyAdmin/client', () => ({
  loadCompanyAdminAccess: vi.fn(),
  saveCompanyAdminProfile: vi.fn(),
  saveCompanyAdminContact: vi.fn(),
}))

const firm = {
  firm_id:'known-firm-alpha',
  canonical_name:'ALPHA WATER LLC',
} as KnownFirmSummaryRecord

test('private import accepts only exact known-firm identity matches', () => {
  const parsed = parseCompanyAdminImport(JSON.stringify({
    schema: COMPANY_ADMIN_IMPORT_SCHEMA,
    companies:[{
      company_id:'known-firm-alpha',
      canonical_name:'ALPHA WATER LLC',
      profile:{ website:'https://alpha.example', website_source_url:'https://alpha.example' },
      contacts:[{ contact_id:'alpha-sales', name:'Sales', email:'sales@alpha.example', active:true }],
    }],
  }), [firm])
  expect(parsed.companies).toHaveLength(1)
  expect(parsed.companies[0].contacts).toHaveLength(1)

  expect(() => parseCompanyAdminImport(JSON.stringify({
    schema: COMPANY_ADMIN_IMPORT_SCHEMA,
    companies:[{ company_id:'known-firm-alpha', canonical_name:'Alpha Water', profile:{} }],
  }), [firm])).toThrow(/Canonical-name mismatch/)

  expect(() => parseCompanyAdminImport(JSON.stringify({
    schema: COMPANY_ADMIN_IMPORT_SCHEMA,
    companies:[{ company_id:'unknown', canonical_name:'UNKNOWN', profile:{} }],
  }), [firm])).toThrow(/Unknown TowerSignal firm_id/)
})

test('private import rechecks admin access and writes profiles before contacts', async () => {
  vi.mocked(client.loadCompanyAdminAccess).mockResolvedValue(true)
  vi.mocked(client.saveCompanyAdminProfile).mockResolvedValue({} as never)
  vi.mocked(client.saveCompanyAdminContact).mockResolvedValue({} as never)

  const bundle = parseCompanyAdminImport(JSON.stringify({
    schema: COMPANY_ADMIN_IMPORT_SCHEMA,
    companies:[{
      company_id:'known-firm-alpha',
      canonical_name:'ALPHA WATER LLC',
      profile:{ relationship_status:'researching', website:'https://alpha.example' },
      contacts:[{ contact_id:'alpha-sales', name:'Sales', email:null, title:null, phone:null, linkedin_url:null, notes:null, source_name:null, source_url:null, verified_at:null, active:true }],
    }],
  }), [firm])

  await expect(applyCompanyAdminImport(bundle)).resolves.toEqual({ companies:1, contacts:1 })
  expect(client.saveCompanyAdminProfile).toHaveBeenCalledWith('known-firm-alpha', 'ALPHA WATER LLC', expect.objectContaining({ website:'https://alpha.example' }))
  expect(client.saveCompanyAdminContact).toHaveBeenCalledWith('alpha-sales', 'known-firm-alpha', expect.objectContaining({ name:'Sales' }))
})

test('private import fails closed for non-admin users', async () => {
  vi.mocked(client.loadCompanyAdminAccess).mockResolvedValue(false)
  const bundle = parseCompanyAdminImport(JSON.stringify({
    schema: COMPANY_ADMIN_IMPORT_SCHEMA,
    companies:[{ company_id:'known-firm-alpha', canonical_name:'ALPHA WATER LLC', profile:{} }],
  }), [firm])
  await expect(applyCompanyAdminImport(bundle)).rejects.toThrow(/Admin company-database access is required/)
  expect(client.saveCompanyAdminProfile).not.toHaveBeenCalled()
})
