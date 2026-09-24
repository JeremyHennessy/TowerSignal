import { useEffect, useMemo, useState } from 'react'
import {
  loadAllCompanyActivities,
  loadAllCompanyContacts,
  loadCompanyAdminAccess,
  loadCompanyAdminDirectory,
  loadCompanyResearchQueue,
} from '../companyAdmin/client'
import { loadKnownFirms } from '../data/api'
import type {
  CompanyAdminActivity,
  CompanyAdminContact,
  CompanyAdminProfile,
  CompanyResearchQueueItem,
} from '../types/companyAdmin'
import type { KnownFirmPayload, KnownFirmSummaryRecord } from '../types/firm'
import { CompanyAdminPanel } from './CompanyAdminPanel'
import { CompanyAuditHistory } from './CompanyAuditHistory'
import { CompanyFamilyPanel } from './CompanyFamilyPanel'
import { CompanySalesCrmPanel } from './CompanySalesCrmPanel'

const number = new Intl.NumberFormat('en-US')

function human(value: string): string {
  return value.replaceAll('_',' ').replaceAll('-',' ').replace(/(^|\s)\S/g, match => match.toUpperCase())
}

function revenueLabel(profile: CompanyAdminProfile): string {
  if (profile.revenue_type === 'range' && profile.revenue_low != null && profile.revenue_high != null) {
    return `${profile.revenue_currency} ${profile.revenue_low.toLocaleString()}–${profile.revenue_high.toLocaleString()}`
  }
  if (profile.revenue_amount != null) return `${profile.revenue_currency} ${profile.revenue_amount.toLocaleString()}`
  return 'Not recorded'
}

