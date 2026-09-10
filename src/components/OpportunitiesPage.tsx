import { useEffect, useMemo, useState } from 'react'
import type { SystemSummary, SystemsPayload } from '../types/data'
import type { AcrisSummaryFields } from '../types/acris'
import type { ProcurementBundle, ProcurementRecord } from '../types/procurement'
import { loadProcurement } from '../data/api'
import { formatDate } from '../domain/labels'
import { ShareButton } from './ShareButton'

const number = new Intl.NumberFormat('en-US')
const currency = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
const PAGE_SIZE = 50

type SortDirection = 'asc' | 'desc'
type ProcurementSortKey = 'title' | 'source' | 'agency' | 'vendor' | 'service' | 'value' | 'date' | 'evidence'
type AccountSortKey = 'address' | 'priority' | 'signal' | 'equipment' | 'contact' | 'dob' | 'oath' | 'acris'

function signalLabel(value: string): string {
  const labels: Record<string, string> = {
    CONFIRMED_RECENT_VIOLATION: 'Confirmed violation',
    POTENTIAL_SAMPLING_GAP: 'Sampling follow-up',
    NO_PUBLIC_SAMPLE_DATE: 'No public sample date',
    MULTIPLE_ACTIVE_EQUIPMENT: 'Multiple equipment',
    RECENT_NYC_HEALTH_INSPECTION: 'Recent inspection',
    NO_CURRENT_SIGNAL: 'No current timing signal',
  }
  return labels[value] ?? value.replaceAll('_', ' ').toLowerCase()
}

function procurementDate(row: ProcurementRecord): string | null {
  return row.due_date ?? row.award_date ?? row.start_date ?? row.notice_start_date ?? row.retrieved_at ?? null
}

function procurementAmount(row: ProcurementRecord): number | null {
  return row.current_amount ?? row.amount ?? row.spend_to_date ?? row.original_amount ?? null
}

function sourceLabel(row: ProcurementRecord): string {
  if (row.source === 'NYC_CITY_RECORD') return row.scope === 'OPEN_SOLICITATIONS' ? 'City Record · Solicitation' : 'City Record · Award'
  if (row.source === 'NYC_CHECKBOOK_EDC') return 'Checkbook · NYCEDC'
  if (row.source === 'NYS_OPEN_BOOK') return 'Open Book NY'
  if (row.source === 'NYC_CHECKBOOK_NYCHA') return 'Checkbook · NYCHA'
  if (row.source.startsWith('NYS_ABO_')) return 'NYS Authority Report'
  return row.vendor_role === 'SUBCONTRACTOR' ? 'Checkbook · Subcontract' : 'Checkbook · Contract'
}

function categoryLabel(value: string): string {
  return value.replaceAll('_', ' ').toLowerCase().replace(/(^|\s)\S/g, match => match.toUpperCase())
}

function compareValues(left: unknown, right: unknown): number {
  if (typeof left === 'number' && typeof right === 'number') return left - right
  if (typeof left === 'boolean' && typeof right === 'boolean') return Number(left) - Number(right)
  return String(left ?? '').localeCompare(String(right ?? ''), undefined, { numeric: true, sensitivity: 'base' })
}

function PageControls({ page, total, onPage }: { page: number; total: number; onPage: (page: number) => void }) {
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))
  if (pageCount <= 1) return null
  const safe = Math.min(page, pageCount)
  return <div className="reference-pagination"><span>Page {safe} of {pageCount}</span><div><button disabled={safe <= 1} onClick={() => onPage(safe - 1)}>Previous</button><button disabled={safe >= pageCount} onClick={() => onPage(safe + 1)}>Next</button></div></div>
}

