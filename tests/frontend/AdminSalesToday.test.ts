import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'

const dashboard=readFileSync('src/components/AdminCompaniesPage.tsx','utf8')
const today=readFileSync('src/components/AdminSalesTodayPanel.tsx','utf8')
const detail=readFileSync('src/components/AdminCompanyProfilePage.tsx','utf8')

test('admin command center uses focused workspaces instead of one long dashboard',()=>{
  expect(dashboard).toContain("navigation.choice('section',['today','pipeline','accounts','data'] as const,'accounts')")
  expect(dashboard).toContain("workspaceView==='today'")
  expect(dashboard).toContain("workspaceView==='pipeline'")
  expect(dashboard).toContain("workspaceView==='accounts'")
  expect(dashboard).toContain("workspaceView==='data'")
  expect(dashboard).toContain('Actions &amp; exceptions')
  expect(dashboard).toContain('Deals &amp; targets')
  expect(dashboard).toContain('Data &amp; ops')
  expect(dashboard).toContain('admin-family-table-compact')
  expect(dashboard).toContain('pipelineBoardStages.map')
})

test('Sales Today stays focused on actionable commercial exceptions',()=>{
  expect(today).toContain('What needs attention')
  expect(today).toContain('overdue')
  expect(today).toContain('due today')
  expect(today).toContain('demos')
  expect(today).toContain('renewals')
  expect(today).toContain('untouched 14+ days')
  expect(today).toContain('Recent sales activity')
  expect(today).toContain('admin-sales-recent-details')
})

test('company admin detail is split into focused sections',()=>{
  expect(detail).toContain("navigation.choice('section',['overview','sales','commercial','customer','research','audit'] as const,'overview')")
  expect(detail).toContain("section==='overview'")
  expect(detail).toContain("section==='sales'")
  expect(detail).toContain("section==='commercial'")
  expect(detail).toContain("section==='customer'")
  expect(detail).toContain("section==='research'")
  expect(detail).toContain("section==='audit'")
  expect(detail).toContain('CompanySalesCrmPanel')
  expect(detail).toContain('CompanyDemoProposalPanel')
  expect(detail).toContain('CompanyCustomerLifecyclePanel')
})
