import { useEffect, useMemo, useState } from 'react'
import {
  loadCompanyAdminOverview,
  saveCompanyResearchQueueItem,
  syncCompanyResearchQueue,
} from '../companyAdmin/client'
import { belongsToSalesAccount } from '../companyAdmin/accountMapping'
import { buildCompanyResearchCandidates } from '../companyAdmin/priority'
import type {
  CompanyAdminActivity,
  CompanyAdminContact,
  CompanyAdminProfile,
  CompanyResearchQueueItem,
  CompanyResearchStatus,
} from '../types/companyAdmin'
import type { KnownFirmSummaryRecord } from '../types/firm'

const statuses: CompanyResearchStatus[] = ['unreviewed', 'researching', 'verified', 'needs-review', 'complete']
const number = new Intl.NumberFormat('en-US')
const label = (value: string) => value.replaceAll('-', ' ').replace(/(^|\s)\S/g, match => match.toUpperCase())

export function CompanyAdminWorkspace({
  firms,
  profiles,
  onProfilesChanged,
}: {
  firms: KnownFirmSummaryRecord[]
  profiles: CompanyAdminProfile[]
  onProfilesChanged: () => Promise<void>
}) {
  const [queue, setQueue] = useState<CompanyResearchQueueItem[]>([])
  const [contacts, setContacts] = useState<CompanyAdminContact[]>([])
  const [activities, setActivities] = useState<CompanyAdminActivity[]>([])
  const [overview,setOverview]=useState<Awaited<ReturnType<typeof loadCompanyAdminOverview>>|null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const applyOverview=(data:Awaited<ReturnType<typeof loadCompanyAdminOverview>>)=>{
    setOverview(data);setQueue(data.queue);setContacts(data.contacts);setActivities(data.activities)
  }
  const reload = async () => applyOverview(await loadCompanyAdminOverview())
  useEffect(() => {
    let cancelled=false
    loadCompanyAdminOverview().then(data=>{if(!cancelled)applyOverview(data)})
      .catch(err=>{if(!cancelled)setError(err instanceof Error?err.message:'Unable to load company operations')})
    return()=>{cancelled=true}
  }, [])

  const candidates = useMemo(() => buildCompanyResearchCandidates(firms, profiles, 100), [firms, profiles])
  const firmById = useMemo(() => new Map(firms.map(firm => [firm.firm_id, firm])), [firms])
  const profileById = useMemo(() => new Map(profiles.map(profile => [profile.company_id, profile])), [profiles])
  const contactsByCompany = useMemo(() => {
    const map=new Map<string,number>()
    for(const account of overview?.accounts??[]) {
      const ids=new Set(overview!.members.filter(m=>m.sales_account_id===account.sales_account_id).map(m=>m.company_id))
      const count=contacts.filter(c=>c.active&&belongsToSalesAccount(c,account.sales_account_id,ids)).length
      if(count)for(const id of ids)map.set(id,count)
    }
    return map
  }, [contacts,overview])
  const coveredAccounts=overview?.accounts.filter(a=>contacts.some(c=>c.active&&c.sales_account_id===a.sales_account_id)).length??0
  const today = new Date().toISOString().slice(0, 10)
  const nextWeek = new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10)
  const openTasks=overview?.tasks.filter(t=>t.status==='open')??[]
  const overdue=openTasks.filter(t=>t.due_at&&t.due_at.slice(0,10)<today)
  const upcoming=openTasks.filter(t=>t.due_at&&t.due_at.slice(0,10)>=today&&t.due_at.slice(0,10)<=nextWeek)
  const pipeline=overview?.opportunities.filter(o=>!['closed-won','closed-lost','nurture'].includes(o.stage))??[]
  const enriched = profiles.filter(profile =>
    profile.website || profile.headquarters_address || profile.parent_company_name || profile.company_type ||
    profile.revenue_amount != null || profile.revenue_low != null || profile.revenue_high != null
  )

  const syncTop100 = async () => {
    setBusy(true)
    setError(null)
    try {
      await syncCompanyResearchQueue(candidates)
      await onProfilesChanged()
      await reload()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to sync research queue')
    } finally {
      setBusy(false)
    }
  }

  const changeStatus = async (item: CompanyResearchQueueItem, status: CompanyResearchStatus) => {
    setBusy(true)
    setError(null)
    try {
      const saved = await saveCompanyResearchQueueItem({
        company_id: item.company_id,
        priority_score: item.priority_score,
        priority_reason: item.priority_reason,
        missing_fields: item.missing_fields,
        status,
        research_owner: item.research_owner,
        last_researched_at: status === 'unreviewed' ? item.last_researched_at : new Date().toISOString(),
      }, { source: 'manual' })
      setQueue(current => current.map(row => row.company_id === saved.company_id ? saved : row))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to update research status')
    } finally {
      setBusy(false)
    }
  }

  const rows: CompanyResearchQueueItem[] = queue.length ? queue : candidates.slice(0, 20).map(candidate => ({
    company_id: candidate.company_id,
    priority_score: candidate.priority_score,
    priority_reason: candidate.priority_reason,
    missing_fields: candidate.missing_fields,
    status: 'unreviewed',
    research_owner: null,
    last_researched_at: null,
    queued_at: '',
    updated_at: '',
    created_by: null,
    updated_by: null,
  }))

  if(!overview)return <section className="company-ops-workspace"><p role={error?"alert":undefined}>{error??"Loading company operations�"}</p></section>
  return <section className="company-ops-workspace" aria-label="Admin company operations">
    <div className="company-ops-heading">
      <div>
        <span className="page-kicker">Admin only · company operations</span>
        <h2>Research queue &amp; pipeline</h2>
        <p>Private prospecting state layered over source-backed Known Firms. Public firm identity and evidence remain unchanged.</p>
      </div>
      <div className="company-ops-heading-actions">
        <a className="secondary-link-button" href="#/service">Service operations</a>
        <button onClick={() => void syncTop100()} disabled={busy || candidates.length === 0}>{busy ? 'Updating…' : 'Sync top 100 research queue'}</button>
      </div>
    </div>

    {error && <div className="company-admin-error"><strong>Company operations error.</strong><span>{error}</span></div>}

    <div className="company-ops-metrics">
      <article><small>Private profiles</small><strong>{number.format(profiles.length)}</strong><span>{number.format(enriched.length)} with enrichment</span></article>
      <article><small>Sourced contacts</small><strong>{number.format(contacts.filter(c=>c.active).length)}</strong><span>{number.format(coveredAccounts)} accounts with active contacts</span></article>
      <article><small>Open deals</small><strong>{number.format(pipeline.length)}</strong><span>Contacted → customer</span></article>
      <article><small>Overdue follow-up</small><strong>{number.format(overdue.length)}</strong><span>{number.format(upcoming.length)} due in next 7 days</span></article>
      <article><small>Research queue</small><strong>{number.format(queue.length)}</strong><span>{number.format(queue.filter(row => row.status === 'complete').length)} complete</span></article>
      <article><small>Interactions</small><strong>{number.format(activities.length)}</strong><span>Private CRM activity history</span></article>
    </div>

    <div className="company-ops-grid">
      <section className="company-ops-card company-research-card">
        <div className="company-ops-card-heading"><div><strong>Research priority</strong><span>Top commercial families after reviewed private rollups</span></div><small>{queue.length ? 'Persisted queue' : 'Preview · queue not seeded yet'}</small></div>
        <div className="company-research-list">
          {rows.slice(0, 25).map(item => {
            const candidate = candidates.find(row => row.company_id === item.company_id)
            const profile = profileById.get(item.company_id)
            const publicFirm = firmById.get(item.company_id)
            const name = candidate?.canonical_name ?? profile?.canonical_name ?? publicFirm?.canonical_name ?? item.company_id
            const missing = item.missing_fields.filter(field=>field!=='contact')
            if (!contactsByCompany.get(item.company_id)) missing.push('contact')
            return <article key={item.company_id}>
              <div className="company-research-score"><strong>{item.priority_score}</strong><span>priority</span></div>
              <div className="company-research-body">
                <a href={`#/admin-company/${encodeURIComponent(item.company_id)}`}>{name}</a>
                <span>{item.priority_reason}</span>
                <small>{missing.length ? `Missing: ${missing.join(' · ')}` : 'Core enrichment complete'}</small>
              </div>
              <select aria-label={`Research status ${name}`} value={item.status} disabled={busy || !queue.length} onChange={event => void changeStatus(item, event.target.value as CompanyResearchStatus)}>
                {statuses.map(status => <option key={status} value={status}>{label(status)}</option>)}
              </select>
            </article>
          })}
        </div>
      </section>

      <section className="company-ops-card">
        <div className="company-ops-card-heading"><div><strong>Follow-up queue</strong><span>Next actions from private CRM state</span></div></div>
        <div className="company-followup-list">
          {[...overdue, ...upcoming].slice(0, 20).map(task => <article key={task.task_id}>
            <a href={`#/admin-company/${encodeURIComponent(task.company_id)}`}>{task.title}</a>
            <strong>{task.due_at?.slice(0,10)}</strong>
            <span>{overview?.accounts.find(a=>a.sales_account_id===task.sales_account_id)?.display_name??'Company follow-up'}</span>
          </article>)}
          {overdue.length + upcoming.length === 0 && <span className="company-admin-empty">No due follow-ups are recorded.</span>}
        </div>
      </section>
    </div>
  </section>
}
