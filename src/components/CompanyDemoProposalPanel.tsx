import { useEffect, useMemo, useState } from 'react'
import {
  addCompanySalesDemo,
  addCompanySalesProposal,
  loadCompanySalesDemos,
  loadCompanySalesOpportunities,
  loadCompanySalesProposals,
  saveCompanySalesDemo,
  saveCompanySalesProposal,
} from '../companyAdmin/client'
import type {
  CompanyAdminContact,
  CompanySalesDemo,
  CompanySalesDemoStatus,
  CompanySalesOpportunity,
  CompanySalesProposal,
  CompanySalesProposalStatus,
} from '../types/companyAdmin'

const demoStatuses:CompanySalesDemoStatus[]=['scheduled','completed','cancelled','no-show']
const proposalStatuses:CompanySalesProposalStatus[]=['draft','sent','revising','accepted','rejected','expired']

function human(value:string){return value.replaceAll('-',' ').replaceAll('_',' ').replace(/(^|\s)\S/g,m=>m.toUpperCase())}
function text(value:string):string|null{const v=value.trim();return v||null}
function numeric(value:string):number|null{if(!value.trim())return null;const n=Number(value);return Number.isFinite(n)?n:null}
function localDateTime(value:string|null):string{
  if(!value)return ''
  const date=new Date(value)
  if(Number.isNaN(date.getTime()))return ''
  return new Date(date.getTime()-date.getTimezoneOffset()*60_000).toISOString().slice(0,16)
}
function iso(value:string):string|null{return value?new Date(value).toISOString():null}
function money(value:number|null){return value==null?'—':value.toLocaleString(undefined,{style:'currency',currency:'USD',maximumFractionDigits:0})}

function emptyDemo():Omit<CompanySalesDemo,'demo_id'|'sales_account_id'|'created_at'|'updated_at'>{
  return {
    opportunity_id:null,primary_contact_id:null,status:'scheduled',scheduled_at:null,completed_at:null,
    meeting_url:null,attendees:[],demo_scope:null,demo_accounts:null,objections:null,outcome:null,next_step:null,notes:null,
  }
}
function emptyProposal():Omit<CompanySalesProposal,'proposal_id'|'sales_account_id'|'created_at'|'updated_at'>{
  return {
    opportunity_id:null,decision_maker_contact_id:null,status:'draft',package_name:'TowerSignal',
    proposed_arr:null,one_time_value:null,seats:null,term_months:12,sent_at:null,valid_until:null,
    expected_decision_date:null,proposal_url:null,procurement_blockers:null,objections:null,next_step:null,
    notes:null,accepted_at:null,rejected_at:null,rejection_reason:null,
  }
}

