import { useEffect, useMemo, useState } from 'react'
import { loadKnownFirmDetail, loadProcurement, loadSystems } from '../data/api'
import type { CompanyIntelligenceRecord } from '../types/company'
import type { KnownFirmDetailPayload, KnownFirmRole, KnownFirmSiteRelationship } from '../types/firm'
import type { ProcurementBundle, ProcurementRecord } from '../types/procurement'
import type { SystemSummary } from '../types/data'
import { formatDate, signalLabel } from '../domain/labels'
import { ShareButton } from './ShareButton'
import { FirmSiteMap } from './FirmSiteMap'
import { StatusBadge } from './StatusBadge'

const number = new Intl.NumberFormat('en-US')
const currency = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
const SITE_PAGE_SIZE = 50
const EVIDENCE_PAGE_SIZE = 50

type EnrichedSystemSummary = SystemSummary & {
  acris_recent_document_count?: number
  latest_acris_recorded_date?: string | null
}

type SiteSortKey = 'address' | 'priority' | 'scale' | 'sampling' | 'activity' | 'last_observed'
type SortDirection = 'asc' | 'desc'

type FirmSiteView = {
  relationship: KnownFirmSiteRelationship
  systems: EnrichedSystemSummary[]
  prioritySystem: EnrichedSystemSummary | null
  priorityScore: number | null
  primarySignal: string | null
  evidenceConfidence: string | null
  activeEquipment: number
  contactCount: number
  missingSampleCount: number
  worstSamplingDays: number | null
  samplingDate: string | null
  latestInspectionDate: string | null
  oathCount: number
  dobCount: number
  acrisCount: number
  activityCount: number
  confirmedViolation: boolean
  institutionalTypes: string[]
}

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

function priorityBand(score: number): string {
  if (score >= 70) return 'high'
  if (score >= 40) return 'medium'
  return 'low'
}

function maxDate(values: Array<string | null | undefined>): string | null {
  const filtered = values.filter((value): value is string => Boolean(value))
  return filtered.length ? filtered.sort().at(-1) ?? null : null
}

function buildSiteView(site: KnownFirmSiteRelationship, systemsById: Map<string, EnrichedSystemSummary>): FirmSiteView {
  const systems = site.system_ids.map(systemId => systemsById.get(systemId)).filter((row): row is EnrichedSystemSummary => Boolean(row))
  const prioritySystem = systems.length
    ? [...systems].sort((left, right) => right.priority_score - left.priority_score || left.system_id.localeCompare(right.system_id))[0]
    : null
  const samplingRows = systems.filter(row => row.days_since_latest_sample != null)
  const worstSamplingSystem = samplingRows.length
    ? [...samplingRows].sort((left, right) => (right.days_since_latest_sample ?? -1) - (left.days_since_latest_sample ?? -1))[0]
    : null
  const oathCount = systems.reduce((sum, row) => sum + (row.oath_case_count ?? 0), 0)
  const dobCount = systems.reduce((sum, row) => sum + (row.dob_recent_activity_count ?? 0), 0)
  const acrisCount = systems.reduce((sum, row) => sum + (row.acris_recent_document_count ?? 0), 0)
  return {
    relationship: site,
    systems,
    prioritySystem,
    priorityScore: prioritySystem?.priority_score ?? null,
    primarySignal: prioritySystem?.primary_signal ?? null,
    evidenceConfidence: prioritySystem?.evidence_confidence ?? null,
    activeEquipment: systems.reduce((sum, row) => sum + row.active_equipment, 0),
    contactCount: systems.reduce((max, row) => Math.max(max, row.hpd_contact_count ?? 0), 0),
    missingSampleCount: systems.filter(row => !row.latest_sample_date).length,
    worstSamplingDays: worstSamplingSystem?.days_since_latest_sample ?? null,
    samplingDate: worstSamplingSystem?.latest_sample_date ?? null,
    latestInspectionDate: maxDate(systems.map(row => row.latest_inspection_date)),
    oathCount,
    dobCount,
    acrisCount,
    activityCount: oathCount + dobCount + acrisCount,
    confirmedViolation: systems.some(row => row.confirmed_violation),
    institutionalTypes: [...new Set(systems.flatMap(row => row.cms_institutional_facility_types ?? []))].sort(),
  }
}

