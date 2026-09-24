import { useEffect, useMemo, useState } from 'react'
import {
  loadAllCompanyActivities,
  loadAllCompanyContacts,
  loadCompanyAdminAccess,
  loadCompanyAdminDirectory,
  loadCompanyResearchQueue,
  loadAllCompanySalesOpportunities,
  loadAllCompanySalesTasks,
} from '../companyAdmin/client'
import { loadKnownFirms } from '../data/api'
import type {
  CompanyAdminActivity,
  CompanyAdminContact,
  CompanyAdminProfile,
  CompanyRelationshipStatus,
  CompanyResearchQueueItem,
  CompanySalesOpportunity,
  CompanySalesTask,
  CompanyOpportunityStage,
} from '../types/companyAdmin'
import type { KnownFirmPayload, KnownFirmSummaryRecord } from '../types/firm'
import { CompanyAdminImportPanel } from './CompanyAdminImportPanel'
import { CompanyAdminWorkspace } from './CompanyAdminWorkspace'

const number = new Intl.NumberFormat('en-US')
const statuses: CompanyRelationshipStatus[] = [
  'uncontacted','researching','outreach-planned','contacted','engaged','opportunity','customer','not-pursuing',
]
const pipelineStatuses = new Set<CompanyRelationshipStatus>(['contacted','engaged','opportunity','customer'])
const opportunityStages: CompanyOpportunityStage[] = ['lead','qualified','demo-scheduled','demo-complete','proposal','negotiation','closed-won','closed-lost','nurture']
const activeOpportunityStages = new Set<CompanyOpportunityStage>(['lead','qualified','demo-scheduled','demo-complete','proposal','negotiation'])
const relationshipRank: Record<CompanyRelationshipStatus, number> = {
  'uncontacted':0,
  'researching':1,
  'outreach-planned':2,
  'contacted':3,
  'engaged':4,
  'opportunity':5,
  'customer':6,
  'not-pursuing':-1,
}

function familyRelationshipStatus(members: CompanyAdminProfile[]): CompanyRelationshipStatus {
  const active = members.filter(member => member.relationship_status !== 'not-pursuing')
  if (!active.length) return 'not-pursuing'
  return [...active].sort((a,b) => relationshipRank[b.relationship_status] - relationshipRank[a.relationship_status])[0].relationship_status
}

