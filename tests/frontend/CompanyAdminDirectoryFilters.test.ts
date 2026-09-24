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
