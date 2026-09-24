import { useEffect, useMemo, useState } from 'react'
import { loadCompanyAdminAccess, loadCompanyAdminDirectory } from '../companyAdmin/client'
import { loadKnownFirmDetail, loadKnownFirms } from '../data/api'
import type { CompanyAdminProfile } from '../types/companyAdmin'
import type { KnownFirmDetailPayload, KnownFirmSummaryRecord } from '../types/firm'

const number = new Intl.NumberFormat('en-US')

export function CompanyFamilyPanel({ companyId }: { companyId: string }) {
  const [profiles, setProfiles] = useState<CompanyAdminProfile[]>([])
  const [firms, setFirms] = useState<KnownFirmSummaryRecord[]>([])
  const [details, setDetails] = useState<KnownFirmDetailPayload[]>([])
  const [allowed, setAllowed] = useState(false)

  useEffect(() => {
    let cancelled = false
    loadCompanyAdminAccess().then(async isAdmin => {
      if (!isAdmin || cancelled) return
      const [nextProfiles, known] = await Promise.all([loadCompanyAdminDirectory(), loadKnownFirms()])
      if (cancelled) return
      setAllowed(true)
      setProfiles(nextProfiles)
      setFirms(known.firms)
      const profileById = new Map(nextProfiles.map(profile => [profile.company_id, profile]))
      const masterId = profileById.get(companyId)?.rollup_company_id || companyId
      const familyIds = nextProfiles.filter(profile => profile.company_id === masterId || profile.rollup_company_id === masterId).map(profile => profile.company_id)
      const publicIds = new Set(known.firms.map(firm => firm.firm_id))
      const results = await Promise.allSettled(familyIds.filter(id => publicIds.has(id)).map(id => loadKnownFirmDetail(id)))
      if (!cancelled) setDetails(results.flatMap(result => result.status === 'fulfilled' ? [result.value] : []))
    }).catch(() => { if (!cancelled) setAllowed(false) })
    return () => { cancelled = true }
  }, [companyId])

  const model = useMemo(() => {
    if (!allowed) return null
    const profileById = new Map(profiles.map(profile => [profile.company_id, profile]))
    const firmById = new Map(firms.map(firm => [firm.firm_id, firm]))
    const current = profileById.get(companyId)
    const masterId = current?.rollup_company_id || companyId
    const master = profileById.get(masterId)
    const members = profiles.filter(profile => profile.company_id === masterId || profile.rollup_company_id === masterId)
      .sort((a,b) => (a.company_id === masterId ? -1 : b.company_id === masterId ? 1 : a.canonical_name.localeCompare(b.canonical_name)))
    if (members.length <= 1 && !master?.parent_company_id && !master?.parent_company_name) return null

    const sites = new Set<string>()
    const serviced = new Set<string>()
    const systems = new Set<string>()
    const procurement = new Set<string>()
    details.forEach(detail => {
      detail.site_relationships.forEach(site => {
        sites.add(site.site_id)
        if (site.serviced) serviced.add(site.site_id)
        site.system_ids.forEach(id => systems.add(id))
      })
      detail.procurement?.procurement_ids?.forEach(id => procurement.add(id))
    })
    return { masterId, master, members, firmById, sites, serviced, systems, procurement }
  }, [allowed, profiles, firms, details, companyId])

  if (!model) return null
  return <section className="company-family-panel" aria-label="Private corporate family">
    <div className="company-ops-card-heading">
      <div><span className="page-kicker">Admin only · reviewed corporate family</span><strong>{model.master?.rollup_name || model.master?.legal_name || model.master?.canonical_name || model.masterId}</strong></div>
      <span>{model.members.length} reviewed source identities</span>
    </div>
    <p>Private analytical rollup only. Every public source identity remains independently retained below.</p>
    <div className="company-family-metrics">
      <article><small>Unique related sites</small><strong>{number.format(model.sites.size)}</strong></article>
      <article><small>Unique serviced sites</small><strong>{number.format(model.serviced.size)}</strong></article>
      <article><small>Tower accounts</small><strong>{number.format(model.systems.size)}</strong></article>
      <article><small>Procurement records</small><strong>{number.format(model.procurement.size)}</strong></article>
    </div>
    <div className="company-family-members">
      {model.members.map(profile => {
        const firm = model.firmById.get(profile.company_id)
        return <a key={profile.company_id} href={`#/admin-company/${encodeURIComponent(profile.company_id)}`}>
          <strong>{profile.canonical_name}</strong>
          <span>{profile.company_id === model.masterId ? 'Master company' : 'Reviewed source-label rollup'}</span>
          <small>{firm ? `${firm.serviced_site_count.toLocaleString()} serviced · ${firm.tower_account_count.toLocaleString()} tower accounts` : 'Private-only company identity'}</small>
        </a>
      })}
    </div>
    {(model.master?.parent_company_id || model.master?.parent_company_name) && <div className="company-family-parent">
      <small>Parent / ownership</small>
      {model.master.parent_company_id
        ? <a href={`#/admin-company/${encodeURIComponent(model.master.parent_company_id)}`}>{model.master.parent_company_name || model.master.parent_company_id}</a>
        : <strong>{model.master.parent_company_name}</strong>}
      {model.master.parent_source_url && <a href={model.master.parent_source_url} target="_blank" rel="noreferrer">Ownership source ↗</a>}
    </div>}
  </section>
}
