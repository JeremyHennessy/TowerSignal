import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'

const migration=readFileSync('database/migrations/009_authoritative_sales_workflow.sql','utf8')
const adminPanel=readFileSync('src/components/CompanyAdminPanel.tsx','utf8')
const dashboard=readFileSync('src/components/AdminCompaniesPage.tsx','utf8')
const importer=readFileSync('src/companyAdmin/import.ts','utf8')

test('sales account, opportunity and task state are authoritative',()=>{
  expect(migration).toContain('company_sales_pipeline_state')
  expect(migration).toContain('Legacy source-identity CRM field')
  expect(migration).toContain('company_private_opportunities.stage')
  expect(migration).toContain('company_private_tasks.due_at')
  expect(dashboard).toContain('account.account_classification')
  expect(dashboard).toContain('activeFamilyOpportunities')
  expect(dashboard).toContain('familyTasks')
  expect(dashboard).toContain('Admin account classification filter')
})

test('source enrichment editor no longer mutates legacy sales workflow fields',()=>{
  expect(adminPanel).not.toContain('Relationship &amp; follow-up')
  expect(adminPanel).not.toContain('Activity next action')
  expect(adminPanel.toLowerCase()).toContain('sales stage, tasks and next actions are managed in the authoritative sales crm above')
  expect(adminPanel).not.toContain("relationship_status: profile.relationship_status === 'uncontacted'")
  expect(adminPanel).not.toContain('setActivityNextAction')
  expect(importer).not.toContain("'relationship_status',")
  expect(importer).not.toContain("'next_action_date',")
  expect(importer).not.toContain("'account_owner',")
})
