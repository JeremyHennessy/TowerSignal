import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'

const source = readFileSync('src/components/AdminCompaniesPage.tsx', 'utf8')
const css = readFileSync('src/styles/company-admin-dashboard.css', 'utf8')

test('private company command center searches CRM fields and exposes operational filters', () => {
  for (const field of [
    'family.master.legal_name',
    'family.master.website',
    'family.parentName',
    'family.master.headquarters_address',
    'salesAccounts.find(account => account.sales_account_id===family.salesAccountId)?.account_owner',
    'family.master.internal_summary',
  ]) expect(source).toContain(field)

  expect(source).toContain('Admin account classification filter')
  expect(source).toContain('Admin enrichment gap filter')
  expect(source).toContain('Parent company hierarchy')
  expect(source).toContain('Master account directory')
  expect(source).toContain('href="#/companies"')
  expect(source).toContain('href="#/service"')
})

test('admin dashboard has independent responsive table and filter layout', () => {
  expect(css).toContain('.admin-family-table-compact{min-width:1180px}')
  expect(css).toContain('.admin-family-filters')
  expect(css).toContain('.admin-workspace-nav')
  expect(css).toContain('.admin-company-dashboard-grid')
  expect(css).toContain('.admin-parent-table')
})
