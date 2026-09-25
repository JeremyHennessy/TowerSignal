import { readFileSync } from 'node:fs'
import { expect, test, vi } from 'vitest'
import { createElement } from 'react'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { CompanyRollupReviewPanel } from '../../src/components/CompanyRollupReviewPanel'
import type { CompanySalesAccount } from '../../src/types/companyAdmin'

const reviewMocks=vi.hoisted(()=>({load:vi.fn(),review:vi.fn(),sync:vi.fn()}))
vi.mock('../../src/companyAdmin/client',()=>({
  loadCompanyRollupSuggestions:reviewMocks.load,
  loadCompanySalesAccounts:vi.fn().mockResolvedValue([{sales_account_id:'old',display_name:'Historical Source Company'}]),
  reviewCompanyRollupSuggestion:reviewMocks.review,
  syncCompanyRollupSuggestions:reviewMocks.sync,
}))

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

test('mapping table requires a row decision and confirmation before merging',async()=>{
  const pending={suggestion_id:'test-review',candidate_sales_account_id:'source',suggested_sales_account_id:'target',score:55,confidence:'low',evidence:['Similar name only'],status:'pending',review_note:null,reviewed_at:null}
  reviewMocks.load.mockResolvedValue([pending])
  reviewMocks.review.mockResolvedValue(undefined)
  const changed=vi.fn().mockResolvedValue(undefined)
  const confirm=vi.spyOn(window,'confirm').mockReturnValue(false)
  render(createElement(CompanyRollupReviewPanel,{
    accounts:[{sales_account_id:'source',display_name:'Source Company'},{sales_account_id:'target',display_name:'Target Company'}] as CompanySalesAccount[],
    members:[],profiles:[],contacts:[],firms:[],onChanged:changed,
  }))
  try{
    await screen.findByText('Similar name only')
    expect(screen.getByRole('table',{name:'Company mapping suggestions'})).toBeTruthy()
    const apply=screen.getByRole('button',{name:'Apply'}) as HTMLButtonElement
    expect(apply.disabled).toBe(true)
    fireEvent.change(screen.getByLabelText('Decision for Source Company'),{target:{value:'accepted'}})
    fireEvent.click(apply)
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('Source Company'))
    expect(reviewMocks.review).not.toHaveBeenCalled()
    confirm.mockReturnValue(true)
    reviewMocks.load.mockResolvedValue([{...pending,status:'accepted'}])
    fireEvent.click(apply)
    await waitFor(()=>expect(reviewMocks.review).toHaveBeenCalledWith('test-review','accepted'))
    await screen.findByText('No pending mapping suggestions.')
    expect(changed).toHaveBeenCalledTimes(1)
    fireEvent.change(screen.getByLabelText('Roll-up suggestion status'),{target:{value:'accepted'}})
    expect(screen.getByRole('link',{name:'Source Company'})).toBeTruthy()
    expect(screen.queryByRole('button',{name:'Apply'})).toBeNull()
  }finally{confirm.mockRestore();cleanup()}
})