export function OpportunitiesPage({ payload, onOpenAccount }: { payload: SystemsPayload; onOpenAccount: (row: SystemSummary) => void }) {
  const [sourceFilter, setSourceFilter] = useState('ALL')
  const [categoryFilter, setCategoryFilter] = useState('ALL')
  const [procurementSearch, setProcurementSearch] = useState('')
  const [procurementSort, setProcurementSort] = useState<{ key: ProcurementSortKey; direction: SortDirection }>({ key: 'date', direction: 'desc' })
  const [procurementPage, setProcurementPage] = useState(1)
  const [accountSearch, setAccountSearch] = useState('')
  const [accountMinPriority, setAccountMinPriority] = useState('ALL')
  const [accountContactOnly, setAccountContactOnly] = useState(false)
  const [accountSort, setAccountSort] = useState<{ key: AccountSortKey; direction: SortDirection }>({ key: 'priority', direction: 'desc' })
  const [accountPage, setAccountPage] = useState(1)
  const [procurement, setProcurement] = useState<ProcurementBundle | null>(null)
  const [procurementError, setProcurementError] = useState<string | null>(null)

  useEffect(() => {
    loadProcurement()
      .then(setProcurement)
      .catch(error => setProcurementError(error instanceof Error ? error.message : 'Unable to load procurement intelligence'))
  }, [])

  const opportunityRows = useMemo(() => payload.systems.filter(row =>
    row.priority_score >= 50 || (row.dob_recent_activity_count ?? 0) > 0 || (row.hpd_contact_count ?? 0) > 0
  ), [payload.systems])

  const filteredAccounts = useMemo(() => {
    const query = accountSearch.trim().toLowerCase()
    return opportunityRows.filter(row => {
      if (query && ![row.address, row.borough, row.zip, row.system_id, row.primary_signal].filter(Boolean).join(' ').toLowerCase().includes(query)) return false
      if (accountMinPriority !== 'ALL' && row.priority_score < Number(accountMinPriority)) return false
      if (accountContactOnly && (row.hpd_contact_count ?? 0) <= 0) return false
      return true
    })
  }, [opportunityRows, accountSearch, accountMinPriority, accountContactOnly])

  const sortedAccounts = useMemo(() => [...filteredAccounts].sort((a, b) => {
    const aa = a as SystemSummary & AcrisSummaryFields
    const bb = b as SystemSummary & AcrisSummaryFields
    const value = (row: SystemSummary & AcrisSummaryFields): unknown => {
      if (accountSort.key === 'address') return row.address ?? row.system_id
      if (accountSort.key === 'priority') return row.priority_score
      if (accountSort.key === 'signal') return row.primary_signal
      if (accountSort.key === 'equipment') return row.active_equipment
      if (accountSort.key === 'contact') return row.hpd_contact_count ?? 0
      if (accountSort.key === 'dob') return row.dob_recent_activity_count ?? 0
      if (accountSort.key === 'oath') return row.oath_case_count ?? 0
      return row.acris_recent_document_count ?? 0
    }
    const result = compareValues(value(aa), value(bb)) || compareValues(a.address, b.address)
    return accountSort.direction === 'asc' ? result : -result
  }), [filteredAccounts, accountSort])
  const accountPageCount = Math.max(1, Math.ceil(sortedAccounts.length / PAGE_SIZE))
  const safeAccountPage = Math.min(accountPage, accountPageCount)
  const visibleAccounts = sortedAccounts.slice((safeAccountPage - 1) * PAGE_SIZE, safeAccountPage * PAGE_SIZE)

  const procurementRows = useMemo(() => procurement ? [
    ...procurement.cityRecord.notices,
    ...procurement.checkbook.contracts,
    ...(procurement.nysAuthorities?.contracts ?? []),
    ...(procurement.openBookWater?.contracts ?? []),
    ...(procurement.nychaWater?.records ?? []),
  ] : [], [procurement])

  const categories = useMemo(() => [...new Set(procurementRows.map(row => row.service_category))].sort(), [procurementRows])
  const filteredProcurement = useMemo(() => {
    const query = procurementSearch.trim().toLowerCase()
    return procurementRows.filter(row => {
      const isNysAuthority = row.source.startsWith('NYS_ABO_')
      const isCoreCheckbook = row.source.startsWith('NYC_CHECKBOOK') && row.source !== 'NYC_CHECKBOOK_NYCHA'
      if (sourceFilter === 'CITY_RECORD' && row.source !== 'NYC_CITY_RECORD') return false
      if (sourceFilter === 'CHECKBOOK' && !isCoreCheckbook) return false
      if (sourceFilter === 'NYS_AUTHORITIES' && !isNysAuthority) return false
      if (sourceFilter === 'OPENBOOK' && row.source !== 'NYS_OPEN_BOOK') return false
      if (sourceFilter === 'NYCHA' && row.source !== 'NYC_CHECKBOOK_NYCHA') return false
      if (categoryFilter !== 'ALL' && row.service_category !== categoryFilter) return false
      if (query && ![
        row.title, row.description, row.source_record_id, row.source_contract_id, row.notice_id,
        row.agency, row.buyer_name, row.vendor_raw, row.service_category, row.source,
      ].filter(Boolean).join(' ').toLowerCase().includes(query)) return false
      return true
    })
  }, [procurementRows, sourceFilter, categoryFilter, procurementSearch])

  const sortedProcurement = useMemo(() => [...filteredProcurement].sort((a, b) => {
    const value = (row: ProcurementRecord): unknown => {
      if (procurementSort.key === 'title') return row.title ?? row.description ?? row.source_record_id
      if (procurementSort.key === 'source') return sourceLabel(row)
      if (procurementSort.key === 'agency') return row.agency ?? row.buyer_name
      if (procurementSort.key === 'vendor') return row.vendor_raw
      if (procurementSort.key === 'service') return row.service_category
      if (procurementSort.key === 'value') return procurementAmount(row) ?? 0
      if (procurementSort.key === 'date') return procurementDate(row) ?? ''
      return row.facility_match_confidence ?? row.tower_link_confidence ?? 'UNLINKED'
    }
    const result = compareValues(value(a), value(b)) || compareValues(procurementDate(a), procurementDate(b))
    return procurementSort.direction === 'asc' ? result : -result
  }), [filteredProcurement, procurementSort])
  const procurementPageCount = Math.max(1, Math.ceil(sortedProcurement.length / PAGE_SIZE))
  const safeProcurementPage = Math.min(procurementPage, procurementPageCount)
  const visibleProcurement = sortedProcurement.slice((safeProcurementPage - 1) * PAGE_SIZE, safeProcurementPage * PAGE_SIZE)

  useEffect(() => { setProcurementPage(1) }, [sourceFilter, categoryFilter, procurementSearch, procurementSort])
  useEffect(() => { setAccountPage(1) }, [accountSearch, accountMinPriority, accountContactOnly, accountSort])

  const observedContractValue = procurementRows.reduce((sum, row) => sum + (procurementAmount(row) ?? 0), 0)
  const unresolved = procurementRows.filter(row => row.vendor_raw && !row.company_id).length
  const nysHealthyCount = procurement?.nysAuthorities?.source_health.filter(row => row.status === 'HEALTHY').length ?? 0
  const nysSourceCount = procurement?.nysAuthorities?.source_health.length ?? 0
  const changeProcurementSort = (key: ProcurementSortKey) => setProcurementSort(current => current.key === key
    ? { key, direction: current.direction === 'asc' ? 'desc' : 'asc' }
    : { key, direction: key === 'date' || key === 'value' ? 'desc' : 'asc' })
  const changeAccountSort = (key: AccountSortKey) => setAccountSort(current => current.key === key
    ? { key, direction: current.direction === 'asc' ? 'desc' : 'asc' }
    : { key, direction: key === 'address' || key === 'signal' ? 'asc' : 'desc' })
  const procurementIndicator = (key: ProcurementSortKey) => procurementSort.key === key ? (procurementSort.direction === 'asc' ? ' ↑' : ' ↓') : ''
  const accountIndicator = (key: AccountSortKey) => accountSort.key === key ? (accountSort.direction === 'asc' ? ' ↑' : ' ↓') : ''

  return <section className="product-page opportunities-page">
    <div className="product-page-heading">
      <div><span className="page-kicker">New York · procurement + commercial timing</span><h1>Opportunities workspace</h1><p>Review live NYC procurement and statewide public-authority contract reporting alongside TowerSignal account timing. Procurement values are source-reported public observations, not vendor revenue, and records are not attached to cooling-tower accounts without a defensible facility/property link.</p></div>
      <div className="page-actions"><ShareButton label="Share this view" /></div>
    </div>

    {procurementError && <div className="reference-empty-state"><strong>Procurement intelligence is unavailable.</strong><span>{procurementError}</span><span>TowerSignal will not substitute roadmap examples or fixture bids for a failed production source.</span></div>}
    {!procurement && !procurementError && <div className="reference-empty-state"><strong>Loading verified procurement intelligence…</strong><span>City Record, durable Checkbook and NYS public-authority procurement are loaded independently from the account dataset.</span></div>}

    {procurement && <>
      {procurement.sourceErrors.nysAuthorities && <div className="reference-empty-state procurement-source-warning"><strong>NYS authority procurement is unavailable.</strong><span>{procurement.sourceErrors.nysAuthorities}</span><span>Verified NYC City Record and Checkbook intelligence remains available; TowerSignal does not substitute fixture or roadmap data for the failed statewide source.</span></div>}
      {procurement.sourceErrors.openBookWater && <div className="reference-empty-state procurement-source-warning"><strong>Open Book NY water procurement is unavailable.</strong><span>{procurement.sourceErrors.openBookWater}</span></div>}
      {procurement.sourceErrors.nychaWater && <div className="reference-empty-state procurement-source-warning"><strong>NYCHA water procurement is unavailable.</strong><span>{procurement.sourceErrors.nychaWater}</span></div>}
      <div className="reference-metric-grid">
        <article><span className="reference-metric-icon urgent">↗</span><div><small>Open solicitations</small><strong>{number.format(procurement.cityRecord.summary.open_relevant_opportunities)}</strong><span>Relevant City Record notices</span></div></article>
        <article><span className="reference-metric-icon warning">◷</span><div><small>Recent awards</small><strong>{number.format(procurement.cityRecord.summary.recent_relevant_awards)}</strong><span>City Record lookback window</span></div></article>
        <article><span className="reference-metric-icon success">◎</span><div><small>Verified NYC contracts</small><strong>{number.format(procurement.checkbook.summary.relevant_contract_count)}</strong><span>Relevant Checkbook records</span></div></article>
        <article><span className="reference-metric-icon">NY</span><div><small>Open Book water contracts</small><strong>{procurement.openBookWater ? number.format(procurement.openBookWater.summary.relevant_contract_count) : '—'}</strong><span>{procurement.openBookWater ? 'OSC transaction history' : 'Source unavailable'}</span></div></article>
        <article><span className="reference-metric-icon">NYC</span><div><small>NYCHA release lines</small><strong>{procurement.nychaWater ? number.format(procurement.nychaWater.summary.relevant_release_line_count) : '—'}</strong><span>{procurement.nychaWater ? 'Line/release evidence' : 'Source unavailable'}</span></div></article>
        <article><span className="reference-metric-icon">$</span><div><small>Observed public value</small><strong>{currency.format(observedContractValue)}</strong><span>Source-reported values · not revenue</span></div></article>
        <article><span className="reference-metric-icon">?</span><div><small>Unresolved vendors</small><strong>{number.format(unresolved)}</strong><span>Preserved for company resolution</span></div></article>
      </div>

      <div className="roadmap-data-banner">
        <div><span className="roadmap-status">LIVE SOURCE DATA</span><strong>Procurement is loaded as source-observed public evidence, separate from account priority.</strong><p>Open Book NY and NYCHA records expand the water-contract view, but facility, department and NYCHA location text remain contracting context unless another source establishes an exact property relationship.</p></div>
        <div className="roadmap-source-list"><span>City Record · {procurement.cityRecord.source_health.status}</span><span>Checkbook · verified {formatDate(procurement.checkbook.generated_at)}</span><span>NYS authorities · {procurement.nysAuthorities ? `${nysHealthyCount}/${nysSourceCount} healthy` : 'unavailable'}</span><span>Open Book · {procurement.openBookWater ? number.format(procurement.openBookWater.summary.relevant_contract_count) : 'unavailable'}</span><span>NYCHA · {procurement.nychaWater ? number.format(procurement.nychaWater.summary.relevant_release_line_count) : 'unavailable'}</span><span>No inferred property linkage</span></div>
      </div>

      <div className="reference-table-card">
        <div className="reference-table-heading">
          <div><strong>Public procurement intelligence</strong><span>{number.format(sortedProcurement.length)} matching · {number.format(visibleProcurement.length)} shown on this page · {number.format(procurementRows.length)} loaded</span></div>
          <div className="page-actions">
            <input aria-label="Search procurement" value={procurementSearch} onChange={event => setProcurementSearch(event.target.value)} placeholder="Contract, vendor, buyer…" />
            <label>Source <select aria-label="Procurement source" value={sourceFilter} onChange={event => setSourceFilter(event.target.value)}><option value="ALL">All</option><option value="CITY_RECORD">City Record</option><option value="CHECKBOOK">Checkbook NYC</option>{procurement.nysAuthorities && <option value="NYS_AUTHORITIES">NYS authorities</option>}{procurement.openBookWater && <option value="OPENBOOK">Open Book NY</option>}{procurement.nychaWater && <option value="NYCHA">NYCHA</option>}</select></label>
            <label>Service <select aria-label="Procurement service category" value={categoryFilter} onChange={event => setCategoryFilter(event.target.value)}><option value="ALL">All services</option>{categories.map(category => <option key={category} value={category}>{categoryLabel(category)}</option>)}</select></label>
          </div>
        </div>
        <div className="reference-table-scroll"><table className="reference-table procurement-table"><thead><tr>
          <th><button onClick={() => changeProcurementSort('title')}>Procurement{procurementIndicator('title')}</button></th>
          <th><button onClick={() => changeProcurementSort('source')}>Source{procurementIndicator('source')}</button></th>
          <th><button onClick={() => changeProcurementSort('agency')}>Agency / buyer{procurementIndicator('agency')}</button></th>
          <th><button onClick={() => changeProcurementSort('vendor')}>Vendor{procurementIndicator('vendor')}</button></th>
          <th><button onClick={() => changeProcurementSort('service')}>Service{procurementIndicator('service')}</button></th>
          <th><button onClick={() => changeProcurementSort('value')}>Observed value{procurementIndicator('value')}</button></th>
          <th><button onClick={() => changeProcurementSort('date')}>Date{procurementIndicator('date')}</button></th>
          <th><button onClick={() => changeProcurementSort('evidence')}>Evidence{procurementIndicator('evidence')}</button></th>
        </tr></thead><tbody>{visibleProcurement.map(row => <tr key={row.procurement_id}>
          <td><strong>{row.title ?? row.description ?? row.source_record_id}</strong><small>{row.source_contract_id ?? row.notice_id ?? row.source_record_id}</small></td>
          <td><strong>{sourceLabel(row)}</strong><small>{row.status ?? 'source record'}</small></td>
          <td>{row.agency ?? row.buyer_name ?? '—'}</td>
          <td>{row.vendor_raw ? <><strong>{row.vendor_raw}</strong><small>{row.company_match_confidence ?? 'UNRESOLVED'}</small></> : <span className="muted-label">Not yet awarded / not published</span>}</td>
          <td><strong>{categoryLabel(row.service_category)}</strong><small>{row.service_confidence}</small></td>
          <td>{procurementAmount(row) == null ? '—' : currency.format(procurementAmount(row) ?? 0)}<small>{row.observed_value_evidence ?? row.amount_evidence ?? 'No amount published'}</small></td>
          <td>{procurementDate(row) ? formatDate(procurementDate(row) ?? '') : '—'}<small>{row.due_date ? 'due date' : row.start_date ? 'contract start' : row.award_date ? 'award date' : 'source date'}</small></td>
          <td>{row.source_url ? <a className="table-link" href={row.source_url} target="_blank" rel="noreferrer">Open source ↗</a> : '—'}<small>{row.facility_match_confidence ?? row.tower_link_confidence ?? 'UNLINKED'} facility/account</small></td>
        </tr>)}</tbody></table></div>
        <PageControls page={safeProcurementPage} total={sortedProcurement.length} onPage={setProcurementPage} />
      </div>
    </>}

    <div className="reference-table-card">
      <div className="reference-table-heading"><div><strong>Current account timing opportunities</strong><span>{number.format(sortedAccounts.length)} matching accounts · {number.format(visibleAccounts.length)} shown on this page</span></div><div className="page-actions"><input aria-label="Search account opportunities" value={accountSearch} onChange={event => setAccountSearch(event.target.value)} placeholder="Account, borough, signal…" /><select aria-label="Account minimum priority" value={accountMinPriority} onChange={event => setAccountMinPriority(event.target.value)}><option value="ALL">Any priority</option><option value="50">Priority 50+</option><option value="70">Priority 70+</option></select><label><input type="checkbox" checked={accountContactOnly} onChange={event => setAccountContactOnly(event.target.checked)} /> Contact-ready</label></div></div>
      <div className="reference-table-scroll"><table className="reference-table opportunity-table"><thead><tr>
        <th><button onClick={() => changeAccountSort('address')}>Account{accountIndicator('address')}</button></th>
        <th><button onClick={() => changeAccountSort('priority')}>Priority{accountIndicator('priority')}</button></th>
        <th><button onClick={() => changeAccountSort('signal')}>Strongest reason{accountIndicator('signal')}</button></th>
        <th><button onClick={() => changeAccountSort('equipment')}>Equipment{accountIndicator('equipment')}</button></th>
        <th><button onClick={() => changeAccountSort('contact')}>Contact{accountIndicator('contact')}</button></th>
        <th><button onClick={() => changeAccountSort('dob')}>DOB activity{accountIndicator('dob')}</button></th>
        <th><button onClick={() => changeAccountSort('oath')}>OATH{accountIndicator('oath')}</button></th>
        <th><button onClick={() => changeAccountSort('acris')}>Recorded property activity{accountIndicator('acris')}</button></th><th>Action</th>
      </tr></thead><tbody>{visibleAccounts.map(row => {
        const acris = row as SystemSummary & AcrisSummaryFields
        return <tr key={row.system_id} onClick={() => onOpenAccount(row)}>
          <td><strong>{row.address ?? row.system_id}</strong><small>{[row.borough, row.zip].filter(Boolean).join(' · ')} · {row.system_id}</small></td>
          <td><span className={`priority-pill ${row.priority_score >= 70 ? 'priority-pill-high' : 'priority-pill-medium'}`}>{row.priority_score}</span></td>
          <td><strong>{signalLabel(row.primary_signal)}</strong><small>{row.evidence_confidence}</small></td>
          <td>{row.active_equipment}<small>active</small></td>
          <td>{(row.hpd_contact_count ?? 0) > 0 ? <span className="ready-label">Contact-ready</span> : <span className="muted-label">No HPD contact</span>}</td>
          <td>{row.dob_recent_activity_count ?? 0}<small>{row.latest_dob_activity_date ? `latest ${formatDate(row.latest_dob_activity_date)}` : 'no recent activity'}</small></td>
          <td>{row.oath_case_count ?? 0}<small>{(row.oath_case_count ?? 0) > 0 ? 'exact case match' : 'none matched'}</small></td>
          <td>{acris.acris_recent_document_count ?? 0}<small>recent exact-BBL docs</small></td>
          <td><button className="table-link" onClick={event => { event.stopPropagation(); onOpenAccount(row) }}>Open profile →</button></td>
        </tr>
      })}</tbody></table></div>
      <PageControls page={safeAccountPage} total={sortedAccounts.length} onPage={setAccountPage} />
    </div>

    <div className="source-health-footnote">Priority remains WHY NOW for cooling-tower accounts. Procurement classifications and observed contract values are separate source-backed commercial evidence and do not change Priority Score 1.0.</div>
  </section>
}
