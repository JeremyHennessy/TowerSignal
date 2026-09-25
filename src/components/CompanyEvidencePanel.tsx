import { useEffect, useState } from 'react'
import {
  addCompanyEnrichmentSource, addCompanyParent, loadCompanyEvidence, proposeCompanyParent,
  reviewCompanyEnrichmentCandidate, reviewCompanyParent, setCompanyEnrichmentSourceEnabled,
} from '../companyAdmin/client'
import type { CompanyEvidence } from '../companyAdmin/evidence'
import { observationText, validObservationDate } from '../companyAdmin/evidence'
import type { CompanySalesAccount } from '../types/companyAdmin'

export function CompanyEvidencePanel({accounts}:{accounts:CompanySalesAccount[]}) {
  const [data,setData]=useState<CompanyEvidence|null>(null)
  const [error,setError]=useState<string|null>(null)
  const [busy,setBusy]=useState(false)
  const [accountId,setAccountId]=useState('')
  const [parentId,setParentId]=useState('')
  const [parentName,setParentName]=useState('')
  const [parentWebsite,setParentWebsite]=useState('')
  const [evidenceUrl,setEvidenceUrl]=useState('')
  const [evidenceNote,setEvidenceNote]=useState('')
  const [observedOn,setObservedOn]=useState('')
  const [sourceUrl,setSourceUrl]=useState('')
  const [expectedName,setExpectedName]=useState('')
  const active=accounts.filter(a=>a.record_status==='active')
  const accountName=(id:string)=>accounts.find(a=>a.sales_account_id===id)?.display_name??'Account unavailable'
  const reload=async()=>setData(await loadCompanyEvidence())
  useEffect(()=>{
    let cancelled=false
    void (async()=>{try{const next=await loadCompanyEvidence();if(!cancelled)setData(next)}catch{if(!cancelled)setError('Company evidence is unavailable. The database upgrade or access check may still be pending.')}})()
    return()=>{cancelled=true}
  },[])
  const act=async(action:()=>Promise<void>)=>{
    setBusy(true);setError(null)
    try{await action();await reload()}catch(err){setError(err instanceof Error?err.message:'Unable to save evidence')}
    finally{setBusy(false)}
  }
  const latest=data?.runs[0]
  return <section className="admin-company-card company-evidence-panel" aria-label="Parent mapping and enrichment">
    <div className="admin-company-card-heading"><div><strong>Parent mapping &amp; enrichment</strong><span>Reviewed ownership and recurring checks of approved company pages</span></div><button disabled={busy} onClick={()=>void act(async()=>{})}>Refresh status</button></div>
    {error&&<div className="company-admin-error" role="alert">{error}</div>}
    {!data&&!error&&<p>Loading company evidence…</p>}
    {data&&<>
      <div className="admin-company-metrics admin-company-metrics-compact">
        <article><small>Confirmed parent links</small><strong>{data.relationships.filter(r=>r.status==='confirmed').length}</strong><span>{data.relationships.filter(r=>r.status==='proposed').length} awaiting review</span></article>
        <article><small>Approved sources</small><strong>{data.sources.filter(s=>s.enabled).length}</strong><span>{data.sources.filter(s=>s.last_outcome==='failed').length} with failed last checks</span></article>
        <article><small>Pending observations</small><strong>{data.candidates.length===100?'100+':data.candidates.length}</strong><span>Evidence to review before updating profiles</span></article>
      </div>
      <p>{latest?`Last run: ${new Date(latest.started_at).toLocaleString()} · ${latest.status} · ${latest.checked_count} checked, ${latest.observed_count} observed, ${latest.unresolved_count} unresolved, ${latest.failed_count} failed.`:'No enrichment runs recorded. Scheduled checks require activation after release.'}</p>
      <p>Existing recorded parents and company mappings remain below. New links are separate reviewed records; source observations do not overwrite company details.</p>
      <label><span>Company account</span><select aria-label="Evidence company account" value={accountId} onChange={e=>setAccountId(e.target.value)}><option value="">Choose an account</option>{active.map(a=><option key={a.sales_account_id} value={a.sales_account_id}>{a.display_name}</option>)}</select></label>
      <details><summary>Parent entities and ownership evidence</summary>
        <div className="company-sales-account-form">
          <label><span>New parent name</span><input value={parentName} onChange={e=>setParentName(e.target.value)}/></label>
          <label><span>Parent website (optional)</span><input type="url" value={parentWebsite} onChange={e=>setParentWebsite(e.target.value)}/></label>
          <button disabled={busy||!parentName.trim()} onClick={()=>void act(async()=>{await addCompanyParent(parentName,parentWebsite);setParentName('');setParentWebsite('')})}>Create parent entity</button>
          <label><span>Parent entity</span><select value={parentId} onChange={e=>setParentId(e.target.value)}><option value="">Choose a parent</option>{data.parents.map(p=><option key={p.parent_entity_id} value={p.parent_entity_id}>{p.display_name}</option>)}</select></label>
          <label><span>Ownership evidence URL</span><input type="url" value={evidenceUrl} onChange={e=>setEvidenceUrl(e.target.value)}/></label>
          <label><span>Observed on</span><input type="text" aria-label="Observed on" placeholder="YYYY-MM-DD" aria-describedby="parent-date-help" aria-invalid={Boolean(observedOn)&&!validObservationDate(observedOn)} value={observedOn} onChange={e=>setObservedOn(e.target.value)}/><small id="parent-date-help">Date you checked the source, in YYYY-MM-DD format.</small></label>
          <button type="button" onClick={()=>{const now=new Date();setObservedOn(`${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`)}}>Use today</button>
          <label className="wide"><span>What the source establishes</span><textarea value={evidenceNote} onChange={e=>setEvidenceNote(e.target.value)}/></label>
          <button disabled={busy||!accountId||!parentId||!validObservationDate(observedOn)||!evidenceUrl||!evidenceNote.trim()} onClick={()=>void act(()=>proposeCompanyParent({sales_account_id:accountId,parent_entity_id:parentId,relationship_type:'parent',evidence_url:evidenceUrl,evidence_note:evidenceNote,observed_on:observedOn,valid_from:null,valid_to:null}))}>Propose parent link</button>
        </div>
        <div className="table-scroll"><table className="account-table"><thead><tr><th>Account</th><th>Parent</th><th>Evidence</th><th>Status</th><th>Review</th></tr></thead><tbody>{data.relationships.map(r=><tr key={r.relationship_id}><td>{accountName(r.sales_account_id)}</td><td>{data.parents.find(p=>p.parent_entity_id===r.parent_entity_id)?.display_name}</td><td><a href={r.evidence_url} target="_blank" rel="noreferrer">Source ↗</a><small>{r.observed_on} · {r.evidence_note}</small></td><td>{r.status}</td><td>{r.status==='proposed'&&<button disabled={busy} onClick={()=>{if(window.confirm('Confirm this evidence-backed parent relationship? Existing legacy mappings will remain unchanged.'))void act(()=>reviewCompanyParent(r.relationship_id,'confirmed'))}}>Confirm</button>}{r.status!=='historical'&&<button disabled={busy} onClick={()=>void act(()=>reviewCompanyParent(r.relationship_id,'historical'))}>Archive link</button>}</td></tr>)}</tbody></table></div>
      </details>
      <details><summary>Approved enrichment sources</summary>
        <p>Approve an official HTTPS page and the exact organization name it publishes. Checks run weekly once activated. Pages without matching structured company data remain unresolved.</p>
        <div className="company-sales-account-form">
          <label><span>Official source URL</span><input type="url" value={sourceUrl} onChange={e=>setSourceUrl(e.target.value)}/></label>
          <label><span>Exact published organization name</span><input value={expectedName} onChange={e=>setExpectedName(e.target.value)}/></label>
          <button disabled={busy||!accountId||!sourceUrl||!expectedName.trim()} onClick={()=>void act(async()=>{await addCompanyEnrichmentSource(accountId,sourceUrl,expectedName);setSourceUrl('');setExpectedName('')})}>Approve source for checks</button>
        </div>
        <div className="table-scroll"><table className="account-table"><thead><tr><th>Account</th><th>Source</th><th>Last attempt</th><th>Outcome</th><th>Schedule</th></tr></thead><tbody>{data.sources.map(s=><tr key={s.source_id}><td>{accountName(s.sales_account_id)}</td><td><a href={s.source_url} target="_blank" rel="noreferrer">{s.expected_name} ↗</a></td><td>{s.last_attempt_at?new Date(s.last_attempt_at).toLocaleString():'Never checked'}</td><td>{s.last_outcome??'Not yet checked'}{s.last_error&&<small>{s.last_error}</small>}</td><td><button disabled={busy} onClick={()=>void act(()=>setCompanyEnrichmentSourceEnabled(s.source_id,!s.enabled))}>{s.enabled?'Pause':'Enable'}</button></td></tr>)}</tbody></table></div>
      </details>
      <details><summary>Review enrichment observations</summary>
        <p>Review the source and update the company’s Research record where appropriate. “Reviewed” closes this observation only; it does not publish a profile change. An organization address may be a branch rather than headquarters.</p>
        {data.candidates.map(c=><article key={c.candidate_id} className="company-enrichment-observation"><strong>{accountName(c.sales_account_id)} · {c.field_name==='headquarters'?'Reported organization address':c.field_name.replaceAll('_',' ')}</strong><p>{observationText(c.proposed_value)}</p><small>Observed {new Date(c.last_observed_at).toLocaleString()}</small><div><a href={c.source_url} target="_blank" rel="noreferrer">Review source ↗</a>{accounts.find(a=>a.sales_account_id===c.sales_account_id)&&<a href={`#/admin-company/${encodeURIComponent(accounts.find(a=>a.sales_account_id===c.sales_account_id)!.primary_company_id)}`}>Open company record</a>}<button disabled={busy} onClick={()=>void act(()=>reviewCompanyEnrichmentCandidate(c.candidate_id,'reviewed'))}>Reviewed</button><button disabled={busy} onClick={()=>void act(()=>reviewCompanyEnrichmentCandidate(c.candidate_id,'rejected'))}>Reject</button></div></article>)}
        {!data.candidates.length&&<p>No pending observations. This does not mean all companies are enriched.</p>}
      </details>
    </>}
  </section>
}
