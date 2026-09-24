import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'

const migration=readFileSync('database/migrations/010_demo_proposal_workflow.sql','utf8')
const client=readFileSync('src/companyAdmin/client.ts','utf8')
const types=readFileSync('src/types/companyAdmin.ts','utf8')
const panel=readFileSync('src/components/CompanyDemoProposalPanel.tsx','utf8')
const profile=readFileSync('src/components/AdminCompanyProfilePage.tsx','utf8')
const commandCenter=readFileSync('src/components/AdminCompaniesPage.tsx','utf8')
const salesToday=readFileSync('src/components/AdminSalesTodayPanel.tsx','utf8')

test('demo and proposal schema is private, audited and keyed to master sales accounts',()=>{
  expect(migration).toContain('CREATE TABLE IF NOT EXISTS public.company_sales_demos')
  expect(migration).toContain('CREATE TABLE IF NOT EXISTS public.company_sales_proposals')
  expect(migration).toContain('sales_account_id text NOT NULL REFERENCES public.company_sales_accounts')
  expect(migration).toContain('company_sales_demos_admin_only')
  expect(migration).toContain('company_sales_proposals_admin_only')
  expect(migration).toContain("towersignal_audit_sales_account('demo','demo_id')")
  expect(migration).toContain("towersignal_audit_sales_account('proposal','proposal_id')")
  expect(migration).toContain('company_sales_demo_proposal_state')
})

test('client and types expose durable demo and proposal CRUD',()=>{
  expect(types).toContain('export interface CompanySalesDemo')
  expect(types).toContain('export interface CompanySalesProposal')
  expect(client).toContain('loadAllCompanySalesDemos')
  expect(client).toContain('addCompanySalesDemo')
  expect(client).toContain('saveCompanySalesDemo')
  expect(client).toContain('loadAllCompanySalesProposals')
  expect(client).toContain('addCompanySalesProposal')
  expect(client).toContain('saveCompanySalesProposal')
})

test('company CRM exposes actual demo and proposal execution tracking',()=>{
  expect(profile).toContain('CompanyDemoProposalPanel')
  expect(panel).toContain('Demos &amp; proposals')
  expect(panel).toContain('Schedule demo')
  expect(panel).toContain('Add proposal')
  expect(panel).toContain('Procurement blockers')
  expect(commandCenter).toContain('loadAllCompanySalesDemos')
  expect(commandCenter).toContain('loadAllCompanySalesProposals')
  expect(commandCenter).toContain('demos={salesDemos}')
  expect(commandCenter).toContain('proposals={salesProposals}')
  expect(salesToday).toContain("demo.status==='scheduled'")
  expect(salesToday).toContain("['sent','revising'].includes(proposal.status)")
})
