import { useEffect, useMemo, useState } from 'react'
import { CompanyEvidencePanel } from './CompanyEvidencePanel'
import { loadCompanyAdminAccess, loadCompanyAdminOverview } from '../companyAdmin/client'
import { belongsToSalesAccount } from '../companyAdmin/accountMapping'
import { loadKnownFirms } from '../data/api'
import type {
  CompanyAdminActivity,
  CompanyAdminContact,
  CompanyAdminProfile,
  CompanyResearchQueueItem,
  CompanySalesOpportunity,
  CompanySalesTask,
  CompanySalesDemo,
  CompanySalesProposal,
  CompanySalesSubscription,
  CompanySalesRenewal,
  CompanyOpportunityStage,
  CompanySalesAccount,
  CompanySalesAccountMember,
  CompanySalesAccountClassification,
} from '../types/companyAdmin'
import type { KnownFirmPayload, KnownFirmSummaryRecord } from '../types/firm'
import { CompanyAdminImportPanel } from './CompanyAdminImportPanel'
import { CompanyAdminWorkspace } from './CompanyAdminWorkspace'
import { CompanyRollupReviewPanel } from './CompanyRollupReviewPanel'
import { AdminSalesTodayPanel } from './AdminSalesTodayPanel'
import { scoreCompanySalesAccount } from '../companyAdmin/scoring'

const number = new Intl.NumberFormat('en-US')
const accountClassifications: CompanySalesAccountClassification[] = [
  'target','active-prospect','customer','former-customer','partner','competitor','do-not-pursue',
]
const opportunityStages: CompanyOpportunityStage[] = ['lead','qualified','demo-scheduled','demo-complete','proposal','negotiation','closed-won','closed-lost','nurture']
const pipelineBoardStages: CompanyOpportunityStage[] = ['lead','qualified','demo-scheduled','demo-complete','proposal','negotiation']
type AdminWorkspaceView = 'today' | 'pipeline' | 'accounts' | 'data'
const activeOpportunityStages = new Set<CompanyOpportunityStage>(['lead','qualified','demo-scheduled','demo-complete','proposal','negotiation'])
const opportunityRank: Record<CompanyOpportunityStage,number> = {
  'lead':0,'qualified':1,'demo-scheduled':2,'demo-complete':3,'proposal':4,'negotiation':5,
  'closed-won':6,'nurture':-1,'closed-lost':-2,
}
function human(value: string): string {
  return value.replaceAll('_',' ').replaceAll('-',' ').replace(/(^|\s)\S/g, match => match.toUpperCase())
}

function ownershipKnown(profile: CompanyAdminProfile): boolean {
  return Boolean(
    profile.parent_company_id ||
    profile.parent_company_name ||
    /independent(ly)? owned|independent company|privately held/i.test(profile.internal_summary ?? '')
  )
}

function revenueKnown(profile: CompanyAdminProfile): boolean {
  return profile.revenue_amount != null || profile.revenue_low != null || profile.revenue_high != null
}

function missingFields(profile: CompanyAdminProfile, contactCount: number): string[] {
  const missing: string[] = []
  if (!profile.website) missing.push('website')
  if (!profile.headquarters_address && !profile.headquarters_city) missing.push('HQ')
  if (!profile.company_type) missing.push('company type')
  if (!ownershipKnown(profile)) missing.push('ownership')
  if (!revenueKnown(profile)) missing.push('revenue')
  if (!profile.identity_source_url) missing.push('identity source')
  if (contactCount === 0) missing.push('contact')
  return missing
}

type FamilyRow = {
  salesAccountId: string
  masterId: string
  name: string
  parentName: string | null
  parentSourceUrl: string | null
  master: CompanyAdminProfile
  memberIds: string[]
  memberCount: number
  publicIdentityCount: number
  publicObservations: number
  servicedRelationships: number
  towerAccountLinks: number
  publicContracts: number
  contacts: number
  activities: number
  accountClassification: CompanySalesAccountClassification
  nextActionDate: string | null
  research: CompanyResearchQueueItem | null
  openOpportunities: number
  pipelineArr: number
  salesStage: CompanyOpportunityStage | null
  salesNextStep: string | null
  salesOpenTasks: number
  fitScore: number
  readinessScore: number
  fitReasons: string[]
  readinessReasons: string[]
  missing: string[]
}

