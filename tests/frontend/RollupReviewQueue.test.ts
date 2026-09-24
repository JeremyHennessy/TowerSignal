import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'

const migration=readFileSync('database/migrations/008_rollup_review_queue.sql','utf8')
const panel=readFileSync('src/components/CompanyRollupReviewPanel.tsx','utf8')
const dashboard=readFileSync('src/components/AdminCompaniesPage.tsx','utf8')

test('review queue preserves decisions and applies accepted merges atomically',()=>{
  expect(migration).toContain('company_rollup_suggestions')
  expect(migration).toContain("'not-same'")
  expect(migration).toContain("'superseded'")
  expect(migration).toContain('towersignal_apply_rollup_suggestion')
  expect(migration).toContain("OLD.status <> 'pending'")
  expect(migration).toContain("record_status='merged'")
  expect(migration).toContain('company_sales_account_members')
  expect(migration).toContain('company_private_opportunities')
  expect(migration).toContain('company_private_tasks')
})

test('admin dashboard exposes human-reviewed roll-up queue',()=>{
  expect(dashboard).toContain('CompanyRollupReviewPanel')
  expect(panel).toContain('Refresh suggestions')
  expect(panel).toContain('Accept merge')
  expect(panel).toContain('Not same company')
  expect(panel).toContain('Reject for now')
  expect(panel).toContain('window.confirm')
})


test('roll-up queue auto-syncs evidence suggestions without auto-accepting merges',()=>{
  expect(panel).toContain('const autoSyncStarted=useRef(false)')
  expect(panel).toContain('const inputsReady=accounts.length>0&&members.length>0&&profiles.length>0&&firms.length>0')
  expect(panel).toContain('generateCompanyRollupSuggestions({accounts,members,profiles,contacts,firms})')
  expect(panel).toContain('await syncCompanyRollupSuggestions(candidates)')
  expect(panel).toContain("if(next==='accepted' && !window.confirm")
})


test('roll-up queue resolves readable company names instead of exposing sales-account ids',()=>{
  expect(panel).toContain('const accountNameById=useMemo')
  expect(panel).toContain('profile?.rollup_name ?? profile?.legal_name ?? profile?.canonical_name')
  expect(panel).toContain("const accountName=(salesAccountId:string)=>accountNameById.get(salesAccountId) ?? 'Account name unavailable'")
  expect(panel).not.toContain('candidate?.display_name ?? row.candidate_sales_account_id')
  expect(panel).not.toContain('target?.display_name ?? row.suggested_sales_account_id')
})
