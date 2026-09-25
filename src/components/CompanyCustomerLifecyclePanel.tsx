import { useEffect, useMemo, useState } from 'react'
import {
  addCompanySalesRenewal,
  addCompanySalesSubscription,
  loadCompanySalesOpportunities,
  loadCompanySalesProposals,
  loadCompanySalesRenewals,
  loadCompanySalesSubscriptions,
  saveCompanySalesRenewal,
  saveCompanySalesSubscription,
} from '../companyAdmin/client'
import type {
  CompanyAdminContact,
  CompanySalesBillingCadence,
  CompanySalesOpportunity,
  CompanySalesProposal,
  CompanySalesRenewal,
  CompanySalesRenewalStatus,
  CompanySalesSubscription,
  CompanySalesSubscriptionStatus,
} from '../types/companyAdmin'

const subscriptionStatuses:CompanySalesSubscriptionStatus[]=['onboarding','active','paused','cancelled','expired']
const renewalStatuses:CompanySalesRenewalStatus[]=['upcoming','contacted','negotiating','renewed','churned','cancelled']
const billingCadences:CompanySalesBillingCadence[]=['monthly','quarterly','annual','multi-year','other']

function human(value:string){return value.replaceAll('-',' ').replaceAll('_',' ').replace(/(^|\s)\S/g,m=>m.toUpperCase())}
function text(value:string):string|null{const v=value.trim();return v||null}
function numeric(value:string):number|null{if(!value.trim())return null;const n=Number(value);return Number.isFinite(n)?n:null}
function money(value:number|null){return value==null?'—':value.toLocaleString(undefined,{style:'currency',currency:'USD',maximumFractionDigits:0})}

function emptySubscription():Omit<CompanySalesSubscription,'subscription_id'|'sales_account_id'|'created_at'|'updated_at'>{
  return {
    opportunity_id:null,proposal_id:null,primary_contact_id:null,status:'onboarding',plan_name:'TowerSignal',
    arr:null,seats:null,start_date:null,renewal_date:null,term_months:12,billing_cadence:'annual',auto_renew:false,
    contract_url:null,customer_success_owner:null,notes:null,ended_at:null,end_reason:null,
  }
}
function emptyRenewal():Omit<CompanySalesRenewal,'renewal_id'|'sales_account_id'|'created_at'|'updated_at'>{
  return {
    subscription_id:'',primary_contact_id:null,status:'upcoming',renewal_date:'',current_arr:null,proposed_arr:null,
    renewed_arr:null,expected_decision_date:null,next_step:null,notes:null,completed_at:null,churn_reason:null,
  }
}

