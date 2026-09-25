import { useEffect, useMemo, useState } from 'react'
import {
  loadAllCompanyActivities,
  loadAllCompanyContacts,
  loadCompanyAdminAccess,
  loadCompanyAdminDirectory,
  loadCompanyResearchQueue,
  loadCompanySalesAccounts,
  loadCompanySalesAccountMembers,
} from '../companyAdmin/client'
import { loadKnownFirms } from '../data/api'
import type {
  CompanyAdminActivity,
  CompanyAdminContact,
  CompanyAdminProfile,
  CompanyResearchQueueItem,
  CompanySalesAccount,
  CompanySalesAccountMember,
} from '../types/companyAdmin'
import type { KnownFirmPayload, KnownFirmSummaryRecord } from '../types/firm'
import { CompanyAdminPanel } from './CompanyAdminPanel'
import { CompanyAuditHistory } from './CompanyAuditHistory'
import { CompanySalesCrmPanel } from './CompanySalesCrmPanel'
import { CompanySalesAccountPanel } from './CompanySalesAccountPanel'
import { CompanyDemoProposalPanel } from './CompanyDemoProposalPanel'
import { CompanyCustomerLifecyclePanel } from './CompanyCustomerLifecyclePanel'

const number = new Intl.NumberFormat('en-US')
type AdminCompanySection = 'overview' | 'sales' | 'commercial' | 'customer' | 'research' | 'audit'

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
  const [salesAccounts,setSalesAccounts]=useState<CompanySalesAccount[]>([])
  const [salesAccountMembers,setSalesAccountMembers]=useState<CompanySalesAccountMember[]>([])
  const [selectedSourceCompanyId,setSelectedSourceCompanyId]=useState<string|null>(null)
  const [known,setKnown]=useState<KnownFirmPayload|null>(null)
  const [error,setError]=useState<string|null>(null)
  const [section,setSection]=useState<AdminCompanySection>('overview')

  useEffect(()=>{
    let cancelled=false
    loadCompanyAdminAccess().then(async isAdmin=>{
      if(cancelled) return
      setAllowed(isAdmin)
      if(!isAdmin) return
      const [nextProfiles,nextContacts,nextActivities,nextQueue,nextKnown,nextSalesAccounts,nextSalesAccountMembers]=await Promise.all([
        loadCompanyAdminDirectory(),
        loadAllCompanyContacts(),
        loadAllCompanyActivities(),
        loadCompanyResearchQueue(),
        loadKnownFirms(),
        loadCompanySalesAccounts(),
        loadCompanySalesAccountMembers(),
      ])
      if(cancelled) return
      setProfiles(nextProfiles)
      setContacts(nextContacts)
      setActivities(nextActivities)
      setQueue(nextQueue)
      setKnown(nextKnown)
      setSalesAccounts(nextSalesAccounts)
      setSalesAccountMembers(nextSalesAccountMembers)
    }).catch(err=>{
      if(!cancelled){setAllowed(false);setError(err instanceof Error?err.message:'Unable to load private company profile')}
    })
    return()=>{cancelled=true}
  },[companyId])

  const model=useMemo(()=>{
    if(!known) return null
    const profileById=new Map(profiles.map(profile=>[profile.company_id,profile]))
    const firmById=new Map(known.firms.map(firm=>[firm.firm_id,firm]))
    const memberByCompany=new Map(salesAccountMembers.map(member=>[member.company_id,member]))
    const account=salesAccounts.find(row=>row.sales_account_id===companyId)
      ?? salesAccounts.find(row=>row.primary_company_id===companyId)
      ?? salesAccounts.find(row=>row.sales_account_id===memberByCompany.get(companyId)?.sales_account_id)
    if(!account) return null
    const memberLinks=salesAccountMembers.filter(member=>member.sales_account_id===account.sales_account_id)
    const members=memberLinks.map(member=>profileById.get(member.company_id)).filter((profile):profile is CompanyAdminProfile=>Boolean(profile))
      .sort((a,b)=>a.company_id===account.primary_company_id?-1:b.company_id===account.primary_company_id?1:a.canonical_name.localeCompare(b.canonical_name))
    const master=profileById.get(account.primary_company_id) ?? members[0]
    if(!master) return null
    const memberIds=new Set(memberLinks.map(member=>member.company_id))
    const selectedId=selectedSourceCompanyId && memberIds.has(selectedSourceCompanyId) ? selectedSourceCompanyId : account.primary_company_id
    const selected=profileById.get(selectedId) ?? master
    const publicRows=members.map(member=>firmById.get(member.company_id)).filter((firm):firm is KnownFirmSummaryRecord=>Boolean(firm))
    const familyContacts=contacts.filter(contact=>(contact.sales_account_id===account.sales_account_id || (!contact.sales_account_id&&memberIds.has(contact.company_id)))&&contact.active)
    const familyActivities=activities.filter(activity=>activity.sales_account_id===account.sales_account_id || (!activity.sales_account_id&&memberIds.has(activity.company_id)))
    const research=queue.find(item=>item.sales_account_id===account.sales_account_id) ?? queue.find(item=>item.company_id===account.primary_company_id) ?? null
    return {
      account,profileById,firmById,selected,masterId:account.primary_company_id,master,members,memberLinks,memberIds:[...memberIds],publicRows,familyContacts,familyActivities,research,
      publicObservations:publicRows.reduce((sum,firm)=>sum+firm.observation_count,0),
      servicedRelationships:publicRows.reduce((sum,firm)=>sum+firm.serviced_site_count,0),
      towerAccountLinks:publicRows.reduce((sum,firm)=>sum+firm.tower_account_count,0),
      publicContracts:publicRows.reduce((sum,firm)=>sum+firm.observed_contract_count,0),
    }
  },[known,profiles,contacts,activities,queue,salesAccounts,salesAccountMembers,companyId,selectedSourceCompanyId])

  if(allowed===null) return <section className="product-page admin-company-page"><div className="reference-empty-state"><strong>Loading private company profile…</strong></div></section>
  if(!allowed) return <section className="product-page admin-company-page"><div className="reference-empty-state"><strong>Administrator access required.</strong><span>{error||'This route contains private company and CRM data.'}</span></div></section>
  if(!known) return <section className="product-page admin-company-page"><div className="reference-empty-state"><strong>Loading company administration…</strong></div></section>
  if(!model) return <section className="product-page admin-company-page"><div className="reference-empty-state"><strong>Private company profile not found.</strong><a className="secondary-link-button" href="#/admin-companies">Return to company command center</a></div></section>

  const displayName=model.account.display_name
  const publicFirm=model.firmById.get(model.selected.company_id)

  return <section className="product-page admin-company-page admin-company-profile-page">
    <div className="product-page-heading compact-heading admin-company-heading">
      <div>
        <span className="page-kicker">Admin only · private company detail</span>
        <h1>{displayName}</h1>
        <p>{human(model.account.account_classification)} · {model.members.length} retained source identities · editing {model.selected.canonical_name}</p>
      </div>
      <div className="page-actions">
        <a className="secondary-link-button" href="#/admin-companies">Company command center</a>
        {publicFirm&&<a className="secondary-link-button" href={`#/company/${encodeURIComponent(publicFirm.firm_id)}`}>Public Known Firm</a>}
      </div>
    </div>

    {error&&<div className="company-admin-error"><strong>Private company error.</strong><span>{error}</span></div>}

    <div className="admin-profile-command-strip">
      <article><small>Account</small><strong>{human(model.account.account_classification)}</strong><span>{model.account.account_owner||'Owner unassigned'}</span></article>
      <article><small>Contacts</small><strong>{number.format(model.familyContacts.length)}</strong><span>{number.format(model.familyActivities.length)} interactions</span></article>
      <article><small>Public evidence</small><strong>{number.format(model.publicObservations)}</strong><span>{number.format(model.servicedRelationships)} serviced relationships</span></article>
      <article><small>Research</small><strong>{model.research?model.research.priority_score:'—'}</strong><span>{model.research?human(model.research.status):'Not queued'}</span></article>
    </div>

    <nav className="admin-profile-nav" aria-label="Company admin sections">
      <button type="button" className={section==='overview'?'active':''} onClick={()=>setSection('overview')}>Overview</button>
      <button type="button" className={section==='sales'?'active':''} onClick={()=>setSection('sales')}>Sales</button>
      <button type="button" className={section==='commercial'?'active':''} onClick={()=>setSection('commercial')}>Demos &amp; proposals</button>
      <button type="button" className={section==='customer'?'active':''} onClick={()=>setSection('customer')}>Customer</button>
      <button type="button" className={section==='research'?'active':''} onClick={()=>setSection('research')}>Research</button>
      <button type="button" className={section==='audit'?'active':''} onClick={()=>setSection('audit')}>Audit</button>
    </nav>

    {section==='overview'&&<div className="admin-profile-section">
      <div className="admin-company-dashboard-grid admin-company-profile-summary">
        <section className="admin-company-card">
          <div className="admin-company-card-heading"><div><strong>Account summary</strong><span>Reviewed master identity</span></div></div>
          <dl className="admin-company-definition-list">
            <div><dt>Sales account</dt><dd>{model.account.display_name}</dd></div>
            <div><dt>Primary identity</dt><dd>{model.master.legal_name||model.master.canonical_name}</dd></div>
            <div><dt>Parent / owner</dt><dd>{model.account.parent_name||model.master.parent_company_name||'Not recorded'}{(model.account.parent_source_url||model.master.parent_source_url)&&<a href={model.account.parent_source_url||model.master.parent_source_url||'#'} target="_blank" rel="noreferrer">Source ↗</a>}</dd></div>
            <div><dt>Website</dt><dd>{model.master.website?<a href={model.master.website} target="_blank" rel="noreferrer">{model.master.website}</a>:'Not recorded'}</dd></div>
            <div><dt>Headquarters</dt><dd>{[model.master.headquarters_address,model.master.headquarters_city,model.master.headquarters_region,model.master.headquarters_postal_code,model.master.headquarters_country].filter(Boolean).join(', ')||'Not recorded'}</dd></div>
            <div><dt>Company type</dt><dd>{model.master.company_type||'Not recorded'}</dd></div>
            <div><dt>Revenue</dt><dd>{revenueLabel(model.master)}{model.master.revenue_year?` · ${model.master.revenue_year}`:''}</dd></div>
            <div><dt>Last enrichment check</dt><dd>{model.master.enrichment_checked_at?new Date(model.master.enrichment_checked_at).toLocaleString():'Not recorded'}</dd></div>
          </dl>
        </section>

        <section className="admin-company-card admin-family-member-card">
          <div className="admin-company-card-heading"><div><strong>Source identities</strong><span>{model.members.length} retained identities · select one for research editing</span></div></div>
          <div className="table-scroll"><table className="account-table admin-family-member-table"><thead><tr><th>Identity</th><th>Role</th><th>Location</th><th>Evidence</th><th></th></tr></thead><tbody>
            {model.members.map(member=>{
              const firm=model.firmById.get(member.company_id)
              return <tr
                key={member.company_id}
                className={member.company_id===model.selected.company_id?'selected-row':''}
                onClick={()=>{setSelectedSourceCompanyId(member.company_id);setSection('research')}}
                tabIndex={0}
                onKeyDown={event=>{if(event.key==='Enter'){setSelectedSourceCompanyId(member.company_id);setSection('research')}}}
              >
                <td><strong>{member.canonical_name}</strong><small>{member.legal_name||member.company_id}</small></td>
                <td><strong>{member.company_id===model.masterId?'Master':'Rolled-up identity'}</strong><small>{member.rollup_source_name||'Reviewed family member'}</small></td>
                <td><strong>{[member.headquarters_city,member.headquarters_region].filter(Boolean).join(', ')||'Not recorded'}</strong><small>{member.website?member.website.replace(/^https?:\/\//,'').replace(/\/$/,''):'Website not recorded'}</small></td>
                <td><strong>{firm?number.format(firm.observation_count):'—'} observations</strong><small>{firm?`${number.format(firm.serviced_site_count)} serviced · ${number.format(firm.tower_account_count)} tower links`:'Private-only identity'}</small></td>
                <td className="row-arrow">›</td>
              </tr>
            })}
          </tbody></table></div>
        </section>
      </div>
    </div>}

    {section==='sales'&&<div className="admin-profile-section">
      <CompanySalesAccountPanel salesAccountId={model.account.sales_account_id} />
      <CompanySalesCrmPanel salesAccountId={model.account.sales_account_id} companyId={model.masterId} companyIds={model.memberIds} companyName={model.account.display_name} />
    </div>}

    {section==='commercial'&&<div className="admin-profile-section">
      <CompanyDemoProposalPanel salesAccountId={model.account.sales_account_id} companyId={model.masterId} contacts={model.familyContacts} />
    </div>}

    {section==='customer'&&<div className="admin-profile-section">
      <CompanyCustomerLifecyclePanel salesAccountId={model.account.sales_account_id} companyId={model.masterId} contacts={model.familyContacts} />
    </div>}

    {section==='research'&&<div className="admin-profile-section">
      <div className="admin-profile-context"><strong>Editing source identity:</strong><span>{model.selected.canonical_name}</span>{publicFirm&&<a href={`#/company/${encodeURIComponent(publicFirm.firm_id)}`}>Open public Known Firm ↗</a>}</div>
      <CompanyAdminPanel companyId={model.selected.company_id} canonicalName={model.selected.canonical_name} />
    </div>}

    {section==='audit'&&<div className="admin-profile-section">
      <div className="admin-profile-context"><strong>Audit source identity:</strong><span>{model.selected.canonical_name}</span></div>
      <CompanyAuditHistory companyId={model.selected.company_id} />
    </div>}
  </section>
}
