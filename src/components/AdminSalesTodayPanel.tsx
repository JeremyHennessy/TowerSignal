import { useMemo } from 'react'
import type {
  CompanyAdminActivity,
  CompanySalesAccount,
  CompanySalesOpportunity,
  CompanySalesTask,
  CompanySalesDemo,
  CompanySalesProposal,
  CompanySalesSubscription,
  CompanySalesRenewal,
} from '../types/companyAdmin'

const activeStages=new Set(['lead','qualified','demo-scheduled','demo-complete','proposal','negotiation'])
const number=new Intl.NumberFormat('en-US')

function human(value:string){return value.replaceAll('-',' ').replaceAll('_',' ').replace(/(^|\s)\S/g,m=>m.toUpperCase())}
function dateOnly(value:string|null|undefined){return value?.slice(0,10)??null}

export function AdminSalesTodayPanel({
  accounts,opportunities,tasks,activities,demos,proposals,subscriptions,renewals,
}:{
  accounts:CompanySalesAccount[]
  opportunities:CompanySalesOpportunity[]
  tasks:CompanySalesTask[]
  activities:CompanyAdminActivity[]
  demos:CompanySalesDemo[]
  proposals:CompanySalesProposal[]
  subscriptions:CompanySalesSubscription[]
  renewals:CompanySalesRenewal[]
}) {
  const accountById=useMemo(()=>new Map(accounts.map(account=>[account.sales_account_id,account])),[accounts])
  const subscriptionById=useMemo(()=>new Map(subscriptions.map(subscription=>[subscription.subscription_id,subscription])),[subscriptions])
  const today=new Date().toISOString().slice(0,10)
  const nextWeek=new Date(Date.now()+7*86400000).toISOString().slice(0,10)
  const next90Days=new Date(Date.now()+90*86400000).toISOString().slice(0,10)
  const staleCutoff=new Date(Date.now()-14*86400000).toISOString()

  const openTasks=tasks.filter(task=>task.status==='open')
  const overdue=openTasks.filter(task=>task.due_at&&dateOnly(task.due_at)!==null&&dateOnly(task.due_at)!<today)
  const dueToday=openTasks.filter(task=>dateOnly(task.due_at)===today)
  const nextSeven=openTasks.filter(task=>{
    const date=dateOnly(task.due_at)
    return date!=null&&date>today&&date<=nextWeek
  })
  const upcomingDemos=demos.filter(demo=>{
    const date=dateOnly(demo.scheduled_at)
    return demo.status==='scheduled'&&date!=null&&date>=today&&date<=nextWeek
  })
  const openProposals=proposals.filter(proposal=>['sent','revising'].includes(proposal.status))
  const openRenewals=renewals.filter(renewal=>['upcoming','contacted','negotiating'].includes(renewal.status))
  const renewalAttention=openRenewals.filter(renewal=>renewal.renewal_date<=next90Days)
  const trackedRenewalSubscriptions=new Set(openRenewals.map(renewal=>renewal.subscription_id))
  const untrackedRenewalSubscriptions=subscriptions.filter(subscription=>
    ['onboarding','active','paused'].includes(subscription.status)&&
    subscription.renewal_date!=null&&subscription.renewal_date<=next90Days&&
    !trackedRenewalSubscriptions.has(subscription.subscription_id)
  )
  const overdueRenewals=renewalAttention.filter(renewal=>renewal.renewal_date<today)
  const noNextStep=opportunities.filter(opportunity=>activeStages.has(opportunity.stage)&&!opportunity.next_step?.trim())
  const stale=opportunities.filter(opportunity=>activeStages.has(opportunity.stage)&&opportunity.updated_at&&opportunity.updated_at<staleCutoff)
  const recentActivities=activities.slice(0,10)

  const rowAccount=(salesAccountId?:string|null,companyId?:string)=>{
    if(salesAccountId) return accountById.get(salesAccountId)
    return accounts.find(account=>account.primary_company_id===companyId)
  }

  return <section className="admin-sales-today">
    <div className="admin-sales-today-heading">
      <div><span className="page-kicker">Internal sales · today</span><h2>What needs attention</h2><p>Work the exceptions first. Research and maintenance live in Data &amp; ops.</p></div>
      <div className="admin-today-summary">
        <span className={overdue.length?'urgent':''}><b>{number.format(overdue.length)}</b> overdue</span>
        <span><b>{number.format(dueToday.length)}</b> due today</span>
        <span><b>{number.format(upcomingDemos.length)}</b> demos</span>
        <span className={overdueRenewals.length?'urgent':''}><b>{number.format(renewalAttention.length+untrackedRenewalSubscriptions.length)}</b> Renewal attention</span>
      </div>
    </div>

    <div className="admin-sales-today-grid">
      <section className="admin-company-card">
        <div className="admin-company-card-heading"><div><strong>Priority actions</strong><span>Overdue first, then today and the next seven days</span></div><small>{number.format(overdue.length+dueToday.length+nextSeven.length)} scheduled</small></div>
        <div className="admin-sales-action-list">
          {[...overdue,...dueToday,...nextSeven].slice(0,16).map(task=>{
            const account=rowAccount(task.sales_account_id,task.company_id)
            return <a key={task.task_id} href={account?`#/admin-company/${encodeURIComponent(account.sales_account_id)}`:'#/admin-companies'} className={task.due_at&&dateOnly(task.due_at)!<today?'overdue':''}>
              <div><strong>{task.title}</strong><span>{account?.display_name??task.company_id}</span></div>
              <small>{human(task.task_type)} · {human(task.priority)} · {task.due_at?new Date(task.due_at).toLocaleString():'No due date'}</small>
            </a>
          })}
          {!overdue.length&&!dueToday.length&&!nextSeven.length&&<span className="company-admin-empty">No scheduled sales tasks are due in the next seven days.</span>}
        </div>
      </section>

      <section className="admin-company-card">
        <div className="admin-company-card-heading"><div><strong>Deal &amp; renewal attention</strong><span>Demos, proposals, renewals, missing next steps and stale active deals</span></div><small>{number.format(upcomingDemos.length+openProposals.length+renewalAttention.length+untrackedRenewalSubscriptions.length+noNextStep.length+stale.length)} signals</small></div>
        <div className="admin-sales-deal-list">
          {upcomingDemos.slice(0,6).map(demo=>{
            const account=rowAccount(demo.sales_account_id)
            return <a key={`demo-${demo.demo_id}`} href={account?`#/admin-company/${encodeURIComponent(account.sales_account_id)}`:'#/admin-companies'}>
              <strong>{account?.display_name??demo.sales_account_id}</strong><span>Demo · {demo.scheduled_at?new Date(demo.scheduled_at).toLocaleString():'scheduled'}</span><small>{demo.next_step||demo.demo_scope||'Demo scheduled'}</small>
            </a>
          })}
          {openProposals.slice(0,6).map(proposal=>{
            const account=rowAccount(proposal.sales_account_id)
            return <a key={`proposal-${proposal.proposal_id}`} href={account?`#/admin-company/${encodeURIComponent(account.sales_account_id)}`:'#/admin-companies'}>
              <strong>{account?.display_name??proposal.sales_account_id}</strong><span>{human(proposal.status)} proposal · {proposal.proposed_arr==null?'ARR not set':proposal.proposed_arr.toLocaleString(undefined,{style:'currency',currency:'USD',maximumFractionDigits:0})+' ARR'}</span><small>{proposal.next_step||proposal.package_name||'Proposal decision pending'}</small>
            </a>
          })}
          {renewalAttention.slice(0,6).map(renewal=>{
            const account=rowAccount(renewal.sales_account_id)
            const subscription=subscriptionById.get(renewal.subscription_id)
            return <a key={`renewal-${renewal.renewal_id}`} href={account?`#/admin-company/${encodeURIComponent(account.sales_account_id)}`:'#/admin-companies'} className={renewal.renewal_date<today?'overdue':''}>
              <strong>{account?.display_name??renewal.sales_account_id}</strong><span>{human(renewal.status)} renewal · {renewal.renewal_date}</span><small>{renewal.next_step||subscription?.plan_name||'Renewal follow-up required'}</small>
            </a>
          })}
          {untrackedRenewalSubscriptions.slice(0,6).map(subscription=>{
            const account=rowAccount(subscription.sales_account_id)
            return <a key={`subscription-renewal-${subscription.subscription_id}`} href={account?`#/admin-company/${encodeURIComponent(account.sales_account_id)}`:'#/admin-companies'}>
              <strong>{account?.display_name??subscription.sales_account_id}</strong><span>Renewal workflow missing · {subscription.renewal_date}</span><small>{subscription.plan_name} · create a renewal record and next step</small>
            </a>
          })}
          {noNextStep.slice(0,6).map(opportunity=>{
            const account=rowAccount(opportunity.sales_account_id,opportunity.company_id)
            return <a key={`next-${opportunity.opportunity_id}`} href={account?`#/admin-company/${encodeURIComponent(account.sales_account_id)}`:'#/admin-companies'}>
              <strong>{account?.display_name??opportunity.name}</strong><span>{human(opportunity.stage)} · no next step</span><small>{opportunity.estimated_arr==null?'ARR not set':opportunity.estimated_arr.toLocaleString(undefined,{style:'currency',currency:'USD',maximumFractionDigits:0})+' ARR'}</small>
            </a>
          })}
          {stale.slice(0,6).map(opportunity=>{
            const account=rowAccount(opportunity.sales_account_id,opportunity.company_id)
            return <a key={`stale-${opportunity.opportunity_id}`} href={account?`#/admin-company/${encodeURIComponent(account.sales_account_id)}`:'#/admin-companies'}>
              <strong>{account?.display_name??opportunity.name}</strong><span>{human(opportunity.stage)} · untouched 14+ days</span><small>{opportunity.updated_at?new Date(opportunity.updated_at).toLocaleDateString():'No update timestamp'}</small>
            </a>
          })}
          {!upcomingDemos.length&&!openProposals.length&&!renewalAttention.length&&!untrackedRenewalSubscriptions.length&&!noNextStep.length&&!stale.length&&<span className="company-admin-empty">No active deals or renewals currently need exception handling.</span>}
        </div>
      </section>

      <details className="admin-company-card admin-sales-recent-card admin-sales-recent-details">
        <summary><div><strong>Recent sales activity</strong><span>Latest calls, email, meetings and outreach</span></div><small>{number.format(activities.length)} total</small></summary>
        <div className="admin-sales-recent-list">
          {recentActivities.map(activity=>{
            const account=rowAccount(activity.sales_account_id,activity.company_id)
            return <a key={activity.activity_id} href={account?`#/admin-company/${encodeURIComponent(account.sales_account_id)}`:'#/admin-companies'}>
              <strong>{account?.display_name??activity.company_id}</strong><span>{new Date(activity.occurred_at).toLocaleString()} · {human(activity.activity_type)}</span><small>{activity.subject||activity.outcome||activity.details||'Interaction logged'}</small>
            </a>
          })}
          {!recentActivities.length&&<span className="company-admin-empty">No sales activity logged yet.</span>}
        </div>
      </details>
    </div>
  </section>
}
