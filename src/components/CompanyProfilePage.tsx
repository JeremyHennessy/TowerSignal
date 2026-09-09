import { useEffect, useMemo, useState } from 'react'
import { loadKnownFirmDetail, loadProcurement } from '../data/api'
import type { KnownFirmDetailPayload, KnownFirmRole, KnownFirmSiteRelationship } from '../types/firm'
import type { ProcurementBundle, ProcurementRecord } from '../types/procurement'
import { formatDate } from '../domain/labels'
import { ShareButton } from './ShareButton'
import { FirmSiteMap } from './FirmSiteMap'

const number = new Intl.NumberFormat('en-US')
const currency = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
const PROFILE_RECORD_LIMIT = 200
const SITE_RECORD_LIMIT = 250

function label(value: string): string {
  return value.replaceAll('_', ' ').toLowerCase().replace(/(^|\s)\S/g, match => match.toUpperCase())
}

function roleLabel(value: KnownFirmRole): string {
  const overrides: Record<string, string> = {
    DWT_INSPECTION_PROVIDER: 'DWT service provider',
    DWT_LABORATORY: 'DWT laboratory',
    PROCUREMENT_VENDOR: 'Procurement vendor',
    DEC_7G_REGISTERED_BUSINESS: 'DEC 7G business',
    DOB_NOW_APPLICANT_BUSINESS: 'DOB applicant business',
    DOB_NOW_OWNER_BUSINESS: 'DOB owner business',
    LEGACY_DOB_OWNER_BUSINESS: 'Legacy DOB owner business',
  }
  return overrides[value] ?? label(value)
}

function recordDate(row: ProcurementRecord): string | null {
  return row.due_date ?? row.award_date ?? row.start_date ?? row.notice_start_date ?? row.retrieved_at ?? null
}

function recordAmount(row: ProcurementRecord): number | null {
  return row.current_amount ?? row.amount ?? row.spend_to_date ?? row.original_amount ?? null
}

function sourceLabel(row: ProcurementRecord): string {
  if (row.source === 'NYC_CITY_RECORD') return row.scope === 'OPEN_SOLICITATIONS' ? 'City Record · Solicitation' : 'City Record · Award'
  if (row.source === 'NYC_CHECKBOOK_NYCHA') return 'Checkbook · NYCHA'
  if (row.source === 'NYS_OPEN_BOOK') return 'Open Book NY'
  if (row.source === 'NYC_CHECKBOOK_EDC') return 'Checkbook · NYCEDC'
  if (row.source.startsWith('NYS_ABO_')) return 'NYS Authority Report'
  return row.vendor_role === 'SUBCONTRACTOR' ? 'Checkbook · Subcontract' : 'Checkbook · Contract'
}

function siteRelationshipLabel(site: KnownFirmSiteRelationship): string {
  if (site.serviced) return 'Observed service'
  if (site.contracted) return 'Confirmed contract link'
  if (site.project_role) return 'Project role'
  return 'Related evidence'
}