export function CompanyDemoProposalPanel({
  salesAccountId,companyId,contacts,
}:{
  salesAccountId:string
  companyId:string
  contacts:CompanyAdminContact[]
}) {
  const [demos,setDemos]=useState<CompanySalesDemo[]>([])
  const [proposals,setProposals]=useState<CompanySalesProposal[]>([])
  const [opportunities,setOpportunities]=useState<CompanySalesOpportunity[]>([])
  const [newDemo,setNewDemo]=useState(()=>emptyDemo())
  const [newProposal,setNewProposal]=useState(()=>emptyProposal())
  const [editingDemo,setEditingDemo]=useState<CompanySalesDemo|null>(null)
  const [editingProposal,setEditingProposal]=useState<CompanySalesProposal|null>(null)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState<string|null>(null)

  const reload=async()=>{
    const [nextDemos,nextProposals,nextOpportunities]=await Promise.all([
      loadCompanySalesDemos(salesAccountId),
      loadCompanySalesProposals(salesAccountId),
      loadCompanySalesOpportunities(companyId,salesAccountId),
    ])
    setDemos(nextDemos);setProposals(nextProposals);setOpportunities(nextOpportunities)
  }

  useEffect(()=>{
    let cancelled=false
    Promise.all([
      loadCompanySalesDemos(salesAccountId),
      loadCompanySalesProposals(salesAccountId),
      loadCompanySalesOpportunities(companyId,salesAccountId),
    ]).then(([nextDemos,nextProposals,nextOpportunities])=>{
      if(cancelled)return
      setDemos(nextDemos);setProposals(nextProposals);setOpportunities(nextOpportunities)
      setNewDemo(emptyDemo());setNewProposal(emptyProposal())
    }).catch(err=>{if(!cancelled)setError(err instanceof Error?err.message:'Unable to load demo and proposal tracking')})
    return()=>{cancelled=true}
  },[salesAccountId,companyId])

  const contactById=useMemo(()=>new Map(contacts.map(contact=>[contact.contact_id,contact])),[contacts])
  const opportunityById=useMemo(()=>new Map(opportunities.map(opportunity=>[opportunity.opportunity_id,opportunity])),[opportunities])
  const upcoming=demos.filter(row=>row.status==='scheduled'&&row.scheduled_at&&row.scheduled_at>=new Date().toISOString())
  const openProposals=proposals.filter(row=>['sent','revising'].includes(row.status))
  const openProposalArr=openProposals.reduce((sum,row)=>sum+(row.proposed_arr??0),0)

  const addDemo=async()=>{
    if(!newDemo.scheduled_at)return
    setBusy(true);setError(null)
    try{
      await addCompanySalesDemo(salesAccountId,newDemo)
      setNewDemo(emptyDemo());await reload()
    }catch(err){setError(err instanceof Error?err.message:'Unable to schedule demo')}
    finally{setBusy(false)}
  }

  const saveDemo=async()=>{
    if(!editingDemo)return
    setBusy(true);setError(null)
    try{
      await saveCompanySalesDemo(editingDemo.demo_id,salesAccountId,{
        opportunity_id:editingDemo.opportunity_id,primary_contact_id:editingDemo.primary_contact_id,status:editingDemo.status,
        scheduled_at:editingDemo.scheduled_at,completed_at:editingDemo.status==='completed'?(editingDemo.completed_at??new Date().toISOString()):editingDemo.completed_at,
        meeting_url:text(editingDemo.meeting_url??''),attendees:editingDemo.attendees,
        demo_scope:text(editingDemo.demo_scope??''),demo_accounts:text(editingDemo.demo_accounts??''),
        objections:text(editingDemo.objections??''),outcome:text(editingDemo.outcome??''),
        next_step:text(editingDemo.next_step??''),notes:text(editingDemo.notes??''),
      })
      setEditingDemo(null);await reload()
    }catch(err){setError(err instanceof Error?err.message:'Unable to update demo')}
    finally{setBusy(false)}
  }

  const completeDemo=async(row:CompanySalesDemo)=>{
    setBusy(true);setError(null)
    try{
      await saveCompanySalesDemo(row.demo_id,salesAccountId,{
        opportunity_id:row.opportunity_id,primary_contact_id:row.primary_contact_id,status:'completed',
        scheduled_at:row.scheduled_at,completed_at:new Date().toISOString(),meeting_url:row.meeting_url,attendees:row.attendees,
        demo_scope:row.demo_scope,demo_accounts:row.demo_accounts,objections:row.objections,outcome:row.outcome,next_step:row.next_step,notes:row.notes,
      })
      await reload()
    }catch(err){setError(err instanceof Error?err.message:'Unable to complete demo')}
    finally{setBusy(false)}
  }

  const addProposal=async()=>{
    if(!newProposal.package_name?.trim())return
    setBusy(true);setError(null)
    try{
      const row={...newProposal,package_name:newProposal.package_name.trim()}
      if(row.status==='sent'&&!row.sent_at)row.sent_at=new Date().toISOString()
      await addCompanySalesProposal(salesAccountId,row)
      setNewProposal(emptyProposal());await reload()
    }catch(err){setError(err instanceof Error?err.message:'Unable to add proposal')}
    finally{setBusy(false)}
  }

  const saveProposal=async()=>{
    if(!editingProposal)return
    setBusy(true);setError(null)
    try{
      const status=editingProposal.status
      await saveCompanySalesProposal(editingProposal.proposal_id,salesAccountId,{
        opportunity_id:editingProposal.opportunity_id,decision_maker_contact_id:editingProposal.decision_maker_contact_id,status,
        package_name:text(editingProposal.package_name??''),proposed_arr:editingProposal.proposed_arr,one_time_value:editingProposal.one_time_value,
        seats:editingProposal.seats,term_months:editingProposal.term_months,
        sent_at:status==='sent'?(editingProposal.sent_at??new Date().toISOString()):editingProposal.sent_at,
        valid_until:editingProposal.valid_until,expected_decision_date:editingProposal.expected_decision_date,
        proposal_url:text(editingProposal.proposal_url??''),procurement_blockers:text(editingProposal.procurement_blockers??''),
        objections:text(editingProposal.objections??''),next_step:text(editingProposal.next_step??''),notes:text(editingProposal.notes??''),
        accepted_at:status==='accepted'?(editingProposal.accepted_at??new Date().toISOString()):editingProposal.accepted_at,
        rejected_at:status==='rejected'?(editingProposal.rejected_at??new Date().toISOString()):editingProposal.rejected_at,
        rejection_reason:text(editingProposal.rejection_reason??''),
      })
      setEditingProposal(null);await reload()
    }catch(err){setError(err instanceof Error?err.message:'Unable to update proposal')}
    finally{setBusy(false)}
  }

  return <section className="company-commercial-tracking-panel" aria-label="Demo and proposal tracking">
    <div className="company-sales-crm-heading">
      <div><span className="page-kicker">Commercial execution</span><h2>Demos &amp; proposals</h2><p>Track the actual meeting, proposal package, decision timing, objections and next step separately from opportunity stage.</p></div>
      <div className="company-commercial-metrics">
        <article><small>Upcoming demos</small><strong>{upcoming.length}</strong></article>
        <article><small>Open proposals</small><strong>{openProposals.length}</strong></article>
        <article><small>Open proposal ARR</small><strong>{money(openProposalArr)}</strong></article>
      </div>
    </div>
    {error&&<div className="company-admin-error"><strong>Commercial tracking error.</strong><span>{error}</span></div>}

    <div className="company-commercial-grid">
      <section className="company-sales-crm-card">
        <div className="company-admin-card-heading"><strong>Demos</strong><span>{demos.length} tracked</span></div>
        <div className="company-commercial-create">
          <select aria-label="Demo opportunity" value={newDemo.opportunity_id??''} onChange={e=>setNewDemo(v=>({...v,opportunity_id:e.target.value||null}))}><option value="">Opportunity (optional)</option>{opportunities.map(row=><option key={row.opportunity_id} value={row.opportunity_id}>{row.name}</option>)}</select>
          <select aria-label="Demo primary contact" value={newDemo.primary_contact_id??''} onChange={e=>setNewDemo(v=>({...v,primary_contact_id:e.target.value||null}))}><option value="">Primary contact</option>{contacts.filter(c=>c.active).map(c=><option key={c.contact_id} value={c.contact_id}>{c.name}</option>)}</select>
          <input aria-label="Demo scheduled time" type="datetime-local" value={localDateTime(newDemo.scheduled_at)} onChange={e=>setNewDemo(v=>({...v,scheduled_at:iso(e.target.value)}))} />
          <input aria-label="Demo meeting URL" type="url" value={newDemo.meeting_url??''} onChange={e=>setNewDemo(v=>({...v,meeting_url:text(e.target.value)}))} placeholder="Meeting URL" />
          <input aria-label="Demo scope" value={newDemo.demo_scope??''} onChange={e=>setNewDemo(v=>({...v,demo_scope:e.target.value}))} placeholder="Demo scope / use case" />
          <input aria-label="Demo next step" value={newDemo.next_step??''} onChange={e=>setNewDemo(v=>({...v,next_step:e.target.value}))} placeholder="Expected next step" />
          <button onClick={()=>void addDemo()} disabled={busy||!newDemo.scheduled_at}>Schedule demo</button>
        </div>
        <div className="company-commercial-list">
          {demos.map(row=><article key={row.demo_id}>
            <div className="company-commercial-row-heading"><strong>{row.scheduled_at?new Date(row.scheduled_at).toLocaleString():'Unscheduled demo'}</strong><span className="admin-status-chip">{human(row.status)}</span></div>
            <div className="company-commercial-facts">
              <span>{row.opportunity_id?opportunityById.get(row.opportunity_id)?.name??'Linked opportunity':'No linked opportunity'}</span>
              <span>{row.primary_contact_id?contactById.get(row.primary_contact_id)?.name??'Linked contact':'No primary contact'}</span>
            </div>
            {row.demo_scope&&<p>{row.demo_scope}</p>}{row.next_step&&<small>Next: {row.next_step}</small>}
            <div className="company-commercial-actions"><button onClick={()=>setEditingDemo({...row})}>Edit</button>{row.status==='scheduled'&&<button onClick={()=>void completeDemo(row)} disabled={busy}>Complete</button>}</div>
          </article>)}
          {!demos.length&&<span className="company-admin-empty">No demos tracked yet.</span>}
        </div>
        {editingDemo&&<div className="company-commercial-editor">
          <div className="company-admin-card-heading"><strong>Edit demo</strong><button onClick={()=>setEditingDemo(null)}>Close</button></div>
          <div className="company-commercial-editor-grid">
            <select aria-label="Edit demo status" value={editingDemo.status} onChange={e=>setEditingDemo(v=>v?({...v,status:e.target.value as CompanySalesDemoStatus}):v)}>{demoStatuses.map(v=><option key={v} value={v}>{human(v)}</option>)}</select>
            <input aria-label="Edit demo scheduled time" type="datetime-local" value={localDateTime(editingDemo.scheduled_at)} onChange={e=>setEditingDemo(v=>v?({...v,scheduled_at:iso(e.target.value)}):v)} />
            <input aria-label="Edit demo meeting URL" type="url" value={editingDemo.meeting_url??''} onChange={e=>setEditingDemo(v=>v?({...v,meeting_url:e.target.value}):v)} placeholder="Meeting URL" />
            <textarea aria-label="Edit demo outcome" value={editingDemo.outcome??''} onChange={e=>setEditingDemo(v=>v?({...v,outcome:e.target.value}):v)} placeholder="Outcome" />
            <textarea aria-label="Edit demo objections" value={editingDemo.objections??''} onChange={e=>setEditingDemo(v=>v?({...v,objections:e.target.value}):v)} placeholder="Objections" />
            <textarea aria-label="Edit demo next step" value={editingDemo.next_step??''} onChange={e=>setEditingDemo(v=>v?({...v,next_step:e.target.value}):v)} placeholder="Next step" />
          </div>
          <div className="company-commercial-actions"><button onClick={()=>void saveDemo()} disabled={busy}>Save demo</button></div>
        </div>}
      </section>

      <section className="company-sales-crm-card">
        <div className="company-admin-card-heading"><strong>Proposals</strong><span>{proposals.length} tracked</span></div>
        <div className="company-commercial-create">
          <select aria-label="Proposal opportunity" value={newProposal.opportunity_id??''} onChange={e=>setNewProposal(v=>({...v,opportunity_id:e.target.value||null}))}><option value="">Opportunity (optional)</option>{opportunities.map(row=><option key={row.opportunity_id} value={row.opportunity_id}>{row.name}</option>)}</select>
          <select aria-label="Proposal decision maker" value={newProposal.decision_maker_contact_id??''} onChange={e=>setNewProposal(v=>({...v,decision_maker_contact_id:e.target.value||null}))}><option value="">Decision maker</option>{contacts.filter(c=>c.active).map(c=><option key={c.contact_id} value={c.contact_id}>{c.name}</option>)}</select>
          <select aria-label="Proposal status" value={newProposal.status} onChange={e=>setNewProposal(v=>({...v,status:e.target.value as CompanySalesProposalStatus}))}>{proposalStatuses.map(v=><option key={v} value={v}>{human(v)}</option>)}</select>
          <input aria-label="Proposal package" value={newProposal.package_name??''} onChange={e=>setNewProposal(v=>({...v,package_name:e.target.value}))} placeholder="Package name" />
          <input aria-label="Proposed ARR" type="number" min="0" value={newProposal.proposed_arr??''} onChange={e=>setNewProposal(v=>({...v,proposed_arr:numeric(e.target.value)}))} placeholder="Proposed ARR" />
          <input aria-label="Proposal seats" type="number" min="0" value={newProposal.seats??''} onChange={e=>setNewProposal(v=>({...v,seats:numeric(e.target.value)}))} placeholder="Seats" />
          <input aria-label="Proposal term" type="number" min="1" value={newProposal.term_months??''} onChange={e=>setNewProposal(v=>({...v,term_months:numeric(e.target.value)}))} placeholder="Term months" />
          <input aria-label="Proposal decision date" type="date" value={newProposal.expected_decision_date??''} onChange={e=>setNewProposal(v=>({...v,expected_decision_date:e.target.value||null}))} />
          <input aria-label="Proposal URL" type="url" value={newProposal.proposal_url??''} onChange={e=>setNewProposal(v=>({...v,proposal_url:e.target.value}))} placeholder="Proposal URL" />
          <input aria-label="Proposal next step" value={newProposal.next_step??''} onChange={e=>setNewProposal(v=>({...v,next_step:e.target.value}))} placeholder="Next step" />
          <button onClick={()=>void addProposal()} disabled={busy||!newProposal.package_name?.trim()}>Add proposal</button>
        </div>
        <div className="company-commercial-list">
          {proposals.map(row=><article key={row.proposal_id}>
            <div className="company-commercial-row-heading"><strong>{row.package_name||'TowerSignal proposal'}</strong><span className="admin-status-chip">{human(row.status)}</span></div>
            <div className="company-commercial-facts"><span>{money(row.proposed_arr)} ARR</span><span>{row.seats==null?'Seats not set':row.seats+' seats'}</span><span>{row.term_months==null?'Term not set':row.term_months+' months'}</span></div>
            {row.expected_decision_date&&<small>Decision target: {row.expected_decision_date}</small>}{row.next_step&&<small>Next: {row.next_step}</small>}
            <div className="company-commercial-actions"><button onClick={()=>setEditingProposal({...row})}>Edit</button>{row.proposal_url&&<a href={row.proposal_url} target="_blank" rel="noreferrer">Open proposal ↗</a>}</div>
          </article>)}
          {!proposals.length&&<span className="company-admin-empty">No proposals tracked yet.</span>}
        </div>
        {editingProposal&&<div className="company-commercial-editor">
          <div className="company-admin-card-heading"><strong>Edit proposal</strong><button onClick={()=>setEditingProposal(null)}>Close</button></div>
          <div className="company-commercial-editor-grid">
            <select aria-label="Edit proposal status" value={editingProposal.status} onChange={e=>setEditingProposal(v=>v?({...v,status:e.target.value as CompanySalesProposalStatus}):v)}>{proposalStatuses.map(v=><option key={v} value={v}>{human(v)}</option>)}</select>
            <input aria-label="Edit proposed ARR" type="number" min="0" value={editingProposal.proposed_arr??''} onChange={e=>setEditingProposal(v=>v?({...v,proposed_arr:numeric(e.target.value)}):v)} />
            <input aria-label="Edit proposal decision date" type="date" value={editingProposal.expected_decision_date??''} onChange={e=>setEditingProposal(v=>v?({...v,expected_decision_date:e.target.value||null}):v)} />
            <input aria-label="Edit proposal URL" type="url" value={editingProposal.proposal_url??''} onChange={e=>setEditingProposal(v=>v?({...v,proposal_url:e.target.value}):v)} placeholder="Proposal URL" />
            <textarea aria-label="Edit proposal procurement blockers" value={editingProposal.procurement_blockers??''} onChange={e=>setEditingProposal(v=>v?({...v,procurement_blockers:e.target.value}):v)} placeholder="Procurement blockers" />
            <textarea aria-label="Edit proposal objections" value={editingProposal.objections??''} onChange={e=>setEditingProposal(v=>v?({...v,objections:e.target.value}):v)} placeholder="Objections" />
            <textarea aria-label="Edit proposal next step" value={editingProposal.next_step??''} onChange={e=>setEditingProposal(v=>v?({...v,next_step:e.target.value}):v)} placeholder="Next step" />
            <textarea aria-label="Edit proposal rejection reason" value={editingProposal.rejection_reason??''} onChange={e=>setEditingProposal(v=>v?({...v,rejection_reason:e.target.value}):v)} placeholder="Rejection reason" />
          </div>
          <div className="company-commercial-actions"><button onClick={()=>void saveProposal()} disabled={busy}>Save proposal</button></div>
        </div>}
      </section>
    </div>
  </section>
}
