import { useEffect, useState } from 'react'
import { loadCompanySalesAccount, saveCompanySalesAccount } from '../companyAdmin/client'
import type { CompanySalesAccount, CompanySalesAccountClassification } from '../types/companyAdmin'

const classifications:CompanySalesAccountClassification[]=[
  'target','active-prospect','customer','former-customer','partner','competitor','do-not-pursue',
]

function human(value:string){return value.replaceAll('-',' ').replace(/(^|\s)\S/g,m=>m.toUpperCase())}

export function CompanySalesAccountPanel({salesAccountId}:{salesAccountId:string}) {
  const [account,setAccount]=useState<CompanySalesAccount|null>(null)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState<string|null>(null)

  useEffect(()=>{
    let cancelled=false
    loadCompanySalesAccount(salesAccountId)
      .then(value=>{if(!cancelled)setAccount(value)})
      .catch(err=>{if(!cancelled)setError(err instanceof Error?err.message:'Unable to load sales account')})
    return()=>{cancelled=true}
  },[salesAccountId])

  const save=async()=>{
    if(!account||!account.display_name.trim()) return
    setBusy(true);setError(null)
    try{
      const saved=await saveCompanySalesAccount(account.sales_account_id,{
        display_name:account.display_name.trim(),
        account_classification:account.account_classification,
        parent_name:account.parent_name?.trim()||null,
        parent_source_url:account.parent_source_url?.trim()||null,
        account_owner:account.account_owner?.trim()||null,
        sales_notes:account.sales_notes?.trim()||null,
      })
      setAccount(saved)
    }catch(err){setError(err instanceof Error?err.message:'Unable to save sales account')}
    finally{setBusy(false)}
  }

  if(!account) return error ? <div className="company-admin-error"><strong>Sales account unavailable.</strong><span>{error}</span></div> : null

  return <section className="company-sales-account-panel" aria-label="Master sales account">
    <div className="company-admin-card-heading"><div><strong>Master sales account</strong><span>Authoritative internal TowerSignal account record</span></div><span>{human(account.account_classification)}</span></div>
    {error&&<div className="company-admin-error"><strong>Sales account error.</strong><span>{error}</span></div>}
    <div className="company-sales-account-form">
      <label><span>Account name</span><input value={account.display_name} onChange={e=>setAccount(v=>v?({...v,display_name:e.target.value}):v)} /></label>
      <label><span>Classification</span><select value={account.account_classification} onChange={e=>setAccount(v=>v?({...v,account_classification:e.target.value as CompanySalesAccountClassification}):v)}>{classifications.map(value=><option key={value} value={value}>{human(value)}</option>)}</select></label>
      <label><span>Account owner</span><input value={account.account_owner??''} onChange={e=>setAccount(v=>v?({...v,account_owner:e.target.value}):v)} placeholder="Jeremy" /></label>
      <label><span>Parent / owner</span><input value={account.parent_name??''} onChange={e=>setAccount(v=>v?({...v,parent_name:e.target.value}):v)} /></label>
      <label className="wide"><span>Parent evidence URL</span><input type="url" value={account.parent_source_url??''} onChange={e=>setAccount(v=>v?({...v,parent_source_url:e.target.value}):v)} /></label>
      <label className="wide"><span>Sales notes</span><textarea rows={3} value={account.sales_notes??''} onChange={e=>setAccount(v=>v?({...v,sales_notes:e.target.value}):v)} placeholder="Internal TowerSignal sales account context" /></label>
    </div>
    <div className="company-sales-account-actions"><button onClick={()=>void save()} disabled={busy||!account.display_name.trim()}>{busy?'Saving…':'Save sales account'}</button></div>
  </section>
}