export function CompanyCustomerLifecyclePanel({
  salesAccountId,companyId,contacts,
}:{
  salesAccountId:string
  companyId:string
  contacts:CompanyAdminContact[]
}) {
  const [subscriptions,setSubscriptions]=useState<CompanySalesSubscription[]>([])
  const [renewals,setRenewals]=useState<CompanySalesRenewal[]>([])
  const [opportunities,setOpportunities]=useState<CompanySalesOpportunity[]>([])
  const [proposals,setProposals]=useState<CompanySalesProposal[]>([])
  const [newSubscription,setNewSubscription]=useState(()=>emptySubscription())
  const [newRenewal,setNewRenewal]=useState(()=>emptyRenewal())
  const [editingSubscription,setEditingSubscription]=useState<CompanySalesSubscription|null>(null)
  const [editingRenewal,setEditingRenewal]=useState<CompanySalesRenewal|null>(null)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState<string|null>(null)

  const reload=async()=>{
    const [nextSubscriptions,nextRenewals,nextOpportunities,nextProposals]=await Promise.all([
      loadCompanySalesSubscriptions(salesAccountId),
      loadCompanySalesRenewals(salesAccountId),
      loadCompanySalesOpportunities(companyId,salesAccountId),
      loadCompanySalesProposals(salesAccountId),
    ])
    setSubscriptions(nextSubscriptions);setRenewals(nextRenewals);setOpportunities(nextOpportunities);setProposals(nextProposals)
  }

  useEffect(()=>{
    let cancelled=false
    Promise.all([
      loadCompanySalesSubscriptions(salesAccountId),
      loadCompanySalesRenewals(salesAccountId),
      loadCompanySalesOpportunities(companyId,salesAccountId),
      loadCompanySalesProposals(salesAccountId),
    ]).then(([nextSubscriptions,nextRenewals,nextOpportunities,nextProposals])=>{
      if(cancelled)return
      setSubscriptions(nextSubscriptions);setRenewals(nextRenewals);setOpportunities(nextOpportunities);setProposals(nextProposals)
      setNewSubscription(emptySubscription());setNewRenewal(emptyRenewal())
    }).catch(err=>{if(!cancelled)setError(err instanceof Error?err.message:'Unable to load customer lifecycle')})
    return()=>{cancelled=true}
  },[salesAccountId,companyId])

  const subscriptionById=useMemo(()=>new Map(subscriptions.map(row=>[row.subscription_id,row])),[subscriptions])
  const activeSubscriptions=subscriptions.filter(row=>['onboarding','active','paused'].includes(row.status))
  const activeArr=activeSubscriptions.reduce((sum,row)=>sum+(row.arr??0),0)
  const openRenewals=renewals.filter(row=>['upcoming','contacted','negotiating'].includes(row.status))
  const nextRenewal=[...activeSubscriptions].filter(row=>row.renewal_date).sort((a,b)=>String(a.renewal_date).localeCompare(String(b.renewal_date)))[0]?.renewal_date??null

  const createSubscription=async()=>{
    if(!newSubscription.plan_name.trim())return
    setBusy(true);setError(null)
    try{
      await addCompanySalesSubscription(salesAccountId,{...newSubscription,plan_name:newSubscription.plan_name.trim()})
      setNewSubscription(emptySubscription());await reload()
    }catch(err){setError(err instanceof Error?err.message:'Unable to add customer subscription')}
    finally{setBusy(false)}
  }

  const updateSubscription=async()=>{
    if(!editingSubscription)return
    setBusy(true);setError(null)
    try{
      const status=editingSubscription.status
      await saveCompanySalesSubscription(editingSubscription.subscription_id,salesAccountId,{
        opportunity_id:editingSubscription.opportunity_id,proposal_id:editingSubscription.proposal_id,
        primary_contact_id:editingSubscription.primary_contact_id,status,plan_name:editingSubscription.plan_name.trim(),
        arr:editingSubscription.arr,seats:editingSubscription.seats,start_date:editingSubscription.start_date,
        renewal_date:editingSubscription.renewal_date,term_months:editingSubscription.term_months,
        billing_cadence:editingSubscription.billing_cadence,auto_renew:editingSubscription.auto_renew,
        contract_url:text(editingSubscription.contract_url??''),customer_success_owner:text(editingSubscription.customer_success_owner??''),
        notes:text(editingSubscription.notes??''),
        ended_at:['cancelled','expired'].includes(status)?(editingSubscription.ended_at??new Date().toISOString()):null,
        end_reason:['cancelled','expired'].includes(status)?text(editingSubscription.end_reason??''):null,
      })
      setEditingSubscription(null);await reload()
    }catch(err){setError(err instanceof Error?err.message:'Unable to update customer subscription')}
    finally{setBusy(false)}
  }

  const createRenewal=async()=>{
    if(!newRenewal.subscription_id||!newRenewal.renewal_date)return
    setBusy(true);setError(null)
    try{
      const subscription=subscriptionById.get(newRenewal.subscription_id)
      await addCompanySalesRenewal(salesAccountId,{
        ...newRenewal,current_arr:newRenewal.current_arr??subscription?.arr??null,
      })
      setNewRenewal(emptyRenewal());await reload()
    }catch(err){setError(err instanceof Error?err.message:'Unable to add renewal')}
    finally{setBusy(false)}
  }

  const updateRenewal=async()=>{
    if(!editingRenewal)return
    setBusy(true);setError(null)
    try{
      const status=editingRenewal.status
      await saveCompanySalesRenewal(editingRenewal.renewal_id,salesAccountId,{
        subscription_id:editingRenewal.subscription_id,primary_contact_id:editingRenewal.primary_contact_id,status,
        renewal_date:editingRenewal.renewal_date,current_arr:editingRenewal.current_arr,proposed_arr:editingRenewal.proposed_arr,
        renewed_arr:editingRenewal.renewed_arr,expected_decision_date:editingRenewal.expected_decision_date,
        next_step:text(editingRenewal.next_step??''),notes:text(editingRenewal.notes??''),
        completed_at:['renewed','churned','cancelled'].includes(status)?(editingRenewal.completed_at??new Date().toISOString()):null,
        churn_reason:status==='churned'?text(editingRenewal.churn_reason??''):null,
      })
      setEditingRenewal(null);await reload()
    }catch(err){setError(err instanceof Error?err.message:'Unable to update renewal')}
    finally{setBusy(false)}
  }

  return <section className="company-commercial-tracking-panel" aria-label="Customer lifecycle">
    <div className="company-sales-crm-heading">
      <div><span className="page-kicker">Post-sale execution</span><h2>Customer lifecycle</h2><p>Track subscriptions, recurring revenue, contract timing and renewals independently from the sales opportunity that created the customer.</p></div>
      <div className="company-commercial-metrics">
        <article><small>Live subscriptions</small><strong>{activeSubscriptions.length}</strong></article>
        <article><small>Live ARR</small><strong>{money(activeArr)}</strong></article>
        <article><small>Next renewal</small><strong>{nextRenewal||'—'}</strong></article>
      </div>
    </div>
    {error&&<div className="company-admin-error"><strong>Customer lifecycle error.</strong><span>{error}</span></div>}

    <div className="company-commercial-grid">
      <section className="company-sales-crm-card">
        <div className="company-admin-card-heading"><strong>Subscriptions</strong><span>{subscriptions.length} tracked</span></div>
        <div className="company-commercial-create">
          <input aria-label="Subscription plan" value={newSubscription.plan_name} onChange={e=>setNewSubscription(v=>({...v,plan_name:e.target.value}))} placeholder="Plan / package" />
          <select aria-label="Subscription status" value={newSubscription.status} onChange={e=>setNewSubscription(v=>({...v,status:e.target.value as CompanySalesSubscriptionStatus}))}>{subscriptionStatuses.map(v=><option key={v} value={v}>{human(v)}</option>)}</select>
          <input aria-label="Subscription ARR" type="number" min="0" value={newSubscription.arr??''} onChange={e=>setNewSubscription(v=>({...v,arr:numeric(e.target.value)}))} placeholder="ARR" />
          <input aria-label="Subscription seats" type="number" min="0" value={newSubscription.seats??''} onChange={e=>setNewSubscription(v=>({...v,seats:numeric(e.target.value)}))} placeholder="Seats" />
          <input aria-label="Subscription start date" type="date" value={newSubscription.start_date??''} onChange={e=>setNewSubscription(v=>({...v,start_date:e.target.value||null}))} />
          <input aria-label="Subscription renewal date" type="date" value={newSubscription.renewal_date??''} onChange={e=>setNewSubscription(v=>({...v,renewal_date:e.target.value||null}))} />
          <select aria-label="Subscription billing cadence" value={newSubscription.billing_cadence} onChange={e=>setNewSubscription(v=>({...v,billing_cadence:e.target.value as CompanySalesBillingCadence}))}>{billingCadences.map(v=><option key={v} value={v}>{human(v)}</option>)}</select>
          <input aria-label="Subscription term months" type="number" min="1" value={newSubscription.term_months??''} onChange={e=>setNewSubscription(v=>({...v,term_months:numeric(e.target.value)}))} placeholder="Term months" />
          <select aria-label="Subscription opportunity" value={newSubscription.opportunity_id??''} onChange={e=>setNewSubscription(v=>({...v,opportunity_id:e.target.value||null}))}><option value="">Won opportunity (optional)</option>{opportunities.map(row=><option key={row.opportunity_id} value={row.opportunity_id}>{row.name}</option>)}</select>
          <select aria-label="Subscription proposal" value={newSubscription.proposal_id??''} onChange={e=>setNewSubscription(v=>({...v,proposal_id:e.target.value||null}))}><option value="">Accepted proposal (optional)</option>{proposals.map(row=><option key={row.proposal_id} value={row.proposal_id}>{row.package_name||'TowerSignal proposal'}</option>)}</select>
          <select aria-label="Subscription primary contact" value={newSubscription.primary_contact_id??''} onChange={e=>setNewSubscription(v=>({...v,primary_contact_id:e.target.value||null}))}><option value="">Primary contact</option>{contacts.filter(c=>c.active).map(c=><option key={c.contact_id} value={c.contact_id}>{c.name}</option>)}</select>
          <input aria-label="Customer success owner" value={newSubscription.customer_success_owner??''} onChange={e=>setNewSubscription(v=>({...v,customer_success_owner:e.target.value}))} placeholder="Customer success owner" />
          <input aria-label="Subscription contract URL" type="url" value={newSubscription.contract_url??''} onChange={e=>setNewSubscription(v=>({...v,contract_url:e.target.value}))} placeholder="Contract URL" />
          <label><input aria-label="Subscription auto renew" type="checkbox" checked={newSubscription.auto_renew} onChange={e=>setNewSubscription(v=>({...v,auto_renew:e.target.checked}))} /> Auto renew</label>
          <button onClick={()=>void createSubscription()} disabled={busy||!newSubscription.plan_name.trim()}>Add subscription</button>
        </div>
        <div className="company-commercial-list">
          {subscriptions.map(row=><article key={row.subscription_id}>
            <div className="company-commercial-row-heading"><strong>{row.plan_name}</strong><span className="admin-status-chip">{human(row.status)}</span></div>
            <div className="company-commercial-facts"><span>{money(row.arr)} ARR</span><span>{row.seats==null?'Seats not set':row.seats+' seats'}</span><span>{human(row.billing_cadence)}</span></div>
            <small>{row.renewal_date?'Renewal '+row.renewal_date:'Renewal date not set'}{row.auto_renew?' · auto renew':''}</small>
            {row.customer_success_owner&&<small>Owner: {row.customer_success_owner}</small>}
            <div className="company-commercial-actions"><button onClick={()=>setEditingSubscription({...row})}>Edit</button>{row.contract_url&&<a href={row.contract_url} target="_blank" rel="noreferrer">Open contract ↗</a>}</div>
          </article>)}
          {!subscriptions.length&&<span className="company-admin-empty">No subscriptions tracked yet.</span>}
        </div>
        {editingSubscription&&<div className="company-commercial-editor">
          <div className="company-admin-card-heading"><strong>Edit subscription</strong><button onClick={()=>setEditingSubscription(null)}>Close</button></div>
          <div className="company-commercial-editor-grid">
            <select aria-label="Edit subscription status" value={editingSubscription.status} onChange={e=>setEditingSubscription(v=>v?({...v,status:e.target.value as CompanySalesSubscriptionStatus}):v)}>{subscriptionStatuses.map(v=><option key={v} value={v}>{human(v)}</option>)}</select>
            <input aria-label="Edit subscription ARR" type="number" min="0" value={editingSubscription.arr??''} onChange={e=>setEditingSubscription(v=>v?({...v,arr:numeric(e.target.value)}):v)} />
            <input aria-label="Edit subscription renewal date" type="date" value={editingSubscription.renewal_date??''} onChange={e=>setEditingSubscription(v=>v?({...v,renewal_date:e.target.value||null}):v)} />
            <input aria-label="Edit customer success owner" value={editingSubscription.customer_success_owner??''} onChange={e=>setEditingSubscription(v=>v?({...v,customer_success_owner:e.target.value}):v)} placeholder="Customer success owner" />
            <input aria-label="Edit subscription contract URL" type="url" value={editingSubscription.contract_url??''} onChange={e=>setEditingSubscription(v=>v?({...v,contract_url:e.target.value}):v)} placeholder="Contract URL" />
            <label><input aria-label="Edit subscription auto renew" type="checkbox" checked={editingSubscription.auto_renew} onChange={e=>setEditingSubscription(v=>v?({...v,auto_renew:e.target.checked}):v)} /> Auto renew</label>
            <textarea aria-label="Edit subscription notes" value={editingSubscription.notes??''} onChange={e=>setEditingSubscription(v=>v?({...v,notes:e.target.value}):v)} placeholder="Subscription notes" />
            {['cancelled','expired'].includes(editingSubscription.status)&&<textarea aria-label="Edit subscription end reason" value={editingSubscription.end_reason??''} onChange={e=>setEditingSubscription(v=>v?({...v,end_reason:e.target.value}):v)} placeholder="End reason" />}
          </div>
          <div className="company-commercial-actions"><button onClick={()=>void updateSubscription()} disabled={busy}>Save subscription</button></div>
        </div>}
      </section>

      <section className="company-sales-crm-card">
        <div className="company-admin-card-heading"><strong>Renewals</strong><span>{openRenewals.length} open · {renewals.length} total</span></div>
        <div className="company-commercial-create">
          <select aria-label="Renewal subscription" value={newRenewal.subscription_id} onChange={e=>{
            const subscription=subscriptionById.get(e.target.value)
            setNewRenewal(v=>({...v,subscription_id:e.target.value,renewal_date:subscription?.renewal_date??v.renewal_date,current_arr:subscription?.arr??v.current_arr}))
          }}><option value="">Subscription</option>{subscriptions.map(row=><option key={row.subscription_id} value={row.subscription_id}>{row.plan_name}</option>)}</select>
          <select aria-label="Renewal status" value={newRenewal.status} onChange={e=>setNewRenewal(v=>({...v,status:e.target.value as CompanySalesRenewalStatus}))}>{renewalStatuses.map(v=><option key={v} value={v}>{human(v)}</option>)}</select>
          <input aria-label="Renewal date" type="date" value={newRenewal.renewal_date} onChange={e=>setNewRenewal(v=>({...v,renewal_date:e.target.value}))} />
          <input aria-label="Renewal current ARR" type="number" min="0" value={newRenewal.current_arr??''} onChange={e=>setNewRenewal(v=>({...v,current_arr:numeric(e.target.value)}))} placeholder="Current ARR" />
          <input aria-label="Renewal proposed ARR" type="number" min="0" value={newRenewal.proposed_arr??''} onChange={e=>setNewRenewal(v=>({...v,proposed_arr:numeric(e.target.value)}))} placeholder="Proposed ARR" />
          <input aria-label="Renewal decision date" type="date" value={newRenewal.expected_decision_date??''} onChange={e=>setNewRenewal(v=>({...v,expected_decision_date:e.target.value||null}))} />
          <select aria-label="Renewal primary contact" value={newRenewal.primary_contact_id??''} onChange={e=>setNewRenewal(v=>({...v,primary_contact_id:e.target.value||null}))}><option value="">Renewal contact</option>{contacts.filter(c=>c.active).map(c=><option key={c.contact_id} value={c.contact_id}>{c.name}</option>)}</select>
          <input aria-label="Renewal next step" value={newRenewal.next_step??''} onChange={e=>setNewRenewal(v=>({...v,next_step:e.target.value}))} placeholder="Next step" />
          <button onClick={()=>void createRenewal()} disabled={busy||!newRenewal.subscription_id||!newRenewal.renewal_date}>Add renewal</button>
        </div>
        <div className="company-commercial-list">
          {renewals.map(row=><article key={row.renewal_id}>
            <div className="company-commercial-row-heading"><strong>{subscriptionById.get(row.subscription_id)?.plan_name||'Subscription renewal'}</strong><span className="admin-status-chip">{human(row.status)}</span></div>
            <div className="company-commercial-facts"><span>{row.renewal_date}</span><span>{money(row.current_arr)} current ARR</span>{row.proposed_arr!=null&&<span>{money(row.proposed_arr)} proposed</span>}</div>
            {row.expected_decision_date&&<small>Decision target: {row.expected_decision_date}</small>}
            {row.next_step&&<small>Next: {row.next_step}</small>}
            <div className="company-commercial-actions"><button onClick={()=>setEditingRenewal({...row})}>Edit</button></div>
          </article>)}
          {!renewals.length&&<span className="company-admin-empty">No renewals tracked yet.</span>}
        </div>
        {editingRenewal&&<div className="company-commercial-editor">
          <div className="company-admin-card-heading"><strong>Edit renewal</strong><button onClick={()=>setEditingRenewal(null)}>Close</button></div>
          <div className="company-commercial-editor-grid">
            <select aria-label="Edit renewal status" value={editingRenewal.status} onChange={e=>setEditingRenewal(v=>v?({...v,status:e.target.value as CompanySalesRenewalStatus}):v)}>{renewalStatuses.map(v=><option key={v} value={v}>{human(v)}</option>)}</select>
            <input aria-label="Edit renewal date" type="date" value={editingRenewal.renewal_date} onChange={e=>setEditingRenewal(v=>v?({...v,renewal_date:e.target.value}):v)} />
            <input aria-label="Edit renewal proposed ARR" type="number" min="0" value={editingRenewal.proposed_arr??''} onChange={e=>setEditingRenewal(v=>v?({...v,proposed_arr:numeric(e.target.value)}):v)} />
            <input aria-label="Edit renewal renewed ARR" type="number" min="0" value={editingRenewal.renewed_arr??''} onChange={e=>setEditingRenewal(v=>v?({...v,renewed_arr:numeric(e.target.value)}):v)} />
            <input aria-label="Edit renewal decision date" type="date" value={editingRenewal.expected_decision_date??''} onChange={e=>setEditingRenewal(v=>v?({...v,expected_decision_date:e.target.value||null}):v)} />
            <textarea aria-label="Edit renewal next step" value={editingRenewal.next_step??''} onChange={e=>setEditingRenewal(v=>v?({...v,next_step:e.target.value}):v)} placeholder="Next step" />
            <textarea aria-label="Edit renewal notes" value={editingRenewal.notes??''} onChange={e=>setEditingRenewal(v=>v?({...v,notes:e.target.value}):v)} placeholder="Renewal notes" />
            {editingRenewal.status==='churned'&&<textarea aria-label="Edit renewal churn reason" value={editingRenewal.churn_reason??''} onChange={e=>setEditingRenewal(v=>v?({...v,churn_reason:e.target.value}):v)} placeholder="Churn reason" />}
          </div>
          <div className="company-commercial-actions"><button onClick={()=>void updateRenewal()} disabled={busy}>Save renewal</button></div>
        </div>}
      </section>
    </div>
  </section>
}