export function CompanyProfilePage({
  companyId,
  onBack,
  onOpenCompany,
}: {
  companyId: string
  onBack: () => void
  onOpenCompany: (firmId: string) => void
}) {
  const [detail, setDetail] = useState<KnownFirmDetailPayload | null>(null)
  const [procurement, setProcurement] = useState<ProcurementBundle | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [procurementError, setProcurementError] = useState<string | null>(null)
  const [siteFilter, setSiteFilter] = useState('ALL')
  const [selectedSiteId, setSelectedSiteId] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setDetail(null)
    setError(null)
    setProcurement(null)
    setProcurementError(null)
    setSelectedSiteId(null)
    setSiteFilter('ALL')
    loadKnownFirmDetail(companyId)
      .then(value => {
        if (cancelled) return
        setDetail(value)
        if (value.procurement?.procurement_ids?.length) {
          loadProcurement()
            .then(bundle => { if (!cancelled) setProcurement(bundle) })
            .catch(err => { if (!cancelled) setProcurementError(err instanceof Error ? err.message : 'Procurement evidence is unavailable') })
        }
      })
      .catch(err => { if (!cancelled) setError(err instanceof Error ? err.message : 'Unable to load known-firm profile') })
    return () => { cancelled = true }
  }, [companyId])

  const sites = useMemo(() => detail ? detail.site_relationships.filter(site => {
    if (siteFilter === 'SERVICED') return site.serviced
    if (siteFilter === 'CONTRACTED') return site.contracted
    if (siteFilter === 'PROJECT') return site.project_role
    if (siteFilter === 'MAPPED') return site.mapped
    return true
  }) : [], [detail, siteFilter])
  const visibleSites = useMemo(() => sites.slice(0, SITE_RECORD_LIMIT), [sites])
  const selectedSite = useMemo(() => {
    if (!selectedSiteId) return null
    return detail?.site_relationships.find(site => site.site_id === selectedSiteId) ?? null
  }, [detail, selectedSiteId])

  const records = useMemo(() => {
    if (!detail?.procurement?.procurement_ids?.length || !procurement) return []
    const ids = new Set(detail.procurement.procurement_ids)
    return [
      ...procurement.cityRecord.notices,
      ...procurement.checkbook.contracts,
      ...(procurement.nysAuthorities?.contracts ?? []),
      ...(procurement.openBookWater?.contracts ?? []),
      ...(procurement.nychaWater?.records ?? []),
    ]
      .filter(row => ids.has(row.procurement_id))
      .sort((a, b) => (recordDate(b) ?? '').localeCompare(recordDate(a) ?? ''))
  }, [detail, procurement])
  const visibleRecords = useMemo(() => records.slice(0, PROFILE_RECORD_LIMIT), [records])

  if (error) return <section className="product-page company-profile-page"><div className="account-profile-toolbar"><button className="breadcrumb-back" onClick={onBack}>← Back to Known firms</button></div><div className="reference-empty-state"><strong>Known-firm profile evidence is unavailable.</strong><span>{error}</span></div></section>
  if (!detail) return <section className="product-page company-profile-page"><div className="account-profile-toolbar"><button className="breadcrumb-back" onClick={onBack}>← Back to Known firms</button></div><div className="reference-empty-state"><strong>Loading source-backed firm profile…</strong></div></section>

  const firm = detail.firm

  return <section className="product-page company-profile-page known-firm-profile-page">
    <div className="account-profile-toolbar"><div><button className="breadcrumb-back" onClick={onBack}>← Back to Known firms</button><span>Normalized firm · role and site evidence</span></div><div className="page-actions"><ShareButton label="Copy firm link" /></div></div>
    <div className="product-page-heading company-profile-heading">
      <div><span className="page-kicker">{roleLabel(firm.primary_role)} · {firm.source_classes.length} source classes</span><h1>{firm.canonical_name}</h1><p>Source-observed firm identity with service, contract, qualification and project-role evidence kept distinct. A related property is not represented as a serviced property unless the source explicitly names this firm or laboratory on a DWT inspection.</p><div className="firm-role-chip-row">{firm.roles.map(role => <span key={role}>{roleLabel(role)}</span>)}</div></div>
      <div className="company-identity-card"><span className={`health-badge health-${firm.identity_confidence === 'VERIFY' || firm.identity_confidence === 'UNRESOLVED' ? 'warning' : 'healthy'}`}>{firm.identity_confidence}</span><small>Identity resolution</small><strong>{label(firm.resolution_method)}</strong><span>{firm.procurement_company_id ? 'Reuses procurement company ID' : 'Normalized observed label'}</span></div>
    </div>

    <div className="reference-metric-grid known-firm-profile-metrics">
      <article><span className="reference-metric-icon urgent">⌂</span><div><small>Serviced sites</small><strong>{number.format(firm.serviced_site_count)}</strong><span>Explicit DWT provider/lab observations</span></div></article>
      <article><span className="reference-metric-icon">⌁</span><div><small>Related sites</small><strong>{number.format(firm.observed_site_count)}</strong><span>{number.format(firm.contracted_site_count)} confirmed contract · {number.format(firm.project_site_count)} project-role</span></div></article>
      <article><span className="reference-metric-icon success">◎</span><div><small>Tower accounts</small><strong>{number.format(firm.tower_account_count)}</strong><span>{number.format(firm.mapped_site_count)} mapped site relationships</span></div></article>
      <article><span className="reference-metric-icon warning">◷</span><div><small>Last observed</small><strong>{firm.latest_observed_date ? formatDate(firm.latest_observed_date) : '—'}</strong><span>{firm.active_last_12m ? 'Public-record observation within 12 months' : 'No observation within 12 months'}</span></div></article>
      <article><span className="reference-metric-icon">▤</span><div><small>Observed contracts</small><strong>{number.format(firm.observed_contract_count)}</strong><span>{number.format(firm.active_contract_count)} active · {number.format(firm.observed_customer_count)} buyers</span></div></article>
      <article><span className="reference-metric-icon">7G</span><div><small>Active qualifications</small><strong>{number.format(firm.active_qualification_count)}</strong><span>{number.format(firm.qualification_count)} observed DEC 7G registrations</span></div></article>
    </div>

    <div className="company-profile-grid known-firm-evidence-grid">
      <section className="reference-table-card company-evidence-card"><div className="reference-table-heading"><div><strong>Identity &amp; role evidence</strong><span>{number.format(firm.observation_count)} source observations</span></div></div><dl className="detail-grid"><div><dt>Canonical label</dt><dd>{firm.canonical_name}</dd></div><div><dt>Strict normalized label</dt><dd>{firm.strict_name || '—'}</dd></div><div><dt>Base normalized label</dt><dd>{firm.normalized_name || '—'}</dd></div><div><dt>First observed</dt><dd>{firm.first_observed_date ? formatDate(firm.first_observed_date) : '—'}</dd></div><div><dt>Last observed</dt><dd>{firm.latest_observed_date ? formatDate(firm.latest_observed_date) : '—'}</dd></div><div><dt>Sources</dt><dd>{firm.source_classes.map(label).join(' · ') || '—'}</dd></div></dl><div className="evidence-list"><strong>Observed roles</strong>{firm.roles.map(role => <div key={role}><span>{roleLabel(role)}</span><small>{number.format(firm.role_counts[role] ?? 0)} observations</small></div>)}</div></section>
      <section className="reference-table-card company-evidence-card"><div className="reference-table-heading"><div><strong>Commercial footprint</strong><span>Public records only</span></div></div><dl className="detail-grid"><div><dt>Observed contract value</dt><dd>{firm.observed_contract_value ? currency.format(firm.observed_contract_value) : '—'}</dd></div><div><dt>Observed buyers</dt><dd>{number.format(firm.observed_customer_count)}</dd></div><div><dt>Repeat buyers</dt><dd>{number.format(firm.repeat_buyer_count)}</dd></div><div><dt>Confirmed contract sites</dt><dd>{number.format(firm.contracted_site_count)}</dd></div></dl>{firm.service_categories.length > 0 && <div className="evidence-list"><strong>Procurement service categories</strong>{firm.service_categories.map(value => <div key={value}><span>{label(value)}</span></div>)}</div>}{detail.procurement?.observed_buyers?.length ? <div className="evidence-list"><strong>Public buyers</strong>{detail.procurement.observed_buyers.slice(0, 20).map(value => <div key={value}><span>{value}</span></div>)}</div> : null}</section>
    </div>

    <div className="reference-table-card known-firm-site-card">
      <div className="reference-table-heading"><div><strong>Firm sites &amp; roles</strong><span>{number.format(sites.length)} filtered relationships · {number.format(firm.serviced_site_count)} source-observed service sites</span></div><div className="page-actions firm-site-filter-actions"><select aria-label="Firm site relationship filter" value={siteFilter} onChange={event => setSiteFilter(event.target.value)}><option value="ALL">All related sites</option><option value="SERVICED">Observed service only</option><option value="CONTRACTED">Confirmed contract sites</option><option value="PROJECT">Project-role sites</option><option value="MAPPED">Mapped sites</option></select></div></div>
      {sites.some(site => site.mapped) ? <div className="firm-site-map-grid"><FirmSiteMap sites={sites} selectedSiteId={selectedSiteId} onSelect={site => setSelectedSiteId(site.site_id)} />{selectedSite ? <aside className="firm-selected-site"><small>Selected site</small><strong>{selectedSite.address ?? selectedSite.site_id}</strong><span>{[selectedSite.borough, selectedSite.zip].filter(Boolean).join(' · ') || selectedSite.site_id}</span><dl><div><dt>Relationship</dt><dd>{siteRelationshipLabel(selectedSite)}</dd></div><div><dt>Roles</dt><dd>{selectedSite.roles.map(roleLabel).join(' · ')}</dd></div><div><dt>Observations</dt><dd>{number.format(selectedSite.observation_count)}</dd></div><div><dt>Last observed</dt><dd>{selectedSite.last_observed_date ? formatDate(selectedSite.last_observed_date) : '—'}</dd></div><div><dt>Tower accounts</dt><dd>{number.format(selectedSite.tower_account_count)}</dd></div></dl>{selectedSite.system_ids.length > 0 && <div className="firm-site-account-links">{selectedSite.system_ids.slice(0, 8).map(systemId => <a key={systemId} href={`#/account/${encodeURIComponent(systemId)}`}>Open account {systemId} →</a>)}</div>}</aside> : <aside className="firm-selected-site empty"><strong>Select a map point</strong><span>Inspect the source-backed role and open linked TowerSignal accounts.</span></aside>}</div> : <div className="reference-empty-state compact"><strong>No mapped site relationships for this firm.</strong><span>Unmapped source relationships remain available in the table below.</span></div>}
      <div className="reference-table-scroll"><table className="reference-table firm-sites-table"><thead><tr><th>Site</th><th>Relationship</th><th>Roles</th><th>Observations</th><th>Last observed</th><th>Tower accounts</th><th>Evidence</th></tr></thead><tbody>{visibleSites.map(site => <tr key={site.site_id} className={selectedSiteId === site.site_id ? 'selected-row' : ''} onClick={() => setSelectedSiteId(site.site_id)}><td><strong>{site.address ?? site.site_id}</strong><small>{[site.borough, site.zip, site.bin ? `BIN ${site.bin}` : null, site.bbl ? `BBL ${site.bbl}` : null].filter(Boolean).join(' · ')}</small></td><td><span className={`firm-relationship-badge ${site.serviced ? 'serviced' : site.contracted ? 'contracted' : 'related'}`}>{siteRelationshipLabel(site)}</span><small>{site.relationship_classes.map(label).join(' · ')}</small></td><td>{site.roles.map(roleLabel).slice(0, 3).join(' · ')}</td><td>{number.format(site.observation_count)}<small>{site.first_observed_date ? `since ${formatDate(site.first_observed_date)}` : ''}</small></td><td>{site.last_observed_date ? formatDate(site.last_observed_date) : '—'}</td><td>{number.format(site.tower_account_count)}<small>{site.system_ids.length > 0 ? site.system_ids.slice(0, 2).join(' · ') : 'No exact account link'}</small></td><td>{site.evidence_classes.slice(0, 2).map(label).join(' · ')}<small>{site.source_record_ids.length ? `${site.source_record_ids.length} retained source IDs` : ''}</small></td></tr>)}</tbody></table></div>
      {sites.length > SITE_RECORD_LIMIT && <div className="source-health-footnote">Showing the first {number.format(SITE_RECORD_LIMIT)} of {number.format(sites.length)} relationships in the table. The map includes all mapped filtered relationships.</div>}
    </div>

    {detail.qualifications.length > 0 && <div className="reference-table-card"><div className="reference-table-heading"><div><strong>DEC 7G qualifications</strong><span>Qualification evidence only · not property-service evidence</span></div></div><div className="reference-table-scroll"><table className="reference-table"><thead><tr><th>Registration</th><th>Location</th><th>Effective</th><th>Expiration</th><th>Status</th><th>Scope</th></tr></thead><tbody>{detail.qualifications.map(item => <tr key={item.qualification_id ?? item.registration_number ?? `${item.city}-${item.registration_expiration_date}`}><td><strong>{item.registration_number ?? '—'}</strong></td><td>{[item.city, item.state].filter(Boolean).join(', ') || '—'}</td><td>{item.registration_effective_date ? formatDate(item.registration_effective_date) : '—'}</td><td>{item.registration_expiration_date ? formatDate(item.registration_expiration_date) : '—'}</td><td><span className={`health-badge health-${item.active_as_of_generation ? 'healthy' : 'warning'}`}>{item.active_as_of_generation ? 'ACTIVE AT GENERATION' : 'NOT CURRENT'}</span></td><td>{item.qualification_scope ?? 'Category 7G'}</td></tr>)}</tbody></table></div></div>}

    <div className="reference-table-card"><div className="reference-table-heading"><div><strong>Observed names &amp; aliases</strong><span>Source labels retained with role and count</span></div></div><div className="reference-table-scroll"><table className="reference-table"><thead><tr><th>Observed label</th><th>Role</th><th>Source class</th><th>Observations</th></tr></thead><tbody>{detail.aliases.slice(0, 200).map((alias, index) => <tr key={`${alias.source_class}-${alias.role}-${alias.name}-${index}`}><td><strong>{alias.name}</strong></td><td>{roleLabel(alias.role)}</td><td>{label(alias.source_class)}</td><td>{number.format(alias.observation_count)}</td></tr>)}</tbody></table></div></div>

    {firm.candidate_related_company_ids.length > 0 && <div className="reference-table-card"><div className="reference-table-heading"><div><strong>Identity candidates requiring review</strong><span>Similar or ambiguous observed labels; not a confirmed corporate relationship.</span></div></div><div className="candidate-company-list">{firm.candidate_related_company_ids.map(candidateId => <button key={candidateId} onClick={() => onOpenCompany(candidateId)}><strong>{candidateId}</strong><span>Open separate known-firm entity →</span></button>)}</div></div>}

    {detail.procurement && <div className="reference-table-card"><div className="reference-table-heading"><div><strong>Public procurement observations</strong><span>{procurement ? `${number.format(visibleRecords.length)} shown · ${number.format(records.length)} source-backed records` : 'Loading retained procurement records…'}</span></div></div>{procurementError ? <div className="reference-empty-state compact"><strong>Procurement record detail is unavailable.</strong><span>{procurementError}</span><span>The known-firm identity and site evidence above remain available from the generated firm dataset.</span></div> : procurement ? <div className="reference-table-scroll"><table className="reference-table company-procurement-table"><thead><tr><th>Record</th><th>Source</th><th>Buyer</th><th>Service</th><th>Observed value</th><th>Date</th><th>Source evidence</th></tr></thead><tbody>{visibleRecords.map(row => <tr key={row.procurement_id}><td><strong>{row.title ?? row.description ?? row.source_record_id}</strong><small>{row.source_contract_id ?? row.notice_id ?? row.source_record_id}</small></td><td>{sourceLabel(row)}<small>{row.vendor_role ?? row.scope ?? 'source observation'}</small></td><td>{row.buyer_name ?? row.agency ?? '—'}</td><td>{label(row.service_category)}<small>{row.service_confidence}</small></td><td>{recordAmount(row) == null ? '—' : currency.format(recordAmount(row) ?? 0)}<small>{row.observed_value_evidence ?? row.amount_evidence ?? 'No amount published'}</small></td><td>{recordDate(row) ? formatDate(recordDate(row) ?? '') : '—'}</td><td>{row.source_url ? <a className="table-link" href={row.source_url} target="_blank" rel="noreferrer">Open source ↗</a> : '—'}<small>{row.facility_match_confidence ?? row.tower_link_confidence ?? 'UNLINKED'} facility/account</small></td></tr>)}</tbody></table></div> : <div className="reference-empty-state compact"><strong>Loading procurement evidence…</strong></div>}</div>}

    <div className="known-firm-boundary-grid firm-profile-boundaries">{Object.entries(detail.evidence_boundaries).map(([key, value]) => <div key={key}><strong>{label(key)}</strong><span>{value}</span></div>)}</div>
  </section>
}
