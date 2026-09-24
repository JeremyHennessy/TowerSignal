import { useEffect, useMemo, useState } from 'react'
import {
  addCompanySalesOpportunity,
  addCompanySalesTask,
  loadCompanyAdminSnapshot,
  loadCompanySalesOpportunities,
  loadCompanySalesTasks,
  saveCompanySalesOpportunity,
  saveCompanySalesTask,
} from '../companyAdmin/client'
import type {
  CompanyAdminContact,
  CompanyOpportunityStage,
  CompanySalesOpportunity,
  CompanySalesTask,
  CompanyTaskPriority,
  CompanyTaskType,
} from '../types/companyAdmin'

const stages: CompanyOpportunityStage[] = [
  'lead','qualified','demo-scheduled','demo-complete','proposal','negotiation','closed-won','closed-lost','nurture',
]
const taskTypes: CompanyTaskType[] = ['call','email','demo','proposal','research','follow-up','meeting','other']
const priorities: CompanyTaskPriority[] = ['low','medium','high']

function human(value:string):string {
  return value.replaceAll('-',' ').replaceAll('_',' ').replace(/(^|\s)\S/g,m=>m.toUpperCase())
}

function text(value:string):string|null {
  const trimmed=value.trim()
  return trimmed || null
}

function numberValue(value:string):number|null {
  if(!value.trim()) return null
  const parsed=Number(value)
  return Number.isFinite(parsed)?parsed:null
}

function localDateTime(value:string|null):string {
  if(!value) return ''
  const date=new Date(value)
  if(Number.isNaN(date.getTime())) return ''
  const offset=date.getTimezoneOffset()*60_000
  return new Date(date.getTime()-offset).toISOString().slice(0,16)
}

function emptyOpportunity(companyName:string):Omit<CompanySalesOpportunity,'opportunity_id'|'company_id'|'created_at'|'updated_at'> {
  return {
    name:`${companyName} · TowerSignal`,
    stage:'lead',
    product_scope:['TowerSignal'],
    estimated_arr:null,
    one_time_value:null,
    probability_percent:null,
    primary_contact_id:null,
    lead_source:'Known Firms / TowerSignal research',
    target_close_date:null,
    next_step:null,
    next_action_date:null,
    demo_scheduled_at:null,
    proposal_sent_at:null,
    won_at:null,
    lost_at:null,
    lost_reason:null,
    notes:null,
  }
}

function emptyTask():Omit<CompanySalesTask,'task_id'|'company_id'|'created_at'|'updated_at'> {
  return {
    opportunity_id:null,
    contact_id:null,
    title:'',
    task_type:'follow-up',
    priority:'medium',
    status:'open',
    due_at:null,
    completed_at:null,
    notes:null,
  }
}

