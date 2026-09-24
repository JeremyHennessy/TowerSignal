import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'

const migration=readFileSync('database/migrations/007_master_sales_accounts.sql','utf8')
const dashboard=readFileSync('src/components/AdminCompaniesPage.tsx','utf8')
const detail=readFileSync('src/components/AdminCompanyProfilePage.tsx','utf8')
const client=readFileSync('src/companyAdmin/client.ts','utf8')

test('master sales-account migration preserves every reviewed source identity and rollup',()=>{
  expect(migration).toContain('company_sales_accounts')
  expect(migration).toContain('company_sales_account_members')
  expect(migration).toContain("COALESCE(p.rollup_company_id,p.company_id)")
  expect(migration).toContain("v_members <> v_profiles")
  expect(migration).toContain("v_profiles - v_expected_accounts <> v_rollups")
  expect(migration).toContain("changed a reviewed master decision")
  expect(migration).toContain("master-sales-account-migration-20260924")
})

test('admin CRM is driven by durable sales accounts rather than inferred rollup IDs',()=>{
  expect(client).toContain('loadCompanySalesAccounts')
  expect(client).toContain('loadCompanySalesAccountMembers')
  expect(dashboard).toContain('membersBySalesAccount')
  expect(dashboard).toContain('account.sales_account_id')
  expect(dashboard).toContain('account.primary_company_id')
  expect(detail).toContain('CompanySalesAccountPanel')
  expect(detail).toContain('account.display_name')
  expect(detail).toContain('account.account_classification')
  expect(detail).not.toContain('CompanyFamilyPanel')
})
