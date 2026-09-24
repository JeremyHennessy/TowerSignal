import { useEffect, useMemo, useRef, useState } from 'react'
import {
  loadCompanyRollupSuggestions,
  reviewCompanyRollupSuggestion,
  syncCompanyRollupSuggestions,
} from '../companyAdmin/client'
import { generateCompanyRollupSuggestions } from '../companyAdmin/rollupSuggestions'
import type {
  CompanyAdminContact,
  CompanyAdminProfile,
  CompanyRollupSuggestion,
  CompanyRollupSuggestionStatus,
  CompanySalesAccount,
  CompanySalesAccountMember,
} from '../types/companyAdmin'
import type { KnownFirmSummaryRecord } from '../types/firm'

const statusOptions:CompanyRollupSuggestionStatus[]=['pending','accepted','rejected','not-same','superseded']

function human(value:string){return value.replaceAll('-',' ').replace(/(^|\s)\S/g,m=>m.toUpperCase())}

export function CompanyRollupReviewPanel({
  accounts,members,profiles,contacts,firms,onChanged,
}:{
  accounts:CompanySalesAccount[]
  members:CompanySalesAccountMember[]
  profiles:CompanyAdminProfile[]
  contacts:CompanyAdminContact[]
  firms:KnownFirmSummaryRecord[]
  onChanged:()=>Promise<void>
}) {
  const [rows,setRows]=useState<CompanyRollupSuggestion[]>([])
  const [status,setStatus]=useState<CompanyRollupSuggestionStatus>('pending')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState<string|null>(null)
  const autoSyncStarted=useRef(false)

  const reload=async()=>setRows(await loadCompanyRollupSuggestions())

  useEffect(()=>{
    let cancelled=false
    const hydrate=async()=>{
      try{
        const existing=await loadCompanyRollupSuggestions()
        if(!cancelled)setRows(existing)
        const inputsReady=accounts.length>0&&members.length>0&&profiles.length>0&&firms.length>0
        if(!inputsReady||autoSyncStarted.current)return
        autoSyncStarted.current=true
        const candidates=generateCompanyRollupSuggestions({accounts,members,profiles,contacts,firms})
        await syncCompanyRollupSuggestions(candidates)
        const updated=await loadCompanyRollupSuggestions()
        if(!cancelled)setRows(updated)
      }catch(err){
        if(!cancelled)setError(err instanceof Error?err.message:'Unable to synchronize roll-up suggestions')
      }
    }
    void hydrate()
    return()=>{cancelled=true}
  },[accounts,members,profiles,contacts,firms])

  const accountById=useMemo(()=>new Map(accounts.map(account=>[account.sales_account_id,account])),[accounts])
  const visible=rows.filter(row=>row.status===status)

  const refresh=async()=>{
    setBusy(true);setError(null)
    try{
      const candidates=generateCompanyRollupSuggestions({accounts,members,profiles,contacts,firms})
      await syncCompanyRollupSuggestions(candidates)
      await reload()
    }catch(err){setError(err instanceof Error?err.message:'Unable to refresh roll-up suggestions')}
    finally{setBusy(false)}
  }

  const review=async(row:CompanyRollupSuggestion,next:'accepted'|'rejected'|'not-same')=>{
    const candidate=accountById.get(row.candidate_sales_account_id)?.display_name ?? row.candidate_sales_account_id
    const target=accountById.get(row.suggested_sales_account_id)?.display_name ?? row.suggested_sales_account_id
    if(next==='accepted' && !window.confirm(`Merge "${candidate}" into "${target}"? This changes the private master sales-account roll-up while retaining every source identity.`)) return
    setBusy(true);setError(null)
    try{
      await reviewCompanyRollupSuggestion(row.suggestion_id,next)
      await Promise.all([reload(),onChanged()])
    }catch(err){setError(err instanceof Error?err.message:'Unable to review roll-up suggestion')}
    finally{setBusy(false)}
  }

  return <section className="admin-company-card company-rollup-review">
    <div className="admin-company-card-heading">
      <div><strong>Roll-up review queue</strong><span>Evidence-based suggestions only; no fuzzy merge is applied without review</span></div>
      <div className="company-rollup-review-actions">
        <select aria-label="Roll-up suggestion status" value={status} onChange={e=>setStatus(e.target.value as CompanyRollupSuggestionStatus)}>{statusOptions.map(value=><option key={value} value={value}>{human(value)}</option>)}</select>
        <button onClick={()=>void refresh()} disabled={busy}>{busy?'Working…':'Refresh suggestions'}</button>
      </div>
    </div>
    {error&&<div className="company-admin-error"><strong>Roll-up review error.</strong><span>{error}</span></div>}
    <div className="company-rollup-review-list">
      {visible.length ? visible.map(row=>{
        const candidate=accountById.get(row.candidate_sales_account_id)
        const target=accountById.get(row.suggested_sales_account_id)
        return <article key={row.suggestion_id}>
          <div className="company-rollup-review-main">
            <div><small>Candidate</small><strong>{candidate?.display_name ?? row.candidate_sales_account_id}</strong></div>
            <span aria-hidden="true">→</span>
            <div><small>Suggested master</small><strong>{target?.display_name ?? row.suggested_sales_account_id}</strong></div>
            <div className="company-rollup-score"><strong>{row.score}</strong><small>{human(row.confidence)}</small></div>
          </div>
          <div className="company-rollup-evidence">{row.evidence.map(item=><span key={item}>{item}</span>)}</div>
          {row.review_note&&<p>{row.review_note}</p>}
          {row.status==='pending'&&<div className="company-rollup-buttons">
            <button className="primary" onClick={()=>void review(row,'accepted')} disabled={busy}>Accept merge</button>
            <button onClick={()=>void review(row,'not-same')} disabled={busy}>Not same company</button>
            <button onClick={()=>void review(row,'rejected')} disabled={busy}>Reject for now</button>
          </div>}
          {row.status!=='pending'&&<small className="company-rollup-reviewed">{human(row.status)}{row.reviewed_at?` · ${new Date(row.reviewed_at).toLocaleString()}`:''}</small>}
        </article>
      }) : <span className="company-admin-empty">No {human(status).toLowerCase()} roll-up suggestions.</span>}
    </div>
  </section>
}