export function AdminCompanyProfilePage({ companyId }: { companyId: string }) {
  const [allowed,setAllowed]=useState<boolean|null>(null)
  const [profiles,setProfiles]=useState<CompanyAdminProfile[]>([])
  const [contacts,setContacts]=useState<CompanyAdminContact[]>([])
  const [activities,setActivities]=useState<CompanyAdminActivity[]>([])
  const [queue,setQueue]=useState<CompanyResearchQueueItem[]>([])
  const [known,setKnown]=useState<KnownFirmPayload|null>(null)
  const [error,setError]=useState<string|null>(null)

  useEffect(()=>{
    let cancelled=false
    loadCompanyAdminAccess().then(async isAdmin=>{
      if(cancelled) return
      setAllowed(isAdmin)
      if(!isAdmin) return
      const [nextProfiles,nextContacts,nextActivities,nextQueue,nextKnown]=await Promise.all([
        loadCompanyAdminDirectory(),
        loadAllCompanyContacts(),
        loadAllCompanyActivities(),
        loadCompanyResearchQueue(),
        loadKnownFirms(),
      ])
      if(cancelled) return
      setProfiles(nextProfiles)
      setContacts(nextContacts)
      setActivities(nextActivities)
      setQueue(nextQueue)
      setKnown(nextKnown)
    }).catch(err=>{
      if(!cancelled){setAllowed(false);setError(err instanceof Error?err.message:'Unable to load private company profile')}
    })
    return()=>{cancelled=true}
  },[companyId])

  const model=useMemo(()=>{
    if(!known) return null
    const profileById=new Map(profiles.map(profile=>[profile.company_id,profile]))
    const firmById=new Map(known.firms.map(firm=>[firm.firm_id,firm]))
    const selected=profileById.get(companyId)
    if(!selected) return null
    const masterId=selected.rollup_company_id||selected.company_id
    const master=profileById.get(masterId)||selected
    const members=profiles.filter(profile=>profile.company_id===masterId||profile.rollup_company_id===masterId)
      .sort((a,b)=>a.company_id===masterId?-1:b.company_id===masterId?1:a.canonical_name.localeCompare(b.canonical_name))
    const memberIds=new Set(members.map(member=>member.company_id))
    const publicRows=members.map(member=>firmById.get(member.company_id)).filter((firm):firm is KnownFirmSummaryRecord=>Boolean(firm))
    const familyContacts=contacts.filter(contact=>memberIds.has(contact.company_id)&&contact.active)
    const familyActivities=activities.filter(activity=>memberIds.has(activity.company_id))
    const research=queue.find(item=>item.company_id===masterId)||null
    return {
      profileById,firmById,selected,masterId,master,members,memberIds:[...memberIds],publicRows,familyContacts,familyActivities,research,
      publicObservations:publicRows.reduce((sum,firm)=>sum+firm.observation_count,0),
      servicedRelationships:publicRows.reduce((sum,firm)=>sum+firm.serviced_site_count,0),
      towerAccountLinks:publicRows.reduce((sum,firm)=>sum+firm.tower_account_count,0),
      publicContracts:publicRows.reduce((sum,firm)=>sum+firm.observed_contract_count,0),
    }
  },[known,profiles,contacts,activities,queue,companyId])

  if(allowed===null) return <section className="product-page admin-company-page"><div className="reference-empty-state"><strong>Loading private company profile…</strong></div></section>
  if(!allowed) return <section className="product-page admin-company-page"><div className="reference-empty-state"><strong>Administrator access required.</strong><span>{error||'This route contains private company and CRM data.'}</span></div></section>
  if(!known) return <section className="product-page admin-company-page"><div className="reference-empty-state"><strong>Loading company administration…</strong></div></section>
  if(!model) return <section className="product-page admin-company-page"><div className="reference-empty-state"><strong>Private company profile not found.</strong><a className="secondary-link-button" href="#/admin-companies">Return to company command center</a></div></section>

  const displayName=model.selected.rollup_name||model.selected.legal_name||model.selected.canonical_name
  const publicFirm=model.firmById.get(model.selected.company_id)

  return <section className="product-page admin-company-page admin-company-profile-page">
    <div className="product-page-heading compact-heading admin-company-heading">
      <div>
        <span className="page-kicker">Admin only · private company detail</span>
        <h1>{displayName}</h1>
        <p>{model.selected.company_id===model.masterId?'Master family record':'Reviewed source identity within '+(model.master.rollup_name||model.master.canonical_name)}</p>
      </div>
      <div className="page-actions">
        <a className="secondary-link-button" href="#/admin-companies">Company command center</a>
        {publicFirm&&<a className="secondary-link-button" href={`#/company/${encodeURIComponent(publicFirm.firm_id)}`}>Public Known Firm</a>}
      </div>
    </div>

    {error&&<div className="company-admin-error"><strong>Private company error.</strong><span>{error}</span></div>}

    <div className="admin-company-metrics admin-company-profile-metrics">
      <article><small>Source identities</small><strong>{number.format(model.members.length)}</strong><span>{number.format(model.publicRows.length)} represented in Known Firms</span></article>
      <article><small>Public observations</small><strong>{number.format(model.publicObservations)}</strong><span>Across retained source identities</span></article>
      <article><small>Serviced relationships</small><strong>{number.format(model.servicedRelationships)}</strong><span>Sum across public identities</span></article>
      <article><small>Tower account links</small><strong>{number.format(model.towerAccountLinks)}</strong><span>Public firm/account relationships</span></article>
      <article><small>Public contracts</small><strong>{number.format(model.publicContracts)}</strong><span>Observed procurement records</span></article>
      <article><small>Active contacts</small><strong>{number.format(model.familyContacts.length)}</strong><span>{number.format(model.familyActivities.length)} logged interactions</span></article>
      <article><small>CRM status</small><strong>{human(model.master.relationship_status)}</strong><span>{model.master.account_owner||'Owner unassigned'}</span></article>
      <article><small>Research</small><strong>{model.research?model.research.priority_score:'—'}</strong><span>{model.research?human(model.research.status):'Not in active queue'}</span></article>
    </div>

    <div className="admin-company-dashboard-grid admin-company-profile-summary">
      <section className="admin-company-card">
        <div className="admin-company-card-heading"><div><strong>Master company summary</strong><span>Private reviewed identity</span></div></div>
        <dl className="admin-company-definition-list">
          <div><dt>Master company</dt><dd>{model.master.legal_name||model.master.canonical_name}</dd></div>
          <div><dt>Rolled-up name</dt><dd>{model.master.rollup_name||model.master.canonical_name}</dd></div>
          <div><dt>Parent / owner</dt><dd>{model.master.parent_company_name||'Not recorded'}{model.master.parent_source_url&&<a href={model.master.parent_source_url} target="_blank" rel="noreferrer">Source ↗</a>}</dd></div>
          <div><dt>Website</dt><dd>{model.master.website?<a href={model.master.website} target="_blank" rel="noreferrer">{model.master.website}</a>:'Not recorded'}</dd></div>
          <div><dt>Headquarters</dt><dd>{[model.master.headquarters_address,model.master.headquarters_city,model.master.headquarters_region,model.master.headquarters_postal_code,model.master.headquarters_country].filter(Boolean).join(', ')||'Not recorded'}</dd></div>
          <div><dt>Company type</dt><dd>{model.master.company_type||'Not recorded'}</dd></div>
          <div><dt>Revenue</dt><dd>{revenueLabel(model.master)}{model.master.revenue_year? ` · ${model.master.revenue_year}`:''}</dd></div>
          <div><dt>Last enrichment check</dt><dd>{model.master.enrichment_checked_at?new Date(model.master.enrichment_checked_at).toLocaleString():'Not recorded'}</dd></div>
        </dl>
      </section>

      <section className="admin-company-card admin-family-member-card">
        <div className="admin-company-card-heading"><div><strong>Family identities</strong><span>Every reviewed source identity remains addressable</span></div></div>
        <div className="table-scroll"><table className="account-table admin-family-member-table"><thead><tr><th>Identity</th><th>Private role</th><th>Website / HQ</th><th>Public evidence</th><th>CRM</th><th></th></tr></thead><tbody>
          {model.members.map(member=>{
            const firm=model.firmById.get(member.company_id)
            return <tr key={member.company_id} className={member.company_id===companyId?'selected-row':''} onClick={()=>{window.location.hash=`#/admin-company/${encodeURIComponent(member.company_id)}`}}>
              <td><strong>{member.canonical_name}</strong><small>{member.legal_name||member.company_id}</small></td>
              <td><strong>{member.company_id===model.masterId?'Master':'Rolled-up identity'}</strong><small>{member.rollup_source_name||'Private reviewed family'}</small></td>
              <td><strong>{member.website?member.website.replace(/^https?:\/\//,'').replace(/\/$/,''):'Website not recorded'}</strong><small>{[member.headquarters_city,member.headquarters_region].filter(Boolean).join(', ')||'HQ not recorded'}</small></td>
              <td><strong>{firm?number.format(firm.observation_count):'—'} observations</strong><small>{firm?`${number.format(firm.serviced_site_count)} serviced · ${number.format(firm.tower_account_count)} tower links`:'Private-only identity'}</small></td>
              <td><strong>{human(member.relationship_status)}</strong><small>{member.next_action_date?`Next ${member.next_action_date}`:'No next action'}</small></td>
              <td className="row-arrow">›</td>
            </tr>
          })}
        </tbody></table></div>
      </section>
    </div>

    <CompanySalesCrmPanel companyId={model.masterId} companyIds={model.memberIds} companyName={model.master.rollup_name || model.master.legal_name || model.master.canonical_name} />
    <CompanyAdminPanel companyId={model.selected.company_id} canonicalName={model.selected.canonical_name} />
    <CompanyFamilyPanel companyId={model.selected.company_id} />
    <CompanyAuditHistory companyId={model.selected.company_id} />
  </section>
}
