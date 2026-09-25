import { useEffect, useMemo, useRef, useState } from 'react'
import {
  loadCompanyRollupSuggestions,
  loadCompanySalesAccounts,
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
  const [historicalAccounts,setHistoricalAccounts]=useState<CompanySalesAccount[]>([])
  const [status,setStatus]=useState<CompanyRollupSuggestionStatus>('pending')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState<string|null>(null)
  const [decisions,setDecisions]=useState<Record<string,''|'accepted'|'rejected'|'not-same'>>({})
  const autoSyncStarted=useRef(false)

  const reload=async()=>setRows(await loadCompanyRollupSuggestions())

  useEffect(()=>{
    let cancelled=false
    const hydrate=async()=>{
      try{
        const [existing,allAccounts]=await Promise.all([loadCompanyRollupSuggestions(),loadCompanySalesAccounts(true)])
        if(!cancelled){setRows(existing);setHistoricalAccounts(allAccounts)}
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

  const profileById=useMemo(()=>new Map(profiles.map(profile=>[profile.company_id,profile])),[profiles])
  const accountNameById=useMemo(()=>{
    const labels=new Map([...historicalAccounts,...accounts].map(account=>[account.sales_account_id,account.display_name]))
    const grouped=new Map<string,CompanySalesAccountMember[]>()
    members.forEach(member=>{
      const current=grouped.get(member.sales_account_id) ?? []
      current.push(member)
      grouped.set(member.sales_account_id,current)
    })
    grouped.forEach((accountMembers,salesAccountId)=>{
      if(labels.has(salesAccountId)) return
      const preferred=accountMembers.find(member=>member.is_primary) ?? accountMembers[0]
      const profile=preferred ? profileById.get(preferred.company_id) : null
      const label=profile?.rollup_name ?? profile?.legal_name ?? profile?.canonical_name
      if(label) labels.set(salesAccountId,label)
    })
    return labels
  },[accounts,historicalAccounts,members,profileById])
  const accountName=(salesAccountId:string)=>accountNameById.get(salesAccountId) ?? 'Account name unavailable'
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
    const candidate=accountName(row.candidate_sales_account_id)
    const target=accountName(row.suggested_sales_account_id)
    if(next==='accepted' && !window.confirm(`Merge "${candidate}" into "${target}"? This changes the private master sales-account roll-up while retaining every source identity.`)) return
    setBusy(true);setError(null)
    try{
      await reviewCompanyRollupSuggestion(row.suggestion_id,next)
      await Promise.all([reload(),onChanged()])
    }catch(err){setError(err instanceof Error?err.message:'Unable to review roll-up suggestion')}
    finally{setBusy(false)}
  }

  return <section className="company-mapping-review" aria-label="Company mapping review">
    <div className="admin-company-card-heading">
      <div><strong>Company mapping review</strong><span>Compare identities before combining accounts. Name similarity alone is not proof.</span></div>
      <div className="company-rollup-review-actions">
        <select aria-label="Roll-up suggestion status" value={status} onChange={e=>setStatus(e.target.value as CompanyRollupSuggestionStatus)}>{statusOptions.map(value=><option key={value} value={value}>{human(value)}</option>)}</select>
        <button onClick={()=>void refresh()} disabled={busy}>{busy?'Working…':'Refresh suggestions'}</button>
      </div>
    </div>
    {error&&<div className="company-admin-error"><strong>Roll-up review error.</strong><span>{error}</span></div>}
    <div className="table-scroll"><table className="account-table company-mapping-table" aria-label="Company mapping suggestions">
      <thead><tr><th>Company</th><th>Suggested account</th><th>Match evidence</th><th>Confidence</th><th>Decision</th></tr></thead><tbody>
      {visible.length ? visible.map(row=>{
        const candidateName=accountName(row.candidate_sales_account_id)
        const targetName=accountName(row.suggested_sales_account_id)
        const decision=decisions[row.suggestion_id]??''
        const resolvable=accounts.some(a=>a.sales_account_id===row.candidate_sales_account_id)&&accounts.some(a=>a.sales_account_id===row.suggested_sales_account_id)
        return <tr key={row.suggestion_id}>
          <td><a href={`#/admin-company/${encodeURIComponent(row.candidate_sales_account_id)}`}>{candidateName}</a></td>
          <td><a href={`#/admin-company/${encodeURIComponent(row.suggested_sales_account_id)}`}>{targetName}</a></td>
          <td>{row.evidence.map(item=><small key={item}>{item}</small>)}{row.review_note&&<small>{row.review_note}</small>}</td>
          <td><strong>{human(row.confidence)}</strong><small>{row.score} / 100</small></td>
          <td>{row.status==='pending'?<div className="company-mapping-decision">
            <select aria-label={`Decision for ${candidateName}`} value={decision} disabled={busy||!resolvable} onChange={e=>setDecisions(current=>({...current,[row.suggestion_id]:e.target.value as typeof decision}))}><option value="">Choose decision</option><option value="accepted">Accept merge</option><option value="not-same">Not same company</option><option value="rejected">Reject for now</option></select>
            <button disabled={busy||!decision||!resolvable} onClick={()=>{if(decision)void review(row,decision)}}>Apply</button>
          </div>:<><strong>{human(row.status)}</strong><small>{row.reviewed_at?new Date(row.reviewed_at).toLocaleString():''}</small></>}</td>
        </tr>
      }) : <tr><td colSpan={5}>No {human(status).toLowerCase()} mapping suggestions.</td></tr>}
    </tbody></table></div>
  </section>
}