export function CompanySalesCrmPanel({companyId,companyName}:{companyId:string;companyName:string}) {
  const [opportunities,setOpportunities]=useState<CompanySalesOpportunity[]>([])
  const [tasks,setTasks]=useState<CompanySalesTask[]>([])
  const [contacts,setContacts]=useState<CompanyAdminContact[]>([])
  const [newOpportunity,setNewOpportunity]=useState(()=>emptyOpportunity(companyName))
  const [newTask,setNewTask]=useState(()=>emptyTask())
  const [editingOpportunity,setEditingOpportunity]=useState<CompanySalesOpportunity|null>(null)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState<string|null>(null)

  const reload=async()=>{
    const [nextOpportunities,nextTasks,snapshot]=await Promise.all([
      loadCompanySalesOpportunities(companyId),
      loadCompanySalesTasks(companyId),
      loadCompanyAdminSnapshot(companyId),
    ])
    setOpportunities(nextOpportunities)
    setTasks(nextTasks)
    setContacts(snapshot.contacts)
  }

  useEffect(()=>{
    let cancelled=false
    Promise.all([
      loadCompanySalesOpportunities(companyId),
      loadCompanySalesTasks(companyId),
      loadCompanyAdminSnapshot(companyId),
    ]).then(([nextOpportunities,nextTasks,snapshot])=>{
      if(cancelled) return
      setOpportunities(nextOpportunities)
      setTasks(nextTasks)
      setContacts(snapshot.contacts)
      setNewOpportunity(emptyOpportunity(companyName))
      setNewTask(emptyTask())
    }).catch(err=>{if(!cancelled)setError(err instanceof Error?err.message:'Unable to load TowerSignal sales CRM')})
    return()=>{cancelled=true}
  },[companyId,companyName])

  const contactById=useMemo(()=>new Map(contacts.map(contact=>[contact.contact_id,contact])),[contacts])
  const openTasks=tasks.filter(task=>task.status==='open')
  const overdueTasks=openTasks.filter(task=>task.due_at && task.due_at < new Date().toISOString())
  const openPipeline=opportunities.filter(opportunity=>!['closed-won','closed-lost'].includes(opportunity.stage))
  const pipelineArr=openPipeline.reduce((sum,opportunity)=>sum+(opportunity.estimated_arr??0),0)

  const addOpportunity=async()=>{
    if(!newOpportunity.name.trim()) return
    setBusy(true);setError(null)
    try{
      await addCompanySalesOpportunity(companyId,{
        ...newOpportunity,
        name:newOpportunity.name.trim(),
        lead_source:text(newOpportunity.lead_source??''),
        next_step:text(newOpportunity.next_step??''),
        notes:text(newOpportunity.notes??''),
        lost_reason:text(newOpportunity.lost_reason??''),
      })
      setNewOpportunity(emptyOpportunity(companyName))
      await reload()
    }catch(err){setError(err instanceof Error?err.message:'Unable to add opportunity')}
    finally{setBusy(false)}
  }

  const saveOpportunity=async()=>{
    if(!editingOpportunity||!editingOpportunity.name.trim()) return
    setBusy(true);setError(null)
    try{
      const now=new Date().toISOString()
      const stage=editingOpportunity.stage
      await saveCompanySalesOpportunity(editingOpportunity.opportunity_id,companyId,{
        name:editingOpportunity.name.trim(),
        stage,
        product_scope:editingOpportunity.product_scope,
        estimated_arr:editingOpportunity.estimated_arr,
        one_time_value:editingOpportunity.one_time_value,
        probability_percent:editingOpportunity.probability_percent,
        primary_contact_id:editingOpportunity.primary_contact_id,
        lead_source:text(editingOpportunity.lead_source??''),
        target_close_date:editingOpportunity.target_close_date,
        next_step:text(editingOpportunity.next_step??''),
        next_action_date:editingOpportunity.next_action_date,
        demo_scheduled_at:editingOpportunity.demo_scheduled_at,
        proposal_sent_at:editingOpportunity.proposal_sent_at,
        won_at:stage==='closed-won' ? (editingOpportunity.won_at??now) : null,
        lost_at:stage==='closed-lost' ? (editingOpportunity.lost_at??now) : null,
        lost_reason:text(editingOpportunity.lost_reason??''),
        notes:text(editingOpportunity.notes??''),
      })
      setEditingOpportunity(null)
      await reload()
    }catch(err){setError(err instanceof Error?err.message:'Unable to update opportunity')}
    finally{setBusy(false)}
  }

  const addTask=async()=>{
    if(!newTask.title.trim()) return
    setBusy(true);setError(null)
    try{
      await addCompanySalesTask(companyId,{...newTask,title:newTask.title.trim(),notes:text(newTask.notes??'')})
      setNewTask(emptyTask())
      await reload()
    }catch(err){setError(err instanceof Error?err.message:'Unable to add sales task')}
    finally{setBusy(false)}
  }

  const completeTask=async(task:CompanySalesTask)=>{
    setBusy(true);setError(null)
    try{
      await saveCompanySalesTask(task.task_id,companyId,{...task,status:'completed',completed_at:new Date().toISOString()})
      await reload()
    }catch(err){setError(err instanceof Error?err.message:'Unable to complete sales task')}
    finally{setBusy(false)}
  }

  return <section className="company-sales-crm-panel" aria-label="TowerSignal internal sales CRM">
    <div className="company-sales-crm-heading">
      <div><span className="page-kicker">Internal TowerSignal sales CRM</span><h2>Sales pipeline &amp; follow-up</h2><p>Track the commercial relationship with this company separately from public evidence and company research.</p></div>
      <div className="company-sales-crm-metrics">
        <article><small>Open opportunities</small><strong>{openPipeline.length}</strong></article>
        <article><small>Pipeline ARR</small><strong>{pipelineArr.toLocaleString(undefined,{style:'currency',currency:'USD',maximumFractionDigits:0})}</strong></article>
        <article><small>Open tasks</small><strong>{openTasks.length}</strong></article>
        <article><small>Overdue</small><strong>{overdueTasks.length}</strong></article>
      </div>
    </div>

    {error&&<div className="company-admin-error"><strong>Sales CRM error.</strong><span>{error}</span></div>}

    <div className="company-sales-crm-grid">
      <section className="company-sales-crm-card">
        <div className="company-admin-card-heading"><strong>Opportunities</strong><span>{opportunities.length} tracked</span></div>
        <div className="sales-opportunity-create">
          <input aria-label="Opportunity name" value={newOpportunity.name} onChange={e=>setNewOpportunity(v=>({...v,name:e.target.value}))} />
          <select aria-label="Opportunity stage" value={newOpportunity.stage} onChange={e=>setNewOpportunity(v=>({...v,stage:e.target.value as CompanyOpportunityStage}))}>{stages.map(stage=><option key={stage} value={stage}>{human(stage)}</option>)}</select>
          <input aria-label="Estimated ARR" type="number" min="0" value={newOpportunity.estimated_arr??''} onChange={e=>setNewOpportunity(v=>({...v,estimated_arr:numberValue(e.target.value)}))} placeholder="Estimated ARR" />
          <input aria-label="Opportunity probability" type="number" min="0" max="100" value={newOpportunity.probability_percent??''} onChange={e=>setNewOpportunity(v=>({...v,probability_percent:numberValue(e.target.value)}))} placeholder="Probability %" />
          <select aria-label="Opportunity primary contact" value={newOpportunity.primary_contact_id??''} onChange={e=>setNewOpportunity(v=>({...v,primary_contact_id:e.target.value||null}))}><option value="">Primary contact</option>{contacts.filter(c=>c.active).map(c=><option key={c.contact_id} value={c.contact_id}>{c.name}</option>)}</select>
          <input aria-label="Opportunity target close" type="date" value={newOpportunity.target_close_date??''} onChange={e=>setNewOpportunity(v=>({...v,target_close_date:e.target.value||null}))} />
          <input aria-label="Opportunity next step" value={newOpportunity.next_step??''} onChange={e=>setNewOpportunity(v=>({...v,next_step:e.target.value}))} placeholder="Next step" />
          <input aria-label="Opportunity next action" type="date" value={newOpportunity.next_action_date??''} onChange={e=>setNewOpportunity(v=>({...v,next_action_date:e.target.value||null}))} />
          <button onClick={()=>void addOpportunity()} disabled={busy||!newOpportunity.name.trim()}>Add opportunity</button>
        </div>

        <div className="sales-opportunity-list">
          {opportunities.length ? opportunities.map(opportunity=><article key={opportunity.opportunity_id}>
            <div className="sales-opportunity-main"><strong>{opportunity.name}</strong><span className="admin-status-chip">{human(opportunity.stage)}</span></div>
            <div className="sales-opportunity-facts">
              <span>{opportunity.estimated_arr==null?'ARR not set':opportunity.estimated_arr.toLocaleString(undefined,{style:'currency',currency:'USD',maximumFractionDigits:0})+' ARR'}</span>
              <span>{opportunity.probability_percent==null?'Probability not set':opportunity.probability_percent+'%'}</span>
              <span>{opportunity.primary_contact_id ? contactById.get(opportunity.primary_contact_id)?.name ?? 'Linked contact' : 'No primary contact'}</span>
              <span>{opportunity.target_close_date ? 'Target '+opportunity.target_close_date : 'No close target'}</span>
            </div>
            {opportunity.next_step&&<p>{opportunity.next_step}</p>}
            <div className="sales-opportunity-actions"><button onClick={()=>setEditingOpportunity({...opportunity})}>Edit</button></div>
          </article>) : <span className="company-admin-empty">No TowerSignal sales opportunities yet.</span>}
        </div>

        {editingOpportunity&&<div className="sales-opportunity-editor">
          <div className="company-admin-card-heading"><strong>Edit opportunity</strong><span>{editingOpportunity.name}</span></div>
          <div className="sales-opportunity-editor-grid">
            <input aria-label="Edit opportunity name" value={editingOpportunity.name} onChange={e=>setEditingOpportunity(v=>v?({...v,name:e.target.value}):v)} />
            <select aria-label="Edit opportunity stage" value={editingOpportunity.stage} onChange={e=>setEditingOpportunity(v=>v?({...v,stage:e.target.value as CompanyOpportunityStage}):v)}>{stages.map(stage=><option key={stage} value={stage}>{human(stage)}</option>)}</select>
            <input aria-label="Edit opportunity ARR" type="number" min="0" value={editingOpportunity.estimated_arr??''} onChange={e=>setEditingOpportunity(v=>v?({...v,estimated_arr:numberValue(e.target.value)}):v)} placeholder="Estimated ARR" />
            <input aria-label="Edit opportunity one-time value" type="number" min="0" value={editingOpportunity.one_time_value??''} onChange={e=>setEditingOpportunity(v=>v?({...v,one_time_value:numberValue(e.target.value)}):v)} placeholder="One-time value" />
            <input aria-label="Edit opportunity probability" type="number" min="0" max="100" value={editingOpportunity.probability_percent??''} onChange={e=>setEditingOpportunity(v=>v?({...v,probability_percent:numberValue(e.target.value)}):v)} placeholder="Probability %" />
            <select aria-label="Edit opportunity contact" value={editingOpportunity.primary_contact_id??''} onChange={e=>setEditingOpportunity(v=>v?({...v,primary_contact_id:e.target.value||null}):v)}><option value="">Primary contact</option>{contacts.filter(c=>c.active).map(c=><option key={c.contact_id} value={c.contact_id}>{c.name}</option>)}</select>
            <input aria-label="Edit opportunity lead source" value={editingOpportunity.lead_source??''} onChange={e=>setEditingOpportunity(v=>v?({...v,lead_source:e.target.value}):v)} placeholder="Lead source" />
            <input aria-label="Edit opportunity target close" type="date" value={editingOpportunity.target_close_date??''} onChange={e=>setEditingOpportunity(v=>v?({...v,target_close_date:e.target.value||null}):v)} />
            <input aria-label="Edit opportunity next step" value={editingOpportunity.next_step??''} onChange={e=>setEditingOpportunity(v=>v?({...v,next_step:e.target.value}):v)} placeholder="Next step" />
            <input aria-label="Edit opportunity next action" type="date" value={editingOpportunity.next_action_date??''} onChange={e=>setEditingOpportunity(v=>v?({...v,next_action_date:e.target.value||null}):v)} />
            <input aria-label="Edit demo scheduled" type="datetime-local" value={localDateTime(editingOpportunity.demo_scheduled_at)} onChange={e=>setEditingOpportunity(v=>v?({...v,demo_scheduled_at:e.target.value?new Date(e.target.value).toISOString():null}):v)} />
            <input aria-label="Edit proposal sent" type="datetime-local" value={localDateTime(editingOpportunity.proposal_sent_at)} onChange={e=>setEditingOpportunity(v=>v?({...v,proposal_sent_at:e.target.value?new Date(e.target.value).toISOString():null}):v)} />
            <input aria-label="Edit lost reason" value={editingOpportunity.lost_reason??''} onChange={e=>setEditingOpportunity(v=>v?({...v,lost_reason:e.target.value}):v)} placeholder="Lost reason" />
            <textarea aria-label="Edit opportunity notes" rows={3} value={editingOpportunity.notes??''} onChange={e=>setEditingOpportunity(v=>v?({...v,notes:e.target.value}):v)} placeholder="Deal notes" />
          </div>
          <div className="sales-opportunity-editor-actions"><button onClick={()=>void saveOpportunity()} disabled={busy}>Save opportunity</button><button onClick={()=>setEditingOpportunity(null)} disabled={busy}>Cancel</button></div>
        </div>}
      </section>

      <section className="company-sales-crm-card">
        <div className="company-admin-card-heading"><strong>Tasks &amp; follow-ups</strong><span>{openTasks.length} open</span></div>
        <div className="sales-task-create">
          <input aria-label="Sales task title" value={newTask.title} onChange={e=>setNewTask(v=>({...v,title:e.target.value}))} placeholder="Task" />
          <select aria-label="Sales task type" value={newTask.task_type} onChange={e=>setNewTask(v=>({...v,task_type:e.target.value as CompanyTaskType}))}>{taskTypes.map(type=><option key={type} value={type}>{human(type)}</option>)}</select>
          <select aria-label="Sales task priority" value={newTask.priority} onChange={e=>setNewTask(v=>({...v,priority:e.target.value as CompanyTaskPriority}))}>{priorities.map(priority=><option key={priority} value={priority}>{human(priority)}</option>)}</select>
          <select aria-label="Sales task opportunity" value={newTask.opportunity_id??''} onChange={e=>setNewTask(v=>({...v,opportunity_id:e.target.value||null}))}><option value="">No opportunity</option>{openPipeline.map(opportunity=><option key={opportunity.opportunity_id} value={opportunity.opportunity_id}>{opportunity.name}</option>)}</select>
          <select aria-label="Sales task contact" value={newTask.contact_id??''} onChange={e=>setNewTask(v=>({...v,contact_id:e.target.value||null}))}><option value="">No contact</option>{contacts.filter(c=>c.active).map(c=><option key={c.contact_id} value={c.contact_id}>{c.name}</option>)}</select>
          <input aria-label="Sales task due" type="datetime-local" value={localDateTime(newTask.due_at)} onChange={e=>setNewTask(v=>({...v,due_at:e.target.value?new Date(e.target.value).toISOString():null}))} />
          <button onClick={()=>void addTask()} disabled={busy||!newTask.title.trim()}>Add task</button>
        </div>
        <div className="sales-task-list">
          {tasks.length ? tasks.map(task=><article key={task.task_id} className={task.status==='completed'?'completed':''}>
            <div><strong>{task.title}</strong><span>{human(task.task_type)} · {human(task.priority)}</span></div>
            <small>{task.due_at?new Date(task.due_at).toLocaleString():'No due date'}{task.contact_id?` · ${contactById.get(task.contact_id)?.name??'Linked contact'}`:''}</small>
            {task.status==='open'?<button onClick={()=>void completeTask(task)} disabled={busy}>Complete</button>:<span className="health-badge health-healthy">{human(task.status)}</span>}
          </article>) : <span className="company-admin-empty">No sales tasks recorded.</span>}
        </div>
      </section>
    </div>
  </section>
}