function siteSortValue(row: FirmSiteView, key: SiteSortKey): string | number {
  if (key === 'address') return row.relationship.address ?? row.relationship.site_id
  if (key === 'priority') return row.priorityScore ?? -1
  if (key === 'scale') return row.activeEquipment
  if (key === 'sampling') return row.missingSampleCount > 0 ? 1_000_000 : row.worstSamplingDays ?? -1
  if (key === 'activity') return row.activityCount
  return row.relationship.last_observed_date ?? ''
}

function compareValues(left: string | number, right: string | number): number {
  if (typeof left === 'number' && typeof right === 'number') return left - right
  return String(left).localeCompare(String(right), undefined, { numeric: true, sensitivity: 'base' })
}

export function CompanyProfilePage({
  companyId,
  onBack,
  onOpenCompany,
}: {
  companyId: string
  onBack: () => void
  onOpenCompany: (company: CompanyIntelligenceRecord) => void
}) {
  void onOpenCompany
  const [detail, setDetail] = useState<KnownFirmDetailPayload | null>(null)
  const [systems, setSystems] = useState<EnrichedSystemSummary[]>([])
  const [procurement, setProcurement] = useState<ProcurementBundle | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [procurementError, setProcurementError] = useState<string | null>(null)
  const [siteSearch, setSiteSearch] = useState('')
  const [siteFilter, setSiteFilter] = useState('ALL')
  const [boroughFilter, setBoroughFilter] = useState('ALL')
  const [siteSort, setSiteSort] = useState<{ key: SiteSortKey; direction: SortDirection }>({ key: 'priority', direction: 'desc' })
  const [sitePage, setSitePage] = useState(0)
  const [selectedSiteId, setSelectedSiteId] = useState<string | null>(null)
  const [procurementPage, setProcurementPage] = useState(0)
  const [aliasPage, setAliasPage] = useState(0)

  useEffect(() => {
    let cancelled = false
    setDetail(null)
    setSystems([])
    setError(null)
    setProcurement(null)
    setProcurementError(null)
    setSelectedSiteId(null)
    setSiteSearch('')
    setSiteFilter('ALL')
    setBoroughFilter('ALL')
    setSitePage(0)
    setProcurementPage(0)
    setAliasPage(0)
    Promise.all([loadKnownFirmDetail(companyId), loadSystems()])
      .then(([firmDetail, systemsPayload]) => {
        if (cancelled) return
        setDetail(firmDetail)
        setSystems(systemsPayload.systems as EnrichedSystemSummary[])
        if (firmDetail.procurement?.procurement_ids?.length) {
          loadProcurement()
            .then(bundle => { if (!cancelled) setProcurement(bundle) })
            .catch(err => { if (!cancelled) setProcurementError(err instanceof Error ? err.message : 'Procurement evidence is unavailable') })
        }
      })
      .catch(err => { if (!cancelled) setError(err instanceof Error ? err.message : 'Unable to load known-firm profile') })
    return () => { cancelled = true }
  }, [companyId])

  const systemsById = useMemo(() => new Map(systems.map(row => [row.system_id, row])), [systems])
  const allSiteViews = useMemo(() => detail ? detail.site_relationships.map(site => buildSiteView(site, systemsById)) : [], [detail, systemsById])
  const boroughs = useMemo(() => [...new Set(allSiteViews.map(row => row.relationship.borough).filter((value): value is string => Boolean(value)))].sort(), [allSiteViews])
  const filteredSites = useMemo(() => allSiteViews.filter(row => {
    const site = row.relationship
    const query = siteSearch.trim().toLowerCase()
    const haystack = [site.address, site.borough, site.zip, site.bin, site.bbl, ...site.system_ids, ...site.roles].filter(Boolean).join(' ').toLowerCase()
    if (query && !haystack.includes(query)) return false
    if (siteFilter === 'SERVICED' && !site.serviced) return false
    if (siteFilter === 'CONTRACTED' && !site.contracted) return false
    if (siteFilter === 'PROJECT' && !site.project_role) return false
    if (siteFilter === 'TOWER' && site.system_ids.length === 0) return false
    if (siteFilter === 'MAPPED' && !site.mapped) return false
    if (boroughFilter !== 'ALL' && site.borough !== boroughFilter) return false
    return true
  }), [allSiteViews, siteSearch, siteFilter, boroughFilter])
  const sortedSites = useMemo(() => [...filteredSites].sort((left, right) => {
    const result = compareValues(siteSortValue(left, siteSort.key), siteSortValue(right, siteSort.key))
      || String(left.relationship.address ?? left.relationship.site_id).localeCompare(String(right.relationship.address ?? right.relationship.site_id))
    return siteSort.direction === 'asc' ? result : -result
  }), [filteredSites, siteSort])
  const siteMaxPage = Math.max(0, Math.ceil(sortedSites.length / SITE_PAGE_SIZE) - 1)
  const activeSitePage = Math.min(sitePage, siteMaxPage)
  const visibleSites = useMemo(() => sortedSites.slice(activeSitePage * SITE_PAGE_SIZE, activeSitePage * SITE_PAGE_SIZE + SITE_PAGE_SIZE), [sortedSites, activeSitePage])
  const selectedView = useMemo(() => allSiteViews.find(row => row.relationship.site_id === selectedSiteId) ?? null, [allSiteViews, selectedSiteId])

  useEffect(() => { setSitePage(0) }, [siteSearch, siteFilter, boroughFilter, siteSort])

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
  const procurementMaxPage = Math.max(0, Math.ceil(records.length / EVIDENCE_PAGE_SIZE) - 1)
  const activeProcurementPage = Math.min(procurementPage, procurementMaxPage)
  const visibleRecords = records.slice(activeProcurementPage * EVIDENCE_PAGE_SIZE, activeProcurementPage * EVIDENCE_PAGE_SIZE + EVIDENCE_PAGE_SIZE)
  const aliasMaxPage = Math.max(0, Math.ceil((detail?.aliases.length ?? 0) / EVIDENCE_PAGE_SIZE) - 1)
  const activeAliasPage = Math.min(aliasPage, aliasMaxPage)
  const visibleAliases = detail?.aliases.slice(activeAliasPage * EVIDENCE_PAGE_SIZE, activeAliasPage * EVIDENCE_PAGE_SIZE + EVIDENCE_PAGE_SIZE) ?? []
  const openFirmId = (firmId: string) => { window.location.hash = `#/company/${encodeURIComponent(firmId)}` }
  const changeSiteSort = (key: SiteSortKey) => setSiteSort(current => current.key === key
    ? { key, direction: current.direction === 'asc' ? 'desc' : 'asc' }
    : { key, direction: key === 'address' ? 'asc' : 'desc' })
  const siteSortIndicator = (key: SiteSortKey) => siteSort.key === key ? (siteSort.direction === 'asc' ? ' ↑' : ' ↓') : ''

  if (error) return <section className="product-page company-profile-page"><div className="account-profile-toolbar"><button className="breadcrumb-back" onClick={onBack}>← Back to companies</button></div><div className="reference-empty-state"><strong>Company profile evidence is unavailable.</strong><span>{error}</span></div></section>
  if (!detail) return <section className="product-page company-profile-page"><div className="account-profile-toolbar"><button className="breadcrumb-back" onClick={onBack}>← Back to companies</button></div><div className="reference-empty-state"><strong>Loading source-backed company profile…</strong></div></section>

  const firm = detail.firm
  const mappedFilteredSites = sortedSites.map(row => row.relationship).filter(site => site.mapped)

  return <section className="product-page company-profile-page known-firm-profile-page">
    <div className="account-profile-toolbar">
      <div><button className="breadcrumb-back" onClick={onBack}>← Back to companies</button><span>Company intelligence · all retained public evidence</span></div>
      <div className="page-actions"><ShareButton label="Copy firm link" /></div>
    </div>

    <div className="product-page-heading company-profile-heading firm-profile-heading">
      <div>
        <span className="page-kicker">{roleLabel(firm.primary_role)} · {firm.source_classes.length} source classes</span>
        <h1>{firm.canonical_name}</h1>
        <p>{number.format(firm.observation_count)} source observations across {number.format(firm.observed_site_count)} related sites. Service, procurement, qualification and project-role evidence remain separately labeled so related does not imply incumbent service.</p>
        <div className="firm-role-chip-row">{firm.roles.map(role => <span key={role}>{roleLabel(role)}</span>)}</div>
      </div>
      <div className="company-identity-card">
        <span className={`health-badge health-${firm.identity_confidence === 'VERIFY' || firm.identity_confidence === 'UNRESOLVED' ? 'warning' : 'healthy'}`}>{firm.identity_confidence}</span>
        <small>Identity resolution</small>
        <strong>{label(firm.resolution_method)}</strong>
        <span>{firm.latest_observed_date ? `Last observed ${formatDate(firm.latest_observed_date)}` : 'No dated observation'}</span>
      </div>
    </div>

    <div className="reference-metric-grid known-firm-profile-metrics">
      <article><span className="reference-metric-icon urgent">⌂</span><div><small>Serviced sites</small><strong>{number.format(firm.serviced_site_count)}</strong><span>Explicit DWT provider/lab evidence</span></div></article>
      <article><span className="reference-metric-icon success">◎</span><div><small>Tower accounts</small><strong>{number.format(firm.tower_account_count)}</strong><span>{number.format(firm.mapped_site_count)} mapped relationships</span></div></article>
      <article><span className="reference-metric-icon">⌁</span><div><small>All related sites</small><strong>{number.format(firm.observed_site_count)}</strong><span>{number.format(firm.contracted_site_count)} contract · {number.format(firm.project_site_count)} project-role</span></div></article>
      <article><span className="reference-metric-icon">▤</span><div><small>Public contracts</small><strong>{number.format(firm.observed_contract_count)}</strong><span>{number.format(firm.active_contract_count)} active · {number.format(firm.observed_customer_count)} buyers</span></div></article>
      <article><span className="reference-metric-icon warning">$</span><div><small>Observed public value</small><strong>{firm.observed_contract_value ? currency.format(firm.observed_contract_value) : '—'}</strong><span>Source-reported values · not revenue</span></div></article>
      <article><span className="reference-metric-icon">7G</span><div><small>Active 7G registrations</small><strong>{number.format(firm.active_qualification_count)}</strong><span>{number.format(firm.qualification_count)} observed registrations</span></div></article>
    </div>

    <section className="reference-table-card firm-site-workspace">
      <div className="reference-table-heading firm-site-workspace-heading">
        <div><strong>Sites connected to {firm.canonical_name}</strong><span>{number.format(sortedSites.length)} matching relationships · map shows all mapped filtered sites</span></div>
        <div className="firm-site-controls">
          <input aria-label="Firm site search" value={siteSearch} onChange={event => setSiteSearch(event.target.value)} placeholder="Address, BIN, BBL, system ID or role…" />
          <select aria-label="Firm site relationship filter" value={siteFilter} onChange={event => setSiteFilter(event.target.value)}>
            <option value="ALL">All relationships</option>
            <option value="SERVICED">Observed service</option>
            <option value="TOWER">TowerSignal accounts</option>
            <option value="CONTRACTED">Confirmed contract links</option>
            <option value="PROJECT">Project roles</option>
            <option value="MAPPED">Mapped sites</option>
          </select>
          <select aria-label="Firm site borough filter" value={boroughFilter} onChange={event => setBoroughFilter(event.target.value)}>
            <option value="ALL">All boroughs</option>
            {boroughs.map(value => <option key={value} value={value}>{value}</option>)}
          </select>
        </div>
      </div>

      {mappedFilteredSites.length > 0 ? <div className="firm-site-map-grid">
        <FirmSiteMap sites={mappedFilteredSites} selectedSiteId={selectedSiteId} onSelect={site => setSelectedSiteId(site.site_id)} />
        {selectedView ? <aside className="firm-selected-site firm-selected-prospect-site">
          <small>Selected site</small>
          <strong>{selectedView.relationship.address ?? selectedView.relationship.site_id}</strong>
          <span>{[selectedView.relationship.borough, selectedView.relationship.zip, selectedView.relationship.bin ? `BIN ${selectedView.relationship.bin}` : null].filter(Boolean).join(' · ')}</span>
          <div className="firm-selected-site-signal">
            <span className={`firm-relationship-badge ${selectedView.relationship.serviced ? 'serviced' : selectedView.relationship.contracted ? 'contracted' : 'related'}`}>{siteRelationshipLabel(selectedView.relationship)}</span>
            {selectedView.primarySignal && <span className={`signal signal-${selectedView.primarySignal.toLowerCase()}`}>{signalLabel(selectedView.primarySignal)}</span>}
          </div>
          <dl>
            <div><dt>Priority</dt><dd>{selectedView.priorityScore == null ? 'No exact TowerSignal account' : selectedView.priorityScore}</dd></div>
            <div><dt>Scale</dt><dd>{selectedView.systems.length ? `${number.format(selectedView.activeEquipment)} active unit${selectedView.activeEquipment === 1 ? '' : 's'} · ${number.format(selectedView.systems.length)} account${selectedView.systems.length === 1 ? '' : 's'}` : 'No exact account link'}</dd></div>
            <div><dt>Contact</dt><dd>{selectedView.contactCount ? `${number.format(selectedView.contactCount)} HPD contact${selectedView.contactCount === 1 ? '' : 's'}` : 'No matched HPD contact'}</dd></div>
            <div><dt>Sampling</dt><dd>{selectedView.missingSampleCount ? `${selectedView.missingSampleCount} account${selectedView.missingSampleCount === 1 ? '' : 's'} missing public sample date` : selectedView.samplingDate ? `${formatDate(selectedView.samplingDate)} · ${number.format(selectedView.worstSamplingDays ?? 0)} days` : 'No linked sampling record'}</dd></div>
            <div><dt>Activity</dt><dd>OATH {number.format(selectedView.oathCount)} · DOB {number.format(selectedView.dobCount)} · ACRIS {number.format(selectedView.acrisCount)}</dd></div>
            <div><dt>Firm roles</dt><dd>{selectedView.relationship.roles.map(roleLabel).join(' · ') || 'Related evidence'}</dd></div>
          </dl>
          {selectedView.relationship.system_ids.length > 0 && <div className="firm-site-account-links">{selectedView.relationship.system_ids.map(systemId => <a key={systemId} href={`#/account/${encodeURIComponent(systemId)}`}>Open account {systemId} →</a>)}</div>}
        </aside> : <aside className="firm-selected-site empty"><strong>Select a map point</strong><span>Inspect priority, timing, contact, sampling and activity for that company-site relationship.</span></aside>}
      </div> : <div className="reference-empty-state compact"><strong>No mapped site relationships match these filters.</strong><span>Unmapped source relationships remain available in the table.</span></div>}

      {sortedSites.length === 0 ? <div className="empty-state"><strong>No sites match these filters.</strong><span>Widen the relationship, borough or search criteria.</span></div> : <div className="table-scroll"><table className="account-table firm-prospect-sites-table"><thead><tr>
        <th><button onClick={() => changeSiteSort('address')}>Site{siteSortIndicator('address')}</button></th>
        <th>Relationship</th>
        <th><button onClick={() => changeSiteSort('priority')}>Priority{siteSortIndicator('priority')}</button></th>
        <th>Timing signal</th>
        <th><button onClick={() => changeSiteSort('scale')}>Scale{siteSortIndicator('scale')}</button></th>
        <th>Contact</th>
        <th><button onClick={() => changeSiteSort('sampling')}>Sampling{siteSortIndicator('sampling')}</button></th>
        <th><button onClick={() => changeSiteSort('activity')}>Activity{siteSortIndicator('activity')}</button></th>
        <th>Evidence</th>
        <th aria-label="Open account" />
      </tr></thead><tbody>{visibleSites.map(row => {
        const site = row.relationship
        return <tr key={site.site_id} className={selectedSiteId === site.site_id ? 'selected-row' : ''} onClick={() => setSelectedSiteId(site.site_id)} tabIndex={0} onKeyDown={event => { if (event.key === 'Enter') setSelectedSiteId(site.site_id) }}>
          <td className="account-cell"><strong>{site.address ?? site.site_id}</strong><span>{[site.borough, site.zip].filter(Boolean).join(' · ') || 'Location not published'}</span><small>{[site.bin ? `BIN ${site.bin}` : null, site.bbl ? `BBL ${site.bbl}` : null].filter(Boolean).join(' · ') || site.site_id}</small></td>
          <td><span className={`firm-relationship-badge ${site.serviced ? 'serviced' : site.contracted ? 'contracted' : 'related'}`}>{siteRelationshipLabel(site)}</span><small>{site.roles.slice(0, 2).map(roleLabel).join(' · ')}{site.roles.length > 2 ? ` · +${site.roles.length - 2}` : ''}</small></td>
          <td>{row.priorityScore == null ? <span className="muted-copy">No account score</span> : <div className={`priority-indicator priority-${priorityBand(row.priorityScore)}`}><strong>{row.priorityScore}</strong><span><i style={{ width:`${Math.max(4, row.priorityScore)}%` }} /></span></div>}</td>
          <td>{row.primarySignal ? <><span className={`signal signal-${row.primarySignal.toLowerCase()}`}>{signalLabel(row.primarySignal)}</span>{row.confirmedViolation && <small className="urgent-copy">Confirmed record</small>}</> : <span className="muted-copy">No exact tower timing signal</span>}</td>
          <td>{row.systems.length ? <><strong>{number.format(row.activeEquipment)} active unit{row.activeEquipment === 1 ? '' : 's'}</strong><small>{number.format(row.systems.length)} linked account{row.systems.length === 1 ? '' : 's'}</small></> : <span className="muted-copy">No exact tower account</span>}</td>
          <td>{row.contactCount ? <span className="contact-ready">✓ {number.format(row.contactCount)} HPD contact{row.contactCount === 1 ? '' : 's'}</span> : <span className="muted-copy">No matched contact</span>}</td>
          <td>{row.missingSampleCount ? <><strong>Missing public date</strong><small>{number.format(row.missingSampleCount)} linked account{row.missingSampleCount === 1 ? '' : 's'}</small></> : row.samplingDate ? <>{formatDate(row.samplingDate)}<small>{number.format(row.worstSamplingDays ?? 0)} days ago</small></> : <span className="muted-copy">No linked sampling record</span>}</td>
          <td><div className="activity-stack">{row.oathCount > 0 && <span>OATH · {number.format(row.oathCount)}</span>}{row.dobCount > 0 && <span>DOB · {number.format(row.dobCount)}</span>}{row.acrisCount > 0 && <span>ACRIS · {number.format(row.acrisCount)}</span>}{row.activityCount === 0 && <span className="muted-copy">No linked recent activity</span>}</div></td>
          <td>{row.evidenceConfidence ? <StatusBadge value={row.evidenceConfidence as 'CONFIRMED' | 'STRONG_SIGNAL' | 'VERIFY'} /> : <><span className="firm-source-evidence">{site.evidence_classes.slice(0, 2).map(label).join(' · ') || 'Source relationship'}</span><small>{number.format(site.observation_count)} firm observation{site.observation_count === 1 ? '' : 's'}</small></>}</td>
          <td className="row-arrow">{site.system_ids.length === 1 ? <a href={`#/account/${encodeURIComponent(site.system_ids[0])}`} onClick={event => event.stopPropagation()} aria-label={`Open account ${site.system_ids[0]}`}>›</a> : '›'}</td>
        </tr>
      })}</tbody></table></div>}
      <div className="firm-site-table-footer">
        <span><strong>Observed service</strong> requires explicit DWT firm/lab evidence. Priority, timing, contact, sampling and activity are shown only when this site has an exact TowerSignal account link.</span>
        <div className="pagination"><button disabled={activeSitePage === 0} onClick={() => setSitePage(value => Math.max(0, value - 1))}>Previous</button><span>Page {activeSitePage + 1} of {siteMaxPage + 1}</span><button disabled={activeSitePage === siteMaxPage} onClick={() => setSitePage(value => Math.min(siteMaxPage, value + 1))}>Next</button></div>
      </div>
    </section>

    <div className="firm-evidence-heading"><div><span className="page-kicker">Complete retained evidence</span><h2>Everything TowerSignal knows about this firm</h2></div><span>Public-record observations only; source roles and identity confidence are preserved.</span></div>

    <div className="company-profile-grid known-firm-evidence-grid">
      <section className="reference-table-card company-evidence-card">
        <div className="reference-table-heading"><div><strong>Identity &amp; observed roles</strong><span>{number.format(firm.observation_count)} source observations</span></div></div>
        <dl className="detail-grid"><div><dt>Canonical label</dt><dd>{firm.canonical_name}</dd></div><div><dt>Strict normalized label</dt><dd>{firm.strict_name || '—'}</dd></div><div><dt>Base normalized label</dt><dd>{firm.normalized_name || '—'}</dd></div><div><dt>First observed</dt><dd>{firm.first_observed_date ? formatDate(firm.first_observed_date) : '—'}</dd></div><div><dt>Last observed</dt><dd>{firm.latest_observed_date ? formatDate(firm.latest_observed_date) : '—'}</dd></div><div><dt>Sources</dt><dd>{firm.source_classes.map(label).join(' · ') || '—'}</dd></div></dl>
        <div className="evidence-list"><strong>Roles</strong>{firm.roles.map(role => <div key={role}><span>{roleLabel(role)}</span><small>{number.format(firm.role_counts[role] ?? 0)} observations</small></div>)}</div>
      </section>
      <section className="reference-table-card company-evidence-card">
        <div className="reference-table-heading"><div><strong>Commercial footprint</strong><span>Observed public procurement only</span></div></div>
        <dl className="detail-grid"><div><dt>Observed contract value</dt><dd>{firm.observed_contract_value ? currency.format(firm.observed_contract_value) : '—'}</dd></div><div><dt>Observed contracts</dt><dd>{number.format(firm.observed_contract_count)}</dd></div><div><dt>Active contracts</dt><dd>{number.format(firm.active_contract_count)}</dd></div><div><dt>Public buyers</dt><dd>{number.format(firm.observed_customer_count)}</dd></div><div><dt>Repeat buyers</dt><dd>{number.format(firm.repeat_buyer_count)}</dd></div><div><dt>Contract-linked sites</dt><dd>{number.format(firm.contracted_site_count)}</dd></div></dl>
        {firm.service_categories.length > 0 && <div className="evidence-list"><strong>Service categories</strong>{firm.service_categories.map(value => <div key={value}><span>{label(value)}</span></div>)}</div>}
        {detail.procurement?.observed_buyers?.length ? <div className="firm-buyer-list"><strong>Observed public buyers</strong><div>{detail.procurement.observed_buyers.map(value => <span key={value}>{value}</span>)}</div></div> : null}
      </section>
    </div>

    {detail.qualifications.length > 0 && <section className="reference-table-card firm-evidence-card">
      <div className="reference-table-heading"><div><strong>DEC 7G qualifications</strong><span>{number.format(detail.qualifications.length)} observed registrations · qualification evidence only</span></div></div>
      <div className="table-scroll"><table className="account-table firm-evidence-table"><thead><tr><th>Registration</th><th>Location</th><th>Effective</th><th>Expiration</th><th>Status</th><th>Scope</th></tr></thead><tbody>{detail.qualifications.map(item => <tr key={item.qualification_id ?? item.registration_number ?? `${item.city}-${item.registration_expiration_date}`}><td><strong>{item.registration_number ?? '—'}</strong></td><td>{[item.city, item.state].filter(Boolean).join(', ') || '—'}</td><td>{item.registration_effective_date ? formatDate(item.registration_effective_date) : '—'}</td><td>{item.registration_expiration_date ? formatDate(item.registration_expiration_date) : '—'}</td><td><span className={`health-badge health-${item.active_as_of_generation ? 'healthy' : 'warning'}`}>{item.active_as_of_generation ? 'ACTIVE AT GENERATION' : 'NOT CURRENT'}</span></td><td>{item.qualification_scope ?? 'Category 7G'}</td></tr>)}</tbody></table></div>
    </section>}

    <section className="reference-table-card firm-evidence-card">
      <div className="reference-table-heading"><div><strong>Observed names &amp; aliases</strong><span>{number.format(detail.aliases.length)} retained source labels</span></div></div>
      <div className="table-scroll"><table className="account-table firm-evidence-table"><thead><tr><th>Observed label</th><th>Role</th><th>Source class</th><th>Observations</th></tr></thead><tbody>{visibleAliases.map((alias, index) => <tr key={`${alias.source_class}-${alias.role}-${alias.name}-${activeAliasPage}-${index}`}><td><strong>{alias.name}</strong></td><td>{roleLabel(alias.role)}</td><td>{label(alias.source_class)}</td><td>{number.format(alias.observation_count)}</td></tr>)}</tbody></table></div>
      <div className="pagination"><button disabled={activeAliasPage === 0} onClick={() => setAliasPage(value => Math.max(0, value - 1))}>Previous</button><span>Page {activeAliasPage + 1} of {aliasMaxPage + 1}</span><button disabled={activeAliasPage === aliasMaxPage} onClick={() => setAliasPage(value => Math.min(aliasMaxPage, value + 1))}>Next</button></div>
    </section>

    {firm.candidate_related_company_ids.length > 0 && <section className="reference-table-card firm-evidence-card"><div className="reference-table-heading"><div><strong>Identity candidates requiring review</strong><span>Similar or ambiguous labels; not confirmed corporate relationships</span></div></div><div className="candidate-company-list">{firm.candidate_related_company_ids.map(candidateId => <button key={candidateId} onClick={() => openFirmId(candidateId)}><strong>{candidateId}</strong><span>Open separate known-firm entity →</span></button>)}</div></section>}

    {detail.procurement && <section className="reference-table-card firm-evidence-card">
      <div className="reference-table-heading"><div><strong>Public procurement observations</strong><span>{procurement ? `${number.format(records.length)} source-backed records` : 'Loading retained procurement records…'}</span></div></div>
      {procurementError ? <div className="reference-empty-state compact"><strong>Procurement record detail is unavailable.</strong><span>{procurementError}</span><span>Firm identity and site evidence above remain available from the generated firm dataset.</span></div> : procurement ? <><div className="table-scroll"><table className="account-table company-procurement-table"><thead><tr><th>Record</th><th>Source</th><th>Buyer</th><th>Service</th><th>Observed value</th><th>Date</th><th>Source evidence</th></tr></thead><tbody>{visibleRecords.map(row => <tr key={row.procurement_id}><td><strong>{row.title ?? row.description ?? row.source_record_id}</strong><small>{row.source_contract_id ?? row.notice_id ?? row.source_record_id}</small></td><td>{sourceLabel(row)}<small>{row.vendor_role ?? row.scope ?? 'source observation'}</small></td><td>{row.buyer_name ?? row.agency ?? '—'}</td><td>{label(row.service_category)}<small>{row.service_confidence}</small></td><td>{recordAmount(row) == null ? '—' : currency.format(recordAmount(row) ?? 0)}<small>{row.observed_value_evidence ?? row.amount_evidence ?? 'No amount published'}</small></td><td>{recordDate(row) ? formatDate(recordDate(row) ?? '') : '—'}</td><td>{row.source_url ? <a className="table-link" href={row.source_url} target="_blank" rel="noreferrer">Open source ↗</a> : '—'}<small>{row.facility_match_confidence ?? row.tower_link_confidence ?? 'UNLINKED'} facility/account</small></td></tr>)}</tbody></table></div><div className="pagination"><button disabled={activeProcurementPage === 0} onClick={() => setProcurementPage(value => Math.max(0, value - 1))}>Previous</button><span>Page {activeProcurementPage + 1} of {procurementMaxPage + 1}</span><button disabled={activeProcurementPage === procurementMaxPage} onClick={() => setProcurementPage(value => Math.min(procurementMaxPage, value + 1))}>Next</button></div></> : <div className="reference-empty-state compact"><strong>Loading procurement evidence…</strong></div>}
    </section>}

    <div className="known-firm-boundary-grid firm-profile-boundaries">{Object.entries(detail.evidence_boundaries).map(([key, value]) => <div key={key}><strong>{label(key)}</strong><span>{value}</span></div>)}</div>
  </section>
}