export function AdminCompaniesPage() {
  const [allowed, setAllowed] = useState<boolean | null>(null)
  const [payload, setPayload] = useState<KnownFirmPayload | null>(null)
  const [profiles, setProfiles] = useState<CompanyAdminProfile[]>([])
  const [contacts, setContacts] = useState<CompanyAdminContact[]>([])
  const [activities, setActivities] = useState<CompanyAdminActivity[]>([])
  const [queue, setQueue] = useState<CompanyResearchQueueItem[]>([])
  const [opportunities, setOpportunities] = useState<CompanySalesOpportunity[]>([])
  const [salesTasks, setSalesTasks] = useState<CompanySalesTask[]>([])
  const [salesDemos, setSalesDemos] = useState<CompanySalesDemo[]>([])
  const [salesProposals, setSalesProposals] = useState<CompanySalesProposal[]>([])
  const [salesSubscriptions, setSalesSubscriptions] = useState<CompanySalesSubscription[]>([])
  const [salesRenewals, setSalesRenewals] = useState<CompanySalesRenewal[]>([])
  const [salesAccounts, setSalesAccounts] = useState<CompanySalesAccount[]>([])
  const [salesAccountMembers, setSalesAccountMembers] = useState<CompanySalesAccountMember[]>([])
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [classification, setClassification] = useState('ALL')
  const [salesStageFilter, setSalesStageFilter] = useState('ALL')
  const [scoreFilter, setScoreFilter] = useState('ALL')
  const [gap, setGap] = useState('ALL')
  const [workspaceView,setWorkspaceView]=useState<AdminWorkspaceView>('today')
  const [accountView,setAccountView]=useState<'directory'|'mapping'>('directory')

  const applyOverview = (data:Awaited<ReturnType<typeof loadCompanyAdminOverview>>) => {
    setProfiles(data.profiles);setContacts(data.contacts);setActivities(data.activities);setQueue(data.queue)
    setOpportunities(data.opportunities);setSalesTasks(data.tasks);setSalesDemos(data.demos);setSalesProposals(data.proposals)
    setSalesSubscriptions(data.subscriptions);setSalesRenewals(data.renewals);setSalesAccounts(data.accounts);setSalesAccountMembers(data.members)
  }
  const reloadPrivate = async () => applyOverview(await loadCompanyAdminOverview())
  useEffect(() => {
    let cancelled=false
    void (async()=>{
      try {
        const isAdmin=await loadCompanyAdminAccess()
        if(cancelled)return
        setAllowed(isAdmin)
        if(!isAdmin)return
        const [known,data]=await Promise.all([loadKnownFirms(),loadCompanyAdminOverview()])
        if(cancelled)return
        applyOverview(data);setPayload(known)
      } catch(err) {
        if(!cancelled)setError(err instanceof Error?err.message:'Unable to load company administration')
      }
    })()
    return()=>{cancelled=true}
  }, [])

  const profileById = useMemo(() => new Map(profiles.map(profile => [profile.company_id, profile])), [profiles])
  const firmById = useMemo(() => new Map((payload?.firms ?? []).map(firm => [firm.firm_id, firm])), [payload?.firms])
  const queueById = useMemo(() => new Map(queue.map(item => [item.company_id, item])), [queue])

  const membersBySalesAccount = useMemo(() => {
    const map = new Map<string, CompanySalesAccountMember[]>()
    salesAccountMembers.forEach(member => {
      const rows=map.get(member.sales_account_id) ?? []
      rows.push(member)
      map.set(member.sales_account_id,rows)
    })
    return map
  },[salesAccountMembers])

  const families = useMemo<FamilyRow[]>(() => salesAccounts.flatMap(account => {
    const memberLinks=membersBySalesAccount.get(account.sales_account_id) ?? []
    const members=memberLinks.map(member=>profileById.get(member.company_id)).filter((profile): profile is CompanyAdminProfile => Boolean(profile))
    const master=profileById.get(account.primary_company_id) ?? members[0]
    if(!master) return []
    const publicRows=members.map(member=>firmById.get(member.company_id)).filter((firm): firm is KnownFirmSummaryRecord => Boolean(firm))
    const memberIds=memberLinks.map(member=>member.company_id)
    const memberIdSet=new Set(memberIds)
    const familyContactRows=contacts.filter(contact=>belongsToSalesAccount(contact,account.sales_account_id,memberIdSet)&&contact.active)
    const familyContacts=familyContactRows.length
    const familyActivities=activities.filter(activity=>belongsToSalesAccount(activity,account.sales_account_id,memberIdSet)).length
    const familyOpportunities=opportunities.filter(opportunity =>
      opportunity.sales_account_id===account.sales_account_id ||
      (!opportunity.sales_account_id && memberIdSet.has(opportunity.company_id))
    )
    const activeFamilyOpportunities=familyOpportunities.filter(opportunity=>activeOpportunityStages.has(opportunity.stage))
    const familyTasks=salesTasks.filter(task =>
      task.status==='open' && (
        task.sales_account_id===account.sales_account_id ||
        (!task.sales_account_id && memberIdSet.has(task.company_id))
      )
    )
    const mostAdvancedOpportunity=[...familyOpportunities].sort((a,b)=>opportunityRank[b.stage]-opportunityRank[a.stage] || String(b.updated_at??'').localeCompare(String(a.updated_at??'')))[0] ?? null
    const salesDates=[
      ...activeFamilyOpportunities.map(opportunity=>opportunity.next_action_date),
      ...familyTasks.map(task=>task.due_at?.slice(0,10)??null),
    ].filter((value): value is string=>Boolean(value)).sort()
    const scores=scoreCompanySalesAccount({publicFirms:publicRows,masterProfile:master,contacts:familyContactRows})
    const family:FamilyRow={
      salesAccountId:account.sales_account_id,
      masterId:account.primary_company_id,
      name:account.display_name,
      parentName:account.parent_name ?? master.parent_company_name,
      parentSourceUrl:account.parent_source_url ?? master.parent_source_url,
      master,
      memberIds,
      memberCount:memberLinks.length,
      publicIdentityCount:publicRows.length,
      publicObservations:publicRows.reduce((sum,firm)=>sum+firm.observation_count,0),
      servicedRelationships:publicRows.reduce((sum,firm)=>sum+firm.serviced_site_count,0),
      towerAccountLinks:publicRows.reduce((sum,firm)=>sum+firm.tower_account_count,0),
      publicContracts:publicRows.reduce((sum,firm)=>sum+firm.observed_contract_count,0),
      contacts:familyContacts,
      activities:familyActivities,
      accountClassification:account.account_classification,
      research:queue.find(item=>item.sales_account_id===account.sales_account_id) ?? queueById.get(account.primary_company_id) ?? null,
      openOpportunities:activeFamilyOpportunities.length,
      pipelineArr:activeFamilyOpportunities.reduce((sum,opportunity)=>sum+(opportunity.estimated_arr??0),0),
      salesStage:mostAdvancedOpportunity?.stage ?? null,
      salesNextStep:mostAdvancedOpportunity?.next_step ?? null,
      salesOpenTasks:familyTasks.length,
      fitScore:scores.fitScore,
      readinessScore:scores.readinessScore,
      fitReasons:scores.fitReasons,
      readinessReasons:scores.readinessReasons,
      nextActionDate:salesDates[0] ?? null,
      missing:missingFields(master,familyContacts),
    }
    return [family]
  }).sort((a,b)=>b.publicObservations-a.publicObservations || a.name.localeCompare(b.name)),
  [salesAccounts,membersBySalesAccount,profileById,firmById,contacts,activities,opportunities,salesTasks,queue,queueById])

  const filteredFamilies = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return families.filter(family => {
      if (classification !== 'ALL' && family.accountClassification !== classification) return false
      if (salesStageFilter !== 'ALL' && family.salesStage !== salesStageFilter) return false
      if (scoreFilter === 'HIGH_FIT' && family.fitScore < 70) return false
      if (scoreFilter === 'READY' && family.readinessScore < 70) return false
      if (scoreFilter === 'HIGH_FIT_READY' && (family.fitScore < 70 || family.readinessScore < 70)) return false
      if (gap !== 'ALL' && !family.missing.some(value => value.toLowerCase() === gap.toLowerCase())) return false
      if (!needle) return true
      const haystack = [
        family.name,
        family.parentName,
        family.master.legal_name,
        family.master.website,
        family.master.headquarters_address,
        family.master.headquarters_city,
        family.master.company_type,
        salesAccounts.find(account => account.sales_account_id===family.salesAccountId)?.account_owner,
        family.master.internal_summary,
        ...family.memberIds.map(id => profileById.get(id)?.canonical_name),
      ].filter(Boolean).join(' ').toLowerCase()
      return haystack.includes(needle)
    })
  }, [families, classification, salesStageFilter, scoreFilter, gap, search, profileById, salesAccounts])

  const explicitAliases = profiles.filter(profile => profile.rollup_company_id).length
  const parentsRecorded = families.filter(family => family.parentName).length
  const fullyEnriched = families.filter(family => family.missing.length === 0).length

  const coverage = useMemo(() => [
    ['Website', families.filter(family => Boolean(family.master.website)).length],
    ['Headquarters', families.filter(family => Boolean(family.master.headquarters_address || family.master.headquarters_city)).length],
    ['Company type', families.filter(family => Boolean(family.master.company_type)).length],
    ['Ownership', families.filter(family => ownershipKnown(family.master)).length],
    ['Revenue', families.filter(family => revenueKnown(family.master)).length],
    ['Identity source', families.filter(family => Boolean(family.master.identity_source_url)).length],
    ['Active contact', families.filter(family => family.contacts > 0).length],
  ] as const, [families])

  const accountClassificationCounts = useMemo(() => accountClassifications.map(value => [
    value,
    families.filter(family => family.accountClassification === value).length,
  ] as const), [families])

  const familyByMemberId = useMemo(() => {
    const map = new Map<string, FamilyRow>()
    families.forEach(family => family.memberIds.forEach(id => map.set(id, family)))
    return map
  }, [families])

  const activeSalesOpportunities = opportunities.filter(opportunity => activeOpportunityStages.has(opportunity.stage))
  const openPipelineArr = activeSalesOpportunities.reduce((sum, opportunity) => sum + (opportunity.estimated_arr ?? 0), 0)
  const wonArr = opportunities.filter(opportunity => opportunity.stage === 'closed-won').reduce((sum, opportunity) => sum + (opportunity.estimated_arr ?? 0), 0)
  const nowIso = new Date().toISOString()
  const overdueSalesTasks = salesTasks.filter(task => task.status === 'open' && task.due_at && task.due_at < nowIso)
  const upcomingDemos = salesDemos.filter(demo => demo.status === 'scheduled' && demo.scheduled_at && demo.scheduled_at >= nowIso)
  const proposalsOut = salesProposals.filter(proposal => proposal.status === 'sent' || proposal.status === 'revising')
  const liveSubscriptions=salesSubscriptions.filter(subscription=>['onboarding','active','paused'].includes(subscription.status))
  const renewalAttention=salesRenewals.filter(renewal=>['upcoming','contacted','negotiating'].includes(renewal.status))
  const opportunityByStage = useMemo(() => new Map(opportunityStages.map(stage => [
    stage,
    opportunities.filter(opportunity => opportunity.stage === stage),
  ])), [opportunities])

  const topTargets = useMemo(() => families
    .filter(family => !['customer','former-customer','partner','competitor','do-not-pursue'].includes(family.accountClassification))
    .sort((a,b) => b.fitScore-a.fitScore || b.readinessScore-a.readinessScore || b.publicObservations-a.publicObservations)
    .slice(0,12), [families])

  const highFitReadyCount=families.filter(family=>family.fitScore>=70&&family.readinessScore>=70&&!['customer','do-not-pursue'].includes(family.accountClassification)).length

  const parentRows = useMemo(() => {
    const map = new Map<string, {
      name: string
      familyCount: number
      identityCount: number
      observations: number
      contacts: number
      pipeline: number
      openDeals: number
      pipelineArr: number
      sourceUrl: string | null
    }>()
    families.forEach(family => {
      const key = family.parentName || 'No parent company recorded'
      const row = map.get(key) ?? { name:key, familyCount:0, identityCount:0, observations:0, contacts:0, pipeline:0, openDeals:0, pipelineArr:0, sourceUrl:null }
      row.familyCount += 1
      row.identityCount += family.memberCount
      row.observations += family.publicObservations
      row.contacts += family.contacts
      row.openDeals += family.openOpportunities
      row.pipelineArr += family.pipelineArr
      if (family.openOpportunities > 0 || family.accountClassification === 'active-prospect' || family.accountClassification === 'customer') row.pipeline += 1
      if (!row.sourceUrl && family.parentSourceUrl) row.sourceUrl = family.parentSourceUrl
      map.set(key,row)
    })
    return [...map.values()].sort((a,b) => b.familyCount - a.familyCount || b.observations - a.observations || a.name.localeCompare(b.name))
  }, [families])

  if (error) return <section className="product-page admin-company-page"><div className="reference-empty-state" role="alert"><strong>Company administration is unavailable.</strong><span>{error}</span><button onClick={()=>window.location.reload()}>Retry loading</button></div></section>
  if (allowed === null) return <section className="product-page admin-company-page"><div className="reference-empty-state"><strong>Loading private company administration…</strong></div></section>
  if (!allowed) return <section className="product-page admin-company-page"><div className="reference-empty-state"><strong>Administrator access required.</strong><span>{error || 'This workspace contains private company, contact and relationship records.'}</span></div></section>
  if (!payload) return <section className="product-page admin-company-page"><div className="reference-empty-state"><strong>Loading private company command center…</strong></div></section>

  return <section className="product-page admin-company-page">
    <div className="product-page-heading compact-heading admin-company-heading">
      <div>
        <span className="page-kicker">Admin · private TowerSignal CRM</span>
        <h1>Sales &amp; account command center</h1>
        <p>Work today’s follow-ups, manage deals and customer renewals, then move into account research only when you need it.</p>
      </div>
      <div className="page-actions">
        <a className="secondary-link-button" href="#/companies">Known Firms</a>
        <a className="secondary-link-button" href="#/service">Service operations</a>
      </div>
    </div>

    {error && <div className="company-admin-error"><strong>Company administration error.</strong><span>{error}</span></div>}

    <nav className="admin-workspace-nav" aria-label="Admin workspace sections">
      <button type="button" className={workspaceView==='today'?'active':''} onClick={()=>setWorkspaceView('today')}>
        <strong>Today</strong><span>Actions &amp; exceptions</span>
      </button>
      <button type="button" className={workspaceView==='pipeline'?'active':''} onClick={()=>setWorkspaceView('pipeline')}>
        <strong>Pipeline</strong><span>Deals &amp; targets</span>
      </button>
      <button type="button" className={workspaceView==='accounts'?'active':''} onClick={()=>setWorkspaceView('accounts')}>
        <strong>Accounts</strong><span>{number.format(families.length)} master families</span>
      </button>
      <button type="button" className={workspaceView==='data'?'active':''} onClick={()=>setWorkspaceView('data')}>
        <strong>Data &amp; ops</strong><span>Ownership &amp; research</span>
      </button>
    </nav>

    <div className="admin-command-strip">
      <article><small>Open deals</small><strong>{number.format(activeSalesOpportunities.length)}</strong><span>{openPipelineArr.toLocaleString(undefined,{style:'currency',currency:'USD',maximumFractionDigits:0})} pipeline</span></article>
      <article><small>Needs action</small><strong>{number.format(overdueSalesTasks.length)}</strong><span>overdue sales tasks</span></article>
      <article><small>Customers</small><strong>{number.format(liveSubscriptions.length)}</strong><span>{renewalAttention.length} open renewal workflow{renewalAttention.length===1?'':'s'}</span></article>
      <article><small>Ready targets</small><strong>{number.format(highFitReadyCount)}</strong><span>high fit + sales ready</span></article>
    </div>

    {workspaceView==='today'&&<div className="admin-workspace-view">
      <AdminSalesTodayPanel accounts={salesAccounts} opportunities={opportunities} tasks={salesTasks} activities={activities} demos={salesDemos} proposals={salesProposals} subscriptions={salesSubscriptions} renewals={salesRenewals} />
    </div>}

    {workspaceView==='pipeline'&&<div className="admin-workspace-view">
      <div className="admin-sales-metrics admin-sales-metrics-compact">
        <article><small>Open pipeline ARR</small><strong>{openPipelineArr.toLocaleString(undefined,{style:'currency',currency:'USD',maximumFractionDigits:0})}</strong><span>{number.format(activeSalesOpportunities.length)} active deals</span></article>
        <article><small>Upcoming demos</small><strong>{number.format(upcomingDemos.length)}</strong><span>scheduled meetings</span></article>
        <article><small>Open proposals</small><strong>{number.format(proposalsOut.length)}</strong><span>sent or revising</span></article>
        <article><small>Won ARR</small><strong>{wonArr.toLocaleString(undefined,{style:'currency',currency:'USD',maximumFractionDigits:0})}</strong><span>{number.format(opportunities.filter(opportunity=>opportunity.stage==='closed-won').length)} won deal(s)</span></article>
      </div>

      <section className="admin-sales-pipeline-card">
        <div className="admin-company-card-heading"><div><strong>Active sales pipeline</strong><span>Only stages that require active selling are shown here</span></div><small>{number.format(activeSalesOpportunities.length)} active</small></div>
        <div className="admin-sales-pipeline-board">
          {pipelineBoardStages.map(stage => <div key={stage} className="admin-sales-stage">
            <div className="admin-sales-stage-heading"><strong>{human(stage)}</strong><span>{number.format(opportunityByStage.get(stage)?.length ?? 0)}</span></div>
            <div className="admin-sales-stage-list">
              {(opportunityByStage.get(stage) ?? []).map(opportunity => {
                const family = familyByMemberId.get(opportunity.company_id)
                return <a key={opportunity.opportunity_id} href={`#/admin-company/${encodeURIComponent(family?.salesAccountId ?? opportunity.sales_account_id ?? opportunity.company_id)}`}>
                  <strong>{family?.name ?? opportunity.name}</strong>
                  <span>{opportunity.estimated_arr == null ? 'ARR not set' : opportunity.estimated_arr.toLocaleString(undefined,{style:'currency',currency:'USD',maximumFractionDigits:0})+' ARR'}{opportunity.probability_percent == null ? '' : ` · ${opportunity.probability_percent}%`}</span>
                  <small>{opportunity.next_step || (opportunity.demo_scheduled_at ? 'Demo '+new Date(opportunity.demo_scheduled_at).toLocaleString() : 'No next step')}</small>
                </a>
              })}
              {!(opportunityByStage.get(stage)?.length) && <span className="company-admin-empty">No deals</span>}
            </div>
          </div>)}
        </div>
      </section>

      <section className="admin-company-card admin-target-accounts">
        <div className="admin-company-card-heading"><div><strong>Priority target accounts</strong><span>Fit = customer potential · Ready = usable sales intelligence</span></div><small>{number.format(highFitReadyCount)} high fit + ready</small></div>
        <div className="admin-target-list">
          {topTargets.slice(0,8).map(family => <a key={family.salesAccountId} href={`#/admin-company/${encodeURIComponent(family.salesAccountId)}`}>
            <div><strong>{family.name}</strong><span>{family.parentName||'No parent recorded'}</span></div>
            <div className="admin-target-scores"><span><b>{family.fitScore}</b> Fit</span><span><b>{family.readinessScore}</b> Ready</span></div>
            <small>{family.fitReasons[0]||'Limited public fit evidence'} · {family.readinessReasons[0]||'Needs enrichment'}</small>
          </a>)}
        </div>
      </section>
    </div>}

    {workspaceView==='accounts'&&<div className="admin-workspace-view">
      <section className="admin-company-card admin-family-directory">
        <div className="admin-account-views" role="group" aria-label="Account table view">
          <button type="button" aria-pressed={accountView==='directory'} onClick={()=>setAccountView('directory')}>Companies</button>
          <button type="button" aria-pressed={accountView==='mapping'} onClick={()=>setAccountView('mapping')}>Mapping review</button>
        </div>
        {accountView==='mapping'?<CompanyRollupReviewPanel
          accounts={salesAccounts} members={salesAccountMembers} profiles={profiles}
          contacts={contacts} firms={payload.firms} onChanged={reloadPrivate}
        />:<>
        <div className="admin-company-card-heading admin-directory-heading">
          <div><strong>Master account directory</strong><span>{number.format(filteredFamilies.length)} of {number.format(families.length)} reviewed companies</span></div>
          <div className="admin-family-filters">
            <input aria-label="Admin company search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search company, parent, website, owner or notes…" />
            <select aria-label="Admin account classification filter" value={classification} onChange={event => setClassification(event.target.value)}><option value="ALL">All account types</option>{accountClassifications.map(value => <option key={value} value={value}>{human(value)}</option>)}</select>
            <select aria-label="Admin deal stage filter" value={salesStageFilter} onChange={event => setSalesStageFilter(event.target.value)}><option value="ALL">All deal stages</option>{opportunityStages.map(stage => <option key={stage} value={stage}>{human(stage)}</option>)}</select>
            <select aria-label="Admin sales score filter" value={scoreFilter} onChange={event => setScoreFilter(event.target.value)}><option value="ALL">All fit/readiness</option><option value="HIGH_FIT">High fit ≥70</option><option value="READY">Sales ready ≥70</option><option value="HIGH_FIT_READY">High fit + ready</option></select>
            <select aria-label="Admin enrichment gap filter" value={gap} onChange={event => setGap(event.target.value)}><option value="ALL">All data states</option><option value="website">Missing website</option><option value="HQ">Missing HQ</option><option value="company type">Missing company type</option><option value="ownership">Missing ownership</option><option value="revenue">Missing revenue</option><option value="identity source">Missing identity source</option><option value="contact">Missing contact</option></select>
          </div>
        </div>
        <div className="table-scroll"><table className="account-table admin-family-table admin-family-table-compact"><thead><tr><th>Account</th><th>Fit / ready</th><th>Sales</th><th>Contacts</th><th>Public evidence</th><th>Data gaps</th><th>Next</th></tr></thead><tbody>
          {filteredFamilies.map(family => <tr key={family.salesAccountId} onClick={() => { window.location.hash = `#/admin-company/${encodeURIComponent(family.salesAccountId)}` }} tabIndex={0} onKeyDown={event => { if (event.key === 'Enter') window.location.hash = `#/admin-company/${encodeURIComponent(family.salesAccountId)}` }}>
            <td><strong>{family.name}</strong><small>{family.parentName||family.master.legal_name||family.master.canonical_name}</small>{family.master.website&&<small>{family.master.website.replace(/^https?:\/\//,'').replace(/\/$/,'')}</small>}</td>
            <td><div className="admin-table-scores"><span><b>{family.fitScore}</b> Fit</span><span><b>{family.readinessScore}</b> Ready</span></div></td>
            <td><span className="admin-status-chip">{family.salesStage ? human(family.salesStage) : human(family.accountClassification)}</span><small>{family.openOpportunities} deal{family.openOpportunities===1?'':'s'} · {family.pipelineArr.toLocaleString(undefined,{style:'currency',currency:'USD',maximumFractionDigits:0})} ARR</small><small>{family.salesOpenTasks} open task{family.salesOpenTasks===1?'':'s'}</small></td>
            <td><strong>{number.format(family.contacts)}</strong><small>{number.format(family.activities)} interactions</small></td>
            <td><strong>{number.format(family.publicObservations)} observations</strong><small>{number.format(family.servicedRelationships)} serviced · {number.format(family.towerAccountLinks)} tower links</small></td>
            <td>{family.missing.length?<><strong>{family.missing.length} gaps</strong><small>{family.missing.slice(0,3).join(' · ')}{family.missing.length>3?' · …':''}</small></>:<span className="health-badge health-healthy">COMPLETE</span>}{family.research&&<small>Research {family.research.priority_score} · {human(family.research.status)}</small>}</td>
            <td><strong>{family.nextActionDate||'—'}</strong><small>{family.salesNextStep||'Open account'}</small></td>
          </tr>)}
        </tbody></table></div>
        </>}
      </section>
    </div>}

    {workspaceView==='data'&&<div className="admin-workspace-view admin-data-workspace">
      <div className="admin-company-metrics admin-company-metrics-compact">
        <article><small>Master families</small><strong>{number.format(families.length)}</strong><span>{number.format(explicitAliases)} rolled-up identities</span></article>
        <article><small>Parents recorded</small><strong>{number.format(parentsRecorded)}</strong><span>{families.length ? Math.round(parentsRecorded/families.length*100) : 0}% coverage</span></article>
        <article><small>Active contacts</small><strong>{number.format(contacts.filter(contact=>contact.active).length)}</strong><span>{number.format(families.filter(family=>family.contacts>0).length)} accounts covered</span></article>
        <article><small>Fully enriched</small><strong>{number.format(fullyEnriched)}</strong><span>all tracked fields populated</span></article>
      </div>

      <div className="admin-company-dashboard-grid admin-data-summary-grid">
        <section className="admin-company-card">
          <div className="admin-company-card-heading"><div><strong>Enrichment coverage</strong><span>Master-account private data completeness</span></div></div>
          <div className="admin-coverage-list">{coverage.map(([label,count]) => <div key={label}><div><strong>{label}</strong><span>{number.format(count)} / {number.format(families.length)}</span></div><progress max={Math.max(1,families.length)} value={count}/><small>{families.length?Math.round(count/families.length*100):0}% covered</small></div>)}</div>
        </section>
        <section className="admin-company-card">
          <div className="admin-company-card-heading"><div><strong>Account classification</strong><span>Authoritative master-account state</span></div></div>
          <div className="admin-pipeline-grid">{accountClassificationCounts.map(([value,count]) => <article key={value}><small>{human(value)}</small><strong>{number.format(count)}</strong></article>)}</div>
        </section>
      </div>

      <details className="admin-company-secondary-panel">
        <summary><div><strong>Parent mapping &amp; enrichment checks</strong><small>Reviewed relationships, approved sources and run status</small></div><span>Open evidence</span></summary>
        <div className="admin-company-secondary-body"><CompanyEvidencePanel accounts={salesAccounts}/></div>
      </details>

      <details className="admin-company-secondary-panel">
        <summary><div><strong>Parent company hierarchy</strong><small>{number.format(parentRows.length)} ownership states</small></div><span>Open hierarchy</span></summary>
        <div className="admin-company-secondary-body">
          <div className="table-scroll"><table className="account-table admin-parent-table"><thead><tr><th>Parent / owner</th><th>Families</th><th>Source identities</th><th>Observations</th><th>Contacts</th><th>Open deals</th><th>Pipeline ARR</th><th>Evidence</th></tr></thead><tbody>
            {parentRows.map(parent => <tr key={parent.name}><td><strong>{parent.name}</strong></td><td>{number.format(parent.familyCount)}</td><td>{number.format(parent.identityCount)}</td><td>{number.format(parent.observations)}</td><td>{number.format(parent.contacts)}</td><td>{number.format(parent.openDeals)}</td><td>{parent.pipelineArr.toLocaleString(undefined,{style:'currency',currency:'USD',maximumFractionDigits:0})}</td><td>{parent.sourceUrl?<a className="table-link" href={parent.sourceUrl} target="_blank" rel="noreferrer">Source ↗</a>:'Not recorded'}</td></tr>)}
          </tbody></table></div>
        </div>
      </details>

      <details className="admin-company-operations-panel">
        <summary><div><strong>Research queue &amp; enrichment operations</strong><span>Ranking, workflow state and synchronization</span></div><span>Open operations</span></summary>
        <div className="admin-company-operations-body"><CompanyAdminWorkspace firms={payload.firms} profiles={profiles} onProfilesChanged={reloadPrivate}/></div>
      </details>

      <details className="admin-company-operations-panel">
        <summary><div><strong>Import reviewed company data</strong><span>Bulk administrative maintenance</span></div><span>Open importer</span></summary>
        <div className="admin-company-operations-body"><CompanyAdminImportPanel firms={payload.firms} onImported={reloadPrivate}/></div>
      </details>
    </div>}
  </section>
}
