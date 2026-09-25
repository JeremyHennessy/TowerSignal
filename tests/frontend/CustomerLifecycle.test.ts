import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'

const migration=readFileSync('database/migrations/011_customer_lifecycle.sql','utf8')
const client=readFileSync('src/companyAdmin/client.ts','utf8')
const types=readFileSync('src/types/companyAdmin.ts','utf8')
const panel=readFileSync('src/components/CompanyCustomerLifecyclePanel.tsx','utf8')
const profile=readFileSync('src/components/AdminCompanyProfilePage.tsx','utf8')
const commandCenter=readFileSync('src/components/AdminCompaniesPage.tsx','utf8')
const salesToday=readFileSync('src/components/AdminSalesTodayPanel.tsx','utf8')
const release=readFileSync('.github/workflows/fast-company-crm-service-release-20260924.yml','utf8')

test('customer lifecycle schema is private, audited and keyed to master sales accounts',()=>{
  expect(migration).toContain('CREATE TABLE IF NOT EXISTS public.company_sales_subscriptions')
  expect(migration).toContain('CREATE TABLE IF NOT EXISTS public.company_sales_renewals')
  expect(migration).toContain('company_sales_renewals_subscription_account_fk')
  expect(migration).toContain('company_sales_subscriptions_admin_only')
  expect(migration).toContain('company_sales_renewals_admin_only')
  expect(migration).toContain("towersignal_audit_sales_account('subscription','subscription_id')")
  expect(migration).toContain("towersignal_audit_sales_account('renewal','renewal_id')")
  expect(migration).toContain('company_sales_customer_lifecycle_state')
})

test('client and types expose subscription and renewal CRUD',()=>{
  expect(types).toContain('export interface CompanySalesSubscription')
  expect(types).toContain('export interface CompanySalesRenewal')
  expect(client).toContain('loadCompanyAdminOverview')
  expect(client).toContain('addCompanySalesSubscription')
  expect(client).toContain('saveCompanySalesSubscription')
  expect(client).toContain('loadCompanyAdminOverview')
  expect(client).toContain('addCompanySalesRenewal')
  expect(client).toContain('saveCompanySalesRenewal')
})

test('company CRM exposes customer lifecycle and renewal attention',()=>{
  expect(profile).toContain('CompanyCustomerLifecyclePanel')
  expect(panel).toContain('Customer lifecycle')
  expect(panel).toContain('Add subscription')
  expect(panel).toContain('Add renewal')
  expect(panel).toContain('Live ARR')
  expect(commandCenter).toContain('loadCompanyAdminOverview')
  expect(commandCenter).toContain('loadCompanyAdminOverview')
  expect(commandCenter).toContain('subscriptions={salesSubscriptions}')
  expect(commandCenter).toContain('renewals={salesRenewals}')
  expect(salesToday).toContain('Renewal attention')
  expect(salesToday).toContain('Renewal workflow missing')
})

test('guarded CRM release includes lifecycle files and hosted marker',()=>{
  expect(release).toContain('database/migrations/011_customer_lifecycle.sql')
  expect(release).toContain('src/components/CompanyCustomerLifecyclePanel.tsx')
  expect(release).toContain('tests/frontend/CustomerLifecycle.test.ts')
  expect(release).toContain('Customer lifecycle')
})
