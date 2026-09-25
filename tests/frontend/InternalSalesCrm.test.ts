import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'

const migration = readFileSync('database/migrations/006_internal_sales_crm.sql','utf8')
const client = readFileSync('src/companyAdmin/client.ts','utf8')
const dashboard = readFileSync('src/components/AdminCompaniesPage.tsx','utf8')
const detail = readFileSync('src/components/AdminCompanyProfilePage.tsx','utf8')
const crm = readFileSync('src/components/CompanySalesCrmPanel.tsx','utf8')
const knownFirms = readFileSync('src/components/CompaniesPage.tsx','utf8')

test('internal sales CRM has opportunity, task and buying-contact persistence', () => {
  expect(migration).toContain('company_private_opportunities')
  expect(migration).toContain('company_private_tasks')
  expect(migration).toContain('demo-scheduled')
  expect(migration).toContain('estimated_arr')
  expect(migration).toContain('proposal_sent_at')
  expect(migration).toContain('contact_role')
  expect(migration).toContain('primary_contact')
  expect(client).toContain('loadAllCompanySalesOpportunities')
  expect(client).toContain('loadAllCompanySalesTasks')
  expect(client).toContain('saveCompanySalesOpportunity')
  expect(client).toContain('saveCompanySalesTask')
})

test('admin dashboard is a personal TowerSignal sales CRM without changing Known Firms', () => {
  expect(dashboard).toContain('Active sales pipeline')
  expect(dashboard).toContain('Open pipeline ARR')
  expect(dashboard).toContain('Upcoming demos')
  expect(dashboard).toContain('Open proposals')
  expect(dashboard).toContain('Needs action')
  expect(detail).toContain('CompanySalesCrmPanel')
  expect(crm).toContain('Sales pipeline &amp; follow-up')
  expect(crm).toContain('Add opportunity')
  expect(crm).toContain('Tasks &amp; follow-ups')
  expect(knownFirms).not.toContain('CompanySalesCrmPanel')
  expect(knownFirms).not.toContain('TowerSignal sales pipeline')
})