function familyNextActionDate(members: CompanyAdminProfile[]): string | null {
  return members.map(member => member.next_action_date).filter((value): value is string => Boolean(value)).sort()[0] ?? null
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
  relationshipStatus: CompanyRelationshipStatus
  nextActionDate: string | null
  research: CompanyResearchQueueItem | null
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
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [relationship, setRelationship] = useState('ALL')
  const [gap, setGap] = useState('ALL')

  const reloadPrivate = async () => {
    const [nextProfiles, nextContacts, nextActivities, nextQueue, nextOpportunities, nextSalesTasks] = await Promise.all([
      loadCompanyAdminDirectory(),
      loadAllCompanyContacts(),
      loadAllCompanyActivities(),
      loadCompanyResearchQueue(),
      loadAllCompanySalesOpportunities(),
      loadAllCompanySalesTasks(),
    ])
    setProfiles(nextProfiles)
    setContacts(nextContacts)
    setActivities(nextActivities)
    setQueue(nextQueue)
    setOpportunities(nextOpportunities)
    setSalesTasks(nextSalesTasks)
  }

  useEffect(() => {
    let cancelled = false
    loadCompanyAdminAccess().then(async isAdmin => {
      if (cancelled) return
      setAllowed(isAdmin)
      if (!isAdmin) return
      const [known, nextProfiles, nextContacts, nextActivities, nextQueue, nextOpportunities, nextSalesTasks] = await Promise.all([
        loadKnownFirms(),
        loadCompanyAdminDirectory(),
        loadAllCompanyContacts(),
        loadAllCompanyActivities(),
        loadCompanyResearchQueue(),
        loadAllCompanySalesOpportunities(),
        loadAllCompanySalesTasks(),
      ])
      if (cancelled) return
      setPayload(known)
      setProfiles(nextProfiles)
      setContacts(nextContacts)
      setActivities(nextActivities)
      setQueue(nextQueue)
      setOpportunities(nextOpportunities)
      setSalesTasks(nextSalesTasks)
    }).catch(err => {
      if (!cancelled) {
        setAllowed(false)
        setError(err instanceof Error ? err.message : 'Unable to load private company administration')
      }
    })
    return () => { cancelled = true }
  }, [])

  const profileById = useMemo(() => new Map(profiles.map(profile => [profile.company_id, profile])), [profiles])
  const firmById = useMemo(() => new Map((payload?.firms ?? []).map(firm => [firm.firm_id, firm])), [payload?.firms])
  const queueById = useMemo(() => new Map(queue.map(item => [item.company_id, item])), [queue])

  const contactsByCompany = useMemo(() => {
    const map = new Map<string, number>()
    contacts.filter(contact => contact.active).forEach(contact => map.set(contact.company_id, (map.get(contact.company_id) ?? 0) + 1))
    return map
  }, [contacts])

  const activitiesByCompany = useMemo(() => {
    const map = new Map<string, number>()
    activities.forEach(activity => map.set(activity.company_id, (map.get(activity.company_id) ?? 0) + 1))
    return map
  }, [activities])

  const families = useMemo<FamilyRow[]>(() => {
    const grouped = new Map<string, CompanyAdminProfile[]>()
    profiles.forEach(profile => {
      const masterId = profile.rollup_company_id || profile.company_id
      const rows = grouped.get(masterId) ?? []
      rows.push(profile)
      grouped.set(masterId, rows)
    })

    return [...grouped.entries()].map(([masterId, members]) => {
      const master = profileById.get(masterId) ?? members.find(member => member.company_id === masterId) ?? members[0]
      const publicRows = members.map(member => firmById.get(member.company_id)).filter((firm): firm is KnownFirmSummaryRecord => Boolean(firm))
      const memberIds = members.map(member => member.company_id)
      const familyContacts = memberIds.reduce((sum, id) => sum + (contactsByCompany.get(id) ?? 0), 0)
      const familyActivities = memberIds.reduce((sum, id) => sum + (activitiesByCompany.get(id) ?? 0), 0)
      return {
        masterId,
        name: master.rollup_name || master.legal_name || master.canonical_name,
        parentName: master.parent_company_name,
        parentSourceUrl: master.parent_source_url,
        master,
        memberIds,
        memberCount: members.length,
        publicIdentityCount: publicRows.length,
        publicObservations: publicRows.reduce((sum, firm) => sum + firm.observation_count, 0),
        servicedRelationships: publicRows.reduce((sum, firm) => sum + firm.serviced_site_count, 0),
        towerAccountLinks: publicRows.reduce((sum, firm) => sum + firm.tower_account_count, 0),
        publicContracts: publicRows.reduce((sum, firm) => sum + firm.observed_contract_count, 0),
        contacts: familyContacts,
        activities: familyActivities,
        relationshipStatus: familyRelationshipStatus(members),
        nextActionDate: familyNextActionDate(members),
        research: queueById.get(masterId) ?? null,
        missing: missingFields(master, familyContacts),
      }
    }).sort((a,b) => b.publicObservations - a.publicObservations || a.name.localeCompare(b.name))
  }, [profiles, profileById, firmById, contactsByCompany, activitiesByCompany, queueById])

  const filteredFamilies = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return families.filter(family => {
      if (relationship !== 'ALL' && family.relationshipStatus !== relationship) return false
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
        family.master.account_owner,
        family.master.internal_summary,
        ...family.memberIds.map(id => profileById.get(id)?.canonical_name),
      ].filter(Boolean).join(' ').toLowerCase()
      return haystack.includes(needle)
    })
  }, [families, relationship, gap, search, profileById])

  const today = new Date().toISOString().slice(0,10)
  const nextWeek = new Date(Date.now() + 7 * 86400000).toISOString().slice(0,10)
  const overdue = families.filter(family => family.nextActionDate && family.nextActionDate < today && !['customer','not-pursuing'].includes(family.relationshipStatus))
  const upcoming = families.filter(family => family.nextActionDate && family.nextActionDate >= today && family.nextActionDate <= nextWeek)
  const pipeline = families.filter(family => pipelineStatuses.has(family.relationshipStatus))
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

  const pipelineCounts = useMemo(() => statuses.map(status => [
    status,
    families.filter(family => family.relationshipStatus === status).length,
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
  const upcomingDemos = opportunities.filter(opportunity => opportunity.demo_scheduled_at && opportunity.demo_scheduled_at >= nowIso && activeOpportunityStages.has(opportunity.stage))
  const proposalsOut = opportunities.filter(opportunity => opportunity.stage === 'proposal' || opportunity.stage === 'negotiation')
  const opportunityByStage = useMemo(() => new Map(opportunityStages.map(stage => [
    stage,
    opportunities.filter(opportunity => opportunity.stage === stage),
  ])), [opportunities])

  const recentActivities = useMemo(() => activities
    .map(activity => ({ activity, family: familyByMemberId.get(activity.company_id) }))
    .filter((row): row is { activity: CompanyAdminActivity; family: FamilyRow } => Boolean(row.family))
    .slice(0, 12), [activities, familyByMemberId])

  const attentionFamilies = useMemo(() => [...overdue, ...upcoming]
    .sort((a,b) => (a.nextActionDate || '').localeCompare(b.nextActionDate || ''))
    .slice(0, 12), [overdue, upcoming])

  const parentRows = useMemo(() => {
    const map = new Map<string, {
      name: string
      familyCount: number
      identityCount: number
      observations: number
      contacts: number
      pipeline: number
      sourceUrl: string | null
    }>()
    families.forEach(family => {
      const key = family.parentName || 'No parent company recorded'
      const row = map.get(key) ?? { name:key, familyCount:0, identityCount:0, observations:0, contacts:0, pipeline:0, sourceUrl:null }
      row.familyCount += 1
      row.identityCount += family.memberCount
      row.observations += family.publicObservations
      row.contacts += family.contacts
      if (pipelineStatuses.has(family.relationshipStatus)) row.pipeline += 1
      if (!row.sourceUrl && family.parentSourceUrl) row.sourceUrl = family.parentSourceUrl
      map.set(key,row)
    })
    return [...map.values()].sort((a,b) => b.familyCount - a.familyCount || b.observations - a.observations || a.name.localeCompare(b.name))
  }, [families])

  if (allowed === null) return <section className="product-page admin-company-page"><div className="reference-empty-state"><strong>Loading private company administration…</strong></div></section>
  if (!allowed) return <section className="product-page admin-company-page"><div className="reference-empty-state"><strong>Administrator access required.</strong><span>{error || 'This workspace contains private company, contact and relationship records.'}</span></div></section>
  if (!payload) return <section className="product-page admin-company-page"><div className="reference-empty-state"><strong>Loading private company command center…</strong></div></section>

  return <section className="product-page admin-company-page">
    <div className="product-page-heading compact-heading admin-company-heading">
      <div>
        <span className="page-kicker">Admin only · private company intelligence &amp; CRM</span>
        <h1>Company command center</h1>
        <p>Your private TowerSignal sales CRM: reviewed company families, contacts, deals, demos, proposals, follow-ups and research. Public Known Firms remains a separate source-backed workspace.</p>
      </div>
      <div className="page-actions">
        <a className="secondary-link-button" href="#/companies">Known Firms</a>
        <a className="secondary-link-button" href="#/service">Service operations</a>
      </div>
    </div>

    {error && <div className="company-admin-error"><strong>Company administration error.</strong><span>{error}</span></div>}

    <div className="admin-sales-metrics">
      <article><small>Open TowerSignal deals</small><strong>{number.format(activeSalesOpportunities.length)}</strong><span>{number.format(opportunities.length)} total opportunities</span></article>
      <article><small>Open pipeline ARR</small><strong>{openPipelineArr.toLocaleString(undefined,{style:'currency',currency:'USD',maximumFractionDigits:0})}</strong><span>Estimated recurring value</span></article>
      <article><small>Demos scheduled</small><strong>{number.format(upcomingDemos.length)}</strong><span>Upcoming demo meetings</span></article>
      <article><small>Proposals / negotiation</small><strong>{number.format(proposalsOut.length)}</strong><span>Commercially active deals</span></article>
      <article><small>Overdue sales tasks</small><strong>{number.format(overdueSalesTasks.length)}</strong><span>{number.format(salesTasks.filter(task=>task.status==='open').length)} open tasks</span></article>
      <article><small>Won ARR</small><strong>{wonArr.toLocaleString(undefined,{style:'currency',currency:'USD',maximumFractionDigits:0})}</strong><span>{number.format(opportunities.filter(opportunity=>opportunity.stage==='closed-won').length)} won deal(s)</span></article>
    </div>

    <div className="admin-company-metrics">
      <article><small>Master families</small><strong>{number.format(families.length)}</strong><span>{number.format(explicitAliases)} rolled-up source identities</span></article>
      <article><small>Private profiles</small><strong>{number.format(profiles.length)}</strong><span>{number.format(payload.summary.known_firm_count)} public Known Firms</span></article>
      <article><small>Parents recorded</small><strong>{number.format(parentsRecorded)}</strong><span>{families.length ? Math.round(parentsRecorded / families.length * 100) : 0}% of master families</span></article>
      <article><small>Active contacts</small><strong>{number.format(contacts.filter(contact => contact.active).length)}</strong><span>{number.format(families.filter(family => family.contacts > 0).length)} families with contacts</span></article>
      <article><small>Pipeline</small><strong>{number.format(pipeline.length)}</strong><span>Contacted → customer</span></article>
      <article><small>Follow-up</small><strong>{number.format(overdue.length)}</strong><span>overdue · {number.format(upcoming.length)} due in 7 days</span></article>
      <article><small>Research queue</small><strong>{number.format(queue.length)}</strong><span>{number.format(queue.filter(item => item.status === 'complete').length)} complete</span></article>
      <article><small>Fully enriched</small><strong>{number.format(fullyEnriched)}</strong><span>All tracked admin fields populated</span></article>
    </div>

    <section className="admin-sales-pipeline-card">
      <div className="admin-company-card-heading"><div><strong>TowerSignal sales pipeline</strong><span>Personal deal board across reviewed master companies</span></div><small>{number.format(activeSalesOpportunities.length)} active</small></div>
      <div className="admin-sales-pipeline-board">
        {opportunityStages.map(stage => <div key={stage} className="admin-sales-stage">
          <div className="admin-sales-stage-heading"><strong>{human(stage)}</strong><span>{number.format(opportunityByStage.get(stage)?.length ?? 0)}</span></div>
          <div className="admin-sales-stage-list">
            {(opportunityByStage.get(stage) ?? []).map(opportunity => {
              const family = familyByMemberId.get(opportunity.company_id)
              return <a key={opportunity.opportunity_id} href={`#/admin-company/${encodeURIComponent(family?.masterId ?? opportunity.company_id)}`}>
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

    <div className="admin-company-dashboard-grid">
      <section className="admin-company-card admin-parent-summary">
        <div className="admin-company-card-heading"><div><strong>Parent company summary</strong><span>Private ownership rollup across reviewed master families</span></div><small>{number.format(parentRows.length)} parent states</small></div>
        <div className="table-scroll"><table className="account-table admin-parent-table"><thead><tr><th>Parent / owner</th><th>Families</th><th>Source identities</th><th>Public observations</th><th>Contacts</th><th>Pipeline families</th><th>Ownership evidence</th></tr></thead><tbody>
          {parentRows.map(parent => <tr key={parent.name}><td><strong>{parent.name}</strong></td><td>{number.format(parent.familyCount)}</td><td>{number.format(parent.identityCount)}</td><td>{number.format(parent.observations)}</td><td>{number.format(parent.contacts)}</td><td>{number.format(parent.pipeline)}</td><td>{parent.sourceUrl ? <a className="table-link" href={parent.sourceUrl} target="_blank" rel="noreferrer">Open source ↗</a> : 'Not recorded'}</td></tr>)}
        </tbody></table></div>
      </section>

      <section className="admin-company-card">
        <div className="admin-company-card-heading"><div><strong>Enrichment coverage</strong><span>Master-family private fields</span></div></div>
        <div className="admin-coverage-list">{coverage.map(([label,count]) => <div key={label}><div><strong>{label}</strong><span>{number.format(count)} / {number.format(families.length)}</span></div><progress max={Math.max(1,families.length)} value={count} /><small>{families.length ? Math.round(count / families.length * 100) : 0}% covered</small></div>)}</div>
      </section>

      <section className="admin-company-card">
        <div className="admin-company-card-heading"><div><strong>CRM pipeline</strong><span>Current master-family relationship state</span></div></div>
        <div className="admin-pipeline-grid">{pipelineCounts.map(([status,count]) => <article key={status}><small>{human(status)}</small><strong>{number.format(count)}</strong></article>)}</div>
      </section>
    </div>

    <div className="admin-company-attention-grid">
      <section className="admin-company-card">
        <div className="admin-company-card-heading"><div><strong>Follow-up attention</strong><span>Overdue and next-seven-day company actions</span></div><small>{number.format(overdue.length + upcoming.length)} due</small></div>
        <div className="admin-company-activity-list">
          {attentionFamilies.length ? attentionFamilies.map(family => <a key={family.masterId} href={`#/admin-company/${encodeURIComponent(family.masterId)}`}>
            <strong>{family.name}</strong>
            <span>{family.nextActionDate || 'No date'} · {human(family.relationshipStatus)}</span>
            <small>{family.contacts} active contact{family.contacts===1?'':'s'} · {family.activities} interaction{family.activities===1?'':'s'}</small>
          </a>) : <span className="company-admin-empty">No company follow-ups are due in the next seven days.</span>}
        </div>
      </section>

      <section className="admin-company-card">
        <div className="admin-company-card-heading"><div><strong>Recent CRM activity</strong><span>Latest private outreach and interaction records</span></div><small>{number.format(activities.length)} total</small></div>
        <div className="admin-company-activity-list">
          {recentActivities.length ? recentActivities.map(({activity,family}) => <a key={activity.activity_id} href={`#/admin-company/${encodeURIComponent(family.masterId)}`}>
            <strong>{family.name}</strong>
            <span>{new Date(activity.occurred_at).toLocaleString()} · {human(activity.activity_type)}</span>
            <small>{activity.subject || activity.outcome || activity.details || 'Interaction logged'}{activity.next_action_date ? ` · next ${activity.next_action_date}` : ''}</small>
          </a>) : <span className="company-admin-empty">No company interactions have been logged yet.</span>}
        </div>
      </section>
    </div>

    <section className="admin-company-card admin-family-directory">
      <div className="admin-company-card-heading">
        <div><strong>Company family directory</strong><span>{number.format(filteredFamilies.length)} of {number.format(families.length)} reviewed master families</span></div>
        <div className="admin-family-filters">
          <input aria-label="Admin company search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search family, parent, website, owner or notes…" />
          <select aria-label="Admin relationship filter" value={relationship} onChange={event => setRelationship(event.target.value)}><option value="ALL">All CRM statuses</option>{statuses.map(status => <option key={status} value={status}>{human(status)}</option>)}</select>
          <select aria-label="Admin enrichment gap filter" value={gap} onChange={event => setGap(event.target.value)}><option value="ALL">All enrichment states</option><option value="website">Missing website</option><option value="HQ">Missing HQ</option><option value="company type">Missing company type</option><option value="ownership">Missing ownership</option><option value="revenue">Missing revenue</option><option value="identity source">Missing identity source</option><option value="contact">Missing contact</option></select>
        </div>
      </div>
      <div className="table-scroll"><table className="account-table admin-family-table"><thead><tr><th>Master family</th><th>Parent / ownership</th><th>Source identities</th><th>Public evidence</th><th>Contacts / activity</th><th>CRM</th><th>Research</th><th>Enrichment gaps</th><th>Next action</th><th></th></tr></thead><tbody>
        {filteredFamilies.map(family => <tr key={family.masterId} onClick={() => { window.location.hash = `#/admin-company/${encodeURIComponent(family.masterId)}` }} tabIndex={0} onKeyDown={event => { if (event.key === 'Enter') window.location.hash = `#/admin-company/${encodeURIComponent(family.masterId)}` }}>
          <td><strong>{family.name}</strong><small>{family.master.legal_name || family.master.canonical_name}</small>{family.master.website && <small>{family.master.website.replace(/^https?:\/\//,'').replace(/\/$/,'')}</small>}</td>
          <td><strong>{family.parentName || 'Not recorded'}</strong><small>{ownershipKnown(family.master) ? 'Ownership reviewed' : 'Needs ownership research'}</small></td>
          <td><strong>{number.format(family.memberCount)}</strong><small>{number.format(family.publicIdentityCount)} in public Known Firms</small></td>
          <td><strong>{number.format(family.publicObservations)} observations</strong><small>{number.format(family.servicedRelationships)} serviced relationships · {number.format(family.towerAccountLinks)} tower links · {number.format(family.publicContracts)} contracts</small></td>
          <td><strong>{number.format(family.contacts)} contacts</strong><small>{number.format(family.activities)} logged interactions</small></td>
          <td><span className="admin-status-chip">{human(family.relationshipStatus)}</span><small>{family.master.account_owner || 'Owner unassigned'}</small></td>
          <td><strong>{family.research ? `${family.research.priority_score} priority` : 'Not queued'}</strong><small>{family.research ? human(family.research.status) : '—'}</small></td>
          <td>{family.missing.length ? <><strong>{family.missing.length}</strong><small>{family.missing.join(' · ')}</small></> : <span className="health-badge health-healthy">COMPLETE</span>}</td>
          <td><strong>{family.nextActionDate || '—'}</strong></td>
          <td className="row-arrow">›</td>
        </tr>)}
      </tbody></table></div>
    </section>

    <details className="admin-company-operations-panel">
      <summary><div><strong>Research queue &amp; follow-up operations</strong><span>Ranking, workflow state and queue synchronization</span></div><span>Open operations</span></summary>
      <div className="admin-company-operations-body"><CompanyAdminWorkspace firms={payload.firms} profiles={profiles} onProfilesChanged={reloadPrivate} /></div>
    </details>

    <CompanyAdminImportPanel firms={payload.firms} onImported={reloadPrivate} />
  </section>
}
