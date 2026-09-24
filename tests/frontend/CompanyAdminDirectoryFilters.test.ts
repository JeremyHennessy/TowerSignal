import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'

const source = readFileSync('src/components/CompaniesPage.tsx', 'utf8')

test('admin company directory searches private CRM fields and exposes operational filters', () => {
  for (const field of [
    'profile.legal_name',
    'profile.rollup_name',
    'profile.website',
    'profile.parent_company_name',
    'profile.headquarters_address',
    'profile.account_owner',
    'profile.internal_summary',
  ]) expect(source).toContain(field)

  expect(source).toContain('CRM relationship status')
  expect(source).toContain('Private enrichment gap')
  expect(source).toContain('Contacted · no next action')
  expect(source).toContain('href="#/service"')
})


const css = readFileSync('src/styles/known-firms.css', 'utf8')

test('company directory stays primary and admin controls do not distort the master table layout', () => {
  const tableIndex = source.indexOf('known-firms-master-card')
  const adminToolsIndex = source.indexOf('<details id="company-admin-tools"')
  expect(tableIndex).toBeGreaterThan(-1)
  expect(adminToolsIndex).toBeGreaterThan(tableIndex)
  expect(source).toContain("admin-filters")
  expect(source).toContain("admin-company-table")
  expect(css).toContain('.known-firms-master-table.admin-company-table{min-width:1580px}')
  expect(css).toContain('.firm-master-filters input{grid-column:1/-1;grid-row:auto}')
  expect(css).not.toContain('.firm-master-filters input{grid-row:span 2}')
})
